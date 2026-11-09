from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

SCHEMA_VERSION = "1.0.0"


def dataset_schema() -> pa.Schema:
    """Single, explicit schema shared by all entity partitions.

    Using one schema keeps the Databricks/Athena contract stable. Columns that
    do not apply to an entity (for example ``latitude`` on a relation) are null.
    """

    return pa.schema(
        [
            pa.field("osm_id", pa.int64(), nullable=False),
            pa.field("osm_type", pa.string(), nullable=False),
            pa.field("name", pa.string()),
            pa.field("amenity", pa.string()),
            pa.field("shop", pa.string()),
            pa.field("tourism", pa.string()),
            pa.field("building", pa.string()),
            pa.field("highway", pa.string()),
            pa.field("surface", pa.string()),
            pa.field("latitude", pa.float64()),
            pa.field("longitude", pa.float64()),
            pa.field("geometry", pa.string()),
            pa.field("node_refs", pa.list_(pa.int64())),
            pa.field("members", pa.list_(pa.string())),
            pa.field("tag_count", pa.int32()),
            pa.field("tags", pa.string()),
        ]
    )


def _normalize_for_arrow(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


@dataclass(frozen=True)
class Artifact:
    path: Path
    records: int
    bytes: int

    def as_dict(self) -> dict[str, Any]:
        return {"path": str(self.path), "records": self.records, "bytes": self.bytes}


class ParquetSink:
    """Memory-bounded, rotating Parquet writer for one entity partition."""

    def __init__(
        self,
        output_dir: str | Path,
        compression: str = "snappy",
        max_records_per_file: int = 250_000,
        row_group_size: int = 100_000,
        schema: pa.Schema | None = None,
        file_prefix: str = "part",
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.compression = compression.lower()
        self.max_records_per_file = max_records_per_file
        self.row_group_size = row_group_size
        self.schema = schema or dataset_schema()
        self.file_prefix = file_prefix

        self.total_records = 0
        self._buffer: list[dict[str, Any]] = []
        self._writer: pq.ParquetWriter | None = None
        self._file_index = 0
        self._current_file_records = 0
        self._artifacts: list[Artifact] = []

    @property
    def _arrow_compression(self) -> str | None:
        if self.compression in {"none", "uncompressed"}:
            return None
        return self.compression

    def _open_writer(self) -> None:
        path = self.output_dir / f"{self.file_prefix}-{self._file_index:05d}.parquet"
        self._writer = pq.ParquetWriter(
            path,
            self.schema,
            compression=self._arrow_compression,
        )

    def _flush_buffer(self) -> None:
        if not self._buffer:
            return
        if self._writer is None:
            self._open_writer()
        table = pa.Table.from_pylist(
            [
                {key: _normalize_for_arrow(value) for key, value in row.items()}
                for row in self._buffer
            ],
            schema=self.schema,
        )
        self._current_file_records += len(self._buffer)
        assert self._writer is not None
        self._writer.write_table(table, row_group_size=self.row_group_size)
        self._buffer.clear()

    def _close_current_file(self) -> None:
        self._flush_buffer()
        if self._writer is None:
            return
        path = self.output_dir / f"{self.file_prefix}-{self._file_index:05d}.parquet"
        self._writer.close()
        self._writer = None
        self._artifacts.append(
            Artifact(path=path, records=self._current_file_records, bytes=path.stat().st_size)
        )
        self._file_index += 1
        self._current_file_records = 0

    def add(self, record: dict[str, Any]) -> None:
        self._buffer.append(record)
        self.total_records += 1
        reached_row_group = len(self._buffer) >= self.row_group_size
        reached_file_limit = (
            self._current_file_records + len(self._buffer) >= self.max_records_per_file
        )
        if reached_row_group or reached_file_limit:
            self._flush_buffer()
        if self._current_file_records >= self.max_records_per_file:
            self._close_current_file()

    def close(self) -> None:
        self._close_current_file()

    def artifacts(self) -> list[Artifact]:
        return list(self._artifacts)

    def __enter__(self) -> ParquetSink:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


def write_dataset(
    records: Iterable[dict[str, Any]],
    output_path: str | Path,
    compression: str = "snappy",
    max_records_per_file: int = 250_000,
    row_group_size: int = 100_000,
) -> list[str]:
    """Write records to one or more Parquet files and return their paths."""

    with ParquetSink(
        output_path,
        compression=compression,
        max_records_per_file=max_records_per_file,
        row_group_size=row_group_size,
    ) as sink:
        for record in records:
            sink.add(record)
    return [str(artifact.path) for artifact in sink.artifacts()]


def prepare_geo_metadata(
    region: str,
    entity_name: str,
    run_id: str,
    record_count: int,
    **extra: Any,
) -> dict[str, Any]:
    metadata = {
        "region": region,
        "entity": entity_name,
        "run_id": run_id,
        "record_count": record_count,
        "schema_version": SCHEMA_VERSION,
        "source": "osm-pbf-data-lake",
    }
    metadata.update(extra)
    return metadata


def write_summary_json(summary_path: str | Path, summary: dict[str, Any]) -> Path:
    output = Path(summary_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return output
