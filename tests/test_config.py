import pytest

from src.config import JobConfig
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


def test_raw_partition_key_uses_region_and_ymd():
    config = JobConfig.from_env(_env())

    assert config.raw_partition_key == "region=monaco/ymd=20261108/monaco-20261108.osm.pbf"


def test_raw_partition_key_preserves_explicit_key():
    env = _env(RAW_KEY="region=monaco/ymd=20250101/custom.osm.pbf")
    env.pop("YMD")
    config = JobConfig.from_env(env)

    assert config.raw_partition_key == "region=monaco/ymd=20250101/custom.osm.pbf"
    assert config.ymd == "20250101"


def test_explicit_ymd_overrides_raw_key():
    config = JobConfig.from_env(
        _env(RAW_KEY="region=monaco/ymd=20250101/custom.osm.pbf", YMD="20260301")
    )

    assert config.ymd == "20260301"


def test_output_and_staging_keys_are_deterministic():
    config = JobConfig.from_env(_env(RUN_ID="run-1"))

    assert config.curated_prefix == "curated/region=monaco/ymd=20261108"
    assert config.manifest_relative_key == "region=monaco/ymd=20261108/_manifest.json"
    assert (
        config.output_key("nodes", "part-00000.parquet")
        == "region=monaco/ymd=20261108/entity=nodes/part-00000.parquet"
    )
    assert config.staging_prefix() == "curated/_staging/run_id=run-1"
    assert (
        config.staging_key(config.manifest_relative_key)
        == "curated/_staging/run_id=run-1/region=monaco/ymd=20261108/_manifest.json"
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
