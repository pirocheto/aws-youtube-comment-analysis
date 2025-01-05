
.PHONY: requirements
requirements:
	uv pip compile pyproject.toml -o src/requirements.txt

.PHONY: build
build:
	sam build --config-env dev

.PHONY: package
package:
	sam package --config-env dev

.PHONY: deploy
deploy:
	sam deploy --config-env dev

.PHONY: validate-template
validate:
	sam validate --lint --config-env dev

.PHONY: update-stack
update-stack: validate build package deploy

.PHONY: test
test:
	pytest -s .

.PHONY: invoke-local
invoke-local:
	sam local invoke test-youtube-comment-sentiment-analysis --config-env dev output.json

.PHONY: invoke_lambda
invoke_lambda:
	aws lambda invoke --function-name dev-youtube-comment-sentiment-analysis --cli-binary-format raw-in-base64-out --payload file://events/dynamodb_stream_event.json output.json

.PHONY: put_dynamodb_item
put_dynamodb_item:
	aws dynamodb put-item --table-name dev_youtube_comment_requests --item file://items/dynamodb_item.json

.PHONY: architecture
architecture:
	awsdac architecture/dac.yaml -o architecture/diagram.png