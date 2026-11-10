data "aws_vpc" "selected" {
  id = local.vpc_id
}

resource "aws_security_group" "vpc_endpoints" {
  count = local.is_fargate ? 1 : 0

  name        = "${var.project_name}-vpc-endpoints"
  description = "Allow Batch Fargate tasks to reach ECR, CloudWatch Logs and S3"
  vpc_id      = local.vpc_id

  # The endpoints accept HTTPS from the whole VPC CIDR rather than from the
  # batch-fargate security group: an SG-referencing-SG rule couples the two
  # groups' deletion order (EC2 blocks deleting a referenced group), which
  # makes infrastructure replacement and teardown brittle.
  ingress {
    description = "HTTPS from the VPC (Batch Fargate tasks)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.selected.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

resource "aws_vpc_endpoint" "ecr_api" {
  count = local.is_fargate ? 1 : 0

  vpc_id              = local.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [local.fargate_subnet_id]
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = var.tags
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  count = local.is_fargate ? 1 : 0

  vpc_id              = local.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [local.fargate_subnet_id]
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = var.tags
}

resource "aws_vpc_endpoint" "logs" {
  count = local.is_fargate ? 1 : 0

  vpc_id              = local.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [local.fargate_subnet_id]
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = var.tags
}

resource "aws_vpc_endpoint" "s3" {
  count = local.is_fargate ? 1 : 0

  vpc_id            = local.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [data.aws_vpc.selected.main_route_table_id]

  tags = var.tags
}
