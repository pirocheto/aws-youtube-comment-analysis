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
