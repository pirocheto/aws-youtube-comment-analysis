
.PHONY: create-requirements
create-requirements:
	uv pip compile pyproject.toml -o src/requirements.txt

build:
	sam build --use-container