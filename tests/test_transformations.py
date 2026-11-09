import json
from types import SimpleNamespace

from src.transformations import (
    build_node_record,
    build_relation_record,
    build_way_record,
    linestring_wkt,
    normalize_tags,
    point_wkt,
    safe_float,
    safe_int,
)


def test_normalize_tags_accepts_dict_and_pyosmium_pairs():
    assert normalize_tags({"name": "Monaco", "population": 39000}) == {
        "name": "Monaco",
        "population": "39000",
    }

    pairs = [SimpleNamespace(k="amenity", v="cafe"), SimpleNamespace(k="name", v="Cafe")]
    assert normalize_tags(pairs) == {"amenity": "cafe", "name": "Cafe"}


def test_normalize_tags_skips_none_and_joins_sequences():
    assert normalize_tags({"name": None, "tags": ["a", "b"]}) == {"tags": "a, b"}
    assert normalize_tags(None) == {}


def test_safe_float_and_int_handle_bad_values():
    assert safe_float("1.25") == 1.25
    assert safe_float("nan") is None
    assert safe_float("bad") is None
    assert safe_int("42") == 42
    assert safe_int("bad") is None


def test_point_and_linestring_wkt():
    assert point_wkt(7.41, 43.73) == "POINT (7.41 43.73)"
    assert point_wkt(None, 1) is None
    assert linestring_wkt([(1, 2), (3, 4)]) == "LINESTRING (1.0 2.0, 3.0 4.0)"
    assert linestring_wkt([(1, 2)]) is None
    assert linestring_wkt(None) is None


def test_build_node_record_matches_dataset_contract():
    record = build_node_record(9001, 45.5, -73.8, {"name": "Example"})

    assert record["osm_id"] == 9001
    assert record["osm_type"] == "node"
    assert record["latitude"] == 45.5
    assert record["longitude"] == -73.8
    assert record["geometry"] == "POINT (-73.8 45.5)"
    assert record["name"] == "Example"
    assert record["tag_count"] == 1
    assert json.loads(record["tags"]) == {"name": "Example"}
    assert record["node_refs"] is None
    assert record["members"] is None


def test_build_node_record_without_location_is_null_but_valid():
    record = build_node_record(1, None, None, {})

    assert record["latitude"] is None
    assert record["longitude"] is None
    assert record["geometry"] is None
    assert record["tag_count"] == 0


def test_build_way_record_filters_refs_and_builds_geometry():
    record = build_way_record(
        10,
        {"highway": "residential"},
        [1, "2", None, "bad", 3],
    )

    assert record["osm_type"] == "way"
    assert record["node_refs"] == [1, 2, 3]
    assert record["highway"] == "residential"
    assert record["geometry"] is None

    with_geometry = build_way_record(
        11,
        {},
        [1, 2, 3],
        [(7.41, 43.73), ("bad", 1), (7.42, 43.74)],
    )
    assert with_geometry["geometry"] == "LINESTRING (7.41 43.73, 7.42 43.74)"


def test_build_relation_record_encodes_members():
    record = build_relation_record(
        20,
        {"type": "route"},
        [("node", 1, "stop"), {"type": "way", "ref": "2", "role": "outer"}, ("bad",)],
    )

    assert record["osm_type"] == "relation"
    assert record["members"] is not None
    members = [json.loads(item) for item in record["members"]]
    assert members == [
        {"ref": 1, "role": "stop", "type": "node"},
        {"ref": 2, "role": "outer", "type": "way"},
    ]
