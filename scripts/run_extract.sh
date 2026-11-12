#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-monaco}"
YMD="${YMD:-20261108}"
GEOFABRIK_AREA="${GEOFABRIK_AREA:-europe}"
SOURCE_URL="${SOURCE_URL:-}"
DOWNLOAD_DIR="${DOWNLOAD_DIR:-data/geofabrik}"
FORCE_DOWNLOAD="${FORCE_DOWNLOAD:-false}"
INCLUDE_WAY_GEOMETRY="${INCLUDE_WAY_GEOMETRY:-true}"
OVERWRITE="${OVERWRITE:-error}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/env.sh
source "${PROJECT_ROOT}/scripts/env.sh"

if [[ ! "$YMD" =~ ^[0-9]{8}$ ]]; then
  echo "YMD must be formatted YYYYMMDD, got ${YMD}" >&2
  exit 2
fi

YYMMDD="${YMD:2:6}"
LOCAL_FILE="${DOWNLOAD_DIR}/${REGION}-${YYMMDD}.osm.pbf"
RAW_KEY="region=${REGION}/${YMD:0:4}/${YMD:4:2}/${YMD:6:2}/${REGION}-${YMD}.osm.pbf"

if [[ -z "$SOURCE_URL" ]]; then
  SOURCE_URL="https://download.geofabrik.de/${GEOFABRIK_AREA}/${REGION}-${YYMMDD}.osm.pbf"
fi

mkdir -p "$DOWNLOAD_DIR"
if [[ -s "$LOCAL_FILE" && "$FORCE_DOWNLOAD" != "true" ]]; then
  echo "Reusing cached ${LOCAL_FILE} (set FORCE_DOWNLOAD=true or delete it to download again)."
else
  echo "Downloading ${SOURCE_URL}"
  curl --fail --location --show-error --retry 3 --output "$LOCAL_FILE" "$SOURCE_URL"
fi

if [[ ! -s "$LOCAL_FILE" ]]; then
  echo "Downloaded extract is empty: ${LOCAL_FILE}" >&2
  exit 3
fi

echo "Uploading s3://${RAW_BUCKET}/${RAW_KEY}"
aws s3 cp "$LOCAL_FILE" "s3://${RAW_BUCKET}/${RAW_KEY}" --region "$AWS_REGION"

if [[ "$S3_TRIGGER_ENABLED" == "true" ]]; then
  echo "S3 trigger is enabled: the upload above started the Batch job."
else
  echo "S3 trigger is disabled: submitting the manual job definition."
  RAW_BUCKET="$RAW_BUCKET" OUTPUT_BUCKET="$OUTPUT_BUCKET" \
    JOB_QUEUE="$JOB_QUEUE" JOB_DEFINITION="$JOB_DEFINITION" AWS_REGION="$AWS_REGION" \
    REGION_NAME="$REGION" YMD="$YMD" RAW_KEY="$RAW_KEY" \
    INCLUDE_WAY_GEOMETRY="$INCLUDE_WAY_GEOMETRY" OVERWRITE="$OVERWRITE" \
    "${PROJECT_ROOT}/scripts/submit_job.sh"
fi
echo "Follow the run with: make logs"
echo "Then verify with:   make verify REGION=${REGION} YMD=${YMD}"
