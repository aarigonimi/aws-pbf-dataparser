#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${ECR_REPOSITORY_URL:-}" || -z "${AWS_REGION:-}" ]]; then
  # Load ECR_REPOSITORY_URL and AWS_REGION from Terraform outputs.
  # shellcheck source=scripts/env.sh
  source "${PROJECT_ROOT}/scripts/env.sh"
fi
ECR_REPOSITORY_URL="${ECR_REPOSITORY_URL:?Set ECR_REPOSITORY_URL (terraform output ecr_repository_url)}"
PLATFORM="${PLATFORM:-linux/amd64}"
TAG="${TAG:-$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null || echo local)}"

if [[ -n "$(git -C "$PROJECT_ROOT" status --porcelain 2>/dev/null)" ]]; then
  echo "Warning: the working tree has uncommitted changes." >&2
  echo "The image will be tagged with the last commit, which does not contain them." >&2
fi

REGISTRY="${ECR_REPOSITORY_URL%%/*}"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

docker buildx build \
  --platform "$PLATFORM" \
  --file "$PROJECT_ROOT/Dockerfile" \
  --tag "${ECR_REPOSITORY_URL}:${TAG}" \
  --push \
  "$PROJECT_ROOT"

echo "Pushed ${ECR_REPOSITORY_URL}:${TAG}"
aws ecr describe-images \
  --repository-name "${ECR_REPOSITORY_URL##*/}" \
  --image-ids "imageTag=${TAG}" \
  --region "$AWS_REGION" \
  --query 'imageDetails[0].imageDigest' \
  --output text
echo "Set the Terraform variable image_tag=${TAG} and apply a reviewed Terraform plan to register that image."
