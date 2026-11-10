resource "aws_cloudwatch_log_group" "batch" {
  name              = "/aws/batch/${var.project_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

resource "aws_batch_compute_environment" "osm_compute" {
  compute_environment_name = "${var.project_name}-compute"
  type                     = "MANAGED"
  state                    = "ENABLED"

  # AWS guidance: Fargate compute environments must not use a customer
  # managed service role; EC2 environments use the AWSBatchServiceRole.
  service_role = local.is_ec2 ? aws_iam_role.batch_service_role.arn : null

  compute_resources {
    type = local.compute_resource_type

    max_vcpus     = var.batch_max_vcpus
    min_vcpus     = local.is_fargate ? null : var.batch_min_vcpus
    desired_vcpus = local.is_fargate ? null : var.batch_desired_vcpus

    subnets = local.subnet_ids
    # The Batch API requires at least one security group id for FARGATE
    # compute environments (Fargate does not support launch templates).
    security_group_ids = local.is_fargate ? [aws_security_group.batch_fargate[0].id] : [aws_security_group.batch[0].id]

    instance_type       = local.is_fargate ? null : var.batch_instance_types
    instance_role       = local.is_fargate ? null : aws_iam_instance_profile.ecs_instance_profile[0].arn
    allocation_strategy = local.is_fargate ? null : (var.batch_use_spot ? "SPOT_CAPACITY_OPTIMIZED" : "BEST_FIT_PROGRESSIVE")
    spot_iam_fleet_role = local.is_fargate ? null : (var.spot_iam_fleet_role_arn != "" ? var.spot_iam_fleet_role_arn : null)
  }

  depends_on = [
    aws_iam_role_policy_attachment.batch_service_policy,
    aws_iam_role_policy_attachment.ecs_instance_policy,
    aws_security_group.batch,
    aws_security_group.batch_fargate,
  ] # tflint-ignore: terraform_unused_depends_on
}

resource "aws_batch_job_queue" "osm_queue" {
  name     = "${var.project_name}-job-queue"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.osm_compute.arn
  }

  tags = var.tags
}

resource "aws_batch_job_definition" "osm_job" {
  name                  = "${var.project_name}-job"
  type                  = "container"
  platform_capabilities = [local.is_fargate ? "FARGATE" : "EC2"]

  container_properties = jsonencode(local.container_properties)

  retry_strategy {
    attempts = var.batch_retry_attempts

    evaluate_on_exit {
      on_exit_code = "75"
      action       = "RETRY"
    }

    evaluate_on_exit {
      on_status_reason = "Host EC2*"
      action           = "RETRY"
    }

    # Image pull / registry auth failures happen before the container starts.
    evaluate_on_exit {
      on_status_reason = "ResourceInitializationError*"
      action           = "RETRY"
    }

    # Authorization failures are deterministic and use AccessDeniedError (5).
    evaluate_on_exit {
      on_exit_code = "5"
      action       = "EXIT"
    }

    # Without a final rule, Batch retries every unmatched failure, including
    # the non-retryable config (2), input (3) and output-conflict (4) exits.
    evaluate_on_exit {
      on_exit_code = "*"
      action       = "EXIT"
    }
  }

  timeout {
    attempt_duration_seconds = var.batch_timeout_seconds
  }

  tags = var.tags

  depends_on = [
    aws_ecr_repository.batch,
    aws_cloudwatch_log_group.batch,
    aws_iam_role_policy_attachment.batch_execution_policy_attachment,
    aws_iam_role_policy_attachment.batch_job_policy_attachment,
  ]
}
