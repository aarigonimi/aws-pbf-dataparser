# ADR 003: Stage output and publish a manifest last

## Decision

Write Parquet and a manifest below a run-specific staging prefix, copy data
objects to the final region/date/entity layout, then copy `_manifest.json` last.
Consumers use the manifest as the successful-run marker.

## Context

S3 does not provide a multi-object transaction. Staging keeps incomplete files
out of the final partition until publication begins; the manifest identifies
the intended file inventory and record counts.

## Trade-offs

This is not an atomic commit. Concurrent jobs can race on one partition, and
`OVERWRITE=replace` can leave previous data unavailable after a failed copy.
S3 versioning supports manual recovery. Enforce one job per partition and use
`OVERWRITE=error` for normal first publication. See
[architecture](../ARCHITECTURE.md) for failure behavior.
