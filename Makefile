
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

test-local:
	sam local invoke YoutubeCommentSentimentAnalysisFunction --event events/event.json