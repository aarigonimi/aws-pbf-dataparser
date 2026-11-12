variable "aws_region" {
  description = "AWS region for the OSM data lake stack."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z]{2}(-gov)?-[a-z]+-[0-9]$", var.aws_region))
    error_message = "aws_region must look like us-east-1 or us-gov-west-1."
  }
}

variable "project_name" {
  description = "Prefix used for resource names and tags."
  type        = string
  default     = "osm-pbf-data-lake"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,40}[a-z0-9]$", var.project_name))
    error_message = "project_name must contain lowercase letters, digits and dashes."
  }
}

variable "raw_bucket_name" {
  description = "Base name for the raw bucket; a random suffix is appended."
  type        = string
  default     = "osm-data-raw"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,40}[a-z0-9]$", var.raw_bucket_name))
    error_message = "raw_bucket_name must be a valid S3 bucket base name."
  }
}

variable "curated_bucket_name" {
  description = "Base name for the curated bucket; a random suffix is appended."
  type        = string
  default     = "osm-data-curated"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,40}[a-z0-9]$", var.curated_bucket_name))
    error_message = "curated_bucket_name must be a valid S3 bucket base name."
  }
}

variable "bucket_suffix_byte_length" {
  description = "Length of the random suffix appended to bucket names."
  type        = number
  default     = 4

  validation {
    condition     = var.bucket_suffix_byte_length >= 2 && var.bucket_suffix_byte_length <= 8
    error_message = "bucket_suffix_byte_length must be between 2 and 8."
  }
}

variable "vpc_id" {
  description = "Optional existing VPC id. Leave empty to use the default VPC."
  type        = string
  default     = ""
}

variable "subnet_ids" {
  description = "Optional subnet ids. Leave empty to use all subnets in the selected VPC."
  type        = list(string)
  default     = []
}

variable "network_access" {
  description = "How Batch tasks reach AWS APIs: vpc_endpoints creates ECR/Logs interface endpoints and an S3 gateway endpoint; public_ip assigns tasks a public IP and creates no endpoints (requires a subnet with an internet route)."
  type        = string
  default     = "vpc_endpoints"

  validation {
    condition     = contains(["vpc_endpoints", "public_ip"], var.network_access)
    error_message = "network_access must be vpc_endpoints or public_ip."
  }
}

variable "batch_compute_type" {
  description = "Batch compute environment type: FARGATE (default) or EC2."
  type        = string
  default     = "FARGATE"

  validation {
    condition     = contains(["FARGATE", "EC2"], var.batch_compute_type)
    error_message = "batch_compute_type must be FARGATE or EC2."
  }
}

variable "batch_use_spot" {
  description = "Use EC2 Spot capacity when batch_compute_type = EC2."
  type        = bool
  default     = false
}

variable "spot_iam_fleet_role_arn" {
  description = "ARN of the Spot Fleet role required by some accounts when batch_use_spot = true."
  type        = string
  default     = ""
}

variable "batch_instance_types" {
  description = "Instance types for the EC2 compute environment. Must fit batch_vcpus/batch_memory_mb."
  type        = list(string)
  default     = ["m5.xlarge"]
}

variable "batch_min_vcpus" {
  description = "Minimum vCPUs for the EC2 compute environment."
  type        = number
  default     = 0
}

variable "batch_desired_vcpus" {
  description = "Desired vCPUs for the EC2 compute environment."
  type        = number
  default     = 0
}

variable "batch_max_vcpus" {
  description = "Maximum vCPUs for the compute environment."
  type        = number
  default     = 32
}

variable "batch_vcpus" {
  description = "vCPUs requested by each job. Fargate supports 0.25-16."
  type        = number
  default     = 2

  validation {
    condition     = var.batch_vcpus > 0 && var.batch_vcpus <= 16
    error_message = "batch_vcpus must be greater than 0 and at most 16."
  }
}

variable "batch_memory_mb" {
  description = "Memory (MiB) requested by each job. Fargate requires a valid vCPU/memory combination."
  type        = number
  default     = 8192

  validation {
    condition     = var.batch_memory_mb >= 512
    error_message = "batch_memory_mb must be at least 512."
  }
}

variable "batch_ephemeral_storage_gb" {
  description = "Fargate ephemeral storage in GiB (21-200). Large PBF extracts need more than the 20 GiB default."
  type        = number
  default     = 100

  validation {
    condition     = var.batch_ephemeral_storage_gb >= 21 && var.batch_ephemeral_storage_gb <= 200
    error_message = "batch_ephemeral_storage_gb must be between 21 and 200."
  }
}

variable "batch_timeout_seconds" {
  description = "Maximum duration of a single job attempt."
  type        = number
  default     = 21600

  validation {
    condition     = var.batch_timeout_seconds >= 60
    error_message = "batch_timeout_seconds must be at least 60."
  }
}

variable "batch_retry_attempts" {
  description = "Number of attempts (including the first) before a job is failed."
  type        = number
  default     = 3

  validation {
    condition     = var.batch_retry_attempts >= 1 && var.batch_retry_attempts <= 10
    error_message = "batch_retry_attempts must be between 1 and 10."
  }
}

variable "image_tag" {
  description = "Required immutable container image tag deployed to Batch."
  type        = string

  validation {
    condition     = trimspace(var.image_tag) != "" && lower(trimspace(var.image_tag)) != "latest"
    error_message = "image_tag must be a non-empty immutable tag and cannot be latest."
  }
}

variable "image_digest" {
  description = "Optional sha256 image digest. When set, Batch uses the repository digest reference."
  type        = string
  default     = ""

  validation {
    condition     = var.image_digest == "" || can(regex("^sha256:[0-9a-f]{64}$", var.image_digest))
    error_message = "image_digest must be empty or sha256 followed by 64 lowercase hexadecimal characters."
  }
}

variable "ecr_repository_name" {
  description = "ECR repository name."
  type        = string
  default     = "osm-pbf-batch"
}

variable "ecr_image_tag_mutability" {
  description = "ECR tag mutability. IMMUTABLE is recommended once SHA tags are used."
  type        = string
  default     = "IMMUTABLE"

  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.ecr_image_tag_mutability)
    error_message = "ecr_image_tag_mutability must be MUTABLE or IMMUTABLE."
  }
}

variable "ecr_untagged_retention_days" {
  description = "Days after which untagged ECR images are expired."
  type        = number
  default     = 14
}

variable "ecr_max_image_count" {
  description = "Maximum number of tagged images to retain."
  type        = number
  default     = 30
}

variable "output_prefix" {
  description = "Curated S3 prefix written by the pipeline and crawled by Glue."
  type        = string
  default     = "curated"

  validation {
    condition = can(regex("^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$", var.output_prefix)) && alltrue(
      [for segment in split("/", var.output_prefix) : segment != "." && segment != ".."]
    )
    error_message = "output_prefix must be a relative S3 prefix without leading/trailing slashes, empty, '.' or '..' segments."
  }
}

variable "mode" {
  description = "Entity extraction mode: all, nodes, ways or relations."
  type        = string
  default     = "all"

  validation {
    condition     = contains(["all", "nodes", "ways", "relations"], var.mode)
    error_message = "mode must be all, nodes, ways or relations."
  }
}

variable "overwrite" {
  description = "Output overwrite behaviour: error, skip or replace."
  type        = string
  default     = "error"

  validation {
    condition     = contains(["error", "skip", "replace"], var.overwrite)
    error_message = "overwrite must be error, skip or replace."
  }
}

variable "s3_trigger_enabled" {
  description = "Create the S3 -> EventBridge -> Batch trigger for new .osm.pbf objects under region=."
  type        = bool
  default     = true
}

variable "parquet_compression" {
  description = "Parquet compression codec."
  type        = string
  default     = "snappy"

  validation {
    condition     = contains(["snappy", "gzip", "brotli", "lz4", "zstd", "none"], var.parquet_compression)
    error_message = "parquet_compression must be snappy, gzip, brotli, lz4, zstd or none."
  }
}

variable "include_way_geometry" {
  description = "Reconstruct WKT LINESTRING geometry for ways (uses a disk-backed node index)."
  type        = bool
  default     = true
}

variable "log_level" {
  description = "Application log level."
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.log_level)
    error_message = "log_level must be DEBUG, INFO, WARNING, ERROR or CRITICAL."
  }
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention in days."
  type        = number
  default     = 30

  validation {
    condition = contains(
      [1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653],
      var.log_retention_days,
    )
    error_message = "log_retention_days must be a value supported by CloudWatch Logs."
  }
}

variable "raw_retention_days" {
  description = "Days to retain raw PBF extracts before expiry."
  type        = number
  default     = 30
}

variable "staging_retention_days" {
  description = "Days to retain abandoned staging objects in the curated bucket."
  type        = number
  default     = 1

  validation {
    condition     = var.staging_retention_days >= 1
    error_message = "staging_retention_days must be at least 1."
  }
}

variable "curated_noncurrent_version_days" {
  description = "Days to retain non-current versions of curated Parquet objects."
  type        = number
  default     = 30
}

variable "athena_results_retention_days" {
  description = "Days to retain Athena query results in the curated bucket."
  type        = number
  default     = 14
}

variable "athena_workgroup_name" {
  description = "Athena workgroup name."
  type        = string
  default     = "osm-pbf-workgroup"
}

variable "athena_bytes_scanned_cutoff" {
  description = "Per-query bytes-scanned cutoff for the Athena workgroup. 0 disables the cutoff."
  type        = number
  default     = 10737418240

  validation {
    condition     = var.athena_bytes_scanned_cutoff >= 0
    error_message = "athena_bytes_scanned_cutoff must be 0 (disabled) or a positive byte count."
  }
}

variable "glue_database_name" {
  description = "Glue catalog database for curated Parquet."
  type        = string
  default     = "osm_catalog"
}

variable "tags" {
  description = "Tags applied to all taggable resources."
  type        = map(string)
  default = {
    Project = "osm-pbf-data-lake"
    Owner   = "aws-data-engineering"
    Env     = "dev"
  }
}
