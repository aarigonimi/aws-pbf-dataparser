locals {
  project_name = var.project_name

  raw_bucket_name     = "${var.raw_bucket_name}-${random_id.bucket_suffix.hex}"
  curated_bucket_name = "${var.curated_bucket_name}-${random_id.bucket_suffix.hex}"

  vpc_id = var.vpc_id != "" ? var.vpc_id : data.aws_vpc.default.id

  is_fargate         = var.batch_compute_type == "FARGATE"
  is_ec2             = !local.is_fargate
  default_subnet_ids = length(var.subnet_ids) > 0 ? var.subnet_ids : sort(data.aws_subnets.default.ids)
  fargate_subnet_id  = local.default_subnet_ids[0]
  subnet_ids         = local.is_fargate ? [local.fargate_subnet_id] : local.default_subnet_ids

  use_vpc_endpoints = local.is_fargate && var.network_access == "vpc_endpoints"
  assign_public_ip  = local.is_fargate && var.network_access == "public_ip"

  compute_resource_type = local.is_fargate ? "FARGATE" : (var.batch_use_spot ? "SPOT" : "EC2")

  container_environment = [
    { name = "AWS_REGION", value = var.aws_region },
    { name = "RAW_BUCKET", value = local.raw_bucket_name },
    { name = "OUTPUT_BUCKET", value = local.curated_bucket_name },
    { name = "OUTPUT_PREFIX", value = var.output_prefix },
    # region=<name> parsed from RAW_KEY
    { name = "JOB_IMAGE_DIGEST", value = var.image_digest == "" ? "unset" : var.image_digest },
    { name = "GIT_SHA", value = var.image_tag },
    { name = "MODE", value = var.mode },
    { name = "OVERWRITE", value = var.overwrite },
    { name = "PARQUET_COMPRESSION", value = var.parquet_compression },
    { name = "INCLUDE_WAY_GEOMETRY", value = tostring(var.include_way_geometry) },
    { name = "LOG_LEVEL", value = var.log_level },
  ]

  image_reference = var.image_digest != "" ? "${aws_ecr_repository.batch.repository_url}@${var.image_digest}" : "${aws_ecr_repository.batch.repository_url}:${var.image_tag}"

  container_properties = merge(
    {
      image = local.image_reference
      command = [
        "--raw-key",
        "Ref::raw_key",
      ]
      resourceRequirements = [
        { type = "VCPU", value = tostring(var.batch_vcpus) },
        { type = "MEMORY", value = tostring(var.batch_memory_mb) },
      ]
      jobRoleArn       = aws_iam_role.batch_job_role.arn
      executionRoleArn = aws_iam_role.batch_execution_role.arn
      environment      = local.container_environment
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.batch.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "osm"
        }
      }
    },
    local.is_fargate ? {
      ephemeralStorage = { sizeInGiB = var.batch_ephemeral_storage_gb }
    } : {},
    local.assign_public_ip ? {
      networkConfiguration = { assignPublicIp = "ENABLED" }
    } : {},
  )

  job_definitions = {
    manual = {
      name = "${var.project_name}-job"
    }
    event = {
      name = "${var.project_name}-job-event"
    }
  }
}
