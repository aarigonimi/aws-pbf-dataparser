# Article review checklist

Use this before submitting `aws-builder-center-article.md` to AWS Builder Center (Community Builder Speed Run 2).

## Publication blockers

- [ ] Publish this project folder as the root of its own public Git repository. Do not publish the containing workspace.
- [x] Replace the article's repository placeholders with `https://github.com/aarigonimi/aws-pbf-dataparser` and use `aws-pbf-dataparse` as the local clone directory.
- [ ] Review the staged publication tree; exclude Terraform state and backups, plans, local tfvars, `.terraform/`, local environment files, PBFs and Parquet outputs.
- [ ] Build the current Docker image and run its documented smoke commands with Docker available.
- [ ] In a separately approved AWS run, test a new small extract with an immutable image tag and save the job ID, attempts, digest, manifest and Athena counts. Do not use or overwrite the historical Quebec partition.

## Technical accuracy checked for this draft

- [x] Python 3.12 `make check`: Ruff check, formatting, mypy and 51 passing tests.
- [x] Python compilation and dependency consistency (`compileall`, `pip check`).
- [x] Terraform 1.11.4 formatting, backend-disabled init and validation passed; no plan or apply was run.
- [x] Docker limitation is stated accurately: daemon unavailable, so the current image build and smoke commands were not run.
- [x] Historical Quebec counts, sizes and durations are marked by source; derived values show their formulas; costs are unavailable.
- [x] The ECR network diagnosis is described as a timestamp/configuration correlation, not packet-capture proof.
- [x] The Quebec overlap, retry history, mutable image tag and untested repository changes are disclosed.
- [x] The article preserves the ODbL attribution and does not imply the software license covers OSM data.
- [x] No Databricks, Delta Lake or Lakebase references were added.

## Security and editorial review

- [x] Account and bucket identifiers in the article and benchmark JSON are replaced with placeholders.
- [x] Local Terraform state and backups were left untouched and remain ignored by Git.
- [x] No screenshot is included. Scan any future screenshot for account IDs, ARNs, bucket names and query output before publication.
- [ ] Preview the article in Builder Center and confirm Mermaid renders; if not, export `figures/architecture.mmd` to an image.
- [ ] Confirm the final event tags and submission length against the current Builder Center instructions.
- [ ] Confirm the public repository URL and add the tag/revision described by the article after the first push is complete.

See [quality-bar assessment](quality-bar-assessment.md) for criterion-by-criterion evidence and current verdict.
