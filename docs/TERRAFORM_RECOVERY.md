# Terraform state and recovery runbook

This folder contains **live local state**. Treat it as production data.

Current artifacts (all gitignored):

- `terraform.tfstate` - current state.
- `terraform.tfstate.backup` - previous state written by Terraform.
- `terraform.tfstate.1794026801.backup` - older timestamped backup.
- `tfplan` - a stale saved plan. **Do not apply it.**
- `.terraform/` and `.terraform.lock.hcl` - provider cache and lock file.

## Golden rules

1. Do not delete or overwrite `terraform.tfstate` to "fix" a problem.
2. Do not run `terraform apply tfplan` on the saved plan. Regenerate a plan from
   the current configuration and state.
3. Back up state before any state-changing command (`state mv`, `state rm`,
   `import`, backend migration).
4. Use one operator at a time. Local state has no locking.
5. Never commit state, backups, plans or `.env` files.
6. `terraform import` changes only state; it does not create or modify AWS
   resources.
7. Keep the `random_id.bucket_suffix` state. It preserves the bucket names
   (`osm-data-raw-<hex>`, `osm-data-curated-<hex>`) across applies.

## Inspect before changing anything

```bash
cd infrastructure
terraform state list
terraform state show aws_batch_job_definition.osm_job
terraform state show random_id.bucket_suffix
terraform output
```

Read-only AWS checks are fine, for example:

```bash
aws s3api head-bucket --bucket "$(terraform output -raw raw_bucket_name)"
aws batch describe-job-queues --job-queues "$(terraform output -raw batch_job_queue_name)"
```

## Safe change workflow

```bash
cp terraform.tfstate "terraform.tfstate.$(date +%Y%m%d%H%M%S).manual-backup"
terraform init -backend=false -input=false
terraform fmt -check -recursive
terraform validate
terraform plan -out=tfplan.new
# Review every destroy/replace entry.
# terraform apply tfplan.new   # only when you intend to change AWS
```

Delete `tfplan.new` after use. The old `tfplan` should not be reused.

## Drift or "resource already exists"

The module now manages resources that may already exist from earlier runs or
manual work: the Batch log group, S3 versioning/encryption/lifecycle policies,
bucket policies, ECR lifecycle policy, and the execution-role log policy.
If a plan fails with "already exists", import the existing object.

Use names/ARNs from `terraform output` or the AWS console; placeholders below:

```bash
# CloudWatch log group
terraform import aws_cloudwatch_log_group.batch /aws/batch/osm-pbf-data-lake

# S3 bucket settings (repeat for raw and curated)
terraform import aws_s3_bucket_versioning.raw <raw-bucket-name>
terraform import aws_s3_bucket_versioning.curated <curated-bucket-name>
terraform import aws_s3_bucket_server_side_encryption_configuration.raw <raw-bucket-name>
terraform import aws_s3_bucket_server_side_encryption_configuration.curated <curated-bucket-name>
terraform import aws_s3_bucket_lifecycle_configuration.raw <raw-bucket-name>
terraform import aws_s3_bucket_lifecycle_configuration.curated <curated-bucket-name>
terraform import aws_s3_bucket_policy.raw_tls_only <raw-bucket-name>
terraform import aws_s3_bucket_policy.curated_tls_only <curated-bucket-name>

# ECR lifecycle policy
terraform import aws_ecr_lifecycle_policy.batch osm-pbf-batch

# IAM policy and attachment
terraform import aws_iam_policy.batch_execution_logs <policy-arn>
terraform import aws_iam_role_policy_attachment.batch_execution_logs osm-pbf-data-lake-batch-execution-role/<policy-arn>

# Existing stack objects, if state is missing
terraform import aws_athena_workgroup.osm_workgroup osm-pbf-workgroup
terraform import aws_batch_compute_environment.osm_compute osm-pbf-data-lake-compute
terraform import aws_batch_job_definition.osm_job osm-pbf-data-lake-job
terraform import aws_batch_job_queue.osm_queue osm-pbf-data-lake-job-queue
terraform import aws_ecr_repository.batch osm-pbf-batch
terraform import aws_glue_catalog_database.osm_catalog osm_catalog
terraform import aws_glue_crawler.osm_crawler osm-pbf-data-lake-crawler
terraform import aws_security_group.batch <security-group-id>
terraform import aws_s3_bucket.raw <raw-bucket-name>
terraform import aws_s3_bucket.curated <curated-bucket-name>
```

Import syntax can differ by resource/provider version. If an import ID is
rejected, check the resource documentation for the current provider and stop
before making changes.

## Recovering from a bad state write

1. Stop all Terraform runs.
2. Make a copy of the current broken state (do not delete it).
3. Inspect the backups: `terraform.tfstate.backup` is the previous state, and
   the timestamped `.backup` is older.
4. Restore only after comparing:
   ```bash
   cp terraform.tfstate "terraform.tfstate.broken.$(date +%Y%m%d%H%M%S)"
   cp terraform.tfstate.backup terraform.tfstate
   terraform state list
   terraform plan -refresh=false
   ```
5. Do not apply during recovery until the plan matches expectations. AWS
   resources are not changed by `state list`/`plan`.

If the state is lost entirely, do not re-apply blindly: that would create new
buckets and roles and may rename the random suffix. Import the existing
resources first, starting with `random_id.bucket_suffix` and the S3 buckets,
then the rest.

## Remote backend migration

Local state is for a single operator. For team use:

```bash
cp backend.tf.example backend.tf
# Fill in bucket, key, region, and optional DynamoDB lock table.
terraform init -migrate-state
```

Terraform will ask to copy the local state to the backend. Back up
`terraform.tfstate` first. After migration, commit `backend.tf` (without
credentials) and keep the state bucket private, versioned and encrypted.

## What not to do

- Do not run `terraform destroy` to reset.
- Do not delete `.terraform.lock.hcl`; it pins provider versions.
- Do not apply the checked-in `tfplan`.
- Do not run `terraform init -reconfigure` against a different backend without
  a state migration plan.
