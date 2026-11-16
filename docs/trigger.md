---
layout: article
title: S3 → EventBridge → Batch trigger
description: How new PBF uploads can submit an AWS Batch job automatically.
permalink: /docs/TRIGGER/
---

## What it does

When `s3_trigger_enabled = true` (the default), Terraform enables S3
EventBridge notifications on the raw bucket and creates a rule that submits
one Batch job for each new object whose key ends with `.osm.pbf`. The
processor itself requires the strict raw key layout, so a triggered job for
any other key fails fast with exit code 3 instead of writing output:

```text
region=<region>/<yyyy>/<mm>/<dd>/<file>.osm.pbf
```

The trigger is optional. Set `s3_trigger_enabled = false` to deploy only the
manual `scripts/submit_job.sh` path.

## Resources

| Resource | Purpose |
| --- | --- |
| `aws_s3_bucket_notification.raw_object_created` | Enables EventBridge notifications on the raw bucket |
| `aws_cloudwatch_event_rule.raw_pbf_uploaded` | Filters S3 `Object Created` events by bucket and `.osm.pbf` suffix |
| `aws_cloudwatch_event_target.raw_pbf_batch` | Submits to the Batch job queue with a parameter input transformer |
| `aws_iam_role.eventbridge_batch_submit` | Lets EventBridge submit this job and pass the Batch roles |

The EventBridge role is scoped to `batch:SubmitJob` on this queue and job
definition, plus `iam:PassRole` for the Batch job and execution roles only when
the target service is `batch.amazonaws.com`.

## Batch parameter contract

EventBridge Batch targets do not support `containerOverrides`, so the event
job definition exposes one parameter:

```hcl
parameters = {
  raw_key = ""
}
```

The container command expands it:

```hcl
command = [
  "--raw-key", "Ref::raw_key",
]
```

The EventBridge input transformer maps the S3 object key (`$.detail.object.key`,
URL-decoded by the processor) into the `SubmitJob` input:

```json
{
  "Parameters": {
    "raw_key": "<raw_key>"
  }
}
```

The submitted job is named `osm-event-extract` and targets the latest
revision of the event job definition (the revisionless ARN prefix), so
applying a new revision takes effect on the next upload without touching the
rule. The application accepts `--raw-key`, `--raw-bucket`, `--region-name`,
`--ymd` and `--overwrite`. Empty values are ignored, so manual submissions
that omit parameters still use environment variables and the job definition
defaults.

## Region and date derivation

A triggered job receives only the object key. `src/config.py` parses the key
strictly and derives:

- `REGION_NAME` from the `region=<name>` path segment;
- `YMD` from the `yyyy/mm/dd` path segment.

There is no fallback region or date: a key that does not match the layout
exits with code 3 before any output is written. `REGION_NAME` and `YMD` are
deliberately not baked into the container environment, because explicit
environment values would override the key-derived region and date.

## Geometry and manual overrides

Triggered jobs use the event job definition's baked `INCLUDE_WAY_GEOMETRY`,
`MODE`, `PARQUET_COMPRESSION`, `MAX_RECORDS_PER_FILE` and similar settings.
Change those in Terraform and apply a new job-definition revision when the
trigger should use different defaults.

Manual submission can override the same values through the Batch container
environment and `scripts/submit_job.sh`. Manual overrides take precedence over
key-derived values.

Way geometry is on by default (`include_way_geometry = true` in Terraform).
Without it, ways have no coordinates, so the real-estate SQL cannot use
way centroids. Node amenities still work.

## Duplicate events

S3/EventBridge delivery is at-least-once. Duplicate events can submit more than
one job for the same object. Two safeguards apply:

1. The baked `OVERWRITE` mode (default `error`) refuses to touch an existing
   partition.
2. The pipeline claims the partition with a conditional `_lock.json` write, so
   a concurrent duplicate normally fails fast with exit code 4 instead of
   interleaving output.

If a duplicate wins the claim first, the other job exits without changing the
partition. Bake `OVERWRITE = "skip"` into the event definition to treat a
completed manifest as done, or `replace` only for controlled recovery.
`replace` is not a distributed transaction.

## Trigger not firing

Check, in order:

1. `terraform -chdir=infra output s3_trigger_enabled` is `true`.
2. The object key ends with `.osm.pbf` (and matches the `region=` layout, or
   the job fails with exit code 3 after it starts).
3. The raw bucket has an EventBridge notification enabled.
4. The EventBridge rule exists and is `ENABLED`.
5. The EventBridge role can call `batch:SubmitJob` and `iam:PassRole`; inspect
   the rule's failed invocations in CloudWatch metrics or EventBridge.
6. The job queue and job definition are in the same region and account.

The rule does not match `.osm.pbf.gz`, files in other formats, or objects in
the curated bucket.

## Limitations

- The S3 event key may be URL-encoded for unusual characters; the processor
  URL-decodes it before parsing. Normal Geofabrik keys are unaffected.
- The trigger submits immediately on upload. It does not wait for a multipart
  upload to be verified beyond S3's `Object Created` event.
- The rule does not deduplicate events; the baked `OVERWRITE` mode and the
  partition claim are the safety net.
- The trigger does not download Geofabrik extracts, run Athena SQL, or refresh
  QuickSight.
- The trigger wiring is validated by unit tests over the Terraform sources;
  no live AWS trigger run is claimed yet.
