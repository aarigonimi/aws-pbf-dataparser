output "athena_workgroup_name" {
  description = "Athena workgroup name."
  value       = aws_athena_workgroup.osm_workgroup.name
}

output "aws_region" {
  description = "AWS region the stack is deployed in."
  value       = var.aws_region
}

output "batch_compute_environment_arn" {
  description = "ARN of the Batch compute environment."
  value       = aws_batch_compute_environment.osm_compute.arn
}

output "batch_job_definition_arn" {
  description = "ARN of the manual Batch job definition (pinned revision)."
  value       = aws_batch_job_definition.osm_job["manual"].arn
}

output "batch_job_definition_name" {
  description = "Name of the manual Batch job definition."
  value       = aws_batch_job_definition.osm_job["manual"].name
}

output "batch_event_job_definition_name" {
  description = "Name of the EventBridge-facing Batch job definition."
  value       = aws_batch_job_definition.osm_job["event"].name
}

output "batch_event_job_definition_arn" {
  description = "Revisionless ARN of the EventBridge-facing Batch job definition."
  value       = aws_batch_job_definition.osm_job["event"].arn_prefix
}

output "batch_job_queue_name" {
  description = "Batch job queue name."
  value       = aws_batch_job_queue.osm_queue.name
}

output "cloudwatch_log_group_name" {
  description = "CloudWatch log group used by Batch jobs."
  value       = aws_cloudwatch_log_group.batch.name
}

output "curated_bucket_name" {
  description = "Curated Parquet bucket."
  value       = aws_s3_bucket.curated.bucket
}

output "curated_prefix_uri" {
  description = "S3 URI cataloged by Glue and queried by Athena."
  value       = "s3://${aws_s3_bucket.curated.bucket}/${var.output_prefix}/"
}

output "ecr_repository_url" {
  description = "ECR repository URL to push the pipeline image to."
  value       = aws_ecr_repository.batch.repository_url
}

output "eventbridge_rule_name" {
  description = "EventBridge rule that submits Batch jobs for new raw PBF uploads, or null when disabled."
  value       = var.s3_trigger_enabled ? aws_cloudwatch_event_rule.raw_pbf_uploaded[0].name : null
}

output "s3_trigger_enabled" {
  description = "Whether the S3 -> EventBridge -> Batch trigger is enabled."
  value       = var.s3_trigger_enabled
}

output "glue_database_name" {
  description = "Glue catalog database for curated Parquet."
  value       = aws_glue_catalog_database.osm_catalog.name
}

output "glue_table_name" {
  description = "Partition-projected Glue table for curated Parquet."
  value       = aws_glue_catalog_table.osm_curated.name
}

output "raw_bucket_name" {
  description = "Raw OSM PBF bucket."
  value       = aws_s3_bucket.raw.bucket
}

output "security_group_id" {
  description = "Security group attached to Batch workers."
  value       = local.is_fargate ? aws_security_group.batch_fargate[0].id : aws_security_group.batch[0].id
}
