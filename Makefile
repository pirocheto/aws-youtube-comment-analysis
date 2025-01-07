
.PHONY: test
test:
	pytest -s .

.PHONY: invoke_lambda
invoke_lambda:
	aws lambda invoke --function-name dev-youtube-comment-sentiment-analysis --cli-binary-format raw-in-base64-out --payload file://events/event.json output.json && cat output.json

.ONESHELL:
.PHONY: build-lambda
build-lambda:
	cd function
	mkdir -p .build
	cp -r src/* .build/
	uv pip compile pyproject.toml -o .build/requirements.txt
	uv pip install -r .build/requirements.txt --target .build --python-platform x86_64-manylinux_2_40 --only-binary=:all:
	cd .build && rm -rf *.dist-info *.egg-info __pycache__

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