resource "aws_glue_catalog_database" "osm_catalog" {
  name = var.glue_database_name

  tags = var.tags
}

resource "aws_glue_catalog_table" "osm_curated" {
  name          = "osm_curated"
  database_name = aws_glue_catalog_database.osm_catalog.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"                  = "TRUE"
    "classification"            = "parquet"
    "projection.enabled"        = "true"
    "projection.region.type"    = "injected"
    "projection.year.type"      = "injected"
    "projection.month.type"     = "injected"
    "projection.day.type"       = "injected"
    "projection.entity.type"    = "enum"
    "projection.entity.values"  = "nodes,ways,relations"
    "storage.location.template" = "s3://${aws_s3_bucket.curated.bucket}/${var.output_prefix}/region=$${region}/$${year}/$${month}/$${day}/entity=$${entity}/"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.curated.bucket}/${var.output_prefix}/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      name                  = "ParquetHiveSerDe"
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "osm_id"
      type = "bigint"
    }
    columns {
      name = "osm_type"
      type = "string"
    }
    columns {
      name = "name"
      type = "string"
    }
    columns {
      name = "amenity"
      type = "string"
    }
    columns {
      name = "shop"
      type = "string"
    }
    columns {
      name = "tourism"
      type = "string"
    }
    columns {
      name = "building"
      type = "string"
    }
    columns {
      name = "highway"
      type = "string"
    }
    columns {
      name = "surface"
      type = "string"
    }
    columns {
      name = "latitude"
      type = "double"
    }
    columns {
      name = "longitude"
      type = "double"
    }
    columns {
      name = "geometry"
      type = "string"
    }
    columns {
      name = "node_refs"
      type = "array<bigint>"
    }
    columns {
      name = "members"
      type = "array<string>"
    }
    columns {
      name = "tag_count"
      type = "int"
    }
    columns {
      name = "tags"
      type = "string"
    }

  }

  partition_keys {
    name = "region"
    type = "string"
  }
  partition_keys {
    name = "year"
    type = "string"
  }
  partition_keys {
    name = "month"
    type = "string"
  }
  partition_keys {
    name = "day"
    type = "string"
  }
  partition_keys {
    name = "entity"
    type = "string"
  }

  depends_on = [aws_glue_catalog_database.osm_catalog]
}
