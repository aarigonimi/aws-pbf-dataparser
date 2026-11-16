-- 01_create_neighborhood_pois.sql
-- Data: © OpenStreetMap contributors, ODbL.

CREATE TABLE osm_catalog.re_pois_quebec_city_20261108
WITH (
    external_location = 's3://<curated-bucket>/derived/re_pois/area=quebec_city/2026/11/08/',
    format = 'PARQUET',
    write_compression = 'SNAPPY'
) AS
WITH source AS (
    SELECT
        entity,
        osm_id,
        name,
        amenity,
        shop,
        highway,
        tags,
        latitude,
        longitude,
        geometry
    FROM osm_catalog.osm_curated
    WHERE region = 'quebec'
      AND year = '2026'
      AND month = '11'
      AND day = '08'
      AND entity IN ('nodes', 'ways')
),
with_coordinates AS (
    SELECT
        entity,
        osm_id,
        name,
        amenity,
        shop,
        highway,
        tags,
        COALESCE(latitude, ST_Y(ST_Centroid(ST_GeomFromText(geometry)))) AS lat,
        COALESCE(longitude, ST_X(ST_Centroid(ST_GeomFromText(geometry)))) AS lon
    FROM source
),
categorized AS (
    SELECT
        entity,
        osm_id,
        name,
        CASE
            WHEN amenity IN ('school', 'kindergarten') THEN 'school'
            WHEN shop IN ('supermarket', 'convenience', 'greengrocer', 'bakery') THEN 'grocery'
            WHEN amenity = 'pharmacy' THEN 'pharmacy'
            WHEN amenity IN ('hospital', 'clinic', 'doctors') THEN 'healthcare'
            WHEN json_extract_scalar(tags, '$.leisure') IN ('park', 'playground', 'garden') THEN 'green_space'
            WHEN highway = 'bus_stop'
                OR json_extract_scalar(tags, '$.public_transport') = 'platform'
                OR json_extract_scalar(tags, '$.railway') = 'station'
                THEN 'transit'
        END AS category,
        lat,
        lon
    FROM with_coordinates
    WHERE lat BETWEEN 46.72 AND 46.99
      AND lon BETWEEN -71.56 AND -71.12
)
SELECT
    entity,
    osm_id,
    name,
    category,
    lat,
    lon
FROM categorized
WHERE category IS NOT NULL
  AND lat IS NOT NULL
  AND lon IS NOT NULL;
