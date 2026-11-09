from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.parquet_writer import (
    ParquetSink,
    dataset_schema,
    prepare_geo_metadata,
    write_dataset,
    write_summary_json,
)


def _row(osm_id: int = 1, osm_type: str = "node") -> dict:
    return {
        "osm_id": osm_id,
        "osm_type": osm_type,
        "name": "Monaco",
        "amenity": "school",
        "shop": None,
        "tourism": None,
        "building": None,
        "highway": None,
        "surface": None,
        "latitude": 43.73,
        "longitude": 7.41,
        "geometry": "POINT (7.41 43.73)",
        "node_refs": None,
        "members": None,
        "tag_count": 1,
        "tags": '{"name":"Monaco"}',
    }


def test_write_dataset_returns_paths_and_valid_parquet(tmp_path: Path):
    output_dir = tmp_path / "curated" / "region=monaco" / "entity=nodes"

    paths = write_dataset([_row(1), _row(2)], output_dir)

    assert len(paths) == 1
    assert Path(paths[0]).exists()
    table = pq.ParquetFile(paths[0]).read()
    assert table.num_rows == 2
    assert table.schema.equals(dataset_schema())
    assert table.column("osm_id").to_pylist() == [1, 2]


def test_parquet_sink_rotates_files(tmp_path: Path):
    closed = []
    sink = ParquetSink(
        tmp_path / "entity=ways",
        max_records_per_file=2,
        row_group_size=1,
        on_file_closed=closed.append,
    )
    for osm_id in range(3):
        sink.add(_row(osm_id, "way"))
    sink.close()

    artifacts = sink.artifacts()
    assert sink.total_records == 3
    assert [artifact.records for artifact in artifacts] == [2, 1]
    assert all(artifact.path.exists() for artifact in artifacts)
    assert sum(artifact.bytes for artifact in artifacts) > 0
    assert closed == artifacts


def test_parquet_sink_callback_runs_on_close_for_final_file(tmp_path: Path):
    closed = []
    sink = ParquetSink(tmp_path / "entity=nodes", on_file_closed=closed.append)
    sink.add(_row())

    assert closed == []
    sink.close()

    assert closed == sink.artifacts()
    assert closed[0].records == 1
    assert closed[0].bytes == closed[0].path.stat().st_size


def test_parquet_sink_honors_file_limit_between_row_group_boundaries(tmp_path: Path):
    sink = ParquetSink(
        tmp_path / "entity=ways",
        max_records_per_file=5,
        row_group_size=4,
    )
    for osm_id in range(6):
        sink.add(_row(osm_id, "way"))
    sink.close()

    assert [artifact.records for artifact in sink.artifacts()] == [5, 1]


def test_parquet_sink_never_exceeds_max_records_per_file(tmp_path: Path):
    # The row-group boundary (6) falls past the file cap (10): the old
    # implementation flushed the whole 11-row buffer into one file with
    # 11 records. The cap must hold exactly.
    sink = ParquetSink(
        tmp_path / "entity=ways",
        max_records_per_file=10,
        row_group_size=6,
    )
    for osm_id in range(11):
        sink.add(_row(osm_id, "way"))
    sink.close()

    assert [artifact.records for artifact in sink.artifacts()] == [10, 1]


@pytest.mark.parametrize(
    "max_records,row_group,total",
    [(1, 1, 5), (3, 7, 11), (7, 3, 20), (250, 100, 1001)],
)
def test_parquet_sink_rotation_respects_cap_for_all_boundaries(
    tmp_path: Path, max_records: int, row_group: int, total: int
):
    sink = ParquetSink(
        tmp_path / "entity=nodes",
        max_records_per_file=max_records,
        row_group_size=row_group,
    )
    for osm_id in range(total):
        sink.add(_row(osm_id))
    sink.close()

    artifacts = sink.artifacts()
    assert sum(artifact.records for artifact in artifacts) == total
    assert all(artifact.records <= max_records for artifact in artifacts)
    assert artifacts[-1].records > 0


def test_write_dataset_with_no_records_creates_no_files(tmp_path: Path):
    paths = write_dataset([], tmp_path / "empty")

    assert paths == []
    assert list((tmp_path / "empty").glob("*.parquet")) == []


def test_metadata_and_summary_json(tmp_path: Path):
    metadata = prepare_geo_metadata("monaco", "nodes", "run-1", 1, extra="x")

    assert metadata == {
        "region": "monaco",
        "entity": "nodes",
        "run_id": "run-1",
        "record_count": 1,
        "schema_version": "1.0.0",
        "source": "osm-pbf-data-lake",
        "extra": "x",
    }

    summary_file = write_summary_json(tmp_path / "summary" / "summary.json", metadata)
    assert summary_file.exists()
    assert '"region": "monaco"' in summary_file.read_text(encoding="utf-8")
