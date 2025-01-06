output "database_name" {
  value = aws_glue_catalog_database.database.name
}

output "table_name" {
  value = aws_glue_catalog_table.table.name
}
