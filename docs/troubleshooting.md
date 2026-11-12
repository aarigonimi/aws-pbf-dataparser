# Troubleshooting

## Batch cannot pull the image from ECR

Check each Batch attempt's `statusReason`. The observed failure in this project
was an ECR `GetAuthorizationToken` connection timeout before the application
container started. The Terraform fix provisions ECR API and ECR DKR interface
endpoints, CloudWatch Logs interface endpoints, an S3 gateway endpoint, endpoint
security-group ingress on TCP 443 from the VPC CIDR, and pins
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

Publication is serialized per partition with an S3 conditional-write claim:
before doing any work a run writes `region=<region>/<yyyy>/<mm>/<dd>/_lock.json`
with `If-None-Match: *`, and only one concurrent run can acquire it. The
losing runs fail fast with exit code 4 (`OutputConflictError`) and leave
the winner's output untouched. This replaced the pre-claim behavior where
two jobs could both pass the `OVERWRITE=error` check and interleave their
copies (observed during the Quebec run). `scripts/submit_job.sh` still
refuses to submit while a non-terminal job named `osm-<region>-*` exists
in the queue; set `ALLOW_CONCURRENT=true` only when you have ruled out
overlap.

The claim is not a lease. If the claim holder is terminated without
cleanup (host failure, job cancellation mid-run), the claim object
remains and later runs fail with exit code 4 pointing at it. After
confirming no run is active, recover with
`OVERWRITE=replace` (`REGION_NAME=... YMD=... OVERWRITE=replace ./scripts/submit_job.sh`),
which force-removes the stale claim before reclaiming.

## S3 access denied

Confirm the job definition uses the application job role, not the execution
role. The job role reads objects under the raw bucket and writes/lists/deletes
curated objects. The execution role retrieves the image and writes container
logs. Check bucket name, region, object key, IAM policy and any organization
SCP or permission boundary.

S3 authorization codes map to exit code 5 (`AccessDeniedError`) and are not
retried. This classification covers downloads, metadata checks (including the
head-based `exists()` probe and the conditional claim write), listing, uploads
and copies; botocore transport errors, throttling and server failures remain
retryable. The claim write itself only needs `s3:PutObject` on the curated
prefix, which the job policy already grants.

## Output conflict

`OVERWRITE=error` returns exit code 4 when a manifest, stray output or another
run's partition claim exists. Use `skip` only when the existing manifest
denotes the desired completed output. `replace` removes stale keys *before*
publishing new data and copies the new manifest last, so a failed replacement
leaves no manifest rather than a manifest over incomplete data; do not query
the partition until a new manifest exists. `replace` also force-removes a
stale claim from a terminated run — confirm no run is active first.

## Athena cannot resolve projected partitions

The Terraform-defined `osm_curated` table uses injected partition projection
for `region`, `year`, `month` and `day`. Every query must include equality
predicates for all four (zero-padded `month`/`day` strings),
for example `WHERE region = 'quebec' AND year = '2026' AND month = '11' AND day = '08'`. Check the Glue table
parameters, its S3 location template, and that the query uses the configured
database. This table was deployed and its Athena counts matched the manifest
for both the historical Quebec partition and the 2026-11-10 Monaco tutorial
run. Query only after the final `_manifest.json`
exists; Athena does not use the manifest as a gate.

## Batch compute environment fails with "Security group ids are required"

The AWS Batch API requires at least one security group ID for `FARGATE`
compute environments and Fargate does not support launch templates. Older
versions of this repository passed no security group for Fargate, which
fails at CE creation with `ClientException: Security group ids are
required` even though the plan validates. The configuration now creates
`<project>-batch-fargate` and attaches it whenever
`batch_compute_type = "FARGATE"`.

A related API limitation: an in-place CE update cannot *clear* an existing
`securityGroupIds` list — the API rejects an empty list with "At least one
compute-resources attribute is required" and silently keeps the old groups,
producing drift. To remove security groups from an existing CE, replace the
resource: taint both the queue and the CE
(`terraform -chdir=infra taint aws_batch_job_queue.osm_queue &&
terraform -chdir=infra taint aws_batch_compute_environment.osm_compute`)
so the next apply destroys and recreates them in dependency order. Jobs do not
run while both are down, so drain the queue first.

## Security group deletion blocked by "dependency" (DependencyViolation)

EC2 refuses to delete a security group that another security group's rules
reference. During the crawler-to-projected-table migration the endpoint
security group's ingress referenced the Batch task security group, which
blocked destroying that task group. The endpoints group now allows HTTPS from
the VPC CIDR instead, so no SG-to-SG references couple the stacks. If you
still hit this, apply the referencing group first with
`terraform apply -target=aws_security_group.<referencing>` to rewrite its
rules, then destroy the referenced group.

## Terraform apply times out mid-run

Batch compute-environment and job-queue changes take minutes each, and a
migration touching the CE, queue and Glue resources can exceed a 15-minute
wrapper timeout. If an apply is killed mid-run the state is partial but
usable: run `terraform plan` immediately to see what remains, then re-apply.
Use a timeout of 30 minutes or more for stack migrations, and never resume
from the checked-in `tfplan` artifact.

## Terraform reports an existing resource or state drift

Stop before applying. Do not apply the checked-in or stale `tfplan`. Review
[Terraform recovery](TERRAFORM_RECOVERY.md), back up state before state changes,
and compare a fresh plan with the actual resources.
