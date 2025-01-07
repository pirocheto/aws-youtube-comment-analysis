
resource "aws_sfn_state_machine" "state_machine" {
  name     = var.state_machine_name
  role_arn = aws_iam_role.state_machine_role.arn

  definition = templatefile("${path.module}/state_machine.json", {
    lambda_arn = var.lambda_arn
  })
}


resource "aws_iam_role" "state_machine_role" {
  name = "${var.state_machine_name}-sfn-execution-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "state_machine_policy" {
  name        = "${var.state_machine_name}-sfn-execution-policy"
  description = "Policy for Step Functions state machine ${var.state_machine_name}"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = "lambda:InvokeFunction",
        Resource = "${var.lambda_arn}:*"
      },
      {
        Effect   = "Allow",
        Action   = "states:StartExecution"
        Resource = aws_sfn_state_machine.state_machine.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "state_machine_policy_attachment" {
  role       = aws_iam_role.state_machine_role.name
  policy_arn = aws_iam_policy.state_machine_policy.arn
}
