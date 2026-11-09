# Changelog

## Unreleased

- Preserve verified Quebec and already-existing London measurements with
  provenance and account-specific S3/ECR identifiers removed.
- Correct Parquet file rotation so the configured record cap is honored between
  row-group boundaries.
- Make Docker image push require an explicit tag and use the project root as
  its build context.
- Add repeatable deployment, execution, validation and cleanup instructions.
- Add separate Python and Terraform GitHub Actions checks.
- Clarify overwrite, retry, partition concurrency, endpoint and cleanup limits.
