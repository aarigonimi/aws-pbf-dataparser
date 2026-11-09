import json
from pathlib import Path
from typing import Any

import pytest

from src.config import JobConfig
from src.errors import JobCancelled, OutputConflictError
from src.pipeline import CancelToken, run_pipeline
from src.transformations import (
    build_node_record,
    build_relation_record,
    build_way_record,
)

INPUT_KEY = "region=monaco/ymd=20261108/monaco-20261108.osm.pbf"


class FakeS3:
    def __init__(
        self,
        objects=None,
        copy_fail_key: str | None = None,
        delete_fail_keys: set[str] | None = None,
    ):
        self.objects = dict(objects or {})
        self.copy_fail_key = copy_fail_key
        self.delete_fail_keys = delete_fail_keys or set()
        self.deleted: list[str] = []
        self.events: list[dict[str, Any]] = []
        self.upload_events: list[tuple[str, bool]] = []

    def _manifest_present(self):
        return any(
            "/_staging/" not in key and "/ymd=" in key and key.endswith("/_manifest.json")
            for key in self.objects
        )

    def head(self, bucket, key):
        return {"bytes": len(self.objects[key]), "etag": ""}

    def download(self, bucket, key, destination):
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.objects[key])
        return target

    def exists(self, bucket, key):
        return key in self.objects

    def list_keys(self, bucket, prefix):
        return sorted(key for key in self.objects if key.startswith(prefix))

    def upload(self, local_path, bucket, key):
        self.upload_events.append((key, Path(local_path).exists()))
        self.objects[key] = Path(local_path).read_bytes()

    def copy(self, bucket, source_key, destination_key):
        self.events.append(
            {
                "action": "copy",
                "key": destination_key,
                "manifest_present": self._manifest_present(),
            }
        )
        if self.copy_fail_key == destination_key:
            raise RuntimeError("simulated copy failure")
        self.objects[destination_key] = self.objects[source_key]

    def delete_keys(self, bucket, keys):
        self.events.append(
            {
                "action": "delete",
                "keys": list(keys),
                "manifest_present": self._manifest_present(),
            }
        )
        for key in keys:
            if key in self.delete_fail_keys:
                continue
            self.objects.pop(key, None)
            self.deleted.append(key)


def _config(tmp_path: Path, **overrides) -> JobConfig:
    env = {
        "RAW_BUCKET": "raw",
        "OUTPUT_BUCKET": "curated",
        "REGION_NAME": "monaco",
        "YMD": "20261108",
        "RUN_ID": "run-1",
        "LOCAL_WORK_DIR": str(tmp_path / "work"),
    }
    env.update(overrides)
    return JobConfig.from_env(env)


def _record(entity: str, index: int) -> dict:
    if entity == "nodes":
        return build_node_record(index, 43.73, 7.41, {"name": "n"})
    if entity == "ways":
        return build_way_record(index, {"highway": "residential"}, [1, 2])
    return build_relation_record(index, {"type": "route"}, [("node", 1, "stop")])


def _processor(records_per_entity: int = 1, cancel: bool = False):
    def process(input_path, sinks, entity_types, **kwargs):
        if cancel:
            raise JobCancelled("cancelled in test")
        for entity in entity_types:
            for index in range(records_per_entity):
                sinks[entity].add(_record(entity, index))
        return {entity: sinks[entity].total_records for entity in entity_types}

    return process


def test_cancel_token_raises_after_cancel():
    token = CancelToken()

    assert token.cancelled is False
    token.cancel()
    assert token.cancelled is True
    with pytest.raises(JobCancelled):
        token.raise_if_cancelled()


def test_successful_run_publishes_data_and_manifest_last(tmp_path: Path):
    fake = FakeS3({INPUT_KEY: b"pbf-bytes"})
    config = _config(tmp_path)

    result = run_pipeline(config, s3=fake, processor=_processor())

    assert result.status == "success"
    assert result.skipped is False
    assert result.record_counts == {"nodes": 1, "ways": 1, "relations": 1}
    assert result.total_records == 3
    assert result.manifest_key in fake.objects
    manifest = json.loads(fake.objects[result.manifest_key])
    assert manifest["image_digest"] is None
    assert manifest["git_sha"] is None
    assert result.manifest_key == ("curated/region=monaco/ymd=20261108/_manifest.json")
    assert "curated/region=monaco/ymd=20261108/entity=nodes/part-00000.parquet" in fake.objects
    assert not any(key.startswith("curated/_staging/") for key in fake.objects)
    data_uploads = [key for key, _ in fake.upload_events if key.endswith(".parquet")]
    assert len(data_uploads) == 3
    assert all(local_exists for key, local_exists in fake.upload_events if key.endswith(".parquet"))
    assert not list((Path(config.local_work_dir) / "curated").rglob("*.parquet"))


def test_empty_input_publishes_empty_manifest(tmp_path: Path):
    fake = FakeS3({INPUT_KEY: b"pbf-bytes"})
    config = _config(tmp_path)

    result = run_pipeline(config, s3=fake, processor=_processor(records_per_entity=0))

    assert result.status == "empty"
    assert result.files == []
    assert result.total_records == 0
    assert result.manifest_key in fake.objects


def test_existing_manifest_is_a_conflict_in_error_mode(tmp_path: Path):
    config = _config(tmp_path)
    manifest_key = f"{config.output_prefix}/{config.manifest_relative_key}"
    fake = FakeS3({INPUT_KEY: b"pbf-bytes", manifest_key: b"{}"})

    with pytest.raises(OutputConflictError):
        run_pipeline(config, s3=fake, processor=_processor())


def test_stray_output_without_manifest_is_a_conflict(tmp_path: Path):
    config = _config(tmp_path)
    stale_key = "curated/region=monaco/ymd=20261108/entity=nodes/part-00000.parquet"
    fake = FakeS3({INPUT_KEY: b"pbf-bytes", stale_key: b"stale"})

    with pytest.raises(OutputConflictError):
        run_pipeline(config, s3=fake, processor=_processor())


def test_skip_mode_returns_skipped_without_processing(tmp_path: Path):
    config = _config(tmp_path, OVERWRITE="skip")
    manifest_key = f"{config.output_prefix}/{config.manifest_relative_key}"
    fake = FakeS3({INPUT_KEY: b"pbf-bytes", manifest_key: b"{}"})

    def should_not_run(*args, **kwargs):
        raise AssertionError("processor must not run when output is skipped")

    result = run_pipeline(config, s3=fake, processor=should_not_run)

    assert result.status == "skipped"
    assert result.skipped is True
    assert result.total_records == 0


def test_skip_mode_rejects_stray_output(tmp_path: Path):
    config = _config(tmp_path, OVERWRITE="skip")
    stale_key = "curated/region=monaco/ymd=20261108/entity=nodes/part-00000.parquet"
    fake = FakeS3({INPUT_KEY: b"pbf-bytes", stale_key: b"stale"})

    with pytest.raises(OutputConflictError) as raised:
        run_pipeline(config, s3=fake, processor=_processor())

    assert (
        'REGION_NAME="$REGION_NAME" YMD="$YMD" OVERWRITE=replace ' "./scripts/submit_job.sh"
    ) in str(raised.value)


def test_replace_mode_removes_stale_objects(tmp_path: Path):
    config = _config(tmp_path, OVERWRITE="replace")
    manifest_key = f"{config.output_prefix}/{config.manifest_relative_key}"
    stale_key = "curated/region=monaco/ymd=20261108/entity=nodes/part-99999.parquet"
    fake = FakeS3({INPUT_KEY: b"pbf-bytes", manifest_key: b"{}", stale_key: b"old"})

    result = run_pipeline(config, s3=fake, processor=_processor())

    assert result.status == "success"
    assert stale_key not in fake.objects
    assert result.manifest_key in fake.objects
    stale_delete = next(
        event for event in fake.events if event["action"] == "delete" and stale_key in event["keys"]
    )
    assert stale_delete["manifest_present"] is True


def test_replace_removes_old_manifest_before_copying_data(tmp_path: Path):
    config = _config(tmp_path, OVERWRITE="replace")
    manifest_key = f"{config.output_prefix}/{config.manifest_relative_key}"
    fake = FakeS3({INPUT_KEY: b"pbf-bytes", manifest_key: b"old-manifest"})

    run_pipeline(config, s3=fake, processor=_processor())

    manifest_delete = next(
        index
        for index, event in enumerate(fake.events)
        if event["action"] == "delete" and manifest_key in event["keys"]
    )
    first_final_copy = next(
        index
        for index, event in enumerate(fake.events)
        if event["action"] == "copy" and event["key"].startswith(config.curated_prefix)
    )
    assert manifest_delete < first_final_copy
    assert fake.events[first_final_copy]["manifest_present"] is False


def test_replace_failure_mid_copy_leaves_no_manifest(tmp_path: Path):
    config = _config(tmp_path, OVERWRITE="replace")
    manifest_key = f"{config.output_prefix}/{config.manifest_relative_key}"
    failing_key = (
        f"{config.output_prefix}/{config.entity_relative_prefix('ways')}/part-00000.parquet"
    )
    fake = FakeS3(
        {INPUT_KEY: b"pbf-bytes", manifest_key: b"old-manifest"},
        copy_fail_key=failing_key,
    )

    with pytest.raises(RuntimeError, match="simulated copy failure"):
        run_pipeline(config, s3=fake, processor=_processor())

    assert manifest_key not in fake.objects


def test_replace_rollback_does_not_delete_preexisting_data_keys(tmp_path: Path):
    config = _config(tmp_path, OVERWRITE="replace")
    manifest_key = f"{config.output_prefix}/{config.manifest_relative_key}"
    node_key = f"{config.output_prefix}/{config.entity_relative_prefix('nodes')}/part-00000.parquet"
    way_key = f"{config.output_prefix}/{config.entity_relative_prefix('ways')}/part-00000.parquet"
    fake = FakeS3(
        {
            INPUT_KEY: b"pbf-bytes",
            manifest_key: b"old-manifest",
            node_key: b"old-node",
            way_key: b"old-way",
        },
        copy_fail_key=way_key,
    )

    with pytest.raises(RuntimeError, match="simulated copy failure"):
        run_pipeline(config, s3=fake, processor=_processor())

    assert node_key in fake.objects
    assert fake.objects[node_key] != b"old-node"
    assert fake.objects[way_key] == b"old-way"
    assert node_key not in fake.deleted
    assert way_key not in fake.deleted
    assert manifest_key not in fake.objects


def test_replace_stops_if_old_manifest_cannot_be_removed(tmp_path: Path):
    config = _config(tmp_path, OVERWRITE="replace")
    manifest_key = f"{config.output_prefix}/{config.manifest_relative_key}"
    fake = FakeS3(
        {INPUT_KEY: b"pbf-bytes", manifest_key: b"old-manifest"},
        delete_fail_keys={manifest_key},
    )

    with pytest.raises(RuntimeError, match="refusing to replace data"):
        run_pipeline(config, s3=fake, processor=_processor())

    assert manifest_key in fake.objects
    assert not any(
        event["action"] == "copy" and event["key"].startswith(config.curated_prefix)
        for event in fake.events
    )


def test_publish_failure_rolls_back_new_objects(tmp_path: Path):
    config = _config(tmp_path)
    manifest_key = f"{config.output_prefix}/{config.manifest_relative_key}"
    fake = FakeS3({INPUT_KEY: b"pbf-bytes"}, copy_fail_key=manifest_key)

    with pytest.raises(RuntimeError):
        run_pipeline(config, s3=fake, processor=_processor())

    assert manifest_key not in fake.objects
    assert not any(
        key.startswith("curated/region=monaco/ymd=20261108/entity=") for key in fake.objects
    )
    assert not any(key.startswith("curated/_staging/") for key in fake.objects)


def test_cancellation_propagates_and_leaves_no_output(tmp_path: Path):
    config = _config(tmp_path)
    fake = FakeS3({INPUT_KEY: b"pbf-bytes"})

    with pytest.raises(JobCancelled):
        run_pipeline(config, s3=fake, processor=_processor(cancel=True))

    assert not any(key.startswith("curated/") for key in fake.objects)
