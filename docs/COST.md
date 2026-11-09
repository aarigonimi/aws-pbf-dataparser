# Cost notes

Prices change and vary by region. Treat the numbers below as illustrative
formulas, not quotes. Check the current AWS pricing pages for your region.

## Main cost drivers

| Driver | Billing dimension | Notes |
| --- | --- | --- |
| AWS Batch on Fargate | vCPU-hour + GiB-hour | Default 2 vCPU / 8 GiB per job |
| Fargate ephemeral storage | GiB-hour above the 20 GiB default | Terraform default is 100 GiB |
| EC2/Spot (optional) | Instance-hour or Spot price | Only when `batch_compute_type = EC2` |
| S3 storage | GB-month | Raw + curated + non-current versions |
| S3 requests | Per 1,000 requests | Uploads, copies, lists, Athena results |
| Data transfer | GB | Cross-region or NAT egress; same-region S3 access is typically free |
| NAT gateway (optional) | Hour + GB processed | Not created by this module; needed for private subnets without endpoints |
| CloudWatch Logs | Ingestion GB + storage | Retention is configured |
| Glue crawler | DPU-hour | On demand, not scheduled |
| Athena | TB scanned | Partition/column pruning matters |
| ECR | GB-month | Lifecycle policy expires old images |

## Estimating Fargate cost

Use the AWS Fargate rates for the selected region and date. The compute
estimate is the requested vCPU-hours multiplied by the vCPU rate, plus
requested memory GiB-hours multiplied by the memory rate, plus billable
ephemeral-storage GiB-hours above the included amount. Add S3 storage and
requests, CloudWatch Logs, Glue, Athena, and any data transfer separately.
This repository does not include a measured Quebec or London cost. Use Cost
Explorer or billing exports to capture actual charges; do not infer them from
wall-clock duration alone.

## Levers

- Right-size `batch_vcpus` / `batch_memory_mb`. More memory is not always
  faster; PyOsmium is streaming and bounded by disk and CPU.
- Use `snappy` or `zstd` and tune `MAX_RECORDS_PER_FILE` /
  `ROW_GROUP_SIZE`. More, smaller files increase S3 request and Athena planning
  cost; fewer, larger files can increase per-task memory.
- Enable S3 lifecycle expiry for raw extracts (`raw_retention_days`),
  abandoned staging (`staging_retention_days`) and non-current curated versions
  (`curated_noncurrent_version_days`).
- Keep the ECR lifecycle policy; avoid unbounded tagged images.
- Use `OVERWRITE=skip` in retries so completed partitions do not reprocess.
- Use partition pruning (`region`, `ymd`) in Athena and set
  `athena_bytes_scanned_cutoff`.
- Run the Glue crawler on demand or on a schedule that matches publishing, not
  continuously.
- For large, interruption-tolerant batches, use EC2 Spot
  (`batch_compute_type = EC2`, `batch_use_spot = true`) and configure
  `spot_iam_fleet_role_arn`. Spot savings vary and can be interrupted; the job
  retries on host interruption.
- Fargate mode already provisions ECR/Logs interface endpoints and an S3
  gateway endpoint, avoiding NAT gateway hours; interface endpoint hours are
  billed per AZ.
- Set CloudWatch Logs retention (`log_retention_days`) to the shortest period
  that still supports debugging.

## Storage sizing rule of thumb

Provision ephemeral storage for at least:

```text
PBF size
+ expected Parquet output
+ node-location index (if INCLUDE_WAY_GEOMETRY=true)
+ headroom for temporary row groups
```

Parquet output size depends on tag density and compression; measure one region
before running the full plan.
