#!/usr/bin/env bash
set -euo pipefail

REGION_NAME="${REGION_NAME:-monaco}"
RUN_ID="${RUN_ID:-${REGION_NAME}-$(date +%Y%m%d%H%M%S)}"
YMD="${YMD:-$(date +%Y%m%d)}"
RAW_BUCKET="${RAW_BUCKET:?Set RAW_BUCKET to the S3 bucket containing the PBF extract}"
RAW_KEY="${RAW_KEY:-region=${REGION_NAME}/ymd=${YMD}/${REGION_NAME}-${YMD}.osm.pbf}"
OUTPUT_BUCKET="${OUTPUT_BUCKET:?Set OUTPUT_BUCKET to the curated S3 bucket}"
OUTPUT_PREFIX="${OUTPUT_PREFIX:-curated}"
JOB_QUEUE="${JOB_QUEUE:?Set JOB_QUEUE to an existing AWS Batch queue}"
JOB_DEFINITION="${JOB_DEFINITION:?Set JOB_DEFINITION to an existing AWS Batch job definition}"
AWS_REGION="${AWS_REGION:-us-east-1}"
MODE="${MODE:-all}"
OVERWRITE="${OVERWRITE:-error}"
PARQUET_COMPRESSION="${PARQUET_COMPRESSION:-snappy}"
INCLUDE_WAY_GEOMETRY="${INCLUDE_WAY_GEOMETRY:-false}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
ALLOW_CONCURRENT="${ALLOW_CONCURRENT:-false}"

# Belt and braces on top of the pipeline's partition claim: publication is
# serialized per region/ymd by an S3 conditional write (_lock.json), and a
# losing run fails fast with exit 4. This client-side guard additionally
# avoids queueing a second job for the same region while one is active,
# which saves the wasted job run entirely.
if [[ "$ALLOW_CONCURRENT" != "true" ]]; then
  ACTIVE_JOBS="$(aws batch list-jobs \
    --job-queue "$JOB_QUEUE" \
    --region "$AWS_REGION" \
    --filters "name=JOB_NAME,values=osm-${REGION_NAME}-*" \
    --query "jobSummaryList[?status!='SUCCEEDED' && status!='FAILED'].[jobId,jobName,status]" \
    --output text)"
  if [[ -n "$ACTIVE_JOBS" ]]; then
    echo "Active job(s) already exist for region ${REGION_NAME}:" >&2
    echo "$ACTIVE_JOBS" >&2
    echo "Wait for them to finish or set ALLOW_CONCURRENT=true." >&2
    exit 1
  fi
fi

CONTAINER_OVERRIDES="$(RAW_BUCKET="$RAW_BUCKET" RAW_KEY="$RAW_KEY" \
  OUTPUT_BUCKET="$OUTPUT_BUCKET" OUTPUT_PREFIX="$OUTPUT_PREFIX" \
  REGION_NAME="$REGION_NAME" RUN_ID="$RUN_ID" YMD="$YMD" \
  AWS_REGION="$AWS_REGION" MODE="$MODE" OVERWRITE="$OVERWRITE" \
  PARQUET_COMPRESSION="$PARQUET_COMPRESSION" \
  INCLUDE_WAY_GEOMETRY="$INCLUDE_WAY_GEOMETRY" LOG_LEVEL="$LOG_LEVEL" \
  python3 -c 'import json, os
keys = (
    "RAW_BUCKET", "RAW_KEY", "OUTPUT_BUCKET", "OUTPUT_PREFIX", "REGION_NAME",
    "RUN_ID", "YMD", "AWS_REGION", "MODE", "OVERWRITE", "PARQUET_COMPRESSION",
    "INCLUDE_WAY_GEOMETRY", "LOG_LEVEL",
)
print(json.dumps({"environment": [{"name": key, "value": os.environ[key]} for key in keys]}))')"

aws batch submit-job \
  --job-name "osm-${REGION_NAME}-${RUN_ID}" \
  --job-queue "$JOB_QUEUE" \
  --job-definition "$JOB_DEFINITION" \
  --region "$AWS_REGION" \
  --container-overrides "$CONTAINER_OVERRIDES"
