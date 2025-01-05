
.PHONY: requirements
requirements:
	uv pip compile pyproject.toml -o src/requirements.txt

.PHONY: build
build:
	sam build --config-env prod

.PHONY: package
package:
	sam package --config-env prod

.PHONY: deploy
deploy:
	sam deploy --config-env prod

.PHONY: validate-template
validate:
	sam validate --lint --config-env prod

.PHONY: test
test:
	pytest -s .

invoke-local:
	sam local invoke test-youtube-comment-sentiment-analysis --config-env test output.json

invoke:
	aws lambda invoke --function-name test-youtube-comment-sentiment-analysis --cli-binary-format raw-in-base64-out --payload file://events/dynamodb_stream.json output.json

.PHONY: architecture
architecture:
	awsdac architecture/dac.yaml -o architecture/diagram.png