variable "aws_region" {
  description = "The AWS region where resources will be deployed"
  type        = string
  default     = "us-east-1"
}

variable "env" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "test", "prod"], var.env)
    error_message = "The environment must be one of the following: 'dev', 'test', or 'prod'."
  }
}

variable "service_name" {
  description = "Name of the service"
  type        = string
  default     = "YoutubeCommentSentimentAnalysis"
}

variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "youtube-comment-sentiment-analysis"
}

variable "function_dir" {
  description = "Directory containing the Lambda function code"
  type        = string
  default     = "function"
}

variable "bucket_name" {
  description = "Name of the S3 bucket"
  type        = string
  default     = "youtube-comment-sentiment-analysis"
}

variable "glue_table_name" {
  description = "Name of the Glue table"
  type        = string
  default     = "youtube_comment_analytics"
}
