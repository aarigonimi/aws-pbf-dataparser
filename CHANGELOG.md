# Changelog

## Unreleased

- Serialize publication per region/ymd partition with an S3 conditional-write
  claim (`_lock.json`): concurrent runs fail fast with exit code 4 instead of
  interleaving output; `OVERWRITE=replace` force-removes a stale claim.
- In `OVERWRITE=replace`, delete stale objects before publishing new data so a
  failed run leaves no manifest referencing missing files.
- Validate `YMD` (real calendar date) and `OUTPUT_PREFIX` (no `.`/`..` or
  unsafe segments) and derive `RUN_ID` from the Batch job ID and attempt
  number, replacing the static `batch-run` default from the job definition.
- Use a head-based `exists()` probe and add conditional `PutObject`
  (`If-None-Match: *`) support.
- Enforce the exact `MAX_RECORDS_PER_FILE` cap on part files between
  row-group boundaries.
- Pin the `python:3.12-slim` base image by manifest digest.
- Fix the Fargate-mode Terraform plan failure (VPC endpoint security group
  referenced the EC2-only Batch security group), set the Batch service role
  only for EC2 compute, and reject `.`/`..` segments in the `output_prefix`
  variable validation.
- Repair the Terraform CI workflow's broken `terraform validate -var` step
  and bump `actions/checkout` v4 to v6.
- Preserve verified Quebec and already-existing London measurements with
  provenance and account-specific S3/ECR identifiers removed.
- Correct Parquet file rotation so the configured record cap is honored between
  row-group boundaries.
- Make Docker image push require an explicit tag and use the project root as
  its build context.
- Add repeatable deployment, execution, validation and cleanup instructions.
- Add separate Python and Terraform GitHub Actions checks.
- Clarify overwrite, retry, partition concurrency, endpoint and cleanup limits.
