# ADR 003: Stage output and publish a manifest last

## Decision

Write Parquet and a manifest below a run-specific staging prefix, copy data
objects to the final region/date/entity layout, then copy `_manifest.json` last.
Readers that check for the final manifest before querying can use it as a
successful-run marker. The marker does not gate direct S3 listings or Athena
queries.

## Context

S3 does not provide a multi-object transaction. Staging keeps local and
intermediate files out of the final partition until publication begins, but
the first final copy makes objects visible to S3 listing and Athena. The
manifest identifies the intended file inventory and record counts; readers
must check for it before querying.

## Trade-offs

This is not an atomic commit. Concurrent jobs can race on one partition. In
`OVERWRITE=replace`, the old manifest is removed before copying, and rollback
does not delete keys that existed before the run; a failed replacement can
leave changed data without a manifest. S3 versioning supports manual recovery.
Enforce one job per partition and use `OVERWRITE=error` for normal first
publication. See
[architecture](../ARCHITECTURE.md) for failure behavior.
