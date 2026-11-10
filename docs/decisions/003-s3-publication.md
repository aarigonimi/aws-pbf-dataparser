# ADR 003: Stage output and publish a manifest last

## Decision

Write Parquet and a manifest below a run-specific staging prefix, copy data
objects to the final region/date/entity layout, then copy `_manifest.json` last.
Before any work, a run must claim the partition with an S3 conditional write
(`PutObject` with `If-None-Match: *`) on
`<prefix>/region=<region>/<yyyy>/<mm>/<dd>/_lock.json`; a run that cannot acquire the
claim fails with exit code 4 instead of publishing. Readers that check for the
final manifest before querying can use it as a successful-run marker. The
marker does not gate direct S3 listings or Athena queries.

## Context

S3 does not provide a multi-object transaction. Staging keeps local and
intermediate files out of the final partition until publication begins, but
the first final copy makes objects visible to S3 listing and Athena. The
manifest identifies the intended file inventory and record counts; readers
must check for it before querying. Two jobs for the same region/date can
pass a pre-publication existence check concurrently (this happened during
the Quebec run), so a check alone cannot serialize publication.

## Trade-offs

This is not an atomic commit. The claim lock serializes *start of
publication* per partition: exactly one concurrent run can hold it, the
others fail fast without touching the partition, and the holder releases
the claim when it finishes (success, failure or cancellation). It requires
only `s3:PutObject` on the curated prefix, which the job role already has,
and no extra infrastructure — but it is not a lease with a TTL: a holder
that is terminated without cleanup leaves the claim behind, and recovery
is `OVERWRITE=replace`, which force-removes a stale claim. In
`OVERWRITE=replace`, stale objects are removed *before* new data is
published and the new manifest is copied last, so a failed run leaves no
manifest rather than a manifest referencing missing files; S3 versioning
supports manual recovery of overwritten keys. Enforce one job per
partition and use `OVERWRITE=error` for normal first publication. See
[architecture](../ARCHITECTURE.md) for failure behavior.
