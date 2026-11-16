from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from urllib.parse import unquote_plus

from src.errors import ConfigError

VALID_COMPRESSIONS: Final = frozenset({"snappy", "gzip", "brotli", "lz4", "zstd", "none"})
VALID_OVERWRITE: Final = frozenset({"error", "skip", "replace"})
VALID_MODES: Final = frozenset({"all", "nodes", "ways", "relations"})
VALID_LOG_LEVELS: Final = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
_ALLOWED_PATH_TOKEN: Final = re.compile(r"^[A-Za-z0-9._-]+$")
_YMD_PATTERN: Final = re.compile(r"^\d{8}$")
_RAW_KEY_PATTERN: Final = re.compile(
    r"^region=(?P<region>[A-Za-z0-9._-]+)/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/"
    r"(?P<filename>[A-Za-z0-9._-]+\.osm\.pbf)$"
)


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"Environment variable {name} is required.")
    return value


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}.") from exc
    if value < 1:
        raise ConfigError(f"{name} must be >= 1, got {value}.")
    return value


def _positive_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}.") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be > 0, got {value}.")
    return value


def _choice(env: Mapping[str, str], name: str, default: str, allowed: frozenset[str]) -> str:
    value = env.get(name, default).strip().lower()
    if value not in allowed:
        raise ConfigError(f"{name} must be one of {sorted(allowed)}, got {value!r}.")
    return value


def _path_token(env: Mapping[str, str], name: str, default: str) -> str:
    value = env.get(name, default).strip().strip("/")
    if not value or not _ALLOWED_PATH_TOKEN.match(value):
        raise ConfigError(
            f"{name} must contain only letters, digits, dot, underscore or dash, got {value!r}."
        )
    return value


def _s3_prefix(env: Mapping[str, str], name: str, default: str) -> str:
    value = (env.get(name, "").strip().strip("/")).strip()
    value = value or default
    for segment in value.split("/"):
        if not _ALLOWED_PATH_TOKEN.match(segment) or segment in {".", ".."}:
            raise ConfigError(
                f"{name} must be a relative S3 prefix containing only letters, "
                f"digits, dot, underscore, dash and single slashes, got {value!r}."
            )
    return value


def _validate_ymd(value: str) -> str:
    ymd = value.strip()
    if not _YMD_PATTERN.match(ymd):
        raise ConfigError(f"YMD must be formatted YYYYMMDD, got {ymd!r}.")
    try:
        datetime.strptime(ymd, "%Y%m%d")
    except ValueError as exc:
        raise ConfigError(f"YMD is not a valid calendar date, got {ymd!r}.") from exc
    return ymd


def _default_run_id(env: Mapping[str, str]) -> str:
    """Derive a safe default run id from the AWS Batch job context when present.

    Including the attempt number keeps staging keys unique across Batch
    retries of the same job id.
    """

    job_id = env.get("AWS_BATCH_JOB_ID", "").strip()
    attempt = env.get("AWS_BATCH_JOB_ATTEMPT", "").strip()
    if not job_id:
        return "local-run"
    candidate = f"{job_id}-attempt-{attempt}" if attempt else job_id
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "-", candidate)
    return sanitized or "local-run"


def parse_raw_key(raw_key: str) -> tuple[str, str, str]:
    """Validate a raw S3 key in the ``region=<name>/yyyy/mm/dd`` layout.

    Returns ``(region_name, ymd, file_name)``. Every raw key must carry both a
    region and a partition date, because triggered jobs receive nothing else;
    missing or malformed keys raise :class:`ConfigError` instead of falling
    back to unrelated defaults.
    """

    key = raw_key.strip().strip("/")
    match = _RAW_KEY_PATTERN.match(key)
    if match is None:
        raise ConfigError(
            "RAW_KEY must follow region=<name>/yyyy/mm/dd/<file>.osm.pbf so the "
            f"region and partition date can be derived; got {raw_key!r}."
        )
    ymd = f"{match.group('year')}{match.group('month')}{match.group('day')}"
    return match.group("region"), _validate_ymd(ymd), match.group("filename")


def env_for_raw_key(raw_key: str, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build a job environment from an EventBridge S3 object key.

    S3 event keys arrive URL-encoded, so the key is decoded first. The region
    and partition date are parsed from the ``region=<name>/yyyy/mm/dd`` layout
    and merged into a copy of ``base_env`` (the process environment when
    omitted), so the event key overrides generic defaults without mutating
    process-global configuration.
    """

    env = dict(os.environ if base_env is None else base_env)
    key = unquote_plus(raw_key.strip())
    region_name, ymd, _file_name = parse_raw_key(key)
    env["RAW_KEY"] = key
    env["REGION_NAME"] = region_name
    env["YMD"] = ymd
    return env


@dataclass(frozen=True)
class JobConfig:
    """Immutable, validated runtime configuration for one Batch job."""

    raw_bucket: str
    raw_key: str
    output_bucket: str
    output_prefix: str
    region_name: str
    run_id: str
    image_digest: str | None
    git_sha: str | None
    aws_region: str
    ymd: str
    mode: str = "all"
    compression: str = "snappy"
    overwrite: str = "error"
    include_way_geometry: bool = True
    max_records_per_file: int = 250_000
    row_group_size: int = 100_000
    log_level: str = "INFO"
    local_work_dir: str | None = None
    s3_max_attempts: int = 5
    s3_connect_timeout: float = 10.0
    s3_read_timeout: float = 300.0

    @property
    def entity_types(self) -> tuple[str, ...]:
        if self.mode == "all":
            return ("nodes", "ways", "relations")
        return (self.mode,)

    @property
    def raw_partition_key(self) -> str:
        return self.raw_key.strip("/")

    @property
    def date_path(self) -> str:
        """Partition directory for the run date: ``yyyy/mm/dd`` (zero-padded)."""

        return f"{self.ymd[0:4]}/{self.ymd[4:6]}/{self.ymd[6:8]}"

    @property
    def curated_prefix(self) -> str:
        return f"{self.output_prefix}/region={self.region_name}/{self.date_path}"

    @property
    def manifest_relative_key(self) -> str:
        return f"region={self.region_name}/{self.date_path}/_manifest.json"

    @property
    def lock_relative_key(self) -> str:
        return f"region={self.region_name}/{self.date_path}/_lock.json"

    def entity_relative_prefix(self, entity_name: str) -> str:
        return f"region={self.region_name}/{self.date_path}/entity={entity_name}"

    def output_key(self, entity_name: str, file_name: str) -> str:
        return f"{self.entity_relative_prefix(entity_name)}/{file_name}"

    def staging_prefix(self) -> str:
        return f"{self.output_prefix}/_staging/run_id={self.run_id}"

    def staging_key(self, relative_key: str) -> str:
        return f"{self.staging_prefix()}/{relative_key.strip('/')}"

    def curated_uri(self, entity_name: str, file_name: str = "part-00000.parquet") -> str:
        return f"s3://{self.output_bucket}/{self.output_key(entity_name, file_name)}"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> JobConfig:
        source: Mapping[str, str] = env if env is not None else os.environ

        raw_bucket = _required(source, "RAW_BUCKET")
        output_bucket = _required(source, "OUTPUT_BUCKET")
        raw_key = source.get("RAW_KEY", "").strip().strip("/")

        key_region: str | None = None
        key_ymd: str | None = None
        if raw_key:
            key_region, key_ymd, _file_name = parse_raw_key(raw_key)

        explicit_region = ""
        region_env_name = "REGION_NAME"
        for region_env_name in ("REGION_NAME", "REGION"):
            explicit_region = source.get(region_env_name, "").strip()
            if explicit_region:
                break
        if explicit_region:
            region_name = _path_token(source, region_env_name, explicit_region)
        elif key_region is not None:
            region_name = key_region
        else:
            raise ConfigError(
                "REGION_NAME is required when RAW_KEY does not carry a region=<name> segment."
            )

        run_id = _path_token(source, "RUN_ID", _default_run_id(source))
        image_digest = source.get("JOB_IMAGE_DIGEST", "").strip() or None
        if image_digest == "unset":
            image_digest = None
        git_sha = source.get("GIT_SHA", "").strip() or None
        aws_region = source.get("AWS_REGION", "us-east-1").strip() or "us-east-1"
        output_prefix = _s3_prefix(source, "OUTPUT_PREFIX", "curated")

        explicit_ymd = (source.get("YMD") or source.get("RAW_YMD") or "").strip()
        if explicit_ymd:
            ymd = _validate_ymd(explicit_ymd)
        elif key_ymd is not None:
            ymd = key_ymd
        else:
            raise ConfigError(
                "YMD is required when RAW_KEY does not carry a yyyy/mm/dd partition path."
            )
        if not raw_key:
            raw_key = (
                f"region={region_name}/{ymd[0:4]}/{ymd[4:6]}/{ymd[6:8]}/{region_name}-{ymd}.osm.pbf"
            )

        compression = _choice(source, "PARQUET_COMPRESSION", "snappy", VALID_COMPRESSIONS)
        overwrite = _choice(source, "OVERWRITE", "error", VALID_OVERWRITE)
        mode = _choice(source, "MODE", "all", VALID_MODES)
        log_level = source.get("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in VALID_LOG_LEVELS:
            raise ConfigError(
                f"LOG_LEVEL must be one of {sorted(VALID_LOG_LEVELS)}, got {log_level!r}."
            )

        return cls(
            raw_bucket=raw_bucket,
            raw_key=raw_key,
            output_bucket=output_bucket,
            output_prefix=output_prefix,
            region_name=region_name,
            run_id=run_id,
            image_digest=image_digest,
            git_sha=git_sha,
            aws_region=aws_region,
            ymd=ymd,
            mode=mode,
            compression=compression,
            overwrite=overwrite,
            include_way_geometry=_bool(source, "INCLUDE_WAY_GEOMETRY", True),
            max_records_per_file=_positive_int(source, "MAX_RECORDS_PER_FILE", 250_000),
            row_group_size=_positive_int(source, "ROW_GROUP_SIZE", 100_000),
            log_level=log_level,
            local_work_dir=(source.get("LOCAL_WORK_DIR") or None),
            s3_max_attempts=_positive_int(source, "S3_MAX_ATTEMPTS", 5),
            s3_connect_timeout=_positive_float(source, "S3_CONNECT_TIMEOUT", 10.0),
            s3_read_timeout=_positive_float(source, "S3_READ_TIMEOUT", 300.0),
        )
