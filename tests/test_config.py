import pytest

from src.config import JobConfig, env_for_raw_key
from src.errors import ConfigError


def _env(**overrides):
    base = {
        "RAW_BUCKET": "raw-bucket",
        "OUTPUT_BUCKET": "curated-bucket",
        "REGION_NAME": "monaco",
        "YMD": "20261108",
    }
    base.update(overrides)
    return base


def test_raw_partition_key_uses_region_and_date_path():
    config = JobConfig.from_env(_env())

    assert config.raw_partition_key == "region=monaco/2026/11/08/monaco-20261108.osm.pbf"
    assert config.image_digest is None
    assert config.git_sha is None


def test_image_provenance_environment_is_optional():
    config = JobConfig.from_env(_env(JOB_IMAGE_DIGEST="sha256:abc", GIT_SHA="commit-1"))

    assert config.image_digest == "sha256:abc"
    assert config.git_sha == "commit-1"


def test_unset_image_digest_marker_becomes_null():
    config = JobConfig.from_env(_env(JOB_IMAGE_DIGEST="unset", GIT_SHA="commit-1"))

    assert config.image_digest is None
    assert config.git_sha == "commit-1"


def test_raw_partition_key_preserves_explicit_key():
    env = _env(RAW_KEY="region=monaco/2025/01/01/custom.osm.pbf")
    env.pop("YMD")
    config = JobConfig.from_env(env)

    assert config.raw_partition_key == "region=monaco/2025/01/01/custom.osm.pbf"
    assert config.ymd == "20250101"


@pytest.mark.parametrize(
    "raw_key",
    [
        "region=monaco/ymd=20250101/custom.osm.pbf",
        "monaco/2025/01/01/custom.osm.pbf",
        "region=monaco/2025/01/01/custom.zip",
        "region=/2025/01/01/custom.osm.pbf",
        "region=monaco/2025/01/custom.osm.pbf",
    ],
)
def test_malformed_raw_key_raises_config_error(raw_key):
    env = _env(RAW_KEY=raw_key)
    env.pop("YMD")
    env.pop("REGION_NAME")

    with pytest.raises(ConfigError):
        JobConfig.from_env(env)


def test_missing_region_name_raises_config_error_without_raw_key():
    env = _env()
    env.pop("REGION_NAME")

    with pytest.raises(ConfigError):
        JobConfig.from_env(env)


def test_missing_ymd_raises_config_error_without_raw_key():
    env = _env()
    env.pop("YMD")

    with pytest.raises(ConfigError):
        JobConfig.from_env(env)


def test_way_geometry_defaults_to_enabled():
    assert JobConfig.from_env(_env()).include_way_geometry is True


def test_env_for_raw_key_decodes_and_derives_region_and_date():
    base = {
        "RAW_BUCKET": "raw-bucket",
        "OUTPUT_BUCKET": "curated-bucket",
        "MODE": "all",
    }
    encoded_key = "region=quebec/2026/11/08/quebec-20261108.osm.pbf"

    env = env_for_raw_key("region=quebec%2F2026%2F11%2F08%2Fquebec-20261108.osm.pbf", base)

    assert env["RAW_KEY"] == encoded_key
    assert env["REGION_NAME"] == "quebec"
    assert env["YMD"] == "20261108"
    # The base environment is copied, not mutated.
    assert base.get("RAW_KEY") is None
    assert base.get("REGION_NAME") is None
    assert base.get("YMD") is None
    config = JobConfig.from_env(env)
    assert config.region_name == "quebec"
    assert config.ymd == "20261108"


def test_env_for_raw_key_rejects_malformed_keys():
    with pytest.raises(ConfigError):
        env_for_raw_key("bucket-root/extract.osm.pbf", {})


def test_explicit_ymd_overrides_raw_key():
    config = JobConfig.from_env(
        _env(RAW_KEY="region=monaco/2025/01/01/custom.osm.pbf", YMD="20260301")
    )

    assert config.ymd == "20260301"


def test_region_is_derived_from_raw_key_for_triggered_jobs():
    env = _env(RAW_KEY="region=quebec/2026/11/08/quebec-20261108.osm.pbf")
    env.pop("REGION_NAME")
    env.pop("YMD")

    config = JobConfig.from_env(env)

    assert config.region_name == "quebec"
    assert config.ymd == "20261108"
    assert config.curated_prefix == "curated/region=quebec/2026/11/08"


def test_explicit_region_name_overrides_raw_key_region():
    env = _env(
        RAW_KEY="region=quebec/2026/11/08/quebec-20261108.osm.pbf",
        REGION_NAME="montreal",
    )

    assert JobConfig.from_env(env).region_name == "montreal"


def test_output_and_staging_keys_are_deterministic():
    config = JobConfig.from_env(_env(RUN_ID="run-1"))

    assert config.curated_prefix == "curated/region=monaco/2026/11/08"
    assert config.manifest_relative_key == "region=monaco/2026/11/08/_manifest.json"
    assert (
        config.output_key("nodes", "part-00000.parquet")
        == "region=monaco/2026/11/08/entity=nodes/part-00000.parquet"
    )
    assert config.staging_prefix() == "curated/_staging/run_id=run-1"
    assert (
        config.staging_key(config.manifest_relative_key)
        == "curated/_staging/run_id=run-1/region=monaco/2026/11/08/_manifest.json"
    )


def test_entity_types_follow_mode():
    assert JobConfig.from_env(_env(MODE="all")).entity_types == (
        "nodes",
        "ways",
        "relations",
    )
    assert JobConfig.from_env(_env(MODE="ways")).entity_types == ("ways",)


@pytest.mark.parametrize(
    "name,value",
    [
        ("PARQUET_COMPRESSION", "zip"),
        ("OVERWRITE", "clobber"),
        ("MODE", "buildings"),
        ("LOG_LEVEL", "TRACE"),
    ],
)
def test_invalid_choices_raise_config_error(name, value):
    with pytest.raises(ConfigError):
        JobConfig.from_env(_env(**{name: value}))


def test_missing_required_bucket_raises_config_error():
    with pytest.raises(ConfigError):
        JobConfig.from_env({"OUTPUT_BUCKET": "curated-bucket"})


def test_region_token_rejects_path_injection():
    with pytest.raises(ConfigError):
        JobConfig.from_env(_env(REGION_NAME="../etc"))


def test_bool_and_numeric_parsing():
    config = JobConfig.from_env(
        _env(
            INCLUDE_WAY_GEOMETRY="yes",
            MAX_RECORDS_PER_FILE="10",
            ROW_GROUP_SIZE="5",
            S3_MAX_ATTEMPTS="7",
        )
    )

    assert config.include_way_geometry is True
    assert config.max_records_per_file == 10
    assert config.row_group_size == 5
    assert config.s3_max_attempts == 7


def test_invalid_int_raises_config_error():
    with pytest.raises(ConfigError):
        JobConfig.from_env(_env(MAX_RECORDS_PER_FILE="many"))


@pytest.mark.parametrize("ymd", ["2026-1", "2026118", "garbage", "202611081"])
def test_invalid_ymd_format_raises_config_error(ymd):
    with pytest.raises(ConfigError):
        JobConfig.from_env(_env(YMD=ymd))


def test_invalid_calendar_date_raises_config_error():
    with pytest.raises(ConfigError):
        JobConfig.from_env(_env(YMD="20261301"))


def test_ymd_extracted_from_raw_key_is_validated():
    env = _env()
    env.pop("YMD")
    env["RAW_KEY"] = "region=monaco/2026/13/08/monaco.osm.pbf"

    with pytest.raises(ConfigError):
        JobConfig.from_env(env)


@pytest.mark.parametrize(
    "prefix",
    ["../escape", "curated/../curated", "curated/./x", "curated//x", "curated/x y"],
)
def test_invalid_output_prefix_raises_config_error(prefix):
    with pytest.raises(ConfigError):
        JobConfig.from_env(_env(OUTPUT_PREFIX=prefix))


def test_output_prefix_strips_surrounding_slashes():
    config = JobConfig.from_env(_env(OUTPUT_PREFIX="/curated/"))

    assert config.output_prefix == "curated"


def test_output_prefix_accepts_nested_relative_prefixes():
    config = JobConfig.from_env(_env(OUTPUT_PREFIX="data/lake.v2/curated"))

    assert config.output_prefix == "data/lake.v2/curated"


def test_run_id_defaults_from_batch_job_and_attempt():
    config = JobConfig.from_env(_env(AWS_BATCH_JOB_ID="job:abc 123", AWS_BATCH_JOB_ATTEMPT="2"))

    assert config.run_id == "job-abc-123-attempt-2"


def test_run_id_defaults_to_local_run_without_batch_context():
    assert JobConfig.from_env(_env()).run_id == "local-run"
