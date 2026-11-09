-- Run in the osm_catalog database and the project's configured Athena workgroup.
SELECT 'nodes' AS entity, count(*) AS records FROM entity_nodes
UNION ALL
SELECT 'ways', count(*) FROM entity_ways
UNION ALL
SELECT 'relations', count(*) FROM entity_relations;

-- Compare these values with record_counts in the S3 _manifest.json.
-- The Glue crawler can suffix table names if multiple locations collide.
