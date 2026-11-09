from pathlib import Path

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
    def __init__(self, objects=None, copy_fail_key: str | None = None):
        self.objects = dict(objects or {})
        self.copy_fail_key = copy_fail_key
        self.deleted: list[str] = []

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
        self.objects[key] = Path(local_path).read_bytes()

    def copy(self, bucket, source_key, destination_key):
        if self.copy_fail_key == destination_key:
            raise RuntimeError("simulated copy failure")
        self.objects[destination_key] = self.objects[source_key]

    def delete_keys(self, bucket, keys):
        for key in keys:
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
    assert result.manifest_key == ("curated/region=monaco/ymd=20261108/_manifest.json")
    assert "curated/region=monaco/ymd=20261108/entity=nodes/part-00000.parquet" in fake.objects
    assert not any(key.startswith("curated/_staging/") for key in fake.objects)


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

    with pytest.raises(OutputConflictError):
        run_pipeline(config, s3=fake, processor=_processor())


def test_replace_mode_removes_stale_objects(tmp_path: Path):
    config = _config(tmp_path, OVERWRITE="replace")
    manifest_key = f"{config.output_prefix}/{config.manifest_relative_key}"
    stale_key = "curated/region=monaco/ymd=20261108/entity=nodes/part-99999.parquet"
    fake = FakeS3({INPUT_KEY: b"pbf-bytes", manifest_key: b"{}", stale_key: b"old"})

    result = run_pipeline(config, s3=fake, processor=_processor())

    assert result.status == "success"
    assert stale_key not in fake.objects
    assert result.manifest_key in fake.objects


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
