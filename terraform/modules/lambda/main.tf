resource "null_resource" "package_lambda" {
  provisioner "local-exec" {
    command = <<EOT
        cd ${var.function_dir}
        mkdir -p .build
        cp -r src/* .build/
    EOT
  }
}

resource "null_resource" "package_lambda_dependencies" {
  provisioner "local-exec" {
    command = <<EOT
        cd ${var.function_dir}
        uv pip compile pyproject.toml -o .build/requirements.txt
        uv pip install -r .build/requirements.txt --target .build
    EOT
  }
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${var.function_dir}/.build"
  output_path = "${var.function_dir}/lambda.zip"
  depends_on = [
    null_resource.package_lambda,
    null_resource.package_lambda_dependencies
  ]
}

resource "aws_lambda_function" "function" {
  function_name = var.function_name
  runtime       = "python3.12"
  handler       = "app.lambda_handler"
  role          = aws_iam_role.lambda_role.arn
  filename      = data.archive_file.lambda.output_path
  timeout       = 300
  environment {
    variables = {
      POWERTOOLS_SERVICE_NAME      = "${var.env}${var.service_name}"
      POWERTOOLS_METRICS_NAMESPACE = "${var.env}${var.service_name}"
      LOG_LEVEL                    = "INFO"
      BUCKET_NAME                  = var.bucket_name
    }
  }
  tags = {
    Env     = var.env
    Service = var.service_name
  }
}

resource "aws_iam_role" "lambda_role" {
  name = "${var.env}-${var.function_name}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
      }
    ]
  })
}
