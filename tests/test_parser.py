import json

import pytest

from src import osm_parser
from src.errors import ConfigError, InputError


def test_process_pbf_requires_pyosmium(monkeypatch, tmp_path):
    monkeypatch.setattr(osm_parser, "osmium", None)

    with pytest.raises(ConfigError):
        osm_parser.process_pbf(tmp_path / "input.osm.pbf", sinks={}, entity_types=["nodes"])


def test_process_pbf_rejects_missing_and_empty_files(monkeypatch, tmp_path):
    monkeypatch.setattr(osm_parser, "osmium", object())

    with pytest.raises(InputError):
        osm_parser.process_pbf(tmp_path / "missing.osm.pbf", sinks={}, entity_types=["nodes"])

    empty = tmp_path / "empty.osm.pbf"
    empty.write_bytes(b"")
    with pytest.raises(InputError):
        osm_parser.process_pbf(empty, sinks={}, entity_types=["nodes"])


def test_process_pbf_rejects_unknown_entity_types(monkeypatch, tmp_path):
    monkeypatch.setattr(osm_parser, "osmium", object())
    source = tmp_path / "input.osm.pbf"
    source.write_bytes(b"not-a-real-pbf")

    with pytest.raises(ConfigError):
        osm_parser.process_pbf(source, sinks={}, entity_types=["buildings"])


def test_process_pbf_extracts_all_entity_types_from_tiny_pbf(tmp_path):
    osmium = pytest.importorskip("osmium")
    from osmium.osm import RelationMember
    from osmium.osm.mutable import Node, Relation, Way

    pbf_path = tmp_path / "sample.osm.pbf"
    writer = osmium.SimpleWriter(str(pbf_path))
    try:
        writer.add_node(
            Node(
                id=1,
                location=osmium.osm.Location(7.420, 43.737),
                tags={"name": "Sample Node"},
            )
        )
        writer.add_node(Node(id=2, location=osmium.osm.Location(7.423, 43.739), tags={}))
        writer.add_way(
            Way(
                id=10,
                nodes=[1, 2],
                tags={"highway": "residential"},
            )
        )
        writer.add_relation(
            Relation(
                id=100,
                members=[RelationMember(mtype="w", ref=10, role="outer")],
                tags={"type": "multipolygon"},
            )
        )
    finally:
        writer.close()

    class ListSink:
        def __init__(self):
            self.rows = []

        def add(self, row):
            self.rows.append(row)

    sinks = {entity: ListSink() for entity in ("nodes", "ways", "relations")}
    counts = osm_parser.process_pbf(
        pbf_path,
        sinks=sinks,
        entity_types=("nodes", "ways", "relations"),
    )

    assert counts == {"nodes": 2, "ways": 1, "relations": 1}
    assert sinks["nodes"].rows[0]["name"] == "Sample Node"
    assert sinks["ways"].rows[0]["node_refs"] == [1, 2]
    relation_member = json.loads(sinks["relations"].rows[0]["members"][0])
    assert relation_member == {"ref": 10, "role": "outer", "type": "w"}
