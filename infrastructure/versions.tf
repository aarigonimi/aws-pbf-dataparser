terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state is strongly recommended. See backend.tf.example and
  # docs/TERRAFORM_RECOVERY.md. The local backend is kept so `terraform
  # validate` works without an existing state bucket.
}
