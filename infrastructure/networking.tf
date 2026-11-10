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

  # This security group and EC2 peer ingress exist only for EC2 compute.
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

# Fargate task ENIs need their own security group: the Batch API requires at
# least one security group id for FARGATE compute environments and Fargate
# does not support launch templates. Tasks only need outbound access; the
# interface endpoints accept HTTPS from the VPC CIDR (see endpoints.tf).
resource "aws_security_group" "batch_fargate" {
  count = local.is_fargate ? 1 : 0

  name        = "${var.project_name}-batch-fargate"
  description = "Security group for AWS Batch Fargate task ENIs"
  vpc_id      = local.vpc_id

  # Same egress contract as the EC2 worker group: reach ECR, S3 and
  # CloudWatch Logs through the VPC endpoints, or the internet if egress
  # is not restricted.
  egress {
    description = "Outbound HTTPS/DNS for image pull, S3 and logs"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}
