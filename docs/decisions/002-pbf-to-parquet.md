# ADR 002: Stream PBF entities into typed Parquet

## Decision

Read PBF entities through PyOsmium callbacks and append normalized records to
bounded, rotating PyArrow Parquet writers. Use one explicit schema for nodes,
ways and relations.

## Context

The Quebec input contained 148,698,370 entities. The full PBF is not loaded
into memory. Parquet supports column pruning and downstream Spark/Databricks
reads; Snappy is the measured default.

## Trade-offs and limitations

Full tags and relation members are JSON strings. Way node references are
arrays. Geometry is WKT text; way geometry is optional and uses a disk-backed
node-location index. Relation geometry is not reconstructed. Per-file row
limits and row-group sizes bound output size, but the current output profile
still creates files much smaller than a typical compaction target.
