# Editorial Changelog — Article V4

**Article:** *What's Around This House? Querying OpenStreetMap with SQL on AWS*
**Deliverables:** `docs/article/article_v4.md` and `docs/article/article_v4.pdf` (15 pages)

---

## 1. What Was Preserved from V1

- **All 15 original section titles verbatim and in order:**
  1. `What the brokerage needs to know`
  2. `Why bother with SQL at all?`
  3. `Picking the services`
  4. `A new file starts the conversion`
  5. `Deploy the stack`
  6. `Drop an extract in the bucket`
  7. `What the runs did`
  8. `Check the output in Athena`
  9. `Issues to watch out for` (`The job never starts, and there are no logs` and `Retry only what a retry can fix`)
  10. `From Parquet to datasets`
  11. `What the datasets showed`
  12. `Hand the datasets to the analyst`
  13. `What it cost me`
  14. `Clean up`
  15. `Wrapping up`
- **15-page layout and visual identity:** Preserved V1's 15-page A4 pacing, typography (`10.45pt` body, `1.51` line-height), code block styling, and generous white space.
- **Full-width architecture diagram (`assets/images/architecture.webp`):** Restored and expanded on Page 3 (`width: calc(100% + 14mm); max-height: none;`) so it is larger than V1 (and significantly larger than V3), preserving its native `3200 × 1520` aspect ratio with zero clipping and crisp labels at 100% zoom.
- **Original charts, screenshots, and single cost table:** Retained all V1 visual assets (`monaco-vs-quebec.png`, `quebec-timing.png`, `batch-quebec-succeeded.png`, `cloudwatch.png`, `athena-entity-counts.png`, `listing-scores.png`, `coverage-layers.png`, `athena-views-director-map.png`) at full column width and kept the single AWS cost breakdown table under `What it cost me` without adding any new tables.
- **First-person narrative and practical workflow:** Preserved the Québec City real-estate brokerage storyline, all reproducible CLI/Terraform/SQL snippets, and the concrete `L-001` audit findings (CPE daycare tag semantics, unnamed green spaces, retail chains vs. duplicates, and `access=private` nodes).

---

## 2. What Was Improved Using V3

- **OpenStreetMap geometry accuracy (`Why bother with SQL at all?`, `Check the output in Athena`, `From Parquet to datasets`):**
  - Clarified that nodes carry point coordinates (`latitude`, `longitude`), ways carry ordered node references (`node_refs`) resolved via PyOsmium's disk-backed `sparse_file_array` index into WKT `LINESTRING` strings when `include_way_geometry = true`, and closed ways remain closed `LINESTRING` geometries rather than validated `POLYGON` objects.
  - Clarified that relations retain `members` and `tags` with `geometry = NULL` (multipolygons are not reconstructed).
  - Explained that `ST_Centroid(ST_GeometryFromText(geometry))` computes a polyline vertex centroid approximation, which may not lie inside a concave boundary or at a park's entrance.
- **Benchmark comparability caveats (`What the runs did`):**
  - Added concise caveats directly below the benchmark chart explaining the writer rotation change (`300,000`-row rotation with `include_way_geometry = false` on the historical Québec and London runs vs. `250,000`-row rotation on the current code run for Monaco, where all 41.8K nodes fit in a single file).
  - Noted that two historical Québec jobs overlapped before partition locking was added, and that ~28 s of Monaco's 31 s Batch wall-clock time is Fargate startup overhead.
  - Explained why the 1.17 GB PBF expands to 6.454 GB of Snappy-compressed Parquet (dense protobuf delta encoding and string tables vs. explicit columnar projection and JSON tags).
- **S3 staging, conditional locking, and manifest publication (`What the runs did`, `Check the output in Athena`, `Issues to watch out for`):**
  - Clarified that S3 multi-object copy from `_staging/<run_id>/` to `curated/` is not an atomic transaction; `_manifest.json` is written last as the completion marker, and Athena reads Parquet files directly without checking `_manifest.json`.
  - Documented the startup `_lock.json` conditional write (`If-None-Match: "*"`) paired with exit code `4` (`OutputConflictError`).
- **Location score qualification (`From Parquet to datasets`):**
  - Qualified the 0–100 proximity score as an illustrative SQL heuristic using example business weights (`25/20/20/15/10/10`) that are not statistically validated, do not estimate property value, and are not an official neighborhood quality index.
- **Geographic coverage grid qualification (`Hand the datasets to the analyst`):**
  - Qualified the `0.01°` (~1.1 km × 0.76 km) grid in `re_director_map_quebec_city` as an analytical proxy whose classifications depend on the six chosen POI categories, grid size, and category thresholds, omit empty cells, and do not capture population density, street networks, physical barriers (highways, rivers, Québec City cliffs), service quality, opening hours, or travel time.

---

## 3. How the Original Reviewer Feedback Was Addressed

- **Meaningful business problem first:** Grounded the opening in the three stakeholder questions (agents, marketing, director) and explicitly separated the synthetic eight-listing example (`sample_listings.csv`) from the measured AWS runs.
- **Why SQL and Athena matter:** Explained how registering curated Parquet in the Glue Data Catalog lets analysts modify distance thresholds, inspect category rules, and audit matched POIs directly in SQL without filing engineering tickets.
- **Service tradeoffs tied to workload behavior:** Connected the single-stream, disk-backed PyOsmium pass directly to why Lambda (15-min / 10 GB cap) and Glue ETL / EMR (multi-executor Spark on a single stream) do not fit, why Batch on Fargate beats raw ECS (managed queueing and `evaluate_on_exit` rules) and Fargate Spot (no mid-stream interruption on a $0.21 monthly run), and why Glue partition projection + Athena fits a monthly refresh better than an always-on database.
- **Understandable benchmarks and SQL verification:** Paired the run charts with stage-by-stage timing (download, parse/stage, copy, manifest) and connected every Athena query to the verification question it answers (row-count parity against `_manifest.json`, node/way geometry audit, POI category filtering, proximity scoring, and `L-001` raw feature inspection).
- **Practical troubleshooting and consistent conclusion:** Kept the `ResourceInitializationError` VPC endpoint diagnosis and Batch `evaluate_on_exit` catch-all rule focused on symptom, root cause, and fix, and closed `Wrapping up` with the two concrete engineering lessons from the build.

---

## 4. What Was Changed to Improve Readability Over V3

- **Eliminated V3's visual compression:** Removed the `max-height: 215px` image constraint from V3 that had shrunk the architecture diagram and screenshots.
- **Replaced dense numbered checklists in `From Parquet to datasets`:** Converted the six-item numbered wall in `From Parquet to datasets` into short, natural 3–5 line narrative paragraphs around the representative SQL snippets while keeping every script and command reproducible.
- **Removed escaped dollar-sign artifacts (`\$`):** Fixed literal `\$` sequences that had rendered as visible backslashes (`\$0.21`, `\$449K`) in V3's PDF.
- **Removed LLM-style filler phrases from V1:** Replaced phrases such as *"so the goal of this project is straightforward"*, *"That takes two steps"*, *"The takeaway is simple"*, and *"the data engineer gets out of the way"* with direct technical prose.

---

## 5. Discrepancies Between V1 and V3 Flagged

1. **Monaco run figures (way geometry enabled vs. disabled):**
   - **V1** reports the EventBridge-triggered Monaco smoke test run with `include_way_geometry = true`: **2.8 s** parse time, **31 s** (31.14 s) Batch wall-clock time, and **3.1 MB** (3.13 MB) across 3 Parquet files.
   - **V3 (7-page draft)** reports the earlier Monaco validation benchmark (`monaco-20261110T023307Z`) run with `include_way_geometry = false`: **2.369 s** parse time, **30.418 s** Batch wall-clock time, and **2.563 MB** across 3 Parquet files.
   - **How V4 handles this:** V4 keeps V1's EventBridge smoke test figures (**2.8 s**, **3.1 MB**, **31 s** Batch wall-clock) to match V1's narrative and chart (`monaco-vs-quebec.png`), while parenthetically noting the `2.4 s` / `2.56 MB` result when way geometry is disabled so both records are reconciled transparently.
2. **Historical London run reference:**
   - **V1** focuses on Monaco (smoke test) and Québec (provincial run) in its prose and charts.
   - **V3 (7-page draft)** includes a third historical run for London (`13,346,901` entities, `46` Parquet files, `588.846 MB`, `549.270 s` parse / `604.629 s` Batch duration) that also used the older `300,000`-row writer configuration without Athena count verification.
   - **How V4 handles this:** V4 preserves V1's two-region chart (`monaco-vs-quebec.png`) without adding a benchmark table, and notes the historical 13.35M-entity London run inside the writer-rotation caveat bullet as required by Section 4.C of the brief.
3. **Terraform directory name (`infra/` vs. `infrastructure/`):**
   - **V1** and the repository use `infra/` (and `Makefile` targets `make deploy`, `make build`, `make run`, `make verify`, `make destroy`).
   - **V3 (7-page draft)** used `infrastructure/` in manual CLI commands.
   - **How V4 handles this:** V4 preserves V1's `infra/` paths and `make` workflow.
