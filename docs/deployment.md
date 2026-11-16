# Infrastructure and image deployment

## Prerequisites

- An AWS account and AWS CLI v2 with an authenticated deployment identity.
- Terraform 1.10 or later.
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
Batch, EventBridge, EC2 networking/security-group/endpoint, CloudWatch, Glue
and Athena resources, including `iam:PassRole` for the roles it creates.
Organizations may require an administrator to approve IAM policy creation.

## Configure and validate Terraform

Run from the repository root:

```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars
```

Edit `infra/terraform.tfvars` for the region, compute and storage
settings. This file is ignored by Git. Set `image_tag` to a full commit SHA;
`latest` is rejected and ECR tags are immutable by default. After pushing,
optionally set `image_digest` to pin the job definition to `repository@sha256:...`.
Keep the provider lock file under version control.

The trigger and networking are controlled by three variables:

```hcl
s3_trigger_enabled = true    # false deploys only the manual submission path
network_access     = "vpc_endpoints" # or "public_ip" (tasks get a public IP,
                                     # no endpoints, subnet needs internet)
overwrite          = "error" # OVERWRITE baked into the job definitions
```

Triggered jobs derive the region and date strictly from the `region=<name>`
segments of the uploaded key — a key outside the layout fails fast with exit
code 3 — so there is no fallback region. `include_way_geometry = true`
(default) makes triggered jobs reconstruct way geometry; otherwise ways have
no coordinates. Changing these values requires a reviewed plan and a new
job-definition revision. See [the trigger guide](trigger.md).

```bash
terraform -chdir=infra init
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
terraform -chdir=infra plan -out=tfplan.new
terraform -chdir=infra show tfplan.new
```

Inspect the complete plan before deployment. When you intend to provision the
stack, apply the reviewed plan:

```bash
terraform -chdir=infra apply tfplan.new
```

This command is documentation only; no apply was run for this repository
review. For team use, configure the remote backend in
`infra/backend.tf.example` before initializing. The default local
state is sensitive and must not be committed. Never apply the pre-existing
`tfplan` artifact; see [Terraform recovery](TERRAFORM_RECOVERY.md).

Terraform creates:

- Separate raw and curated S3 buckets with public access blocked, SSE-S3,
  versioning and lifecycle rules.
- ECR repository and image retention/scanning configuration.
- Batch compute environment, queue, job definition, roles and log group.
- Optional S3 EventBridge notification, EventBridge rule/target and submit role
  when `s3_trigger_enabled = true`.
- VPC security groups (EC2 workers and, for Fargate, task ENIs, which the
  Batch API requires) and, for Fargate in the default `vpc_endpoints` mode,
  ECR/Logs interface endpoints and an S3 gateway endpoint. The stack uses an
  existing VPC and does not create a NAT gateway or subnets. In `public_ip`
  mode no endpoints are created and tasks get public addressing instead.
- Glue database and partition-projected Parquet table, plus an Athena workgroup with a results prefix and a
  per-query scan cutoff (`athena_bytes_scanned_cutoff`, default 10 GiB; `0`
  disables it).

The projected table replaces the previous crawler configuration in this
repository. It was deployed on 2026-11-10 during the migration that retired
the crawler stack, and queried via Athena in the Monaco tutorial validation
(see [benchmarks](benchmarks/README.md)). For an
existing stack, inspect the Terraform plan for crawler removal and creation of
`osm_curated` before applying it; the historical benchmark records describe the
earlier catalog setup.

Inspect outputs:

```bash
terraform -chdir=infra output
```

## Build and push the image

Provisioning creates ECR first. Then push the exact image tag configured in
`terraform.tfvars` — or run `make build`, which loads
`ECR_REPOSITORY_URL` and `AWS_REGION` from Terraform outputs
([scripts/env.sh](../scripts/env.sh)) and defaults `TAG` to the current
commit SHA:

```bash
make build   # or:
export ECR_REPOSITORY_URL="$(terraform -chdir=infra output -raw ecr_repository_url)"
export AWS_REGION="us-east-1"
export TAG="$(git rev-parse HEAD)" # Must equal Terraform's image_tag value.
./scripts/docker_build_push.sh
```

The script logs in through the AWS CLI and builds the root `Dockerfile` with a
Linux/amd64 target. The Docker build context is the repository root. The job
definition can reference a tag before it has been pushed, but do not submit a
job until the push succeeds. For a later image, push a new tag and update
`image_tag` through a reviewed Terraform plan to register a new job definition
revision. The manifest records configured digest and git SHA when available.
Without an explicit digest, its digest field is null because AWS does not pass
the resolved image digest into the container environment.

`make deploy` passes `-var image_tag=$(git rev-parse HEAD)` automatically.
Note that an `image_digest` pinned in `terraform.tfvars` takes precedence over
the tag in `locals.image_reference`, so a pinned stack keeps running the
pinned digest regardless of the `-var` value.

The example base image and OS package repositories are not pinned by digest;
the Python application dependencies are version-pinned. For bit-for-bit image
reproducibility, pin the base image digest and OS package snapshot.
