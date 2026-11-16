---
layout: article
title: OpenStreetMap PBF to Parquet on AWS
description: "Convert regional OpenStreetMap .osm.pbf extracts into partitioned Parquet tables in Amazon S3 using EventBridge, AWS Batch on Fargate, AWS Glue, and Amazon Athena."
permalink: /
---

<img src="{{ '/assets/images/architecture.webp' | relative_url }}" alt="Monthly OSM pipeline architecture" style="width: 100%; max-width: 100%; height: auto; display: block; border-radius: 10px;" />

## Overview

`aws-pbf-dataparser` streams regional OpenStreetMap `.osm.pbf` snapshots into Snappy-compressed Parquet files in Amazon S3, registers them in the AWS Glue Data Catalog with partition projection, and queries them in Amazon Athena.

- **Event-driven ingestion:** Uploading a `.osm.pbf` extract to the raw S3 bucket triggers an EventBridge rule that submits an AWS Batch job on AWS Fargate.
- **Streaming parser:** PyOsmium streams `nodes`, `ways` (with optional WKT `LINESTRING` reconstruction), and `relations` into bounded PyArrow Parquet batches.
- **SQL-ready:** Partition projection on `osm_catalog.osm_curated` exposes new snapshots immediately in Amazon Athena without Glue Crawlers.

## Quickstart

```bash
git clone https://github.com/aarigonimi/aws-pbf-dataparser.git
cd aws-pbf-dataparser
python3.12 -m venv .venv && source .venv/bin/activate
make install

cp -n infra/terraform.tfvars.example infra/terraform.tfvars
make deploy
make build

# Smoke test with Monaco (~707 KB)
make run
make logs
make verify
```

## Documentation

- [Architecture & Publication Semantics](https://github.com/aarigonimi/aws-pbf-dataparser/blob/main/docs/ARCHITECTURE.md)
- [Parquet Schema & Partition Layout](https://github.com/aarigonimi/aws-pbf-dataparser/blob/main/docs/SCHEMA.md)
- [Deployment Guide](https://github.com/aarigonimi/aws-pbf-dataparser/blob/main/docs/deployment.md)
- [S3 → EventBridge → Batch Trigger](https://github.com/aarigonimi/aws-pbf-dataparser/blob/main/docs/trigger.md)
- [Execution & Operations](https://github.com/aarigonimi/aws-pbf-dataparser/blob/main/docs/execution.md)
- [Athena Validation](https://github.com/aarigonimi/aws-pbf-dataparser/blob/main/docs/validation.md)
- [Real-Estate SQL Demo (`sql/athena/real_estate/`)](https://github.com/aarigonimi/aws-pbf-dataparser/blob/main/docs/REAL_ESTATE.md)
- [Cost Breakdown](https://github.com/aarigonimi/aws-pbf-dataparser/blob/main/docs/COST.md)
- [Troubleshooting](https://github.com/aarigonimi/aws-pbf-dataparser/blob/main/docs/troubleshooting.md)
- [Cleanup Guide](https://github.com/aarigonimi/aws-pbf-dataparser/blob/main/docs/cleanup.md)
