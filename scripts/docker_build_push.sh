#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ECR_REPOSITORY_URL="${ECR_REPOSITORY_URL:?Set ECR_REPOSITORY_URL (terraform output ecr_repository_url)}"
AWS_REGION="${AWS_REGION:-us-east-1}"
PLATFORM="${PLATFORM:-linux/amd64}"
TAG="${TAG:?Set TAG to an immutable image tag, such as the source Git commit SHA}"

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
echo "Set infrastructure variable image_tag=${TAG} and apply a reviewed Terraform plan to register that image."
