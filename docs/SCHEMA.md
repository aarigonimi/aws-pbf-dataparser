# Dataset schema (v1.0.0)

Every entity partition uses the same explicit PyArrow schema. This keeps the
Athena/Databricks contract stable and lets readers union partitions without
schema reconciliation.

## Columns

| Column | Arrow type | Nullable | Notes |
| --- | --- | --- | --- |
| `osm_id` | `int64` | no | OSM element id |
| `osm_type` | `string` | no | `node`, `way` or `relation` |
| `name` | `string` | yes | `tags["name"]` |
| `amenity` | `string` | yes | `tags["amenity"]` |
| `shop` | `string` | yes | `tags["shop"]` |
| `tourism` | `string` | yes | `tags["tourism"]` |
| `building` | `string` | yes | `tags["building"]` |
| `highway` | `string` | yes | `tags["highway"]` |
| `surface` | `string` | yes | `tags["surface"]` |
| `latitude` | `float64` | yes | Nodes only; null for ways/relations |
| `longitude` | `float64` | yes | Nodes only; null for ways/relations |
| `geometry` | `string` | yes | WKT: `POINT` for nodes, optional `LINESTRING` for ways |
| `node_refs` | `list<int64>` | yes | Way node ids in order |
| `members` | `list<string>` | yes | Relation members, each a JSON object |
| `tag_count` | `int32` | yes | Number of normalized tags |
| `tags` | `string` | yes | Full tag map as canonical JSON |

## Partitions

```text
curated/region=<region>/ymd=<YYYYMMDD>/entity=<entity>/part-00000.parquet
```

Hive partition columns inferred by Athena/Spark/Databricks:

| Partition | Example | Notes |
| --- | --- | --- |
| `region` | `monaco` | Logical source region |
| `ymd` | `20261108` | Extract date, `YYYYMMDD` |
| `entity` | `nodes` | `nodes`, `ways` or `relations` |

`entity` is both a partition and represented by `osm_type`. `osm_type` uses
singular values (`node`, `way`, `relation`).

## Encodings

- `tags` is a JSON object string with sorted keys and compact separators, for
  example `{"amenity":"cafe","name":"Sample"}`. It is not a Parquet map, which
  keeps the schema identical across engines and avoids per-row map overhead.
- `members` is a list of JSON strings:
  `{"ref":10,"role":"outer","type":"w"}`. The member `type` preserves
  the one-character OSM/PyOsmium value: `n` (node), `w` (way), or `r` (relation).
- `geometry` uses WKT with longitude first: `POINT (lon lat)` and
  `LINESTRING (lon lat, lon lat, ...)`.
- Tag values are normalized to strings. Sequence values are joined with
  `, `.

## Manifest

`_manifest.json` is written last and contains:

- `status`: `success` when `total_records > 0`, otherwise `empty`.
- `schema_version`: `1.0.0`.
- `pipeline_version`.
- `region`, `ymd`, `run_id`, timestamps and durations.
- Source bucket/key/bytes.
- Output bucket/prefix, compression, overwrite mode, geometry flag, entity list.
- `record_counts`, `total_records`, `total_output_bytes`.
- Per-file entity, final S3 key, bytes, records.
- Processor counts and timings.

Readers should query a partition only after its final manifest exists. Athena
does not use the manifest as a visibility gate; direct queries can observe
partial output during publication.

## Athena DDL example

Terraform creates `osm_catalog.osm_curated` with this explicit schema and
partition projection. The `region` and `ymd` projection types are `injected`,
so queries must supply both equality filters. `entity` is an enum of the three
supported partition directories:

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS osm_catalog.osm_curated (
  osm_id bigint,
  osm_type string,
  name string,
  amenity string,
  shop string,
  tourism string,
  building string,
  highway string,
  surface string,
  latitude double,
  longitude double,
  geometry string,
  node_refs array<bigint>,
  members array<string>,
  tag_count int,
  tags string
)
PARTITIONED BY (region string, ymd string, entity string)
STORED AS PARQUET
LOCATION 's3://<curated-bucket>/curated/'
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.region.type' = 'injected',
  'projection.ymd.type' = 'injected',
  'projection.entity.type' = 'enum',
  'projection.entity.values' = 'nodes,ways,relations',
  'storage.location.template' = 's3://<curated-bucket>/curated/region=${region}/ymd=${ymd}/entity=${entity}/'
);
```

The Terraform table uses the same data columns and partition keys, with
projection parameters and an S3 location template. Filter by `entity` when you
want a single element type:

```sql
SELECT * FROM osm_catalog.osm_curated
WHERE region = 'monaco' AND ymd = '20261108' AND entity = 'nodes';
```

This projected table is implemented in the repository but has not been
deployed or verified in AWS.

## Databricks

```sql
CREATE TABLE IF NOT EXISTS osm.curated
USING parquet
PARTITIONED BY (region, ymd, entity)
LOCATION 's3://<curated-bucket>/curated/';
```

Or query the whole curated prefix and let Spark discover partitions:

```sql
SELECT * FROM parquet.`s3://<curated-bucket>/curated/` LIMIT 10;
```

## Evolution policy

- Bump `SCHEMA_VERSION` for any column addition/removal/type change.
- Prefer additive nullable columns so old and new partitions can coexist.
- Do not rename partition columns without a migration; readers depend on
  `region`, `ymd` and `entity`.
- Keep `tags`/`members` JSON encodings stable or bump the schema version.
