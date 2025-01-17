output "database_name" {
  value = aws_glue_catalog_database.database.name
}

output "database_arn" {
  value = aws_glue_catalog_database.database.arn
}

output "table_name" {
  value = aws_glue_catalog_table.table.name
}

output "table_arn" {
  value = aws_glue_catalog_table.table.arn
}
