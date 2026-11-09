# Upload an extract and run AWS Batch

Obtain a regional `.osm.pbf` extract from a source you are licensed to use.
OpenStreetMap data is available under the ODbL and requires attribution; see
the project's [license and attribution notes](../README.md#data-attribution).
This project does not download regional extracts automatically.

After deployment and image push, set the values from Terraform outputs and
choose a unique region/date/run ID. `YMD` is the extract's date and also the
output partition. Do not reuse a completed partition with `OVERWRITE=error`.

```bash
export AWS_REGION="us-east-1"
export RAW_BUCKET="$(terraform -chdir=infrastructure output -raw raw_bucket_name)"
export OUTPUT_BUCKET="$(terraform -chdir=infrastructure output -raw curated_bucket_name)"
export JOB_QUEUE="$(terraform -chdir=infrastructure output -raw batch_job_queue_name)"
export JOB_DEFINITION="$(terraform -chdir=infrastructure output -raw batch_job_definition_name)"

export REGION_NAME="monaco"
export YMD="20261108" # Replace with the date associated with your extract.
export RUN_ID="${REGION_NAME}-$(date -u +%Y%m%dT%H%M%SZ)"
export RAW_KEY="region=${REGION_NAME}/ymd=${YMD}/${REGION_NAME}-${YMD}.osm.pbf"
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

Inspect the submitted job ID from the CLI response, then poll it:

```bash
aws batch describe-jobs --region "$AWS_REGION" --jobs YOUR_JOB_ID
```

The job transitions through queue/running states to `SUCCEEDED` or `FAILED`.
CloudWatch log group and stream names are available in `describe-jobs` output;
the default log group is `/aws/batch/osm-pbf-data-lake`.

For retryable exit code 75, Batch retries up to the configured attempt count.
The Fargate job has a per-attempt timeout. The application logs input bytes,
download and parse timings, entity counts, published file counts, output
bytes, run ID, and the final manifest key.
