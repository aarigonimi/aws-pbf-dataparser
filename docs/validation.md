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

Run the validator first. It fails closed if the final manifest is missing; it
does not make arbitrary Athena queries wait for publication.

```bash
./scripts/validate_output.sh
```

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
does not use it as a gate. **Query a partition only after its final
`_manifest.json` exists.** Partition projection makes the partition queryable
without crawler registration, so it does not prevent early readers from seeing
partially published objects.

## Glue and Athena

Use the workgroup and database Terraform outputs:

```bash
ATHENA_WORKGROUP="$(terraform -chdir=infrastructure output -raw athena_workgroup_name)"
GLUE_DATABASE="$(terraform -chdir=infrastructure output -raw glue_database_name)"
```

The `osm_curated` table is declared in Terraform with the explicit Parquet
schema and partition projection. Its `region` and `ymd` partitions use the
`injected` projection type, so every query must supply equality filters for
both. `entity` is projected from `nodes,ways,relations`. The table change is
implemented in the repository but has **not been deployed or verified in AWS**.

Confirm the table exists and exposes the expected columns and partition keys:

```bash
aws glue get-table --region "$AWS_REGION" --database-name "$GLUE_DATABASE" \
  --name osm_curated \
  --query 'Table.{name:Name,columns:StorageDescriptor.Columns[].Name,partitions:PartitionKeys[].Name}'
```

In the Athena console, select that workgroup and database, and after confirming
the S3 manifest exists, run:

```sql
SHOW TABLES IN osm_catalog;

SELECT entity, count(*) AS records
FROM osm_curated
WHERE region = 'monaco' AND ymd = '20261108'
GROUP BY entity;

SELECT osm_type, count(*) AS entities
FROM osm_curated
WHERE region = 'monaco' AND ymd = '20261108' AND entity = 'ways'
GROUP BY osm_type;

SELECT osm_id, name, highway, tags
FROM osm_curated
WHERE region = 'monaco' AND ymd = '20261108' AND entity = 'ways'
LIMIT 10;
```

The same query from the CLI (the workgroup enforces its own results location,
encryption and scan cutoff):

```bash
QUERY_ID="$(aws athena start-query-execution --region "$AWS_REGION" \
  --query-string "SELECT entity, count(*) AS records FROM osm_curated WHERE region = '${REGION_NAME}' AND ymd = '${YMD}' GROUP BY entity ORDER BY entity" \
  --query-execution-context "Database=${GLUE_DATABASE}" \
  --result-configuration "OutputLocation=s3://${OUTPUT_BUCKET}/athena-results/" \
  --work-group "$ATHENA_WORKGROUP" \
  --query 'QueryExecutionId' --output text)"
aws athena get-query-execution --region "$AWS_REGION" \
  --query-execution-id "$QUERY_ID" \
  --query 'QueryExecution.{state:Status.State,bytesScanned:Statistics.DataScannedInBytes}'
aws athena get-query-results --region "$AWS_REGION" \
  --query-execution-id "$QUERY_ID" \
  --query 'ResultSet.Rows[].Data[].VarCharValue'
```

Compare the three counts with `record_counts` in the S3 manifest. Check Athena
query execution details for state, bytes scanned and engine time. Use the
configured workgroup so its result location and scan cutoff apply. Always
include both injected partition predicates to constrain projection and scans.
