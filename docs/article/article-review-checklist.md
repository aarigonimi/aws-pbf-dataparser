# Article review checklist

Use this before submitting `aws-builder-center-article.md` to AWS Builder Center (Community Builder Speed Run 2).

## Publication blockers

- [x] Publish this project folder as the root of its own public Git repository. Do not publish the containing workspace.
- [x] Use `https://github.com/aarigonimi/aws-pbf-dataparser` and `aws-pbf-dataparser` as the clone directory.
- [ ] Review the final staged publication tree; exclude Terraform state/backups, plans, local tfvars, `.terraform/`, local environment files, PBFs and Parquet outputs.
- [ ] Build the current Docker image and run its documented smoke commands with Docker available.
- [ ] In a separately approved AWS run, test a new small extract with an immutable image tag and save the job ID, attempts, digest, manifest and Athena counts. Do not use or overwrite the historical Quebec partition.
- [ ] Verify that `exists()` returns `False` for a missing manifest under the deployed IAM policy.
- [ ] Deploy the projected Glue table and query two regions/dates to verify partition projection.
- [ ] Record peak memory/CPU and actual cost for one clean, single-job run.

## Technical accuracy checked for this draft

- [x] Python 3.12 `make check`: Ruff check, formatting, mypy and 139 passing tests at the end of task 8; task 9 changed docs and benchmark records only.
- [ ] Python compilation and dependency consistency (`compileall`, `pip check`) were not rerun after tasks 7–9.
- [ ] Terraform format passed locally, but init/validation could not run because the registry is unreachable and cached provider binaries fail to start; CI validates Fargate and EC2 configurations.
- [ ] Docker limitation is recorded accurately: daemon unavailable, so the current image build and smoke commands were not run.
- [x] Historical Quebec counts, sizes and durations are marked by source; derived values show their formulas; costs are unavailable.
- [x] The ECR network diagnosis is described as a timestamp/configuration correlation, not packet-capture proof.
- [x] The Quebec overlap, retry history, historical mutable image tag, and unverified current repository changes are disclosed.
- [x] The article preserves the ODbL attribution and does not imply the software license covers OSM data.
- [x] No Databricks, Delta Lake or Lakebase references were added.

## Security and editorial review

- [x] Account and bucket identifiers in the article and benchmark JSON are replaced with placeholders.
- [x] Local Terraform state and backups were left untouched and remain ignored by Git.
- [ ] No screenshot is included; scan future Builder Center assets for account IDs, ARNs, bucket names and query output.
- [ ] Preview the article in Builder Center and confirm Mermaid renders; if not, export `figures/architecture.mmd` to an image.
- [ ] Confirm the final event tags and submission length against the current Builder Center instructions.
- [x] Confirm the repository URL and initial public revision `5d812e6`.
- [ ] Push current local HEAD and update the public revision reference.

See [quality-bar assessment](quality-bar-assessment.md) for criterion-by-criterion evidence and current verdict.
