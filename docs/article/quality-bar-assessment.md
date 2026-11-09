# AWS Builder Center Quality Explainer assessment

Assessment target: [the article](aws-builder-center-article.md). This review checks whether the article teaches a reader to implement the pipeline and reports gaps that still prevent a full PASS.

| Criterion | Status | Evidence |
| --- | --- | --- |
| Working code/config | **PARTIAL** | Actual Python, Dockerfile, Terraform, IAM, CLI, Glue and SQL excerpts are included and checked against the repository. The Docker build could not be run because the local Docker daemon is unavailable. |
| Step-by-step instructions | **PASS** | Sections 3–9 and 12 cover local validation, AWS setup, deployment, image publishing, job execution, cataloging, queries and cleanup. |
| Real engineering experience | **PASS** | Section 7 traces the ECR timeout, endpoint correction, retries, overlapping jobs and S3 publication using historical AWS records. |
| Decisions and trade-offs | **PASS** | Section 2 and the implementation sections explain service choices and trade-offs; three ADRs provide more detail. |
| Public repository | **PARTIAL** | The public repository exists and the article points to it, but the current local changes have not been pushed. |
| Production thinking | **PASS** | Reliability, IAM, network paths, concurrency, partial failures, lifecycle, sizing, observability, costs and limitations are discussed. |
| Deploy to verify | **PARTIAL** | The historical Quebec implementation ran and was validated. Current audit changes to retry rules, the submission guard and file rotation have not been exercised in AWS; deployment and Batch execution were prohibited for this work. |
| Cleanup | **PASS** | Section 12 and `scripts/cleanup.sh` describe reviewed Terraform cleanup, retained S3 versions/data, ECR, logs and continuing charges. |
| Reader outcome | **PARTIAL** | The implementation sequence is present. Current Terraform provider validation and Docker build remain unverified locally, and current local commits have not been pushed. |

## Criterion details

### Working code/config — PARTIAL

- **Evidence:** Article sections 3–6 and 8–9 show code from `src/osm_parser.py`, `src/parquet_writer.py`, `src/pipeline.py`, `Dockerfile`, `infrastructure/*.tf`, `scripts/*.sh`, `sql/athena/validate_entity_counts.sql`, and the Glue/Athena resources. The architecture figure is in `figures/architecture.mmd`.
- **Checks run for this draft:** Python 3.12 `make check` passed after task 8: Ruff check, Ruff format, mypy, and **139 tests passed**. Task 9 changed editorial/benchmark files only. Terraform formatting passed; init/validation could not run because the registry was unreachable and cached provider binaries would not start. No plan/apply was run.
- **AWS scope:** No new AWS API calls were made while drafting this article. Quebec measurements and troubleshooting are presented as historical evidence from the existing benchmark record and prior read-only audit, not as a fresh deployment verification.
- **Gap:** Docker was installed but its daemon was not available. The article says the Docker build and smoke commands were not run. The historical ECR size is clearly labelled as registry evidence.
- **Required improvement:** Run the documented Docker build and smoke commands in an environment with a working daemon before claiming the current image builds.

### Step-by-step instructions — PASS

- **Evidence:** Section 3.8 gives the local quality gate; sections 4–6 cover Docker/ECR, Terraform deployment, input upload, Batch submission and status; sections 8–9 cover Glue and Athena validation; section 12 explains cleanup.
- **Repository files:** `docs/deployment.md`, `docs/execution.md`, `docs/validation.md`, `docs/cleanup.md`, `scripts/`.
- **Gap:** None for the instructions; the published clone URL is `https://github.com/aarigonimi/aws-pbf-dataparser`.
- **Required improvement:** None.

### Real engineering experience — PASS

- **Evidence:** Section 7 includes the actual `GetAuthorizationToken` timeout, explains why it indicates a network failure, correlates failed attempts with endpoint creation and successful starts, and documents the duplicate Quebec job and final manifest. Section 3.5 explains the 300,000-row historical files and the writer correction.
- **Repository files:** `docs/benchmarks/quebec-20261108.json`, `docs/benchmarks/README.md`, `docs/troubleshooting.md`, `infrastructure/endpoints.tf`, `infrastructure/batch.tf`.
- **Qualification:** The endpoint diagnosis is a timestamp and configuration correlation, not a packet capture; the article says that. Historical evidence is preserved; Quebec was not rerun.
- **Required improvement:** None for the article. A fresh small run would validate the newer code but is outside the authorized scope.

### Decisions and trade-offs — PASS

- **Evidence:** Section 2 compares Batch, Lambda, ECS RunTask, Glue/EMR, storage and catalog options. Sections 3, 5, 7 and 11 discuss the shared schema, optional geometry, single-subnet networking, VPC endpoints, retry behavior, staging and non-atomic replacement.
- **Repository files:** `docs/decisions/001-aws-batch-vs-ecs.md`, `002-pbf-to-parquet.md`, `003-s3-publication.md`.
- **Required improvement:** None.

### Public repository — PASS

- **Evidence:** The standalone repository is publicly available at `https://github.com/aarigonimi/aws-pbf-dataparser`. The article links to it and uses `aws-pbf-dataparser` as its checkout directory. The published initial revision is `5d812e6`; current local HEAD is newer and has not been pushed.
- **Gap:** None for repository publication.
- **Required improvement:** None.

### Production thinking — PASS

- **Evidence:** Sections 7 and 11 explain retries, concurrency, best-effort rollback, S3 versioning, IAM boundaries, network paths, lifecycle, compute sizing, logs, unmeasured costs and observability gaps. Limitations include the missing distributed lock, non-atomic `replace`, unmeasured peak memory, mutable historical image tag and leaf-level Glue tables.
- **Repository files:** `infrastructure/iam.tf`, `s3.tf`, `endpoints.tf`, `batch.tf`, `src/pipeline.py`, `docs/ARCHITECTURE.md`, `docs/COST.md`.
- **Required improvement:** A partition lock and safer replacement protocol are valuable follow-up engineering work; the article accurately presents them as limitations.

### Deploy to verify — PARTIAL

- **Evidence:** The historical Quebec run is supported by its S3 manifest, Batch history, CloudWatch lines and Athena count query. Its entity counts match the manifest. The article distinguishes this from the current local audit.
- **Gap:** The amended retry rules, local submission guard and Parquet file-limit fix have not been tested in AWS. No new infrastructure deployment, Batch job, Quebec reprocessing or curated-object mutation was performed.
- **Required improvement:** In a separately approved deployment, run a small new extract using an immutable image tag and record the job ID, attempts, digest, manifest and Athena results. Do not use the historical Quebec partition for this check.

### Cleanup — PASS

- **Evidence:** Section 12 shows the interactive cleanup script and explains `force_destroy = false`, object versions/delete markers, ECR image retention, log export, state retention and post-destroy checks.
- **Repository files:** `scripts/cleanup.sh`, `docs/cleanup.md`, `infrastructure/s3.tf`.
- **Gap:** The cleanup procedure was reviewed but not run.
- **Required improvement:** None for the article; a reader must review the actual destroy plan before confirming cleanup.

### Reader outcome — PARTIAL

- **Evidence:** The article gives the implementation sequence from environment setup through Athena counts and cleanup, with executable commands and configuration examples.
- **Gap:** The current Docker image build is unverified, and local commits have not been pushed. The article cannot yet promise a reader a fully reproduced result from the current repository revision.
- **Required improvement:** Validate the current Docker build. A future authorized AWS smoke run would close the remaining live-verification gap for the current changes.

## Verdict

**CONDITIONAL PASS — Specific improvements required.** The article has implementation depth and traceable historical evidence. The current Docker build and Terraform schema validation remain unverified locally; newer AWS behavior also remains untested by design. Push and preview the final revision before submission.
