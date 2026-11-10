-- Run in the osm_catalog database and configured Athena workgroup.
-- Partition projection requires exact region, year, month and day filters
-- (month and day are zero-padded two-digit strings).
SELECT entity, count(*) AS records
FROM osm_curated
WHERE region = 'quebec' AND year = '2026' AND month = '11' AND day = '08'
GROUP BY entity
ORDER BY entity;

-- Query only after the partition's _manifest.json exists, then compare these
-- counts with record_counts in that S3 manifest.
