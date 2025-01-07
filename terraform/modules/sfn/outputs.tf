
output "sfn_state_machine_name" {
  value = aws_sfn_state_machine.state_machine.name
}

output "sfn_state_machine_arn" {
  value = aws_sfn_state_machine.state_machine.arn
}
