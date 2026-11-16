---
layout: article
title: OpenStreetMap PBF to Parquet on AWS
description: "Convert regional OpenStreetMap .osm.pbf extracts into partitioned Parquet tables in Amazon S3 using EventBridge, AWS Batch on Fargate, AWS Glue, and Amazon Athena."
permalink: /
---

![Pipeline architecture]({{ '/assets/images/architecture.webp' | relative_url }})

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

- [Architecture & Publication Semantics](docs/ARCHITECTURE.md)
- [Parquet Schema & Partition Layout](docs/SCHEMA.md)
- [Deployment Guide](docs/deployment.md)
- [S3 → EventBridge → Batch Trigger](docs/trigger.md)
- [Execution & Operations](docs/execution.md)
- [Athena Validation](docs/validation.md)
- [Real-Estate SQL Demo (`sql/athena/real_estate/`)](docs/REAL_ESTATE.md)
- [Cost Breakdown](docs/COST.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Cleanup Guide](docs/cleanup.md)
