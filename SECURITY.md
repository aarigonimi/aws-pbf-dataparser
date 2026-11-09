# Security policy

## Supported versions

Security fixes are made against the current default branch. This proof of
concept does not publish production support commitments.

## Reporting a vulnerability

Do not post credentials, access keys, state files or exploitable details in a
public issue. Use GitHub's private vulnerability reporting for this
repository, if enabled, or contact the maintainers privately through the
repository owner.

## Security practices

- Authenticate through AWS CLI profiles or IAM Identity Center; never commit
  keys or put credentials in `.env` or Terraform variables.
- Keep Terraform state and plans private and out of Git.
- Review IAM and the Terraform plan before deployment.
- The example stack blocks public S3 access, enforces TLS, enables SSE-S3 and
  uses workload roles. The Batch security group's default egress is open and
  should be tightened for environments that require restricted networking.
- S3 versioning is recovery support, not a substitute for a backup policy.
