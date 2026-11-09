-- Run in the osm_catalog database and configured Athena workgroup.
-- Partition projection requires exact region and ymd filters.
SELECT entity, count(*) AS records
FROM osm_curated
WHERE region = 'quebec' AND ymd = '20261108'
GROUP BY entity
ORDER BY entity;

-- Query only after the partition's _manifest.json exists, then compare these
-- counts with record_counts in that S3 manifest.
