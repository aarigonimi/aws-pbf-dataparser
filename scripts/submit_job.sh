#!/usr/bin/env bash
set -euo pipefail

REGION_NAME="${REGION_NAME:-monaco}"
YMD="${YMD:-$(date +%Y%m%d)}"
RAW_BUCKET="${RAW_BUCKET:?Set RAW_BUCKET to the S3 bucket containing the PBF extract}"
RAW_KEY="${RAW_KEY:-region=${REGION_NAME}/${YMD:0:4}/${YMD:4:2}/${YMD:6:2}/${REGION_NAME}-${YMD}.osm.pbf}"
OUTPUT_BUCKET="${OUTPUT_BUCKET:?Set OUTPUT_BUCKET to the curated S3 bucket}"
OUTPUT_PREFIX="${OUTPUT_PREFIX:-curated}"
JOB_QUEUE="${JOB_QUEUE:?Set JOB_QUEUE to an existing AWS Batch queue}"
JOB_DEFINITION="${JOB_DEFINITION:?Set JOB_DEFINITION to an existing AWS Batch job definition}"
AWS_REGION="${AWS_REGION:-us-east-1}"
MODE="${MODE:-all}"
OVERWRITE="${OVERWRITE:-error}"
PARQUET_COMPRESSION="${PARQUET_COMPRESSION:-snappy}"
INCLUDE_WAY_GEOMETRY="${INCLUDE_WAY_GEOMETRY:-true}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
ALLOW_CONCURRENT="${ALLOW_CONCURRENT:-false}"

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

# RUN_ID is deliberately not passed: the application derives a unique,
# per-attempt run id from AWS_BATCH_JOB_ID and AWS_BATCH_JOB_ATTEMPT, which
# keeps staging keys unique across Batch retries of the same job.
CONTAINER_OVERRIDES="$(RAW_BUCKET="$RAW_BUCKET" RAW_KEY="$RAW_KEY" \
  OUTPUT_BUCKET="$OUTPUT_BUCKET" OUTPUT_PREFIX="$OUTPUT_PREFIX" \
  REGION_NAME="$REGION_NAME" YMD="$YMD" \
  AWS_REGION="$AWS_REGION" MODE="$MODE" OVERWRITE="$OVERWRITE" \
  PARQUET_COMPRESSION="$PARQUET_COMPRESSION" \
  INCLUDE_WAY_GEOMETRY="$INCLUDE_WAY_GEOMETRY" LOG_LEVEL="$LOG_LEVEL" \
  python3 -c 'import json, os
keys = (
    "RAW_BUCKET", "RAW_KEY", "OUTPUT_BUCKET", "OUTPUT_PREFIX", "REGION_NAME",
    "YMD", "AWS_REGION", "MODE", "OVERWRITE", "PARQUET_COMPRESSION",
    "INCLUDE_WAY_GEOMETRY", "LOG_LEVEL",
)
print(json.dumps({"environment": [{"name": key, "value": os.environ[key]} for key in keys]}))')"

aws batch submit-job \
  --job-name "osm-${REGION_NAME}-${YMD}" \
  --job-queue "$JOB_QUEUE" \
  --job-definition "$JOB_DEFINITION" \
  --region "$AWS_REGION" \
  --container-overrides "$CONTAINER_OVERRIDES"
