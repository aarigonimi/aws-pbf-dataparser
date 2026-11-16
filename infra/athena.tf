resource "aws_athena_workgroup" "osm_workgroup" {
  name        = var.athena_workgroup_name
  state       = "ENABLED"
  description = "Workgroup for OSM curated Parquet queries"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.athena_bytes_scanned_cutoff

    result_configuration {
      output_location = "s3://${aws_s3_bucket.curated.bucket}/athena-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }

  tags = var.tags
}
