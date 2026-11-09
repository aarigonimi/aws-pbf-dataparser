# Architecture

## Components

| Component | Responsibility |
| --- | --- |
| S3 raw bucket | Versioned source extracts under `region=<region>/ymd=<YYYYMMDD>/`, with lifecycle expiry |
| AWS Batch compute environment | Fargate (default) or EC2/Spot workers |
| Batch job definition | Container image, vCPU/memory, env defaults, retries, timeout, log config |
| Batch job queue | Schedules jobs onto the compute environment |
| S3 curated bucket | Staging, final Parquet, manifests, Athena results |
| Glue database + projected table | Explicit Parquet schema and partition projection for the curated prefix |
| Athena workgroup | Query results location, encryption, optional scan cutoff |
| CloudWatch Logs | One log group per stack, retention configured |
| ECR | Container image repository with lifecycle cleanup |
| IAM roles | Execution role, job role, Batch service role and optional EC2 instance role |

## Data flow

1. A caller uploads an extract to
   `s3://<raw>/region=<region>/ymd=<ymd>/<file>.osm.pbf`.
2. `scripts/submit_job.sh` submits the Batch job with container overrides for
   the run (`RAW_KEY`, `RUN_ID`, `OUTPUT_BUCKET`, `OVERWRITE`, ...).
3. The container downloads the PBF to local ephemeral storage. The PBF is never
   loaded into memory as a whole.
4. PyOsmium streams entities. Each selected entity type gets its own
   `ParquetSink`. Sinks flush row groups and rotate part files when
   `MAX_RECORDS_PER_FILE` is reached.
5. Local Parquet files are uploaded to
   `s3://<curated>/<prefix>/_staging/run_id=<run>/...`.
6. The manifest is uploaded to staging.
7. Data objects are copied to their final keys under
   `<prefix>/region=<region>/ymd=<ymd>/entity=<entity>/`.
8. The manifest is copied to its final key **last**. A final manifest is the
   completion marker for readers that check it before querying.
9. Staging objects are deleted on a best-effort basis; the lifecycle rule is
   the fallback for abandoned staging objects.
10. In `OVERWRITE=replace`, stale objects under the partition prefix (keys not
    in the new manifest and not the manifest itself) are deleted after the new
    manifest is published.

In `OVERWRITE=replace`, the pipeline records the pre-existing keys and removes
the old manifest before copying replacement data. If publishing fails, rollback
deletes only keys that did not exist before the run; overwritten keys remain
and may contain new data without a manifest. S3 versioning retains prior object
versions for manual recovery, but the pipeline does not restore them
automatically. `replace` is not a distributed transaction.

The manifest does not gate S3 or Athena visibility. Direct S3 listings and
Athena queries can observe partial or mixed data while publication is in
progress or after a failed rollback. Query a partition only after its final
`_manifest.json` exists and validate its counts against that manifest.

## Why staging plus a manifest

- Readers that check for `_manifest.json` before querying can use it as a
  completion marker. It does not block direct S3 listings or Athena queries.
- `OVERWRITE=error` refuses to clobber an existing manifest or stray data.
- `OVERWRITE=skip` treats a manifest as proof of completion and fails when data
  exists without a manifest (a partial previous run).
- `OVERWRITE=replace` republishes and cleans stale keys.

There is no distributed lock. Run one job per `region`/`ymd` partition.

## Failure and retry model

| Condition | Exit code | Batch behaviour |
| --- | --- | --- |
| Bad env/config | 2 | Fail, no retry |
| Missing/empty/unparseable input | 3 | Fail, no retry |
| Output conflict | 4 | Fail, no retry |
| AWS access denied | 5 | Fail, no retry |
| S3/network failure | 75 | Retry |
| SIGTERM/SIGINT cancellation | 75 | Retry |
| Unexpected exception | 1 | Fail, no retry |

The job definition retries exit code `75`, interrupted EC2 hosts
(`Host EC2*`) and task initialization failures such as ECR image-pull timeouts
(`ResourceInitializationError*`) up to `batch_retry_attempts`, then exits on
any other exit code, and enforces `batch_timeout_seconds`. The final `EXIT`
rule matters: AWS Batch retries failures that match no `evaluate_on_exit` rule.
SIGTERM handlers allow the process to stop cooperatively and be retried.

## Memory, disk and performance

- PyOsmium is streaming; only the current PBF block is held by the parser.
- Parquet buffers are bounded by `ROW_GROUP_SIZE` and
  `MAX_RECORDS_PER_FILE`.
- Way geometry is off by default. Enabling it builds a disk-backed
  node-location index (`.osmium-index/`) during parsing and stores WKT
  LINESTRINGs; the index is removed after the parse. This increases disk use
  and CPU while parsing.
- Fargate ephemeral storage defaults to 100 GiB in Terraform. The container
  downloads the PBF, writes all selected entity partitions, and holds the
  index during parsing when geometry is enabled. Size it for the PBF, Parquet
  output, index and temporary row groups.
- Default Fargate sizing is 2 vCPU / 8192 MiB. Larger extracts benefit from
  more vCPU and memory; Fargate only accepts specific vCPU/memory combinations.
- Glue/Athena performance depends on partition pruning (`region`, `ymd`) and
  Parquet column pruning. `athena_bytes_scanned_cutoff` can cap runaway
  queries.

## Terraform layout

| File | Contents |
| --- | --- |
| `versions.tf` | Terraform/provider constraints; local backend note |
| `providers.tf` | AWS provider, default tags, caller identity |
| `locals.tf` | Bucket names, VPC/subnet selection, container properties |
| `variables.tf` | All inputs with validation |
| `networking.tf` | Default/selected VPC data sources, Batch security group |
| `endpoints.tf` | Fargate ECR/Logs interface endpoints and S3 gateway endpoint |
| `s3.tf` | Buckets, public access blocks, versioning, SSE, lifecycle, TLS policies |
| `ecr.tf` | Repository, scanning, encryption, lifecycle policy |
| `iam.tf` | Roles, policies, attachments |
| `batch.tf` | Log group, compute environment, queue, job definition |
| `glue.tf` | Catalog database and partition-projected `osm_curated` table |
| `athena.tf` | Workgroup, results location, encryption, scan cutoff |
| `outputs.tf` | Names/URIs consumed by scripts and docs |

The stack uses the default VPC unless `vpc_id`/`subnet_ids` are supplied. It
does not create VPCs, subnets or NAT gateways. For Fargate it creates ECR
(`ecr.api`, `ecr.dkr`) and CloudWatch Logs interface endpoints plus an S3
gateway endpoint, so tasks can pull images and read/write S3 without a NAT
gateway in the default configuration. Fargate tasks are pinned to one subnet
because the interface endpoints are created in that subnet. The S3 gateway
endpoint is associated with the selected VPC's main route table; with custom
subnets, confirm that their route table is the main route table or update the
endpoint association to include it.

## Security boundaries

- Batch job role: read raw and manage objects under the configured curated prefix.
- Batch execution role: pull the project ECR image and write to the Batch log group.
- Batch service role: AWS managed `AWSBatchServiceRole`.
- Glue Data Catalog table: explicit dataset schema and projected
  `region`/`ymd`/`entity` locations. No crawler role or crawler is required.
- EC2 instance role/profile exists for optional EC2 compute mode.
- S3 buckets block public access and deny non-TLS requests.
- No secrets are placed in environment variables; workloads use IAM roles.
- Egress is open in the Batch security group by default. Tighten to 443 and
  VPC endpoints in production.

## Extension points

- Add an EventBridge Scheduler or Step Functions state machine to submit jobs
  and query after the partition manifest appears.
- Add a compaction job to merge small part files per partition.
- Add OSM diff (`.osc.gz`) application for incremental updates.
- Reconstruct relation geometry from member ways if required.
- Publish to a data catalog with column statistics and partition projection.
