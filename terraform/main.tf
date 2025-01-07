locals {
  env = terraform.workspace
}

module "lambda" {
  source        = "./modules/lambda"
  env           = local.env
  function_name = "${local.env}-youtube-comment-management"
  bucket_name   = module.s3.bucket_name
  function_dir  = "${abspath(path.root)}/../function"
  service_name  = var.service_name
}

module "s3" {
  source       = "./modules/s3"
  bucket_name  = "${local.env}-youtube-comment-storage"
  env          = local.env
  service_name = var.service_name
}

module "glue" {
  source        = "./modules/glue"
  env           = local.env
  database_name = "${local.env}_youtube_comments"
  table_name    = "${local.env}_youtube_comments_analytics"
  bucket_name   = module.s3.bucket_name
}
