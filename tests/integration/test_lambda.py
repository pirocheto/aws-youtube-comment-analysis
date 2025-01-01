import json
from pathlib import Path

import boto3
import pytest

lambda_client = boto3.client("lambda")


@pytest.fixture
def lambda_function_name():
    return "test-youtube-comment-sentiment-analysis"


@pytest.fixture
def test_event():
    return Path("events/event.json").read_text()


def test_invoke_lambda(lambda_function_name, test_event):
    response = lambda_client.invoke(
        FunctionName=lambda_function_name,
        Payload=json.dumps(test_event),
    )

    response_payload = json.loads(response["Payload"].read().decode("utf-8"))
    assert response_payload["StatusCode"] == 200
