from __future__ import annotations

import json
import math
from collections.abc import Iterable
from typing import Any


def _iter_tag_pairs(raw_tags: Any) -> list[tuple[Any, Any]]:
    if raw_tags is None:
        return []

    if hasattr(raw_tags, "items"):
        try:
            return list(raw_tags.items())
        except Exception:  # pragma: no cover - defensive for odd tag iterators
            return []

    try:
        items = list(raw_tags)
    except TypeError:
        return []

    pairs: list[tuple[Any, Any]] = []
    for item in items:
        if hasattr(item, "k") and hasattr(item, "v"):
            pairs.append((item.k, item.v))
            continue
        try:
            key, value = item
        except (TypeError, ValueError):
            continue
        pairs.append((key, value))
    return pairs


def normalize_tags(raw_tags: Any) -> dict[str, str]:
    """Normalize OSM tags (dict, PyOsmium TagList, or pair iterable) to strings."""

    tags: dict[str, str] = {}
    for key, value in _iter_tag_pairs(raw_tags):
        if key is None or value is None:
            continue
        if isinstance(value, list | tuple | set):
            value = ", ".join(str(item) for item in value)
        tags[str(key)] = str(value)
    return tags


def safe_float(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def safe_int(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def point_wkt(longitude: Any, latitude: Any) -> str | None:
    lon = safe_float(longitude)
    lat = safe_float(latitude)
    if lon is None or lat is None:
        return None
    return f"POINT ({lon} {lat})"


def linestring_wkt(coordinates: Iterable[Any] | None) -> str | None:
    if not coordinates:
        return None

    points: list[str] = []
    for coordinate in coordinates:
        try:
            lon, lat = coordinate
        except (TypeError, ValueError):
            continue
        lon_f = safe_float(lon)
        lat_f = safe_float(lat)
        if lon_f is None or lat_f is None:
            continue
        points.append(f"{lon_f} {lat_f}")

    if len(points) < 2:
        return None
    return f"LINESTRING ({', '.join(points)})"


def _base_record(
    osm_id: Any,
    osm_type: str,
    tags: dict[str, str],
    latitude: Any = None,
    longitude: Any = None,
    geometry: str | None = None,
    node_refs: list[int] | None = None,
    members: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "osm_id": safe_int(osm_id),
        "osm_type": osm_type,
        "name": tags.get("name"),
        "amenity": tags.get("amenity"),
        "shop": tags.get("shop"),
        "tourism": tags.get("tourism"),
        "building": tags.get("building"),
        "highway": tags.get("highway"),
        "surface": tags.get("surface"),
        "latitude": safe_float(latitude),
        "longitude": safe_float(longitude),
        "geometry": geometry,
        "node_refs": node_refs,
        "members": members,
        "tag_count": len(tags),
        "tags": json.dumps(tags, sort_keys=True, separators=(",", ":")),
    }


def build_node_record(
    osm_id: Any,
    latitude: Any,
    longitude: Any,
    tags: Any,
) -> dict[str, Any]:
    normalized = normalize_tags(tags)
    return _base_record(
        osm_id=osm_id,
        osm_type="node",
        tags=normalized,
        latitude=latitude,
        longitude=longitude,
        geometry=point_wkt(longitude, latitude),
    )


def build_way_record(
    osm_id: Any,
    tags: Any,
    node_refs: Iterable[Any] | None,
    coordinates: Iterable[Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_tags(tags)
    refs = [ref for ref in (safe_int(item) for item in (node_refs or [])) if ref is not None]
    return _base_record(
        osm_id=osm_id,
        osm_type="way",
        tags=normalized,
        geometry=linestring_wkt(coordinates),
        node_refs=refs,
    )


def _member_to_dict(member: Any) -> dict[str, Any] | None:
    if isinstance(member, dict):
        return {
            "type": member.get("type"),
            "ref": safe_int(member.get("ref")),
            "role": member.get("role") or "",
        }
    if hasattr(member, "type") and hasattr(member, "ref"):
        return {
            "type": member.type,
            "ref": safe_int(member.ref),
            "role": getattr(member, "role", "") or "",
        }
    try:
        member_type, ref, role = member
    except (TypeError, ValueError):
        return None
    return {"type": member_type, "ref": safe_int(ref), "role": role or ""}


def build_relation_record(
    osm_id: Any,
    tags: Any,
    members: Iterable[Any] | None,
) -> dict[str, Any]:
    normalized = normalize_tags(tags)
    encoded_members: list[str] = []
    for member in members or []:
        payload = _member_to_dict(member)
        if payload is None:
            continue
        encoded_members.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return _base_record(
        osm_id=osm_id,
        osm_type="relation",
        tags=normalized,
        members=encoded_members,
    )
