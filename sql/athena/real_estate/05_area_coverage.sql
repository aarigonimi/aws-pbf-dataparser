-- 05_area_coverage.sql
-- Data: © OpenStreetMap contributors, ODbL.

CREATE TABLE osm_catalog.re_area_coverage_quebec_city_20261108
WITH (
    external_location = 's3://<curated-bucket>/derived/re_area_coverage/area=quebec_city/2026/11/08/',
    format = 'PARQUET',
    write_compression = 'SNAPPY'
) AS
SELECT
    round(floor(lat / 0.01) * 0.01, 2) AS cell_lat,
    round(floor(lon / 0.01) * 0.01, 2) AS cell_lon,
    count(*) FILTER (WHERE category = 'school') AS schools,
    count(*) FILTER (WHERE category = 'grocery') AS groceries,
    count(*) FILTER (WHERE category = 'transit') AS transit_stops,
    count(*) FILTER (WHERE category = 'green_space') AS green_spaces,
    count(*) FILTER (WHERE category = 'healthcare') AS healthcare,
    count(*) FILTER (WHERE category = 'pharmacy') AS pharmacies,
    count(DISTINCT category) AS categories_present
FROM osm_catalog.re_pois_quebec_city_20261108
WHERE lat BETWEEN 46.72 AND 46.99
  AND lon BETWEEN -71.55 AND -71.13
GROUP BY 1, 2;

-- One view with the cells and the listings together, sharing the columns
-- map_layer, lat, lon, label, categories_present and points, so one query or
-- one map shows both. Listing rows carry 'Our listing' as their map layer
-- and the listing label in the label column.
CREATE OR REPLACE VIEW osm_catalog.re_director_map_quebec_city AS
WITH cells AS (
    SELECT
        CASE
            WHEN categories_present >= 5 THEN 'Well served (5-6 of 6)'
            WHEN categories_present >= 3 THEN 'Partly served (3-4 of 6)'
            ELSE 'Thin (1-2 of 6)'
        END AS map_layer,
        cell_lat AS lat,
        cell_lon AS lon,
        CAST(NULL AS varchar) AS label,
        categories_present,
        CAST(1 AS integer) AS points
    FROM osm_catalog.re_area_coverage_quebec_city_20261108
),
listings AS (
    SELECT
        'Our listing' AS map_layer,
        lat,
        lon,
        label,
        CAST(NULL AS integer) AS categories_present,
        CAST(1 AS integer) AS points
    FROM osm_catalog.re_listings
)
SELECT * FROM cells
UNION ALL
SELECT * FROM listings;
