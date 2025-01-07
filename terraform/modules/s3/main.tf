resource "aws_s3_bucket" "bucket" {
  bucket = var.bucket_name

  force_destroy = var.env == "prod" ? false : true
  tags = {
    Env     = var.env
    Service = var.service_name
  }
}
