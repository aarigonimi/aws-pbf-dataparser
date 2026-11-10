# Upload an extract and run AWS Batch

Obtain a regional `.osm.pbf` extract from a source you are licensed to use.
OpenStreetMap data is available under the ODbL and requires attribution; see
the project's [license and attribution notes](../README.md#data-attribution).
This project does not download regional extracts automatically.

For a first reproduction, prefer a small public extract. Geofabrik's Monaco
extract (~0.7 MB) runs in minutes and costs cents; it resolves `monaco-latest`
to a dated file whose date must become `YMD`:

```bash
export REGION_NAME="monaco"
EXTRACT_URL="$(curl -s -o /dev/null -w '%{redirect_url}' \
  https://download.geofabrik.de/europe/monaco-latest.osm.pbf)"
SHORT="$(basename "$EXTRACT_URL" .osm.pbf)"; SHORT="${SHORT#monaco-}"
export YMD="20${SHORT:0:2}${SHORT:2:2}${SHORT:4:2}"
curl -L -o "monaco-${YMD}.osm.pbf" "$EXTRACT_URL"
```

Any regional extract works the same way — adjust `REGION_NAME`, `YMD` and the
file name together, since `YMD` is both the extract's date and the output
partition. This tutorial run is distinct from the full-scale Quebec benchmark
(148.7 M entities, ~1 h 40 m); see the repository's benchmark evidence.

After deployment and image push, set the values from Terraform outputs and
choose a unique region/date. `YMD` is the extract's date and also the
output partition. Do not reuse a completed partition with `OVERWRITE=error`.
`RUN_ID` is optional under Batch: unset, it defaults to a unique value
derived from the Batch job ID and attempt number, so each attempt stages
under its own prefix. Set it explicitly only for local runs.

```bash
export AWS_REGION="us-east-1"
export RAW_BUCKET="$(terraform -chdir=infrastructure output -raw raw_bucket_name)"
export OUTPUT_BUCKET="$(terraform -chdir=infrastructure output -raw curated_bucket_name)"
export JOB_QUEUE="$(terraform -chdir=infrastructure output -raw batch_job_queue_name)"
export JOB_DEFINITION="$(terraform -chdir=infrastructure output -raw batch_job_definition_name)"

export REGION_NAME="monaco"
export YMD="20261108" # Replace with the date associated with your extract.
export RUN_ID="${REGION_NAME}-$(date -u +%Y%m%dT%H%M%SZ)"
export RAW_KEY="region=${REGION_NAME}/${YMD:0:4}/${YMD:4:2}/${YMD:6:2}/${REGION_NAME}-${YMD}.osm.pbf"
export OUTPUT_PREFIX="curated"
export MODE="all"
export OVERWRITE="error"
export PARQUET_COMPRESSION="snappy"
export INCLUDE_WAY_GEOMETRY="false"

aws s3 cp "/path/to/${REGION_NAME}-${YMD}.osm.pbf" \
  "s3://${RAW_BUCKET}/${RAW_KEY}"
./scripts/submit_job.sh
```

The submit script passes the input bucket/key, output bucket/prefix, region,
date, run ID and processing options as Batch container environment overrides.
It does not accept PBF bytes on the command line; the input must already be in
the raw bucket. `OVERWRITE=skip` exits successfully if a manifest already
exists. `OVERWRITE=replace` republishes and should be reserved for a controlled
recovery because it is not failure-atomic.

If a previous attempt left data without `_manifest.json`, inspect the current
objects and logs, then resubmit with the same region/date and `OVERWRITE=replace`:

```bash
REGION_NAME="$REGION_NAME" YMD="$YMD" OVERWRITE=replace ./scripts/submit_job.sh
```

The replacement path force-removes any stale partition claim, removes
stale objects *before* overwriting data, and publishes the new manifest
after all data copies. If the replacement fails, do not query the partition
until a new manifest exists and its contents match the objects. The old
object versions remain available for manual recovery when bucket
versioning is enabled.

Inspect the submitted job ID from the CLI response, then poll it:

```bash
aws batch describe-jobs --region "$AWS_REGION" --jobs YOUR_JOB_ID \
  --query 'jobs[0].{status:status,statusReason:statusReason,attempts:attempts,startedAt:startedAt,stoppedAt:stoppedAt}'
```

The job transitions through queue/running states to `SUCCEEDED` or `FAILED`.
CloudWatch log group and stream names are available in `describe-jobs` output;
the default log group is `/aws/batch/osm-pbf-data-lake`. Follow the live logs:

```bash
aws logs tail /aws/batch/osm-pbf-data-lake --region "$AWS_REGION" --follow --since 30m
```

A successful attempt ends with `Run complete: status=success records=...
files=... manifest=s3://.../_manifest.json`. For retryable exit code 75, Batch
retries up to the configured attempt count. The Fargate job has a per-attempt
timeout. The application logs input bytes, download and parse timings, entity
counts, published file counts, output bytes, run ID, and the final manifest
key.
