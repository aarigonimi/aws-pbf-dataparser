data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "batch" {
  name        = "${var.project_name}-batch-sg"
  description = "Security group for AWS Batch EC2 worker nodes"
  vpc_id      = local.vpc_id

  # Only relevant for EC2 compute environments (node-to-node traffic).
  ingress {
    description = "Self ingress for EC2 Batch nodes"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  # Fargate/EC2 workers need egress to ECR, S3 and CloudWatch Logs. Tighten
  # this to VPC endpoints + 443 in a locked-down account (see docs/COST.md).
  egress {
    description = "Outbound HTTPS/DNS for image pull, S3 and logs"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}
