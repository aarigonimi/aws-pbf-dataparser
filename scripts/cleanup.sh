#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/infra"

echo "This destroys Terraform-managed infrastructure after the plan is reviewed."
echo "It does not delete S3 objects, versions, delete markers or ECR images."
terraform -chdir="$TERRAFORM_DIR" init -input=false
terraform -chdir="$TERRAFORM_DIR" plan -destroy -input=false

read -r -p 'Type DESTROY INFRASTRUCTURE to continue: ' confirmation
if [[ "$confirmation" != "DESTROY INFRASTRUCTURE" ]]; then
  echo "Cleanup cancelled."
  exit 1
fi

terraform -chdir="$TERRAFORM_DIR" destroy
