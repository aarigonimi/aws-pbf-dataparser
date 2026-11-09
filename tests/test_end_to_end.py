"""End-to-end run over a real (tiny) PBF file with an in-memory S3 fake."""

import json
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.osm_parser import osmium
from src.pipeline import run_pipeline
from tests.test_pipeline import INPUT_KEY, FakeS3, _config

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(osmium is None, reason="PyOsmium is not installed")


@pytest.fixture()
def sample_pbf(tmp_path: Path) -> bytes:
    target = tmp_path / "sample.osm.pbf"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_sample_pbf.py"), str(target)],
        check=True,
        capture_output=True,
    )
    return target.read_bytes()


@pytest.mark.parametrize("include_way_geometry", ["false", "true"])
def test_pbf_to_published_parquet(tmp_path: Path, sample_pbf: bytes, include_way_geometry: str):
    s3 = FakeS3({INPUT_KEY: sample_pbf})
    config = _config(tmp_path, INCLUDE_WAY_GEOMETRY=include_way_geometry)

    result = run_pipeline(config, s3=s3)

    assert result.record_counts == {"nodes": 3, "ways": 1, "relations": 1}
    prefix = "curated/region=monaco/ymd=20261108"
    manifest = json.loads(s3.objects[f"{prefix}/_manifest.json"])
    assert manifest["status"] == "success"
    assert manifest["total_records"] == 5
    assert not [key for key in s3.objects if "_staging" in key]

    published = {item["key"] for item in manifest["files"]}
    assert published == {
        f"{prefix}/entity={entity}/part-00000.parquet" for entity in ("nodes", "ways", "relations")
    }

    way_file = tmp_path / "way.parquet"
    way_file.write_bytes(s3.objects[f"{prefix}/entity=ways/part-00000.parquet"])
    way = pq.read_table(way_file).to_pylist()[0]
    assert way["node_refs"] == [1, 2, 3]
    if include_way_geometry == "true":
        assert way["geometry"] == "LINESTRING (7.42 43.737, 7.423 43.739, 7.426 43.741)"
    else:
        assert way["geometry"] is None
