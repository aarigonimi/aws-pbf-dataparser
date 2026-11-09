# Infrastructure and image deployment

## Prerequisites

- An AWS account and AWS CLI v2 with an authenticated deployment identity.
- Terraform 1.6 or later.
- Docker with Buildx support.
- Python 3.11 or later for local checks; Python 3.12 is used by the container.
- A region that supports the selected Batch/Fargate configuration.

For an IAM Identity Center profile, configure and log in with the AWS CLI, then
select it for the commands below:

```bash
aws configure sso
aws sso login --profile YOUR_PROFILE
export AWS_PROFILE="YOUR_PROFILE"
aws sts get-caller-identity
```

Configure credentials through an approved AWS profile or IAM Identity Center;
do not place access keys in `.env`, Terraform variables or shell scripts. The
deployment identity needs permission to create the project's S3, ECR, IAM,
Batch, EC2 networking/security-group/endpoint, CloudWatch, Glue and Athena
resources, including `iam:PassRole` for the roles it creates. Organizations
may require an administrator to approve IAM policy creation.

## Configure and validate Terraform

Run from the repository root:

```bash
cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars
```

Edit `infrastructure/terraform.tfvars` for the region, compute and storage
settings. This file is ignored by Git. Choose an image tag once; use the same
tag for `image_tag` and the image push command. A unique immutable tag is
recommended. Keep the Terraform provider lock file under version control.

```bash
terraform -chdir=infrastructure init
terraform -chdir=infrastructure fmt -check -recursive
terraform -chdir=infrastructure validate
terraform -chdir=infrastructure plan -out=tfplan.new
terraform -chdir=infrastructure show tfplan.new
```

Inspect the complete plan before deployment. When you intend to provision the
stack, apply the reviewed plan:

```bash
terraform -chdir=infrastructure apply tfplan.new
```

This command is documentation only; no apply was run for this repository
review. For team use, configure the remote backend in
`infrastructure/backend.tf.example` before initializing. The default local
state is sensitive and must not be committed. Never apply the pre-existing
`tfplan` artifact; see [Terraform recovery](TERRAFORM_RECOVERY.md).

Terraform creates:

- Separate raw and curated S3 buckets with public access blocked, SSE-S3,
  versioning and lifecycle rules.
- ECR repository and image retention/scanning configuration.
- Batch compute environment, queue, job definition, roles and log group.
- VPC security group and, for Fargate, ECR/Logs interface endpoints and an S3
  gateway endpoint. The stack uses an existing VPC and does not create a NAT
  gateway or subnets.
- Glue database/crawler and an Athena workgroup with a results prefix and an
  optional scan cutoff. The cutoff defaults to disabled (`0`); set a nonzero
  `athena_bytes_scanned_cutoff` to enforce one.

Inspect outputs:

```bash
terraform -chdir=infrastructure output
```

## Build and push the image

Provisioning creates ECR first. Then push the exact image tag configured in
`terraform.tfvars`:

```bash
export ECR_REPOSITORY_URL="$(terraform -chdir=infrastructure output -raw ecr_repository_url)"
export AWS_REGION="us-east-1"
export TAG="v0.1.0" # Must equal Terraform's image_tag value.
./scripts/docker_build_push.sh
```

The script logs in through the AWS CLI and builds the root `Dockerfile` with a
Linux/amd64 target. The Docker build context is the repository root. The job
definition can reference a tag before it has been pushed, but do not submit a
job until the push succeeds. For a later image, push a new tag and update
`image_tag` through a reviewed Terraform plan to register a new job definition
revision.

The example base image and OS package repositories are not pinned by digest;
the Python application dependencies are version-pinned. For bit-for-bit image
reproducibility, pin the base image digest and OS package snapshot.
