resource "null_resource" "build_lambda" {
  triggers = {
    always_run = timestamp()
  }

  provisioner "local-exec" {
    command = <<EOT
        cd ${var.function_dir}
        mkdir -p .build
        cp -r src/* .build/
        uv pip compile pyproject.toml -o .build/requirements.txt
        uv pip install -r .build/requirements.txt --target .build
    EOT
  }
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${var.function_dir}/.build"
  output_path = "${var.function_dir}/lambda.zip"
  depends_on  = [null_resource.build_lambda]
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


resource "aws_iam_policy" "lambda_policy" {
  name        = "${var.env}-${var.function_name}-policy"
  description = "Policy for Lambda function"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Effect = "Allow"
        Resource = [
          "arn:aws:s3:::${var.bucket_name}",
          "arn:aws:s3:::${var.bucket_name}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}
