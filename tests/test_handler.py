from dataclasses import dataclass

import pytest
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics.provider import cold_start

from src.handler import lambda_handler


@pytest.fixture(scope="function", autouse=True)
def reset_metric_set():
    # Clear out every metric data prior to every test
    metrics = Metrics()
    metrics.clear_metrics()
    cold_start.is_cold_start = True  # ensure each test has cold start
    metrics.clear_default_dimensions()  # remove persisted default dimensions, if any
    yield


@pytest.fixture(scope="function", autouse=True)
def mocked_env(monkeypatch):
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "YouTubeSentimentAnalysis")
    monkeypatch.setenv("POWERTOOLS_METRICS_NAMESPACE", "YouTubeSentimentAnalysis")


@pytest.fixture
def context():
    @dataclass
    class LambdaContext:
        aws_request_id = "1234567890"
        log_group_name = "test-log-group"
        log_stream_name = "test-log-stream"
        function_name = "test-function"
        function_version = "1"
        invoked_function_arn = (
            "arn:aws:lambda:us-east-1:1234567890:function:test-function"
        )
        memory_limit_in_mb = "128"
        remaining_time_in_millis = "15000"

    return LambdaContext


def test_lambda_handler(context):
    event = {"video_id": "Ps5kScYvQQk"}

    response = lambda_handler(event, context)
    assert response["video_id"] == "Ps5kScYvQQk"
