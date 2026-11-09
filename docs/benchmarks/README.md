# Benchmarks

Structured JSON is the canonical record for measured runs. Values copied from
the S3 manifest or AWS APIs are identified in each file; derived values include
their derivation. Missing costs are left null instead of estimated.

## Verified runs

Parse throughput below is derived as total manifest records divided by
manifest parse seconds. It excludes input download and final publication.

| Region | Run ID | Entities | Parquet output | Parse / Batch duration | Validation |
| --- | --- | ---: | ---: | ---: | --- |
| Quebec | `quebec-20261108233711` | 148,698,370 | 497 files, 6.454 GB | 5,530.778 / 5,922.575 s; 26,885.6 entities/s | S3 manifest, Glue schema and Athena entity counts verified |
| London | `london-20261109142209` | 13,346,901 | 46 files, 588.846 MB | 549.270 / 604.629 s; 24,299.3 entities/s | Existing S3 manifest, Glue tables and Batch success verified; Athena counts not queried |

Derived parse rates: Quebec **26,885.6 entities/s**
(`148,698,370 / 5,530.778`) and London **24,299.3 entities/s**
(`13,346,901 / 549.270`). These are two different extracts and are not a
scaling study.

The London run was already complete when this audit began. No London job was
submitted by this audit. See [Quebec](quebec-20261108.json) and
[London](london-20261108.json) for details and provenance.

Two Quebec Batch jobs overlapped on the same partition. The job represented by
the final manifest completed in one attempt. A second job had two ECR
initialization timeouts, succeeded on its third attempt, and also processed the
same input and output partition. Treat the 2026 Quebec run as evidence of
throughput, not as a single-job cost baseline. Enforce one job per partition
externally until the pipeline has a distributed lock.

The Quebec manifest duration is measured before the final S3 publication.
CloudWatch recorded 5,894.62 seconds from the application start to completion;
AWS Batch recorded 5,922.575 seconds from `startedAt` to `stoppedAt`.

## How to capture the next run

After a successful job, preserve the exact `_manifest.json` values and record
the AWS Batch job ID and attempts, job definition revision and image digest,
CloudWatch logs, Athena execution ID/count results/bytes scanned, and any
available cost allocation data. Keep actual AWS prices separate from estimates.
The application manifest already captures source bytes, counts, compression,
file inventory and byte sizes, run ID, and parse/download/total durations.
For a prospective run, also record immutable image tag and digest, Git SHA,
AWS Batch job ID and attempts, peak CPU/RSS from Container Insights, Athena
execution ID and bytes scanned, and actual cost allocations by `Project` tag.
Those prospective fields are not available for the historical runs unless
listed in their JSON records.
