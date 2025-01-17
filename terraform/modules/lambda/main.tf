data "aws_caller_identity" "current" {}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = var.code_dir
  output_path = ".artifacts/lambda.zip"
}

resource "aws_lambda_function" "function" {
  function_name    = var.function_name
  runtime          = "python3.12"
  handler          = "src.lambda_handler"
  role             = aws_iam_role.lambda_role.arn
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 300
  environment {
    variables = {
      POWERTOOLS_SERVICE_NAME = "${var.env}${var.service_name}"
      LOG_LEVEL               = "INFO"
      BUCKET_NAME             = var.bucket_name
    }
  }
  tags = {
    Env     = var.env
    Service = var.service_name
  }
}

resource "aws_iam_role" "lambda_role" {
  name = "${var.function_name}-lambda-execution-role"
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
  name        = "${var.function_name}-lambda-execution-policy"
  description = "Policy for Lambda function ${var.function_name}"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.bucket_name}",
          "arn:aws:s3:::${var.bucket_name}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = "comprehend:*"
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = "arn:aws:secretsmanager:us-east-1:${data.aws_caller_identity.current.account_id}:secret:${var.env}/YouTubeAPIKey-*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}
