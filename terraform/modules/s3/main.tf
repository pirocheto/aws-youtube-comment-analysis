resource "aws_s3_bucket" "bucket" {
  bucket = var.bucket_name
  tags = {
    Env     = var.env
    Service = var.service_name
  }
}
