from dataclasses import dataclass

import pytest


@pytest.fixture(scope="session", autouse=True)
def mocked_env(monkeypatch):
    monkeypatch.setenv("BUCKET_NAME", "test-youtube-comment-sentiment-analysis")
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
    from src.lambda_handler import lambda_handler

    event = {"video_id": "Ps5kScYvQQk"}

    response = lambda_handler(event, context)
    assert response["video_id"] == "Ps5kScYvQQk"
