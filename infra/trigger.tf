resource "aws_s3_bucket_notification" "raw_object_created" {
  count  = var.s3_trigger_enabled ? 1 : 0
  bucket = aws_s3_bucket.raw.id

  eventbridge = true

  depends_on = [aws_s3_bucket.raw]
}

resource "aws_cloudwatch_event_rule" "raw_pbf_uploaded" {
  count = var.s3_trigger_enabled ? 1 : 0

  name        = "${var.project_name}-raw-pbf-uploaded"
  description = "Submit one Batch run when a .osm.pbf object lands under region= in the raw bucket."

  event_pattern = jsonencode({
    source        = ["aws.s3"]
    "detail-type" = ["Object Created"]
    detail = {
      bucket = {
        name = [aws_s3_bucket.raw.bucket]
      }
      object = {
        key = [
          { suffix = ".osm.pbf" },
        ]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "raw_pbf_batch" {
  count = var.s3_trigger_enabled ? 1 : 0

  rule      = aws_cloudwatch_event_rule.raw_pbf_uploaded[0].name
  target_id = "osm-batch-job"
  arn       = aws_batch_job_queue.osm_queue.arn
  role_arn  = aws_iam_role.eventbridge_batch_submit[0].arn

  batch_target {
    job_definition = aws_batch_job_definition.osm_job["event"].arn_prefix
    job_name       = "osm-event-extract"
  }

  input_transformer {
    input_paths = {
      raw_key = "$.detail.object.key"
    }

    input_template = "{\"Parameters\": {\"raw_key\": <raw_key>}}"
  }

  retry_policy {
    maximum_event_age_in_seconds = 3600
    maximum_retry_attempts       = 3
  }

  depends_on = [aws_batch_job_definition.osm_job]
}

data "aws_iam_policy_document" "eventbridge_batch_submit" {
  count = var.s3_trigger_enabled ? 1 : 0

  statement {
    sid    = "SubmitOsmBatchJobs"
    effect = "Allow"

    actions = ["batch:SubmitJob"]

    resources = [
      aws_batch_job_queue.osm_queue.arn,
      aws_batch_job_definition.osm_job["event"].arn_prefix,
      "${aws_batch_job_definition.osm_job["event"].arn_prefix}:*",
    ]
  }

  statement {
    sid    = "PassBatchRoles"
    effect = "Allow"

    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.batch_job_role.arn, aws_iam_role.batch_execution_role.arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["batch.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eventbridge_batch_submit" {
  count = var.s3_trigger_enabled ? 1 : 0

  name = "${var.project_name}-eventbridge-batch-submit"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "eventbridge_batch_submit" {
  count = var.s3_trigger_enabled ? 1 : 0

  name   = "${var.project_name}-eventbridge-batch-submit"
  role   = aws_iam_role.eventbridge_batch_submit[0].id
  policy = data.aws_iam_policy_document.eventbridge_batch_submit[0].json
}
