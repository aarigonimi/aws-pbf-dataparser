-- 03_score_listings.sql
-- Data: © OpenStreetMap contributors, ODbL.

CREATE TABLE osm_catalog.re_listing_scores_quebec_city_20261108
WITH (
    external_location = 's3://<curated-bucket>/derived/re_scores/area=quebec_city/2026/11/08/',
    format = 'PARQUET',
    write_compression = 'SNAPPY'
) AS
WITH weights (category, points) AS (
    VALUES
        ('school', 25),
        ('grocery', 20),
        ('transit', 20),
        ('green_space', 15),
        ('healthcare', 10),
        ('pharmacy', 10)
),
nearby AS (
    SELECT
        l.listing_id,
        p.category,
        p.name,
        great_circle_distance(l.lat, l.lon, p.lat, p.lon) * 1000 AS distance_m
    FROM osm_catalog.re_listings l
    JOIN osm_catalog.re_pois_quebec_city_20261108 p
      ON p.lat BETWEEN l.lat - 0.0072 AND l.lat + 0.0072
     AND p.lon BETWEEN l.lon - 0.0072 / cos(radians(l.lat))
                  AND l.lon + 0.0072 / cos(radians(l.lat))
    WHERE great_circle_distance(l.lat, l.lon, p.lat, p.lon) <= 0.8
),
tallies AS (
    SELECT
        listing_id,
        category,
        count(*) AS nearby_count,
        min(distance_m) AS nearest_m,
        min_by(name, distance_m) AS nearest_name
    FROM nearby
    GROUP BY listing_id, category
)
-- CROSS JOIN weights + LEFT JOIN tallies: every input listing produces
-- exactly one row, with zero counts, zero score and null distances when a
-- category has nothing within 800 m.
SELECT
    l.listing_id,
    l.label,
    l.bedrooms,
    l.list_price,
    'quebec' AS region,
    DATE '2026-11-08' AS snapshot_date,
    coalesce(sum(w.points) FILTER (WHERE t.nearby_count >= 1), 0) AS score,
    coalesce(sum(t.nearby_count) FILTER (WHERE w.category = 'school'), 0) AS schools,
    coalesce(sum(t.nearby_count) FILTER (WHERE w.category = 'grocery'), 0) AS groceries,
    coalesce(sum(t.nearby_count) FILTER (WHERE w.category = 'transit'), 0) AS transit_stops,
    coalesce(sum(t.nearby_count) FILTER (WHERE w.category = 'green_space'), 0) AS green_spaces,
    coalesce(sum(t.nearby_count) FILTER (WHERE w.category = 'healthcare'), 0) AS healthcare,
    coalesce(sum(t.nearby_count) FILTER (WHERE w.category = 'pharmacy'), 0) AS pharmacies,
    round(min(t.nearest_m) FILTER (WHERE w.category = 'school')) AS nearest_school_m,
    round(min(t.nearest_m) FILTER (WHERE w.category = 'grocery')) AS nearest_grocery_m,
    round(min(t.nearest_m) FILTER (WHERE w.category = 'transit')) AS nearest_transit_m,
    round(min(t.nearest_m) FILTER (WHERE w.category = 'green_space')) AS nearest_green_m,
    round(min(t.nearest_m) FILTER (WHERE w.category = 'healthcare')) AS nearest_healthcare_m,
    round(min(t.nearest_m) FILTER (WHERE w.category = 'pharmacy')) AS nearest_pharmacy_m,
    min_by(t.nearest_name, t.nearest_m) FILTER (WHERE w.category = 'school') AS nearest_school_name,
    min_by(t.nearest_name, t.nearest_m) FILTER (WHERE w.category = 'green_space') AS nearest_green_name
FROM osm_catalog.re_listings l
CROSS JOIN weights w
LEFT JOIN tallies t
    ON t.listing_id = l.listing_id
   AND t.category = w.category
GROUP BY
    l.listing_id,
    l.label,
    l.bedrooms,
    l.list_price;
