# Clean up a demonstration deployment

`./scripts/cleanup.sh` is interactive and requires the exact phrase
`DESTROY INFRASTRUCTURE`. It runs a destroy plan for review, then invokes
Terraform's interactive destroy. Review every resource before confirming.
This is documentation and a script for the repository user; it was not run in
this review.

Terraform sets `force_destroy = false` on both buckets. If a bucket contains
objects or version history, Terraform should refuse to remove it rather than
purge data. The script does not delete S3 data, versions or delete markers.
The ECR repository also refuses deletion while it contains images. A destroy
can therefore remove compute resources and then stop with retained buckets or
images; review the plan and check the final Terraform result.

Before cleanup, decide whether you need to retain the raw PBF, curated Parquet,
manifests, Athena results or ECR images. Back up anything required. To retain
data while removing compute resources, first plan a Terraform change that
detaches the retained bucket/repository resources from this state; do not
manually remove state entries without a recovery plan.

For a full data purge, first identify the exact bucket names from Terraform
outputs and confirm with the data owner. Versioned S3 buckets require explicit
deletion of object versions and delete markers; `aws s3 rm --recursive` alone
only creates delete markers. Review the version list and delete only after a
separate explicit approval. No data-purge script is provided; the equivalent
commands, for a reader who has confirmed the purge, are:

```bash
for BUCKET in "$RAW_BUCKET" "$OUTPUT_BUCKET"; do
  aws s3api list-object-versions --bucket "$BUCKET" --output json > "/tmp/${BUCKET}.versions.json"
  python3 - "$BUCKET" <<'EOF'
import json, subprocess, sys
bucket = sys.argv[1]
doc = json.load(open(f"/tmp/{bucket}.versions.json"))
objects = [{"Key": v["Key"], "VersionId": v["VersionId"]}
           for field in ("Versions", "DeleteMarkers") for v in doc.get(field, [])]
for i in range(0, len(objects), 1000):
    subprocess.run(["aws", "s3api", "delete-objects", "--bucket", bucket,
                    "--delete", json.dumps({"Objects": objects[i:i+1000], "Quiet": True})],
                   check=True)
print(f"purged {len(objects)} object versions from {bucket}")
EOF
done
```

The ECR repository also refuses deletion while it contains images. Delete the
tagged images you pushed (the repository name is the last path segment of the
`ecr_repository_url` output):

```bash
export ECR_REPOSITORY="${ECR_REPOSITORY_URL##*/}"
aws ecr list-images --repository-name "$ECR_REPOSITORY" --region "$AWS_REGION"
aws ecr batch-delete-image --repository-name "$ECR_REPOSITORY" --region "$AWS_REGION" \
  --image-ids "imageTag=$(git rev-parse HEAD)"
```

Once the buckets and repository are empty, `terraform destroy` (through
`./scripts/cleanup.sh`) removes the stack without forcing data loss.

After infrastructure cleanup, review continuing charges and retained data:

- S3 current/noncurrent objects and versions retained outside Terraform.
- ECR images or repositories retained outside Terraform.
- CloudWatch logs in the Terraform-managed log group are deleted when that
  group is destroyed; export them first if they are needed. External log groups
  remain subject to their configured retention.
- Any Athena query result objects under `athena-results/`.
- Any resources not managed by this Terraform stack.

Terraform state and backups are not cleanup targets. Preserve them according to
your recovery/retention policy; never commit them.
