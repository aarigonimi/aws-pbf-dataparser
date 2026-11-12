# Québec City real-estate demo (Athena SQL)

Five numbered files turn one curated OpenStreetMap partition into
neighborhood datasets for a brokerage demo. The listings are **synthetic**;
the amenities are OpenStreetMap data, **© OpenStreetMap contributors, ODbL**.

| File | Creates | Purpose |
| --- | --- | --- |
| `01_create_neighborhood_pois.sql` | `osm_catalog.re_pois_quebec_city_20261108` | Six amenity categories inside the Québec City bounding box |
| `02_create_listings.sql` + `sample_listings.csv` | `osm_catalog.re_listings` | External CSV table with the eight synthetic listings |
| `03_score_listings.sql` | `osm_catalog.re_listing_scores_quebec_city_20261108` | Counts and nearest distances within 800 m, presence-once score |
| `04_create_marketing_views.sql` | `re_family_friendly_quebec_city`, `re_agent_fact_sheet_quebec_city` | Campaign shortlist and per-listing fact sheet |
| `05_area_coverage.sql` | `osm_catalog.re_area_coverage_quebec_city_20261108`, `re_director_map_quebec_city` | 0.01° coverage grid and the combined map view |

## Running the SQL

1. The Québec partition for 2026-11-08 exists under
   `s3://<curated-bucket>/curated/region=quebec/2026/11/08/` **and** its
   `_manifest.json` is present (check with `make verify REGION=quebec
   YMD=20261108`). Athena does not wait for the manifest, so querying during
   publication can see partial output.
2. The snapshot was produced with `include_way_geometry = true` (the
   default). Ways without geometry have no coordinates and are excluded.
3. Replace `<curated-bucket>` with your curated bucket name in every file.
4. Run the files in order, submitting each SQL statement separately in the
   Athena workgroup created by Terraform (`osm-pbf-workgroup`, 10 GiB
   per-query scan limit).
5. Before `02_create_listings.sql`, upload the sample listings:

   ```bash
   source scripts/env.sh
   aws s3 cp sql/athena/real_estate/sample_listings.csv "s3://${OUTPUT_BUCKET}/derived/re_listings/"
   ```

CTAS destinations must be empty. To rerun for the same snapshot, follow
[docs/cleanup.md](../../docs/cleanup.md) first, or move to a new snapshot
name.

## Using another snapshot

The SQL is pinned to the 2026-11-08 Québec partition. For a new snapshot,
change these together:

- the four partition predicates (`region`, `year`, `month`, `day`) in
  `01_create_neighborhood_pois.sql`;
- the date suffix in every table and view name;
- the `external_location` paths of the CTAS statements;
- the `DATE '2026-11-08'` literal and the source string in
  `04_create_marketing_views.sql`, and every view reference to the scores
  table.

## What the numbers mean

- Coordinates: nodes use their own latitude/longitude; ways use the
  centroid of their reconstructed `LINESTRING` (an approximation, not an
  entrance or address point).
- The bounding box is the city's OSM box padded by roughly 800 m, not an
  administrative boundary; it includes L'Ancienne-Lorette, Wendake and part
  of Lévis.
- Distances are straight-line (great-circle) distances, not walking or
  driving routes.
- A POI that matches several categories is assigned to the first one in a
  fixed order (school, grocery, pharmacy, healthcare, green_space, transit).
  OpenStreetMap completeness varies by neighborhood, so a thin cell can mean
  few amenities or few mapped ones. Verify representative listings against
  openstreetmap.org before acting on the numbers.
- The score adds one weight per category with anything within 800 m
  (school 25, grocery 20, transit 20, green space 15, healthcare 10, pharmacy
  10, out of 100). It is an example, not a validated housing index; change
  the weights to fit your buyers.

## Analyst handoff

Grant analysts Athena and Glue read access on `osm_catalog`, S3 read on the
`derived/` prefix and write on the workgroup's `athena-results/` prefix, and
no access to the raw bucket. The three views answer the three questions:

| Question | View |
| --- | --- |
| How do our listings compare? | `osm_catalog.re_agent_fact_sheet_quebec_city` |
| Which homes fit the family campaign? | `osm_catalog.re_family_friendly_quebec_city` |
| Where are we well served or thin? | `osm_catalog.re_director_map_quebec_city` |

```sql
SELECT map_layer, count(*) AS points
FROM osm_catalog.re_director_map_quebec_city
GROUP BY map_layer
ORDER BY points DESC;
```

The views read the small derived tables, not the province partition, so
routine questions stay cheap. Any BI tool that connects to Athena can draw
the director's view as a points map; whatever shows it must credit
"© OpenStreetMap contributors". Do not present the synthetic listings as
real inventory.
