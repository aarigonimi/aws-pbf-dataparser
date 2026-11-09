# Validate a completed output

Set the bucket and partition values for the completed run:

```bash
export AWS_REGION="us-east-1"
export OUTPUT_BUCKET="$(terraform -chdir=infrastructure output -raw curated_bucket_name)"
export REGION_NAME="monaco"
export YMD="20261108"
export OUTPUT_PREFIX="curated"
export PARTITION_PREFIX="${OUTPUT_PREFIX}/region=${REGION_NAME}/ymd=${YMD}/"
```

## S3 inventory and manifest

List the final objects and count Parquet files (the CLI paginates object
listing):

```bash
aws s3 ls "s3://${OUTPUT_BUCKET}/${PARTITION_PREFIX}" --recursive
aws s3api list-objects-v2 --bucket "$OUTPUT_BUCKET" \
  --prefix "$PARTITION_PREFIX" \
  --query "length(Contents[?ends_with(Key, '.parquet')])" --output text
aws s3 cp "s3://${OUTPUT_BUCKET}/${PARTITION_PREFIX}_manifest.json" -
```

Check `status`, `region`, `ymd`, `run_id`, `record_counts`, `total_records`,
`total_output_bytes`, `files`, `source` and `timings`. The manifest's
`duration_seconds` ends before final S3 publication; CloudWatch's `Run complete`
duration and Batch start/stop timestamps include more of the run.

The manifest path begins with an underscore. Read it directly from S3; Athena
may skip it as an input file even if a crawler creates a Glue table for it.

## Glue and Athena

Start the crawler after the manifest appears:

```bash
GLUE_CRAWLER="$(terraform -chdir=infrastructure output -raw glue_crawler_name)"
aws glue start-crawler --name "$GLUE_CRAWLER" --region "$AWS_REGION"
aws glue get-crawler --name "$GLUE_CRAWLER" --region "$AWS_REGION" \
  --query 'Crawler.State' --output text
```

Use the workgroup and database Terraform outputs:

```bash
ATHENA_WORKGROUP="$(terraform -chdir=infrastructure output -raw athena_workgroup_name)"
GLUE_DATABASE="$(terraform -chdir=infrastructure output -raw glue_database_name)"
```

In the Athena console, select that workgroup and database, then run:

```sql
SHOW TABLES IN osm_catalog;

SELECT count(*) AS nodes FROM entity_nodes;
SELECT count(*) AS ways FROM entity_ways;
SELECT count(*) AS relations FROM entity_relations;

SELECT osm_type, count(*) AS entities
FROM entity_ways
GROUP BY osm_type;

SELECT osm_id, name, highway, tags
FROM entity_ways
LIMIT 10;
```

Replace database/table identifiers with the names produced by your crawler;
conflicting crawls can add suffixes. Compare the three counts with
`record_counts` in the S3 manifest. Check Athena query execution details for
state, bytes scanned and engine time. Use the configured workgroup so its
result location and scan cutoff apply.

The current crawler creates tables at entity leaf paths. For one snapshot, the
tables above work directly. For multi-date analysis, create a partition-aware
Athena table over the `region=`/`ymd=`/`entity=` layout instead of relying on
the per-leaf tables the crawler creates.
