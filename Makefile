
.PHONY: requirements
requirements:
	uv pip compile pyproject.toml -o src/requirements.txt

.PHONY: build
build:
	sam build --config-env prod

.PHONY: deploy
deploy:
	sam deploy --config-env prod


.PHONY: validate
validate:
	sam validate --lint --config-env prod

.PHONY: test
test:
	pytest -s .