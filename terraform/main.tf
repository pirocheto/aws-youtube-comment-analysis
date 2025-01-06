module "lambda" {
  source        = "./modules/lambda"
  env           = var.env
  function_name = "${var.env}-${var.function_name}"
  bucket_name   = module.s3.bucket_name
  function_dir  = "${abspath(path.root)}/../${var.function_dir}"
  service_name  = var.service_name
}

module "s3" {
  source       = "./modules/s3"
  bucket_name  = "${var.env}-${var.bucket_name}"
  env          = var.env
  service_name = var.service_name
}

module "glue" {
  source      = "./modules/glue"
  env         = var.env
  bucket_name = module.s3.bucket_name
}
