#!/usr/bin/env python3
"""Generate a tiny PBF file for local end-to-end testing.

Requires PyOsmium (``pip install osmium``). The exact mutable API is stable
across PyOsmium 4.x, but this helper is not exercised by the unit tests.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Destination .osm.pbf file")
    args = parser.parse_args()

    try:
        import osmium
        from osmium.osm import RelationMember
        from osmium.osm.mutable import Node, Relation, Way
    except ImportError:
        print("PyOsmium is required: pip install osmium", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = osmium.SimpleWriter(str(args.output))
    try:
        writer.add_node(
            Node(
                id=1,
                location=osmium.osm.Location(7.420, 43.737),
                tags={"name": "Sample Cafe", "amenity": "cafe"},
            )
        )
        writer.add_node(
            Node(
                id=2,
                location=osmium.osm.Location(7.423, 43.739),
                tags={"name": "Sample School", "amenity": "school"},
            )
        )
        writer.add_node(Node(id=3, location=osmium.osm.Location(7.426, 43.741), tags={}))
        writer.add_way(
            Way(
                id=10,
                nodes=[1, 2, 3],
                tags={"name": "Sample Road", "highway": "residential"},
            )
        )
        writer.add_relation(
            Relation(
                id=100,
                members=[RelationMember(mtype="w", ref=10, role="outer")],
                tags={"type": "multipolygon", "name": "Sample Area"},
            )
        )
    finally:
        writer.close()

    print(f"Wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
