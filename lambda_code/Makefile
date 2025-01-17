ENV = dev

.PHONY: test
test:
	pytest -s .

.PHONY: invoke
invoke:
	aws lambda invoke --function-name ${ENV}-youtube-comment-sentiment-analysis --cli-binary-format raw-in-base64-out --payload file://events/event.json output.json && cat output.json

.ONESHELL:
.PHONY: build
build:
	mkdir -p build
	cp -r src/* build/
	uv pip compile pyproject.toml -o build/requirements.txt
	uv pip install -r build/requirements.txt --target build --python-platform x86_64-manylinux_2_40 --only-binary=:all:
	cd build && rm -rf *.dist-info *.egg-info __pycache__