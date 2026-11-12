-- 02_create_listings.sql
-- Upload: aws s3 cp sql/athena/real_estate/sample_listings.csv "s3://${OUTPUT_BUCKET}/derived/re_listings/"
-- Note: sample listings are synthetic examples, not real properties.

CREATE EXTERNAL TABLE osm_catalog.re_listings (
    listing_id string,
    label string,
    lat double,
    lon double,
    bedrooms int,
    list_price int
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
LOCATION 's3://<curated-bucket>/derived/re_listings/'
TBLPROPERTIES ('skip.header.line.count' = '1');
