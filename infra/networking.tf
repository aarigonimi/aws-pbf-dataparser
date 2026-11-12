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
  count       = local.is_ec2 ? 1 : 0
  name        = "${var.project_name}-batch-sg"
  description = "Security group for AWS Batch EC2 worker nodes"
  vpc_id      = local.vpc_id

  ingress {
    description = "Self ingress for EC2 Batch nodes"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    description = "Outbound HTTPS/DNS for image pull, S3 and logs"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

resource "aws_security_group" "batch_fargate" {
  count = local.is_fargate ? 1 : 0

  name        = "${var.project_name}-batch-fargate"
  description = "Security group for AWS Batch Fargate task ENIs"
  vpc_id      = local.vpc_id

  egress {
    description = "Outbound HTTPS/DNS for image pull, S3 and logs"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}
