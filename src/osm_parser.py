from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from src.errors import ConfigError, InputError, JobCancelled
from src.transformations import (
    build_node_record,
    build_relation_record,
    build_way_record,
)


def _load_osmium() -> Any | None:
    try:  # pragma: no cover - exercised only when PyOsmium is installed
        import osmium
    except ImportError:  # pragma: no cover
        return None
    return osmium


osmium: Any | None = _load_osmium()

logger = logging.getLogger(__name__)


def _check_cancelled(cancel_token: Any) -> None:
    if cancel_token is not None:
        cancel_token.raise_if_cancelled()


if osmium is not None:  # pragma: no branch

    class _Handler(osmium.SimpleHandler):  # type: ignore[misc, name-defined]
        def __init__(
            self,
            sinks: dict[str, Any],
            entity_types: Iterable[str],
            include_way_geometry: bool,
            counts: dict[str, int],
            cancel_token: Any,
        ) -> None:
            super().__init__()
            self._sinks = sinks
            self._entity_types = set(entity_types)
            self._include_way_geometry = include_way_geometry
            self._counts = counts
            self._cancel_token = cancel_token

        def node(self, node: Any) -> None:
            _check_cancelled(self._cancel_token)
            if "nodes" not in self._entity_types or "nodes" not in self._sinks:
                return
            latitude = longitude = None
            try:
                if node.location.valid():
                    latitude = node.location.lat
                    longitude = node.location.lon
            except Exception:  # pragma: no cover - location may be missing
                pass
            self._sinks["nodes"].add(build_node_record(node.id, latitude, longitude, node.tags))
            self._counts["nodes"] += 1

        def way(self, way: Any) -> None:
            _check_cancelled(self._cancel_token)
            if "ways" not in self._entity_types or "ways" not in self._sinks:
                return
            references: list[int] = []
            coordinates: list[tuple[float, float]] | None = (
                [] if self._include_way_geometry else None
            )
            for node_ref in way.nodes:
                references.append(node_ref.ref)
                if coordinates is not None:
                    try:
                        if node_ref.location.valid():
                            coordinates.append((node_ref.location.lon, node_ref.location.lat))
                    except Exception:  # pragma: no cover
                        continue
            self._sinks["ways"].add(build_way_record(way.id, way.tags, references, coordinates))
            self._counts["ways"] += 1

        def relation(self, relation: Any) -> None:
            _check_cancelled(self._cancel_token)
            if "relations" not in self._entity_types or "relations" not in self._sinks:
                return
            members = [(member.type, member.ref, member.role) for member in relation.members]
            self._sinks["relations"].add(build_relation_record(relation.id, relation.tags, members))
            self._counts["relations"] += 1


def _apply_file(
    handler: Any,
    pbf_path: Path,
    include_way_geometry: bool,
    index_dir: Path,
) -> None:
    if not include_way_geometry:
        handler.apply_file(str(pbf_path))
        return

    index_dir.mkdir(parents=True, exist_ok=True)
    index_path = index_dir / "node-locations.idx"
    if index_path.exists():
        index_path.unlink()

    # A disk-backed index keeps large extracts from blowing up memory.
    try:
        handler.apply_file(
            str(pbf_path),
            locations=True,
            idx=f"sparse_file_array,{index_path}",
        )
    except TypeError:  # pragma: no cover - older PyOsmium signature
        logger.warning(
            "PyOsmium does not support a disk-backed location index; "
            "falling back to the in-memory index."
        )
        handler.apply_file(str(pbf_path), locations=True)
    finally:
        for suffix in ("", ".idx"):
            candidate = Path(str(index_path) + suffix)
            if candidate.exists():
                try:
                    candidate.unlink()
                except OSError:  # pragma: no cover - best effort cleanup
                    pass


def process_pbf(
    pbf_path: str | os.PathLike[str],
    sinks: dict[str, Any],
    entity_types: Iterable[str],
    include_way_geometry: bool = False,
    cancel_token: Any = None,
    index_dir: str | os.PathLike[str] | None = None,
) -> dict[str, int]:
    """Stream a PBF file into per-entity sinks.

    Rows are pushed into ``sinks[entity].add(record)`` as PyOsmium walks the
    file, so the file itself is never materialised in memory. Way geometry is
    optional and, when enabled, uses a disk-backed node-location index.
    Relations are exported as member references; relation geometry is not
    reconstructed (see docs/SCHEMA.md).
    """

    if osmium is None:
        raise ConfigError(
            "PyOsmium is required to read OSM PBF files. "
            "Install the 'osmium' package (see requirements.txt)."
        )

    path = Path(pbf_path)
    if not path.exists():
        raise InputError(f"Input PBF does not exist: {path}")
    if path.stat().st_size == 0:
        raise InputError(f"Input PBF is empty: {path}")

    selected = tuple(dict.fromkeys(entity_types))
    unknown = set(selected) - {"nodes", "ways", "relations"}
    if unknown:
        raise ConfigError(f"Unsupported entity types: {sorted(unknown)}")

    counts = {entity: 0 for entity in selected}
    handler = _Handler(
        sinks=sinks,
        entity_types=selected,
        include_way_geometry=include_way_geometry,
        counts=counts,
        cancel_token=cancel_token,
    )

    resolved_index_dir = Path(index_dir) if index_dir is not None else path.parent / ".osmium-index"

    try:
        _apply_file(handler, path, include_way_geometry, resolved_index_dir)
    except (InputError, JobCancelled):
        raise
    except Exception as exc:
        raise InputError(f"Failed to parse PBF file {path}: {exc}") from exc

    logger.info("PBF parsed: %s (counts=%s)", path.name, counts)
    return counts


def iter_entities(
    pbf_path: str | os.PathLike[str],
    entity_types: Iterable[str] | None = None,
    include_way_geometry: bool = False,
) -> list[dict[str, Any]]:
    """Convenience collector for tests and small files.

    This intentionally buffers every record in memory. Production jobs must use
    :func:`process_pbf` with Parquet sinks instead.
    """

    class _ListSink:
        def __init__(self) -> None:
            self.rows: list[dict[str, Any]] = []

        def add(self, record: dict[str, Any]) -> None:
            self.rows.append(record)

    entities = tuple(entity_types or ("nodes", "ways", "relations"))
    sinks = {entity: _ListSink() for entity in entities}
    process_pbf(
        pbf_path,
        sinks=sinks,
        entity_types=entities,
        include_way_geometry=include_way_geometry,
    )
    rows: list[dict[str, Any]] = []
    for entity in entities:
        rows.extend(sinks[entity].rows)
    return rows


def download_raw_file_from_s3(
    s3_client: Any,
    bucket: str,
    key: str,
    destination_path: str | Path,
) -> str:
    """Backwards-compatible helper; prefer :class:`src.s3_utils.S3Client`."""

    target = Path(destination_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    s3_client.download_file(bucket, key, str(target))
    return str(target)
