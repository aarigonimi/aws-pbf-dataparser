resource "aws_glue_catalog_database" "osm_catalog" {
  name = var.glue_database_name

  tags = var.tags
}

resource "aws_glue_crawler" "osm_crawler" {
  name          = var.glue_crawler_name
  role          = aws_iam_role.glue_crawler_role.arn
  database_name = aws_glue_catalog_database.osm_catalog.name

  s3_target {
    path       = "s3://${aws_s3_bucket.curated.bucket}/${var.output_prefix}/"
    exclusions = ["_staging/**", "athena-results/**"]
  }

  schema_change_policy {
    delete_behavior = "DEPRECATE_IN_DATABASE"
    update_behavior = "UPDATE_IN_DATABASE"
  }

  recrawl_policy {
    recrawl_behavior = "CRAWL_EVERYTHING"
  }

  tags = var.tags

  depends_on = [
    aws_glue_catalog_database.osm_catalog,
    aws_iam_role_policy_attachment.glue_crawler_policy_attachment,
    aws_iam_role_policy_attachment.glue_service_role,
  ]
}
