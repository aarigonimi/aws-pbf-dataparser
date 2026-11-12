---
layout: article
title: Québec real-estate amenity demo
description: Synthetic listings joined to OpenStreetMap amenities in Athena.
permalink: /docs/REAL_ESTATE/
---

## What it is

A small Athena demo that joins eight **fabricated** Québec City listings to
OpenStreetMap amenities extracted by the pipeline. It shows how the curated
Parquet partitions can answer a location question without a separate geocoding
service, and hands the results to analysts as three plain SQL views.

Data: **© OpenStreetMap contributors, ODbL.** The listings are not real
properties and must not be presented as inventory or market data.

## Prerequisites

1. A completed Québec partition:
   `s3://<curated-bucket>/curated/region=quebec/<yyyy>/<mm>/<dd>/`.
2. Its `_manifest.json` exists. Athena does not wait for it.
3. `include_way_geometry = true` (default) if you want way centroids. Node
   amenities work without geometry; ways without geometry have no coordinates
   and are excluded.
4. The Glue table and Athena workgroup from `terraform apply`.
5. `sample_listings.csv` uploaded to
   `s3://<curated-bucket>/derived/re_listings/` (see the
   [SQL README](../sql/athena/real_estate/README.md) for the exact command and
   the bucket-name replacement).

## Run the SQL

Run these in order in the Athena workgroup. The default snapshot is
`region=quebec/2026/11/08`; see the
[SQL README](../sql/athena/real_estate/README.md) for the exact change
procedure when your partition differs:

1. `sql/athena/real_estate/01_create_neighborhood_pois.sql`
2. `sql/athena/real_estate/02_create_listings.sql`
3. `sql/athena/real_estate/03_score_listings.sql`
4. `sql/athena/real_estate/04_create_marketing_views.sql`
5. `sql/athena/real_estate/05_area_coverage.sql`

The README documents each table and view.

## Categories

`re_pois_quebec_city_20261108` assigns each POI to the first matching
category:

| Category | Examples |
| --- | --- |
| `school` | school, college, university, kindergarten |
| `grocery` | supermarket, grocery, convenience, greengrocer, butcher, bakery |
| `transit` | bus stop/station, platform, public-transport and railway tags |
| `green_space` | park, garden, playground, nature reserve, picnic site |
| `healthcare` | hospital, clinic, doctors, dentist, healthcare tags |
| `pharmacy` | pharmacy, chemist |

A POI that matches several categories is assigned to only the first one. The
classification is deliberately simple and not a complete OSM taxonomy.

## Score

`re_listing_scores_quebec_city_20261108` counts amenities within 800 m using
a great-circle distance, then applies presence-once weights:

| Category | Points |
| --- | ---: |
| School | 25 |
| Grocery | 20 |
| Transit | 20 |
| Green space | 15 |
| Healthcare | 10 |
| Pharmacy | 10 |

A category contributes its points once when at least one amenity of that
category is within 800 m, so the maximum is 100. The query pre-filters with a
latitude/longitude bounding box before the exact distance test, so it scans
fewer rows than a plain join. The score is illustrative. It is not a validated
housing index, walkability score, or travel-time model.

## Reporting views for the analyst handoff

- `re_family_friendly_quebec_city`: three or more bedrooms with at least one
  school and one green space within 800 m, ranked by score — the agent
  shortlist.
- `re_agent_fact_sheet_quebec_city`: one row per listing with score, category
  counts, nearest amenity distances and names — the phone-call fact sheet.
- `re_director_map_quebec_city`: 0.01-degree coverage cells labeled
  `Well served (5-6 of 6)`, `Partly served (3-4 of 6)` or `Thin (1-2 of 6)`,
  plus the listings themselves — a ready-made map layer for any BI tool that
  reads Athena.

Analysts connect with any Athena-capable tool; no BI resource is provisioned
by Terraform. Do not publish the synthetic listings as real inventory.

## Limitations

- The bounding box is a demo area around Québec City, not an administrative
  boundary.
- Distances are straight-line, not walking or driving routes.
- OSM completeness varies by neighbourhood; missing amenities lower the score.
- Only the selected partition date is queried.
- The listings are synthetic and intentionally small.
- No Athena query result is claimed by the repository tests; those require an
  AWS deployment and a completed partition.
