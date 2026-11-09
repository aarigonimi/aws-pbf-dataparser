#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
OUTPUT_BUCKET="${OUTPUT_BUCKET:-$(terraform -chdir=infrastructure output -raw curated_bucket_name)}"
REGION_NAME="${REGION_NAME:?Set REGION_NAME, for example monaco}"
YMD="${YMD:?Set YMD as YYYYMMDD}"
OUTPUT_PREFIX="${OUTPUT_PREFIX:-curated}"
PARTITION_PREFIX="${OUTPUT_PREFIX}/region=${REGION_NAME}/ymd=${YMD}/"
PARTITION_URI="s3://${OUTPUT_BUCKET}/${PARTITION_PREFIX}"

echo "Objects in ${PARTITION_URI}"
aws s3 ls "$PARTITION_URI" --recursive --region "$AWS_REGION"

echo "Parquet file count and total prefix bytes (includes the manifest)"
aws s3api list-objects-v2 \
  --bucket "$OUTPUT_BUCKET" \
  --prefix "$PARTITION_PREFIX" \
  --region "$AWS_REGION" \
  --query "{parquet_files:length(Contents[?ends_with(Key, '.parquet')]),total_prefix_bytes:sum(Contents[].Size)}" \
  --output json

echo "Manifest"
aws s3 cp "${PARTITION_URI}_manifest.json" - --region "$AWS_REGION"
