---
layout: article
title: Architecture
description: How the aws-pbf-dataparser components fit together — compute, storage, catalog and query.
permalink: /docs/ARCHITECTURE/
---

## Components

| Component | Responsibility |
| --- | --- |
| S3 raw bucket | Versioned source extracts under `region=<region>/<yyyy>/<mm>/<dd>/`, with lifecycle expiry |
| S3 → EventBridge notification | Optional event source; emits `Object Created` for the raw bucket |
| EventBridge rule and Batch target | Optional; submits one Batch job when a `.osm.pbf` lands in the raw bucket |
| AWS Batch compute environment | Fargate (default) or EC2/Spot workers |
| Batch job definition | Container image, vCPU/memory, env defaults, trigger parameters, retries, timeout, log config |
| Batch job queue | Schedules jobs onto the compute environment |
| S3 curated bucket | Staging, final Parquet, manifests, Athena results |
| Glue database + projected table | Explicit Parquet schema and partition projection for the curated prefix |
| Athena workgroup | Query results location, encryption, optional scan cutoff |
| CloudWatch Logs | One log group per stack, retention configured |
| ECR | Container image repository with lifecycle cleanup |
| IAM roles | Execution role, job role, Batch service role, optional EventBridge submit role and optional EC2 instance role |
| QuickSight (optional) | Not provisioned; can read the Athena views if configured separately |

## Data flow

1. A caller uploads an extract to
   `s3://<raw>/region=<region>/<yyyy>/<mm>/<dd>/<file>.osm.pbf`.
2. Either the optional EventBridge rule submits the Batch job with the object
   key as the `raw_key` job-definition parameter, or `scripts/submit_job.sh`
   submits it with container environment overrides (`RAW_KEY`, `OVERWRITE`, ...).
   Triggered jobs derive the region and date from the key; manual overrides
   take precedence.
3. The job claims the partition: a conditional write (`If-None-Match: *`) of
   `_lock.json` under the final partition prefix. Only one concurrent run can
   hold the claim; the others fail with exit code 4 before doing any work.
   `RUN_ID` defaults to a value derived from `AWS_BATCH_JOB_ID` plus the
   attempt number, so every Batch attempt stages under a unique prefix.
4. The existing-output check is re-run under the claim (a run may have
   published between the first check and claim acquisition).
5. The container downloads the PBF to local ephemeral storage. The PBF is never
   loaded into memory as a whole.
6. PyOsmium streams entities. Each selected entity type gets its own
   `ParquetSink`. Sinks flush row groups and rotate part files when
   `MAX_RECORDS_PER_FILE` is reached; a part file never exceeds the cap.
7. Local Parquet files are uploaded to
   `s3://<curated>/<prefix>/_staging/run_id=<run>/...`.
8. The manifest is uploaded to staging.
9. In `OVERWRITE=replace`, stale objects under the partition prefix (keys not
   in the new manifest, not the manifest itself, and not the claim) are
   deleted *before* any new data is published.
10. Data objects are copied to their final keys under
    `<prefix>/region=<region>/<yyyy>/<mm>/<dd>/entity=<entity>/`.
11. The manifest is copied to its final key **last**. A final manifest is the
    completion marker for readers that check it before querying.
12. Staging objects are deleted on a best-effort basis; the lifecycle rule is
    the fallback for abandoned staging objects. The claim is released on
    success, failure and cancellation.

In `OVERWRITE=replace`, the pipeline removes stale keys before publishing new
data, so a failed run never leaves a manifest referencing missing files: it
leaves no manifest at all, which readers gate on. Overwritten keys keep prior
object versions for manual recovery; the pipeline does not restore them
automatically. `replace` is not a distributed transaction.

The manifest does not gate S3 or Athena visibility. Direct S3 listings and
Athena queries can observe partial or mixed data while publication is in
progress or after a failed rollback. Query a partition only after its final
`_manifest.json` exists and validate its counts against that manifest.

## Trigger contract

- S3 EventBridge notifications are enabled on the raw bucket when
  `s3_trigger_enabled = true` (default).
- The rule matches `source = aws.s3`, `detail-type = Object Created`, the raw
  bucket name and a key suffix of `.osm.pbf`.
- EventBridge Batch targets cannot pass `containerOverrides`. The event job
  definition exposes a `raw_key` parameter, and the container command expands
  it with `Ref::raw_key`; the input transformer maps the S3 object key into
  it. The target submits the job named `osm-event-extract` against the
  latest revision of the event definition (revisionless ARN prefix), while
  manual scripts keep using the stable manual definition.
- The EventBridge submit role may call `batch:SubmitJob` on this queue and job
  definition and `iam:PassRole` only for the Batch job and execution roles,
  restricted to `batch.amazonaws.com`.
- The application derives `REGION_NAME` from the `region=<name>` key segment
  and `YMD` from the `yyyy/mm/dd` path. There is no fallback: a key that does
  not match the layout fails with exit code 3 before any output is written.
- Triggered jobs use the event job definition's baked `MODE`, compression and
  `INCLUDE_WAY_GEOMETRY`; change Terraform and apply a new revision to change
  those defaults. Manual submission can override them.
- S3/EventBridge can deliver duplicate events. The baked `OVERWRITE` mode
  (default `error`) and the per-partition claim make a duplicate safe:
  completed output is not replaced, and a concurrent loser fails with exit
  code 4.

## Why staging plus a manifest

- Readers that check for `_manifest.json` before querying can use it as a
  completion marker. It does not block direct S3 listings or Athena queries.
- `OVERWRITE=error` refuses to clobber an existing manifest or stray data.
- `OVERWRITE=skip` treats a manifest as proof of completion and fails when data
  exists without a manifest (a partial previous run).
- `OVERWRITE=replace` republishes, force-removes a stale claim, and cleans
  stale keys before publishing.
- Publication is serialized per `region`/date partition by the conditional-
  write claim (`_lock.json`); a run that loses the race fails fast with exit
  code 4 and leaves the winner's output untouched. The claim is released when
  the run finishes, so it is not a lease: a holder killed without cleanup
  leaves the claim behind and recovery is `OVERWRITE=replace`.

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
- Way geometry is on by default (`include_way_geometry = true`). Enabling it
  builds a disk-backed node-location index (`.osmium-index/`) during parsing
  and stores WKT
  LINESTRINGs; the index is removed after the parse. This increases disk use
  and CPU while parsing.
- Fargate ephemeral storage defaults to 100 GiB in Terraform. The container
  downloads the PBF, writes all selected entity partitions, and holds the
  index during parsing when geometry is enabled. Size it for the PBF, Parquet
  output, index and temporary row groups.
- Default Fargate sizing is 2 vCPU / 8192 MiB. Larger extracts benefit from
  more vCPU and memory; Fargate only accepts specific vCPU/memory combinations.
- Glue/Athena performance depends on partition pruning (`region`, `year`,
  `month`, `day`) and
  Parquet column pruning. `athena_bytes_scanned_cutoff` can cap runaway
  queries.

## Terraform layout

| File | Contents |
| --- | --- |
| `versions.tf` | Terraform/provider constraints; local backend note |
| `providers.tf` | AWS provider, default tags, caller identity |
| `locals.tf` | Bucket names, VPC/subnet selection, container properties |
| `variables.tf` | All inputs with validation |
| `networking.tf` | Default/selected VPC data sources, Batch security groups (EC2 and Fargate) |
| `endpoints.tf` | Fargate ECR/Logs interface endpoints and S3 gateway endpoint |
| `s3.tf` | Buckets, public access blocks, versioning, SSE, lifecycle, TLS policies |
| `ecr.tf` | Repository, scanning, encryption, lifecycle policy |
| `iam.tf` | Roles, policies, attachments |
| `batch.tf` | Log group, compute environment, queue, job definition |
| `trigger.tf` | Optional S3 notification, EventBridge rule/target and submit role |
| `glue.tf` | Catalog database and partition-projected `osm_curated` table |
| `athena.tf` | Workgroup, results location, encryption, scan cutoff |
| `outputs.tf` | Names/URIs consumed by scripts and docs |

The stack uses the default VPC unless `vpc_id`/`subnet_ids` are supplied. It
does not create VPCs, subnets or NAT gateways. In the default
`network_access = vpc_endpoints` mode it creates ECR (`ecr.api`, `ecr.dkr`)
and CloudWatch Logs interface endpoints plus an S3 gateway endpoint, so tasks
can pull images and read/write S3 without a NAT gateway. Fargate tasks are
pinned to one subnet because the interface endpoints are created in that
subnet. The S3 gateway endpoint is associated with every route table in the
VPC, covering both the main table used by default subnets and any explicit
associations. With
`network_access = public_ip` no endpoints are created; each task gets a
public IP and the subnet needs an internet route.

## Security boundaries

- Batch job role: read raw and manage objects under the configured curated prefix.
- Batch execution role: pull the project ECR image and write to the Batch log group.
- Batch service role: AWS managed `AWSBatchServiceRole`.
- EventBridge submit role: `batch:SubmitJob` on this queue/definition and
  `iam:PassRole` for the Batch roles, only when passed to `batch.amazonaws.com`.
- Glue Data Catalog table: explicit dataset schema and projected
  `region`/`year`/`month`/`day`/`entity` locations. No crawler role or crawler is required.
- EC2 instance role/profile exists for optional EC2 compute mode.
- S3 buckets block public access and deny non-TLS requests.
- No secrets are placed in environment variables; workloads use IAM roles.
- Egress is open in the Batch security group by default. Tighten to 443 and
  VPC endpoints in production.

## Extension points

- Add EventBridge Scheduler or Step Functions to download the monthly Geofabrik
  extract, upload it, and query after the partition manifest appears.
- Add a compaction job to merge small part files per partition.
- Add OSM diff (`.osc.gz`) application for incremental updates.
- Reconstruct relation geometry from member ways if required.
- Publish to a data catalog with column statistics and partition projection.
- Connect QuickSight to the example real-estate views; it is not provisioned
  by this stack.
