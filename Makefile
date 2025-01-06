
.PHONY: test
test:
	pytest -s .

.PHONY: invoke_lambda
invoke_lambda:
	aws lambda invoke --function-name dev-youtube-comment-sentiment-analysis --cli-binary-format raw-in-base64-out --payload file://events/event.json output.json && cat output.json

.PHONY: terraform-init
terraform-init:
	terraform -chdir=terraform init

.PHONY: validate
terraform-validate:
	terraform -chdir=terraform validate

.PHONY: terraform-plan
terraform-plan:
	terraform -chdir=terraform plan

.PHONY: terraform-apply
terraform-apply:
	terraform -chdir=terraform apply -auto-approve

.PHONY: terraform-destroy
terraform-destroy:
	terraform -chdir=terraform destroy

.PHONY: dev-workspace
dev-workspace:
	terraform -chdir=terraform workspace select dev