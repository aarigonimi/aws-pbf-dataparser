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
| Monaco | `monaco-20261110T023307Z` | 48,469 | 3 files, 2.563 MB | 2.369 / 30.418 s; 20,459.7 entities/s | Tutorial-scale run of the current image: manifest, Glue table, Athena counts, sample rows and all three overwrite modes verified |

The Monaco row is a tutorial-scale validation of the current code, not a
throughput data point: 0.7 MB input, one file per entity, 2.4 s parse.

All three partitions were relocated from `region=<region>/ymd=<YYYYMMDD>/`
to `region=<region>/<yyyy>/<mm>/<dd>/` on 2026-11-10, and the Glue table
projection was updated to match; Athena counts for Quebec, London and Monaco
were re-verified against the manifests after the move. Monaco was then
republished in the new layout by the current image (run
`monaco-layout-030559`, recorded in
[monaco-20261108.json](monaco-20261108.json)); Quebec and London data was
moved without modification.

Derived parse rates: Quebec **26,885.6 entities/s**
(`148,698,370 / 5,530.778`) and London **24,299.3 entities/s**
(`13,346,901 / 549.270`). These are two different extracts and are not a
scaling study.

Quebec and London used the older writer, which rotated at 300,000 rows. The
current code rotates at 250,000 rows and was run in AWS for the Monaco
tutorial validation, but each entity fit in a single file, so the rotation
threshold itself remains unexercised in AWS.

The London run was already complete when this audit began. No London job was
submitted by this audit. See [Quebec](quebec-20261108.json),
[London](london-20261108.json) and [Monaco](monaco-20261108.json) for
details and provenance.

Two Quebec Batch jobs overlapped on the same partition. The job represented by
the final manifest completed in one attempt. A second job had two ECR
initialization timeouts, succeeded on its third attempt, and also processed the
same input and output partition. Treat the 2026 Quebec run as evidence of
throughput, not as a single-job cost baseline. The pipeline now serializes
publication per partition with an S3 conditional-write claim, so a rerun of
this scenario fails fast instead of interleaving output; the historical figures
predate that fix.

The Quebec manifest duration is measured before the final S3 publication.
CloudWatch recorded 5,894.62 seconds from the application start to completion;
AWS Batch recorded 5,922.575 seconds from `startedAt` to `stoppedAt`.

## Benchmark protocol for the next run

For one clean, single-job run, preserve the manifest, immutable image digest,
AWS Batch job ID and attempts, peak RSS and CPU from Container Insights, Athena
execution ID and bytes scanned, and actual cost from Cost Explorer filtered by
the Terraform `Project` tag. Keep uncollected values `null`; do not infer cost,
resource peaks or runtime image digests. The application manifest captures
source bytes, counts, compression, file inventory, run ID, and parse/download/
total durations.
