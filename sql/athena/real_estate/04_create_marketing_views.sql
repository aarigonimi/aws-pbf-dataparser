-- 04_create_marketing_views.sql
-- Data: © OpenStreetMap contributors, ODbL.

CREATE OR REPLACE VIEW osm_catalog.re_family_friendly_quebec_city AS
SELECT
    listing_id,
    label,
    bedrooms,
    list_price,
    score,
    nearest_school_m,
    nearest_green_m
FROM osm_catalog.re_listing_scores_quebec_city_20261108
WHERE bedrooms >= 3
  AND nearest_school_m IS NOT NULL
  AND nearest_green_m IS NOT NULL;

CREATE OR REPLACE VIEW osm_catalog.re_agent_fact_sheet_quebec_city AS
SELECT
    listing_id,
    label,
    bedrooms,
    list_price,
    score,
    rtrim(
        concat(
            IF(nearest_school_m IS NOT NULL, 'school ' || CAST(nearest_school_m AS varchar) || ' m; ', ''),
            IF(nearest_green_m IS NOT NULL, 'park ' || CAST(nearest_green_m AS varchar) || ' m; ', ''),
            IF(nearest_grocery_m IS NOT NULL, 'grocery ' || CAST(nearest_grocery_m AS varchar) || ' m; ', ''),
            IF(nearest_transit_m IS NOT NULL, 'transit ' || CAST(nearest_transit_m AS varchar) || ' m; ', '')
        ),
        '; '
    ) AS nearby,
    coalesce(nearest_school_name, 'unnamed') AS nearest_school_name,
    coalesce(nearest_green_name, 'unnamed') AS nearest_park_name,
    'OpenStreetMap snapshot 2026-11-08; straight-line distance, not walking route' AS source
FROM osm_catalog.re_listing_scores_quebec_city_20261108;
