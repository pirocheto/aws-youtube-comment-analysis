resource "aws_glue_catalog_database" "database" {
  name = var.database_name
}

resource "aws_glue_catalog_table" "table" {
  database_name = aws_glue_catalog_database.database.name
  name          = var.table_name

  storage_descriptor {
    location = "s3://${var.bucket_name}/data/"

    columns {
      name = "id"
      type = "string"
    }

    columns {
      name = "channel_id"
      type = "string"
    }

    columns {
      name = "video_id"
      type = "string"
    }

    columns {
      name = "text_display"
      type = "string"
    }

    columns {
      name = "text_original"
      type = "string"
    }

    columns {
      name = "author_display_name"
      type = "string"
    }

    columns {
      name = "author_profile_image_url"
      type = "string"
    }

    columns {
      name = "author_channel_url"
      type = "string"
    }

    columns {
      name = "author_channel_id"
      type = "string"
    }

    columns {
      name = "can_rate"
      type = "boolean"
    }

    columns {
      name = "viewer_rating"
      type = "string"
    }

    columns {
      name = "like_count"
      type = "int"
    }

    columns {
      name = "published_at"
      type = "timestamp"
    }

    columns {
      name = "updated_at"
      type = "timestamp"
    }

    columns {
      name = "parent_id"
      type = "string"
    }

    columns {
      name = "fetched_at"
      type = "timestamp"
    }

    columns {
      name = "sentiment"
      type = "string"
    }

    columns {
      name = "sentiment_score_positive"
      type = "float"
    }

    columns {
      name = "sentiment_score_negative"
      type = "float"
    }

    columns {
      name = "sentiment_score_neutral"
      type = "float"
    }

    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
    }
  }
}
