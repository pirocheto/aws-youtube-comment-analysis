locals {
  env = terraform.workspace
}

module "lambda" {
  source        = "./modules/lambda"
  env           = local.env
  function_name = "${local.env}-youtube-comment-processor"
  bucket_name   = module.s3.bucket_name
  code_dir      = "${abspath(path.root)}/../lambda_code"
  service_name  = var.service_name
}

module "s3" {
  source       = "./modules/s3"
  bucket_name  = "${local.env}-youtube-comment-storage"
  service_name = var.service_name
  env          = local.env
}

module "glue" {
  source        = "./modules/glue"
  database_name = "${local.env}_youtube_comment_db"
  table_name    = "${local.env}_youtube_comment_analytics"
  bucket_name   = module.s3.bucket_name
}

module "sfn" {
  source             = "./modules/sfn"
  state_machine_name = "${local.env}-youtube-comment-requester"
  lambda_arn         = module.lambda.function_arn
}
