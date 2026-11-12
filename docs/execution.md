# Upload an extract and run AWS Batch

Obtain a regional `.osm.pbf` extract from a source you are licensed to use.
OpenStreetMap data is available under the ODbL and requires attribution; see
the project's [license and attribution notes](../README.md#data-attribution).
`make run` (or `scripts/run_extract.sh`) downloads the dated extract from
Geofabrik, caches it under `data/geofabrik/`, and uploads it under the
expected key layout:

```bash
make run REGION=monaco YMD=20261108 GEOFABRIK_AREA=europe
```

`YMD` must match Geofabrik's dated file name (`20261108` ↔
`monaco-261108.osm.pbf`); the script refuses a malformed date and never
substitutes today's extract silently. `SOURCE_URL` overrides the download,
`FORCE_DOWNLOAD=1` bypasses the cache, and `INCLUDE_WAY_GEOMETRY=false`
disables way geometry reconstruction for the manual submission path.

For a first reproduction, prefer a small public extract. Geofabrik's Monaco
extract (~0.7 MB) runs in minutes and costs cents. To resolve the current
dated file by hand:

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
`RUN_ID` is derived inside the job from the Batch job ID and attempt number,
so each attempt stages under its own prefix; set it explicitly only for
debugging.

```bash
export AWS_REGION="us-east-1"
export RAW_BUCKET="$(terraform -chdir=infra output -raw raw_bucket_name)"
export OUTPUT_BUCKET="$(terraform -chdir=infra output -raw curated_bucket_name)"
export JOB_QUEUE="$(terraform -chdir=infra output -raw batch_job_queue_name)"
export JOB_DEFINITION="$(terraform -chdir=infra output -raw batch_job_definition_name)"

export REGION_NAME="monaco"
export YMD="20261108" # Replace with the date associated with your extract.
export RAW_KEY="region=${REGION_NAME}/${YMD:0:4}/${YMD:4:2}/${YMD:6:2}/${REGION_NAME}-${YMD}.osm.pbf"
export OUTPUT_PREFIX="curated"
export MODE="all"
export OVERWRITE="error"
export PARQUET_COMPRESSION="snappy"
export INCLUDE_WAY_GEOMETRY="true"

aws s3 cp "/path/to/${REGION_NAME}-${YMD}.osm.pbf" \
  "s3://${RAW_BUCKET}/${RAW_KEY}"
```

### Automatic trigger

With `s3_trigger_enabled = true` (the default), the upload above matches the
EventBridge rule and submits a Batch job automatically. The rule filters on the
raw bucket and a `.osm.pbf` suffix. EventBridge passes the object key as the
`raw_key` job parameter; the job derives `REGION_NAME` and `YMD` from it, and
a key outside the `region=` layout fails fast with exit code 3. Duplicate
events are made safe by the baked `OVERWRITE` mode (default `error`) plus the
partition claim. Triggered jobs use the event job definition's baked `MODE`,
compression and `INCLUDE_WAY_GEOMETRY`; change Terraform and apply a new
revision when those defaults should change. Manual submission can override
them.

Check the rule and the submitted job:

```bash
terraform -chdir=infra output eventbridge_rule_name
aws events list-rules --region "$AWS_REGION" \
  --name-prefix "$(terraform -chdir=infra output -raw eventbridge_rule_name)"
aws batch list-jobs --region "$AWS_REGION" --job-queue "$JOB_QUEUE" --status RUNNING
```

If the upload does not start a job, see [trigger troubleshooting](trigger.md#trigger-not-firing).
Do not also run the manual submission below for the same object.

### Manual submission

Use this path when the trigger is disabled or you need explicit overrides:

```bash
./scripts/submit_job.sh
```

The submit script passes the input bucket/key, output bucket/prefix, region,
date and processing options as Batch container environment overrides (the run
ID is derived inside the job).
It does not accept PBF bytes on the command line; the input must already be in
the raw bucket. Manual overrides take precedence over the key-derived region and
date. `OVERWRITE=skip` exits successfully if a manifest already exists.
`OVERWRITE=replace` republishes and should be reserved for a controlled
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
the default log group is `/aws/batch/osm-pbf-data-lake`. Follow the live logs
with `make logs` (default lookback `SINCE=1h`) or the AWS CLI:

```bash
aws logs tail /aws/batch/osm-pbf-data-lake --region "$AWS_REGION" --follow --since 30m
```

A successful attempt ends with `Run complete: status=success records=...
files=... manifest=s3://.../_manifest.json`. For retryable exit code 75, Batch
retries up to the configured attempt count. The Fargate job has a per-attempt
timeout. The application logs input bytes, download and parse timings, entity
counts, published file counts, output bytes, run ID, and the final manifest
key.
