---
layout: article
title: Field notes from an OpenStreetMap pipeline on AWS
description: "Articles and engineering notes from streaming OpenStreetMap PBF into queryable Parquet on AWS — benchmarks, production incidents and lessons learned."
permalink: /
---

Everything on this site comes from building and operating [aws-pbf-dataparser](https://github.com/aarigonimi/aws-pbf-dataparser), a streaming PBF-to-Parquet pipeline that turns regional OpenStreetMap extracts into datasets you can query with SQL in Amazon Athena. Start with the field report; go deep with the walkthrough.

## Articles

### [Processing 148 Million OpenStreetMap Entities with AWS Batch]({{ '/processing-148-million-openstreetmap-entities-aws-batch/' | relative_url }})

Building a streaming PBF-to-Parquet data pipeline on AWS, and the engineering lessons learned along the way. One Fargate task, 497 Parquet files, two production incidents and one honestly labeled benchmark.

AWS · AWS Batch · Data Engineering · OpenStreetMap · Parquet

### [The Full Implementation Walkthrough: OpenStreetMap PBF to Parquet on AWS Batch]({{ '/walkthrough/' | relative_url }})

Every module, Terraform block, command and caveat behind the pipeline, in build order — the long-form companion for readers who want the complete implementation, not just the story.
