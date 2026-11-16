# Contributing

Thanks for improving the OSM PBF data lake. Keep changes focused, preserve
the documented Parquet and manifest contracts, and do not include regional
PBF files, generated Parquet, Terraform state or AWS credentials.

## Development checks

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
make check
terraform -chdir=infra validate
```

The Terraform validation target initializes providers without a remote
backend. It does not plan or change infrastructure. A real PBF parse requires
PyOsmium and a small test extract; do not use the historical Quebec dataset as
a local test fixture.

For changes to output schemas or publication semantics, update the schema
documentation, tests and benchmark format notes. Never rewrite historical
benchmark measurements to match a code change.

## Pull requests

- Explain the problem and the implementation choice.
- Include test and validation results, including any checks not run.
- Document AWS behavior as observed or inferred; label inference.
- Do not include credentials, account IDs, private bucket names, state or plan
  files.

The project uses the existing MIT software license. OpenStreetMap data remains
subject to the ODbL and its attribution/share-alike terms.
