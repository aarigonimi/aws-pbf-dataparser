# Changelog

## Unreleased

- Rename the Terraform directory from `infrastructure/` to `infra/` and
  update every script, doc, CI workflow and test that references it.
- Split the Batch job definition into a stable manual definition and an event
  definition the trigger targets by ARN prefix (always the latest revision);
  move the existing definition with a Terraform `moved` block.
- Make the raw-input key strict: `parse_raw_key()` accepts only
  `region=<name>/<yyyy>/<mm>/<dd>/<file>.osm.pbf`, `env_for_raw_key()` merges
  the key-derived `REGION_NAME`/`YMD` into the job environment, and the
  `default_region` fallback is removed — a malformed key fails with exit code 3.
- Rename `enable_s3_trigger` to `s3_trigger_enabled`, remove
  `trigger_overwrite` (the single `overwrite` variable is baked into both job
  definitions) and add `network_access` (`vpc_endpoints` default or `public_ip`
  addressing without endpoints) plus `include_way_geometry = true` and a
  10 GiB `athena_bytes_scanned_cutoff` as defaults.
- Make the EventBridge rule filter on the `.osm.pbf` suffix only, pass the
  object key through an input transformer into the `raw_key` Batch parameter,
  and scope the submit role to `batch:SubmitJob` on the queue, the event job
  definition and its revisions.
- Derive `RUN_ID` inside the job from the Batch job ID and attempt number;
  `submit_job.sh` no longer accepts one and names jobs
  `osm-<region>-<ymd>`.
- Add Make targets (`install`, `deploy`, `build`, `run`, `logs`, `verify`,
  `destroy`) plus `scripts/env.sh` (Terraform-output environment),
  `scripts/run_extract.sh` (dated Geofabrik download, cache and upload) and
  `scripts/logs.sh`; `docker_build_push.sh` now loads the repository URL from
  Terraform outputs and defaults its tag to the current commit SHA.
- Rewrite the real-estate SQL as numbered files (01–05): POI table, external
  synthetic-listings table with `sample_listings.csv` (eight listings),
  presence-based scores, marketing views and a 0.01° coverage grid with a
  director map view.
- Remove the local-validation tooling (`src/local.py`, `run_local.sh`,
  `validate_local_output.sh`, its tests, doc and benchmark record); the
  in-repo end-to-end test still exercises the pipeline against an in-memory
  S3 fake.
- Add the architecture figure (`assets/images/architecture.svg` with a PNG
  render) and rework the README quickstart, tutorial and docs (trigger,
  deployment, execution, architecture, real-estate, cost, validation, cleanup)
  for the renamed variables, the new SQL and the Make targets.
- Change the S3 partition layout from `region=<region>/ymd=<YYYYMMDD>/` to
  `region=<region>/<yyyy>/<mm>/<dd>/`: pipeline output keys, the lock and
  manifest paths, raw-input key derivation (legacy `ymd=` keys still parse),
  `submit_job.sh`/`validate_output.sh` path construction, and the Glue table
  partition keys (`region`, `year`, `month`, `day`, `entity`, all injected
  except the entity enum). Existing S3 data was relocated with `aws s3 mv` on
  2026-11-10; historical manifests still record their run-time prefix.
  Verified in AWS after the move: Athena counts for Quebec, London and Monaco
  matched the manifests, and Monaco was republished in the new layout by the
  current image with identical counts.
- Fix the Fargate Batch compute environment: the Batch API requires
  `securityGroupIds` for FARGATE compute environments, so CE creation failed
  with `ClientException: Security group ids are required`; add a dedicated
  `<project>-batch-fargate` security group for Fargate mode.
- Drop the endpoints security group's SG-to-SG ingress reference in favor of
  VPC-CIDR ingress so security-group deletion is not blocked by
  `DependencyViolation` during stack changes.
- Replace the Glue crawler with a partition-projected `osm_curated` table and
  deploy it: Athena entity counts matched the manifest for both the
  historical Quebec partition and the Monaco tutorial run.
- Add a Monaco tutorial-scale benchmark record (full deploy-run-query cycle,
  digest-pinned image, all three overwrite modes verified in AWS) to
  `docs/benchmarks/`.
- Mark `scripts/docker_build_push.sh`, `submit_job.sh` and
  `generate_sample_pbf.py` executable so the documented `./scripts/...`
  invocations work from a fresh clone.
- Rewrite the README as an end-to-end tutorial (prerequisites through
  cleanup) and align `docs/execution.md`, `docs/validation.md` and
  `docs/cleanup.md` with it, including CLI-based Glue/Athena verification.
- Document Batch CE/SG recovery procedures (in-place update cannot clear
  `securityGroupIds`; taint-and-recreate queue+CE; targeted applies for
  SG-reference blocks; use long apply timeouts) in `docs/troubleshooting.md`.
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
