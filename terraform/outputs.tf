output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = module.lambda.function_arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = module.lambda.function_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = module.s3.bucket_arn
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = module.s3.bucket_name
}

output "glue_database_name" {
  description = "Name of the Glue database"
  value       = module.glue.database_name
}

output "glue_database_arn" {
  description = "ARN of the Glue database"
  value       = module.glue.database_arn
}

output "glue_table_name" {
  description = "Name of the Glue table"
  value       = module.glue.table_name
}

output "glue_table_arn" {
  description = "ARN of the Glue table"
  value       = module.glue.table_arn
}
