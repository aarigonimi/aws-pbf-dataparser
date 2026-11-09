from __future__ import annotations

import json
import logging
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config import JobConfig
from src.errors import JobCancelled, OutputConflictError
from src.parquet_writer import SCHEMA_VERSION, Artifact, ParquetSink, write_summary_json
from src.s3_utils import S3Client

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "1.0.0"


class CancelToken:
    """Cooperative cancellation flag driven by SIGTERM/SIGINT handlers."""

    def __init__(self) -> None:
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self, signum: int | None = None, frame: Any = None) -> None:
        self._cancelled = True

    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise JobCancelled("Job cancellation requested (SIGTERM/SIGINT).")


@dataclass
class PipelineResult:
    status: str
    region: str
    ymd: str
    run_id: str
    record_counts: dict[str, int] = field(default_factory=dict)
    files: list[dict[str, Any]] = field(default_factory=list)
    total_records: int = 0
    total_output_bytes: int = 0
    input_bytes: int = 0
    manifest_key: str = ""
    skipped: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "region": self.region,
            "ymd": self.ymd,
            "run_id": self.run_id,
            "record_counts": self.record_counts,
            "files": self.files,
            "total_records": self.total_records,
            "total_output_bytes": self.total_output_bytes,
            "input_bytes": self.input_bytes,
            "manifest_key": self.manifest_key,
            "skipped": self.skipped,
        }


Processor = Callable[..., dict[str, int]]
REPLACE_RECOVERY_COMMAND = (
    'REGION_NAME="$REGION_NAME" YMD="$YMD" OVERWRITE=replace ./scripts/submit_job.sh'
)


def _default_processor() -> Processor:
    from src.osm_parser import process_pbf

    return process_pbf


def _final_key(config: JobConfig, relative_key: str) -> str:
    return f"{config.output_prefix}/{relative_key.strip('/')}"


def _claim_partition(config: JobConfig, s3: Any, lock_key: str, payload: bytes) -> bool:
    """Atomically claim exclusive publication rights for one partition.

    The claim is an S3 conditional write (``If-None-Match: *``) so exactly one
    of several concurrently starting jobs can acquire it, even when the jobs
    run in different queues or were submitted through different tools. In
    ``OVERWRITE=replace`` mode a leftover claim from a terminated run is
    removed first because ``replace`` explicitly authorises recovery.
    """

    if config.overwrite == "replace":
        s3.delete_keys(config.output_bucket, [lock_key])
    return s3.put(config.output_bucket, lock_key, payload, if_none_match=True)


def _check_existing_outputs(
    config: JobConfig,
    s3: Any,
    manifest_key: str,
    ignore_keys: frozenset[str] = frozenset(),
) -> bool:
    """Return True when the job should be skipped.

    ``ignore_keys`` excludes the caller's own partition claim when the check
    is re-run after the claim is acquired.
    """

    existing_manifest = s3.exists(config.output_bucket, manifest_key)
    if config.overwrite == "skip":
        if existing_manifest:
            return True
        stale = _partition_data_keys(s3, config, ignore_keys)
        if stale:
            raise OutputConflictError(
                "Found output files without a completion manifest under "
                f"s3://{config.output_bucket}/{config.curated_prefix}/. "
                "The previous run did not finish. After reviewing the output, "
                f"run this recovery command: {REPLACE_RECOVERY_COMMAND}"
            )
        return False

    if config.overwrite == "error":
        if existing_manifest:
            raise OutputConflictError(
                f"Output manifest already exists at s3://{config.output_bucket}/"
                f"{manifest_key}. Set OVERWRITE=skip or OVERWRITE=replace."
            )
        existing = _partition_data_keys(s3, config, ignore_keys)
        if existing:
            raise OutputConflictError(
                f"Output already exists under s3://{config.output_bucket}/"
                f"{config.curated_prefix}/. Set OVERWRITE=skip or run the recovery "
                f"command: {REPLACE_RECOVERY_COMMAND}"
            )
    return False


def _partition_data_keys(s3: Any, config: JobConfig, ignore_keys: frozenset[str]) -> list[str]:
    return [
        key
        for key in s3.list_keys(config.output_bucket, config.curated_prefix + "/")
        if key not in ignore_keys
    ]


def run_pipeline(
    config: JobConfig,
    s3: Any | None = None,
    processor: Processor | None = None,
    cancel_token: CancelToken | None = None,
) -> PipelineResult:
    """Execute one PBF -> Parquet run and publish it to S3.

    Publication is serialised per output partition with a conditional-write
    claim object, so concurrent runs of the same ``region``/``ymd`` fail fast
    with an :class:`OutputConflictError` instead of interleaving their
    copies. The claim is released when the run finishes, and stale objects
    are removed before new data is published so a failed run never leaves a
    manifest alongside missing files.
    """

    client = s3 or S3Client(
        region=config.aws_region,
        max_attempts=config.s3_max_attempts,
        connect_timeout=config.s3_connect_timeout,
        read_timeout=config.s3_read_timeout,
    )
    process = processor or _default_processor()
    token = cancel_token or CancelToken()

    manifest_key = _final_key(config, config.manifest_relative_key)
    lock_key = _final_key(config, config.lock_relative_key)
    claim_keys = frozenset({lock_key})
    started_at = datetime.now(UTC)
    run_started = time.monotonic()

    if _check_existing_outputs(config, client, manifest_key, ignore_keys=claim_keys):
        logger.info(
            "Skipping run: completed output already exists at s3://%s/%s",
            config.output_bucket,
            manifest_key,
        )
        return PipelineResult(
            status="skipped",
            region=config.region_name,
            ymd=config.ymd,
            run_id=config.run_id,
            manifest_key=manifest_key,
            skipped=True,
        )

    local_work_dir = config.local_work_dir
    owns_work_dir = local_work_dir is None
    if owns_work_dir:
        work_dir = Path(tempfile.mkdtemp(prefix="osm-pbf-"))
    else:
        assert local_work_dir is not None
        work_dir = Path(local_work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

    input_path = work_dir / "input.osm.pbf"
    local_curated = work_dir / "curated"
    manifest_path = work_dir / "_manifest.json"

    staging_uploaded: list[str] = []
    published_keys: list[str] = []
    sinks: dict[str, ParquetSink] = {}
    lock_held = False

    try:
        claim_payload = json.dumps(
            {
                "run_id": config.run_id,
                "region": config.region_name,
                "ymd": config.ymd,
                "acquired_at": started_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")
        if not _claim_partition(config, client, lock_key, claim_payload):
            raise OutputConflictError(
                "Another run is already publishing this partition (claim at "
                f"s3://{config.output_bucket}/{lock_key}). Wait for it to finish, or, "
                "after confirming no run is active (a previous attempt was terminated "
                f"before cleanup), recover with: {REPLACE_RECOVERY_COMMAND}"
            )
        lock_held = True

        # Re-check under the claim: a run may have published between the
        # first check and claim acquisition.
        if _check_existing_outputs(config, client, manifest_key, ignore_keys=claim_keys):
            logger.info(
                "Skipping run: completed output appeared at s3://%s/%s while "
                "acquiring the partition claim.",
                config.output_bucket,
                manifest_key,
            )
            return PipelineResult(
                status="skipped",
                region=config.region_name,
                ymd=config.ymd,
                run_id=config.run_id,
                manifest_key=manifest_key,
                skipped=True,
            )

        input_bytes = int(client.head(config.raw_bucket, config.raw_partition_key)["bytes"])
        download_started = time.monotonic()
        client.download(config.raw_bucket, config.raw_partition_key, input_path)
        download_seconds = time.monotonic() - download_started
        input_bytes = input_path.stat().st_size
        logger.info(
            "Downloaded s3://%s/%s (%d bytes) in %.2fs",
            config.raw_bucket,
            config.raw_partition_key,
            input_bytes,
            download_seconds,
        )

        uploaded_artifacts: dict[Path, str] = {}

        def upload_closed_artifact(artifact: Artifact) -> None:
            relative_path = artifact.path.relative_to(local_curated)
            relative_key = relative_path.as_posix()
            staging_key = config.staging_key(relative_key)
            client.upload(artifact.path, config.output_bucket, staging_key)
            staging_uploaded.append(staging_key)
            uploaded_artifacts[artifact.path] = staging_key
            artifact.path.unlink()

        for entity in config.entity_types:
            sinks[entity] = ParquetSink(
                local_curated / f"entity={entity}",
                compression=config.compression,
                max_records_per_file=config.max_records_per_file,
                row_group_size=config.row_group_size,
                on_file_closed=upload_closed_artifact,
            )

        parse_started = time.monotonic()
        try:
            processor_counts = process(
                input_path,
                sinks=sinks,
                entity_types=config.entity_types,
                include_way_geometry=config.include_way_geometry,
                cancel_token=token,
                index_dir=work_dir / ".osmium-index",
            )
        finally:
            for sink in sinks.values():
                sink.close()
        parse_seconds = time.monotonic() - parse_started
        token.raise_if_cancelled()

        files: list[dict[str, Any]] = []
        record_counts: dict[str, int] = {}
        for entity, sink in sinks.items():
            record_counts[entity] = sink.total_records
            for artifact in sink.artifacts():
                relative_key = f"{config.entity_relative_prefix(entity)}/{artifact.path.name}"
                files.append(
                    {
                        "entity": entity,
                        "relative_key": relative_key,
                        "local_path": str(artifact.path),
                        "bytes": artifact.bytes,
                        "records": artifact.records,
                    }
                )

        total_records = sum(record_counts.values())
        total_output_bytes = sum(item["bytes"] for item in files)

        finished_at = datetime.now(UTC)
        manifest = {
            "status": "success" if total_records > 0 else "empty",
            "schema_version": SCHEMA_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "image_digest": config.image_digest,
            "git_sha": config.git_sha,
            "region": config.region_name,
            "ymd": config.ymd,
            "run_id": config.run_id,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round(time.monotonic() - run_started, 3),
            "source": {
                "bucket": config.raw_bucket,
                "key": config.raw_partition_key,
                "bytes": input_bytes,
            },
            "output": {
                "bucket": config.output_bucket,
                "prefix": config.curated_prefix,
                "compression": config.compression,
                "overwrite": config.overwrite,
                "include_way_geometry": config.include_way_geometry,
                "entity_types": list(config.entity_types),
            },
            "record_counts": record_counts,
            "total_records": total_records,
            "total_output_bytes": total_output_bytes,
            "files": [
                {
                    "entity": item["entity"],
                    "key": _final_key(config, item["relative_key"]),
                    "bytes": item["bytes"],
                    "records": item["records"],
                }
                for item in files
            ],
            "processor_counts": processor_counts,
            "timings": {
                "download_seconds": round(download_seconds, 3),
                "parse_seconds": round(parse_seconds, 3),
            },
        }
        write_summary_json(manifest_path, manifest)

        manifest_staging_key = config.staging_key(config.manifest_relative_key)
        client.upload(manifest_path, config.output_bucket, manifest_staging_key)
        staging_uploaded.append(manifest_staging_key)

        final_data_keys = {_final_key(config, item["relative_key"]) for item in files}
        preexisting_final_keys: set[str] = set()
        stale_keys: list[str] = []
        if config.overwrite == "replace":
            preexisting_final_keys = set(
                client.list_keys(config.output_bucket, config.curated_prefix + "/")
            )
            stale_keys = [
                key
                for key in preexisting_final_keys
                if key not in final_data_keys and key not in {manifest_key, lock_key}
            ]
            if manifest_key in preexisting_final_keys:
                client.delete_keys(config.output_bucket, [manifest_key])
                if client.exists(config.output_bucket, manifest_key):
                    raise RuntimeError(
                        "Could not remove the previous completion manifest; "
                        "refusing to replace data while it remains visible."
                    )

        # Remove stale objects before publishing new data so a failed
        # publication never leaves a valid manifest referencing missing
        # files: a crash at any point leaves the partition without a
        # manifest, which readers gate on.
        if stale_keys:
            client.delete_keys(config.output_bucket, stale_keys)
            logger.info("Removed %d stale output objects.", len(stale_keys))

        try:
            for item in files:
                final_key = _final_key(config, item["relative_key"])
                if final_key not in preexisting_final_keys:
                    published_keys.append(final_key)
                client.copy(
                    config.output_bucket,
                    uploaded_artifacts[Path(item["local_path"])],
                    final_key,
                )
            if manifest_key not in preexisting_final_keys:
                published_keys.append(manifest_key)
            client.copy(
                config.output_bucket,
                manifest_staging_key,
                manifest_key,
            )
        except Exception:
            logger.error("Publish failed; rolling back %d copied objects.", len(published_keys))
            rollback_keys = [key for key in published_keys if key not in preexisting_final_keys]
            client.delete_keys(config.output_bucket, rollback_keys)
            raise

        for item in files:
            Path(item["local_path"]).unlink(missing_ok=True)

        total_seconds = time.monotonic() - run_started
        logger.info(
            "Run complete: status=%s records=%s files=%d output_bytes=%d "
            "input_bytes=%d duration=%.2fs manifest=s3://%s/%s",
            manifest["status"],
            record_counts,
            len(files),
            total_output_bytes,
            input_bytes,
            total_seconds,
            config.output_bucket,
            manifest_key,
        )

        return PipelineResult(
            status=manifest["status"],
            region=config.region_name,
            ymd=config.ymd,
            run_id=config.run_id,
            record_counts=record_counts,
            files=files,
            total_records=total_records,
            total_output_bytes=total_output_bytes,
            input_bytes=input_bytes,
            manifest_key=manifest_key,
        )
    finally:
        client.delete_keys(config.output_bucket, staging_uploaded)
        if lock_held:
            client.delete_keys(config.output_bucket, [lock_key])
        if owns_work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
