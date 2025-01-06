module "lambda" {
  source        = "./modules/lambda"
  env           = var.env
  function_name = "${var.env}-youtube-comment-sentiment-analysis"
  bucket_name   = module.s3.bucket_name
  function_dir  = "${abspath(path.root)}/../function"
  service_name  = var.service_name
}

module "s3" {
  source       = "./modules/s3"
  bucket_name  = "${var.env}-youtube-comments"
  env          = var.env
  service_name = var.service_name
}

module "glue" {
  source        = "./modules/glue"
  env           = var.env
  database_name = "${var.env}_youtube_comments"
  table_name    = "${var.env}_youtube_comments_analytics"
  bucket_name   = module.s3.bucket_name
}
