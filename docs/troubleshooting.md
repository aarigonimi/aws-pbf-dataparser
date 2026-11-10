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

Publication is serialized per partition with an S3 conditional-write claim:
before doing any work a run writes `region=<region>/ymd=<ymd>/_lock.json`
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
