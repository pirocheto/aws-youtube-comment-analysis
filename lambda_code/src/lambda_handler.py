from __future__ import annotations

import os
from enum import Enum
from typing import TYPE_CHECKING

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.parser import event_parser
from pydantic import BaseModel

from src.data_fetcher import get_data
from src.data_processing import (
    clear_keys,
    detect_sentiment,
    flatten_dict,
    promote_replies,
    underscore_keys,
)
from src.utils import DataPipeline

if TYPE_CHECKING:
    from aws_lambda_powertools.utilities.typing import LambdaContext


BUCKET_NAME = os.environ["BUCKET_NAME"]
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

tracer = Tracer()
logger = Logger()

s3 = boto3.client("s3")


class Action(str, Enum):
    ADD = "ADD"
    REMOVE = "REMOVE"


class InputEvent(BaseModel):
    video_id: str
    action: Action
    execution_id: str


@event_parser(model=InputEvent)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: InputEvent, context: LambdaContext) -> dict:
    """AWS Lambda handler for processing video comments."""

    video_id = event.video_id
    action = event.action
    execution_id = event.execution_id

    s3_key = f"data/{video_id}.json"

    logger.append_keys(
        video_id=video_id,
        action=action,
        execution_id=execution_id,
    )

    match action:
        case Action.ADD:
            logger.info("Processing ADD action")

            data_generator = get_data(video_id)
            data_pipeline = DataPipeline(data_generator)

            transformed_data = (
                data_pipeline
                # Promote replies
                .apply_expand(promote_replies)
                # Flatten nested dictionaries
                .apply(flatten_dict)
                # Convert keys to snake_case
                .apply(underscore_keys)
                # Add execution_id
                .apply(lambda x: {**x, "execution_id": execution_id})
                # Clear keys
                .apply(clear_keys)
                # Batch sentiment analysis
                .apply_batch(detect_sentiment, batch_size=100)
            )

            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=transformed_data.to_jsonl(),
                ContentType="application/json",
                ContentEncoding="utf8",
            )

            logger.info("ADD action completed")

            return {
                "action": action,
                "video_id": video_id,
                "s3_key": s3_key,
            }

        case Action.REMOVE:
            logger.info("Processing REMOVE action")

            s3.delete_object(Bucket=BUCKET_NAME, Key=s3_key)

            logger.info("REMOVE action completed")

            return {"action": action, "video_id": video_id}
