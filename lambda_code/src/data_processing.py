from __future__ import annotations

import json

import boto3
import inflection

SAGEMAKER_ENDPOINT_NAME = "prod-multilingual-sentiment-analysis-endpoint"
sagemaker_runtime = boto3.client("sagemaker-runtime")


def flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """Flatten a nested dictionary.

    Exemple:
    flatten_dict({"a": {"b": 1, "c": 2}}) -> {"a.b": 1, "a.c": 2}
    """

    items: list[tuple] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def underscore_keys(d: dict) -> dict:
    """Convert dictionary keys to snake_case.

    Exemple:
    underscore_keys({"camelCase": 1}) -> {"camel_case": 1}
    """

    return {inflection.underscore(key): value for key, value in d.items()}


def promote_replies(data: dict) -> list[dict]:
    """Promote replies to the top level of the data structure.

    Exemple:
    promote_replies({"replies": {"comments": [{"text": "reply"}]}}) -> [{"text": "reply"}]
    """

    replies = data.pop("replies", None)
    if replies:
        return [data, *replies["comments"]]

    return [data]


def clear_keys(data: dict) -> dict:
    """Remove snippet and top_level_comment prefixes from keys.

    Exemple:
    clear_keys({"snippet.key1": "comment", "top_level_comment.key2": "comment"}) -> {
        "key1": "comment",
        "key2": "comment",
    }
    """

    def clear_key(k: str) -> str:
        key = k.replace("snippet.", "")
        key = key.replace("top_level_comment.", "")
        return key

    return {clear_key(k): v for k, v in data.items()}


def detect_sentiment(data: tuple[dict, ...]) -> tuple[dict, ...]:
    """Detect sentiment for a batch of comments using Amazon SageMaker.

    Exemple:
    detect_sentiment(({"text_original": "comment 1"}, {"text_original": "comment 2"})) -> (
        {"text_original": "comment 1", "sentiment": "POSITIVE", "sentiment_score": 0.99},
        {"text_original": "comment 2", "sentiment": "NEGATIVE", "sentiment_score": 0.01},
    )

    """

    payload = {"inputs": [doc["text_original"] for doc in data]}

    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT_NAME,
        ContentType="application/json",
        Body=json.dumps(payload),
    )

    result = json.loads(response["Body"].read())

    for comment, sentiment in zip(data, result):
        comment["sentiment"] = sentiment["label"]
        comment["sentiment_score"] = sentiment["score"]

    return data
