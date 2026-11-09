#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
OUTPUT_BUCKET="${OUTPUT_BUCKET:-$(terraform -chdir=infrastructure output -raw curated_bucket_name)}"
REGION_NAME="${REGION_NAME:?Set REGION_NAME, for example monaco}"
YMD="${YMD:?Set YMD as YYYYMMDD}"
OUTPUT_PREFIX="${OUTPUT_PREFIX:-curated}"
PARTITION_PREFIX="${OUTPUT_PREFIX}/region=${REGION_NAME}/ymd=${YMD}/"
PARTITION_URI="s3://${OUTPUT_BUCKET}/${PARTITION_PREFIX}"
MANIFEST_KEY="${PARTITION_PREFIX}_manifest.json"
MANIFEST_URI="s3://${OUTPUT_BUCKET}/${MANIFEST_KEY}"

MANIFEST_FOUND="$(aws s3api list-objects-v2 \
  --bucket "$OUTPUT_BUCKET" \
  --prefix "$MANIFEST_KEY" \
  --max-keys 1 \
  --region "$AWS_REGION" \
  --query "Contents[?Key=='${MANIFEST_KEY}'].Key | [0]" \
  --output text)"
if [[ "$MANIFEST_FOUND" != "$MANIFEST_KEY" ]]; then
  echo "ERROR: Refusing to validate before the partition manifest exists: ${MANIFEST_URI}" >&2
  exit 1
fi

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
aws s3 cp "$MANIFEST_URI" - --region "$AWS_REGION"
