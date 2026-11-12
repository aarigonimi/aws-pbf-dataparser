from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "athena" / "real_estate"


def _read(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def test_real_estate_sql_files_exist_and_are_attributed():
    for name in (
        "01_create_neighborhood_pois.sql",
        "02_create_listings.sql",
        "03_score_listings.sql",
        "04_create_marketing_views.sql",
        "05_area_coverage.sql",
        "sample_listings.csv",
        "README.md",
    ):
        assert (SQL_DIR / name).is_file()
    # Files that read OpenStreetMap data carry the attribution.
    for name in (
        "01_create_neighborhood_pois.sql",
        "03_score_listings.sql",
        "04_create_marketing_views.sql",
        "05_area_coverage.sql",
        "README.md",
    ):
        assert "OpenStreetMap" in _read(name)


def test_pois_table_filters_the_exact_partition():
    sql = _read("01_create_neighborhood_pois.sql")

    assert "CREATE TABLE osm_catalog.re_pois_quebec_city_20261108" in sql
    assert (
        "external_location = 's3://<curated-bucket>/derived/re_pois/area=quebec_city/2026/11/08/'"
        in sql
    )
    for partition_filter in (
        "region = 'quebec'",
        "year = '2026'",
        "month = '11'",
        "day = '08'",
        "entity IN ('nodes', 'ways')",
    ):
        assert partition_filter in sql
    assert "ST_Centroid(ST_GeomFromText(geometry))" in sql
    for category in ("school", "grocery", "transit", "green_space", "healthcare", "pharmacy"):
        assert f"'{category}'" in sql


def test_listings_table_is_external_csv_and_synthetic():
    sql = _read("02_create_listings.sql")
    csv = _read("sample_listings.csv")

    assert "CREATE EXTERNAL TABLE osm_catalog.re_listings" in sql
    assert "FIELDS TERMINATED BY ','" in sql
    assert "'skip.header.line.count' = '1'" in sql
    assert "LOCATION 's3://<curated-bucket>/derived/re_listings/'" in sql
    assert "not real properties" in sql
    assert "aws s3 cp sql/athena/real_estate/sample_listings.csv" in sql
    # Eight synthetic listings, L-001 through L-008.
    rows = [line for line in csv.strip().splitlines() if line.startswith("L-")]
    assert len(rows) == 8
    assert [row.split(",")[0] for row in rows] == [f"L-{i:03d}" for i in range(1, 9)]


def test_scores_use_prefilter_exact_distance_and_presence_weights():
    sql = _read("03_score_listings.sql")

    assert "CREATE TABLE osm_catalog.re_listing_scores_quebec_city_20261108" in sql
    assert (
        "external_location = 's3://<curated-bucket>/derived/re_scores/area=quebec_city/2026/11/08/'"
        in sql
    )
    assert "l.lat - 0.0072" in sql
    assert "0.0072 / cos(radians(l.lat))" in sql
    assert "great_circle_distance(l.lat, l.lon, p.lat, p.lon) <= 0.8" in sql
    # Presence-once weights, visible in a weight CTE.
    assert "WITH weights (category, points) AS" in sql
    for weight in ("25", "20", "15", "10"):
        assert weight in sql
    # Every input listing produces exactly one row.
    assert "CROSS JOIN weights w" in sql
    assert "LEFT JOIN tallies t" in sql
    for column in (
        "nearest_school_m",
        "nearest_green_m",
        "nearest_school_name",
        "nearest_green_name",
    ):
        assert column in sql


def test_marketing_views_are_defined():
    sql = _read("04_create_marketing_views.sql")

    assert "CREATE OR REPLACE VIEW osm_catalog.re_family_friendly_quebec_city" in sql
    assert "CREATE OR REPLACE VIEW osm_catalog.re_agent_fact_sheet_quebec_city" in sql
    assert "bedrooms >= 3" in sql
    assert "straight-line distance" in sql
    assert "'unnamed'" in sql


def test_area_coverage_grid_and_director_map():
    sql = _read("05_area_coverage.sql")

    assert "CREATE TABLE osm_catalog.re_area_coverage_quebec_city_20261108" in sql
    assert (
        "external_location = 's3://<curated-bucket>/derived/re_area_coverage/area=quebec_city/2026/11/08/'"
        in sql
    )
    assert "floor(lat / 0.01)" in sql
    assert "floor(lon / 0.01)" in sql
    assert "CREATE OR REPLACE VIEW osm_catalog.re_director_map_quebec_city" in sql
    for label in (
        "'Well served (5-6 of 6)'",
        "'Partly served (3-4 of 6)'",
        "'Thin (1-2 of 6)'",
        "'Our listing'",
    ):
        assert label in sql
    assert "UNION ALL" in sql
