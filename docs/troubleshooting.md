# Troubleshooting

## Batch cannot pull the image from ECR

Check each Batch attempt's `statusReason`. The observed failure in this project
was an ECR `GetAuthorizationToken` connection timeout before the application
container started. The Terraform fix provisions ECR API and ECR DKR interface
endpoints, CloudWatch Logs interface endpoints, an S3 gateway endpoint, endpoint
security-group ingress on TCP 443 from the Batch security group, and pins
Fargate to the subnet hosting the interface endpoints.

Verify endpoint state is `available`, private DNS is enabled for interface
endpoints, task and endpoint security groups allow the connection, the subnet
route table reaches S3, and the Batch execution role can pull from ECR. For a
custom VPC, the S3 gateway endpoint must be associated with the Fargate subnet's
route table. The job definition retries `ResourceInitializationError*` status
reasons within the retry limit; the application may have no CloudWatch log
stream for an image-pull failure.

## Batch retry behavior

The retry strategy retries exit code 75 (`TransientError`/`JobCancelled`),
`Host EC2*` status reasons and `ResourceInitializationError*` status reasons,
then exits on every other exit code. Without the final `EXIT` rule AWS Batch
retries any failure that matches no rule, which would re-run configuration
(2), input (3) and output-conflict (4) failures that cannot succeed.

## Two jobs published the same partition

The pipeline checks for existing outputs before processing, but there is no
distributed lock. Two jobs submitted for the same region/date both pass the
`OVERWRITE=error` check and both publish; the last manifest copy wins. This
happened during the Quebec run. `scripts/submit_job.sh` refuses to submit while
a non-terminal job named `osm-<region>-*` exists in the queue; set
`ALLOW_CONCURRENT=true` only when you have ruled out overlap.

## S3 access denied

Confirm the job definition uses the application job role, not the execution
role. The job role reads objects under the raw bucket and writes/lists/deletes
curated objects. The execution role retrieves the image and writes container
logs. Check bucket name, region, object key, IAM policy and any organization
SCP or permission boundary.

## Output conflict

`OVERWRITE=error` returns exit code 4 when a manifest or stray output exists.
Use `skip` only when the existing manifest denotes the desired completed
output. `replace` is not atomic; inspect and preserve the existing manifest and
S3 versions before using it.

## Athena cannot resolve projected partitions

The Terraform-defined `osm_curated` table uses injected partition projection
for `region` and `ymd`. Every query must include equality predicates for both,
for example `WHERE region = 'quebec' AND ymd = '20261108'`. Check the Glue table
parameters, its S3 location template, and that the query uses the configured
database. This table change is implemented in the repository but has not been
deployed or verified in AWS. Query only after the final `_manifest.json`
exists; Athena does not use the manifest as a gate.

## Terraform reports an existing resource or state drift

Stop before applying. Do not apply the checked-in or stale `tfplan`. Review
[Terraform recovery](TERRAFORM_RECOVERY.md), back up state before state changes,
and compare a fresh plan with the actual resources.
