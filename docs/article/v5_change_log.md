# V5 Editorial Change Log — *What's Around This House? Querying OpenStreetMap with SQL on AWS*

**Baseline:** `docs/article/article_v4.pdf` (15 pages)
**Deliverable:** `docs/article/article_v5.pdf` and `docs/article/article_v5.md` (15 pages)

---

## Summary of Scope

V5 is a targeted editorial refinement of V4. All 15 section headings, the full-width architecture diagram, all charts and AWS console screenshots, the cost table, all Terraform/CLI/SQL blocks, and all measured AWS and Athena metrics are preserved unchanged.

---

## Page-by-Page Changes

### Page 1 — Title, Repository Callout, `What the brokerage needs to know`, `Why bother with SQL at all?`
- **Text removed:** Removed the parenthetical valuation disclaimer `(they do not estimate property value or market prices)` and the mention of connecting a BI tool later from the closing paragraph of `What the brokerage needs to know` (the valuation disclaimer already appears on Page 11 where the score weights are introduced).
- **Text rewritten:** Simplified the final paragraph of `What the brokerage needs to know` into three concise, natural sentences separating the synthetic brokerage scenario from the real AWS execution measurements:
  > *"My work ends at the datasets, which the analyst queries in Athena, adjusts in SQL or exports to CSV. The brokerage scenario and the eight listings in `sample_listings.csv` are synthetic examples used to illustrate how downstream SQL queries consume the curated table. All Batch executions, Athena measurements and deployment issues below come from actual runs in my AWS account."*
- **Text retained unchanged:** Article title, repository callout, opening brokerage questions, EventBridge/Batch/Athena overview, and the opening of `Why bother with SQL at all?`.
- **Pagination added:** Added discreet bottom-right footer `1 / 15`.

### Page 2 — `Why bother with SQL at all?` (cont.), `Picking the services`
- **Text removed:** None.
- **Text rewritten:** None.
- **Text retained unchanged:** Geofabrik snapshot explanation, PBF primitive mapping (`Nodes`, `Ways`, `Relations`), public OSM dataset note, and the service comparison (`AWS Lambda`, `AWS Glue ETL or Amazon EMR`, `Amazon ECS on Fargate`, `AWS Batch on Fargate`).
- **Pagination added:** Added discreet bottom-right footer `2 / 15`.

### Page 3 — `Picking the services` (cont.), `A new file starts the conversion`
- **Text removed:** None on Page 3 (the 5-bullet repository scope inventory that previously started at the bottom of Page 3 / top of Page 4 was removed; see Page 4).
- **Text rewritten:** None.
- **Text retained unchanged:** Discussion of `Array jobs` and `Fargate Spot`, Glue partition projection and Athena workgroup scan cap, container sizing note (`2 vCPU, 8 GiB of memory and 100 GiB of ephemeral storage`), the full-width architecture diagram (`assets/images/architecture.webp`), and the EventBridge lead-in.
- **Pagination added:** Added discreet bottom-right footer `3 / 15`.

### Page 4 — `A new file starts the conversion` (cont.), `Deploy the stack`
- **Text removed:** Removed the standalone 5-item repository scope inventory (`"To keep the scope clear before you deploy, here is what the repository leaves out by design: ..."`), as each of those points (`make run` upload, manual SQL execution, Athena handoff, WKT `LINESTRING` way geometry, and non-reconstructed relations) is already explained in context where it occurs in the walkthrough.
- **Text rewritten:** None.
- **Text retained unchanged:** `infra/trigger.tf` EventBridge rule snippet, input transformer explanation, `Deploy the stack` prerequisites, `include_way_geometry = true` configuration note, clone/deploy/build commands, and VPC endpoint item 1 (`ecr.api`).
- **Pagination added:** Added discreet bottom-right footer `4 / 15`.

### Page 5 — `Deploy the stack` (cont.), `Drop an extract in the bucket`, `What the runs did`
- **Text removed:** Removed parenthetical raw exact integer counts and raw seconds from prose in the Québec run bullet (`(138,606,771 nodes, 9,897,180 ways and 194,419 relations)` and `5,531 s`), keeping human-friendly rounded prose numbers (`148.7M entities`, `138.6M nodes, 9.9M ways and 194K relations`, `92.2 minutes`, `1 h 39 m (98.7 minutes)`).
- **Text rewritten:** None.
- **Text retained unchanged:** VPC endpoints 2–4 (`ecr.dkr`, `logs`, `s3`), PrivateLink pricing explanation (`$0.01 per hour`, `~$0.72 per day total for all three`), Monaco smoke test commands, Québec provincial run commands, and `What the runs did` execution summary.
- **Pagination added:** Added discreet bottom-right footer `5 / 15`.

### Page 6 — `What the runs did` (cont.)
- **Text removed:** Removed the third bullet (`Repository defaults updated after the initial run`) comparing historical `300,000`-row vs. `250,000`-row writer rotation and historical `include_way_geometry = false` vs. `true` defaults, and removed the parenthetical mention of disabled way geometry and the unused London benchmark file from the first bullet.
- **Text rewritten:** Streamlined the first bullet (`Different datasets and run conditions`) to focus strictly on the Monaco and Québec runs shown in the article (overlapping initial Québec jobs before partition locking and the ~28 s Fargate startup share of Monaco's 31 s wall-clock runtime).
- **Text retained unchanged:** Log-scale comparison chart (`Monaco smoke test vs. Québec province run`), `Why Parquet is larger than the PBF input`, the execution-stage breakdown chart (`Québec province run: where execution time went`), and the four runtime stage descriptions (`Download from S3`, `Stream parse and write staged Parquet`, `Publish copy to curated prefix`, `Manifest write and exit`).
- **Pagination added:** Added discreet bottom-right footer `6 / 15`.

### Page 7 — AWS Batch & CloudWatch Screenshots, `Check the output in Athena`
- **Text removed:** Removed parenthetical raw integer counts (`(138,606,771)`, `(9,897,180)`, `(194,419)`, `(148,698,370)`) from the prose paragraph below the Athena row-count query, keeping `138.6M nodes, 9.9M ways and 194K relations for 148.7M total records` (the exact unrounded figures remain visible right below in the CloudWatch and Athena console screenshots).
- **Text rewritten:** None.
- **Text retained unchanged:** AWS Batch job screenshot (`9508f328-f3c1-4e5c-aa3f-39be8946eb8f`), CloudWatch Logs screenshot, `Check the output in Athena` SQL query, and partition projection / Parquet footer explanation.
- **Pagination added:** Added discreet bottom-right footer `7 / 15`.

### Page 8 — Athena Row-Count Screenshot, Coordinate Audit, `Issues to watch out for`
- **Text removed:** Removed the historical configuration discussion after the geometry audit query (`"In my initial provincial run (executed before include_way_geometry = true was made the default in Terraform), ways_with_geometry returned 0..."`), leaving only the measured coordinate audit result.
- **Text rewritten:** Condensed the audit result into a single factual sentence:
  > *"Auditing all 138.6M nodes scanned 2.73 GB in 2.0 s and found **0** nodes missing coordinates and **0** values outside valid latitude/longitude bounds."*
- **Text retained unchanged:** Athena console screenshot, `ways_with_geometry` SQL query, `Issues to watch out for` intro, and `The job never starts, and there are no logs` (`ResourceInitializationError`, `assignPublicIp = DISABLED`, and the four VPC endpoints).
- **Pagination added:** Added discreet bottom-right footer `8 / 15`.

### Page 9 — `The job never starts, and there are no logs` (cont.), `Retry only what a retry can fix`
- **Text removed:** None.
- **Text rewritten:** Reordered and tightened the two paragraphs following the `retry_strategy` HCL block so the real duplicate Monaco upload experience leads the explanation of why the final catch-all `on_exit_code = "*"` (`EXIT`) rule matters, followed by why `TransientError` (exit code `75`) is raised before the generic `except` block during S3 uploads.
- **Text retained unchanged:** S3 gateway endpoint layer-download note, `Retry only what a retry can fix` opening, and the `retry_strategy` Terraform snippet.
- **Pagination added:** Added discreet bottom-right footer `9 / 15`.

### Page 10 — `From Parquet to datasets`
- **Text removed:** Removed parenthetical raw integer counts `(2,994)` and `(2,332)` in prose, keeping `~3K POIs (2.3K transit stops, 283 grocery stores, 165 green spaces, 118 pharmacies, 59 healthcare facilities and 37 schools)`.
- **Text rewritten:** Replaced mechanical sequence transitions (`"First, 01_create_neighborhood_pois.sql..."`, `"Next, upload the eight sample listings..."`, `"Then 03_score_listings.sql..."`) with transitions driven by the data transformation at each step (`"Querying the entire 6.45 GB province partition on every analyst lookup would be wasteful, so 01_create_neighborhood_pois.sql..."`, `"With the city POIs materialized, upload the sample listings CSV..."`, `"To match each property against nearby amenities, 03_score_listings.sql..."`).
- **Text retained unchanged:** All SQL and CLI snippets (`01_create_neighborhood_pois.sql`, `02_create_listings.sql`, `03_score_listings.sql`), `ST_Centroid(ST_GeometryFromText(geometry))` caveating, bounding-box pre-filter explanation, and Athena scan/runtime metrics (`1.80 GB in 8.7 s`, `50 KB`).
- **Pagination added:** Added discreet bottom-right footer `10 / 15`.

### Page 11 — `From Parquet to datasets` (cont.), `What the datasets showed`
- **Text removed:** None.
- **Text rewritten:** Replaced the mechanical transition `"After scoring the listings, 04_create_marketing_views.sql creates..."` and `"Finally, 05_area_coverage.sql..."` with `"Two scripts then shape those scored results for the three teams. 04_create_marketing_views.sql defines... 05_area_coverage.sql buckets..."`.
- **Text retained unchanged:** Bounding-box SQL join block, category point-cap rules and illustrative-score caveat (`81 KB and finished in 1.6 s`), audit query for `L-001`, and the `What the datasets showed` summary rows for `L-001`, `L-003`, and `L-004`.
- **Pagination added:** Added discreet bottom-right footer `11 / 15`.

### Page 12 — `What the datasets showed` (cont.), `Hand the datasets to the analyst`
- **Text removed:** None.
- **Text rewritten:** Converted the 3-item numbered list at the end of `What the datasets showed` into three natural narrative paragraphs explaining what the `L-001` audit rows revealed (`CPE Les Petits Cheminots` tagged `amenity=kindergarten` at 783 m, the `unnamed` park node at 170 m handled via `coalesce(nearest_green_name, 'unnamed')`, and retail chains — 32 *Couche-Tard*, 22 *Familiprix*, 19 *Jean Coutu* — plus 5 `access=private` nodes).
- **Text retained unchanged:** Neighborhood score bar chart (`Eight sample listings. Green = on the family-friendly shortlist`), `re_family_friendly_quebec_city` shortlist explanation (`L-001` and `L-003` vs. `L-004` and `L-007`), and the opening of `Hand the datasets to the analyst`.
- **Pagination added:** Added discreet bottom-right footer `12 / 15`.

### Page 13 — `Hand the datasets to the analyst` (cont.)
- **Text removed:** None on Page 13 (the hypothetical QuickSight/BI sentence at the end of `Hand the datasets to the analyst` was removed from the closing paragraph at the top of Page 14).
- **Text rewritten:** None.
- **Text retained unchanged:** Analyst view list, director's summary SQL query, horizontal bar chart (`Québec City grid cells by how many of the six categories they have`), grid cell counts (`0.68 KB`, `381 populated grid cells`: `16` well served, `74` partly served, `291` thin, `8` listings), urban-planning proxy caveat paragraph, and the Athena console screenshot for `re_director_map_quebec_city`.
- **Pagination added:** Added discreet bottom-right footer `13 / 15`.

### Page 14 — `Hand the datasets to the analyst` (cont.), `What it cost me`, `Clean up`
- **Text removed:** Removed the hypothetical sentence `"If the team connects Amazon Quick Sight or another BI tool later, it reads these same views without changing the ingestion pipeline"` from the closing paragraph of `Hand the datasets to the analyst`.
- **Text rewritten:** None.
- **Text retained unchanged:** Derived Parquet scan cost note (`< 1 KB`), `"© OpenStreetMap contributors"` attribution requirement, the full `What it cost me` table and `$0.27` / `$0.72 per day` summary, and the `Clean up` section (`make destroy` and `describe-vpc-endpoints`).
- **Pagination added:** Added discreet bottom-right footer `14 / 15`.

### Page 15 — `Wrapping up`, Attribution & References
- **Text removed:** None.
- **Text rewritten:** Added one closing sentence at the end of the second paragraph of `Wrapping up` to connect the engineering pipeline back to the brokerage workflow:
  > *"Instead of dealing with raw `.osm.pbf` files, the analyst can now compare listings, adjust radius thresholds and explore nearby amenities directly in SQL."*
- **Text retained unchanged:** First paragraph of `Wrapping up`, the two engineering lessons (private Fargate networking + exit-code retry rules, and materializing the 50 KB city-level POI table), ODbL attribution, and documentation links.
- **Pagination added:** Added discreet bottom-right footer `15 / 15`.
