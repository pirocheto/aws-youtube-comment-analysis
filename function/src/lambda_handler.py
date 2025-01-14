from __future__ import annotations

import json
import os
from datetime import datetime
from enum import Enum
from itertools import batched
from typing import TYPE_CHECKING

import boto3
import inflection
import requests
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools.utilities.parser import event_parser
from pydantic import BaseModel

if TYPE_CHECKING:
    from aws_lambda_powertools.utilities.typing import LambdaContext

# Environment variables
BUCKET_NAME = os.environ["BUCKET_NAME"]
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
SAGEMAKER_ENDPOINT_NAME = "prod-multilingual-sentiment-analysis-endpoint"

# YouTube API settings
YOUTUBE_API_KEY_SECRET_NAME = os.environ["YOUTUBE_API_KEY_SECRET_NAME"]
YOUTUBE_API_URL = "https://youtube.googleapis.com/youtube/v3/commentThreads"

tracer = Tracer()
logger = Logger()

s3 = boto3.client("s3", region_name=AWS_REGION)
sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=AWS_REGION)


class YoutubeCommentProcessor:
    @tracer.capture_method
    def fetch_comments_page(
        self,
        video_id: str,
        api_key: str,
        page_token: str | None = None,
    ) -> dict:
        """Fetch a single page of YouTube comments."""

        logger.info("Fetching comments page")

        headers = {"Accept": "application/json"}
        params = {
            "part": "snippet,replies",
            "key": api_key,
            "order": "time",
            "maxResults": 100,
            "videoId": video_id,
            "pageToken": page_token,
        }

        response = requests.get(
            YOUTUBE_API_URL,
            params=params,  # type: ignore
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()

        logger.debug("YouTube API response received")
        return response.json()

    def _format_comment(
        self,
        comment_data: dict,
        additional_data: dict | None = None,
    ) -> dict:
        """Format a single comment for storage."""

        logger.debug("Formatting comment", comment_id=comment_data["id"])

        snippet_snake_case = {}
        for key, value in comment_data["snippet"].items():
            new_key = inflection.underscore(key)
            snippet_snake_case[new_key] = value

        author_channel_id = (
            comment_data["snippet"].get("authorChannelId", {}).get("value", "none")
        )

        data = {
            "id": comment_data["id"],
            **snippet_snake_case,
            "parent_id": comment_data.get("parentId", "none"),
            "author_channel_id": author_channel_id,
        }

        if additional_data:
            data.update(additional_data)

        logger.debug("Comment formatted", comment_id=comment_data["id"])
        return data

    @tracer.capture_method
    def retrieve_comments_from_youtube(
        self, video_id: str, api_key: str, additional_data: dict | None = None
    ) -> list[dict]:
        """Retrieve all comments for a given video."""

        logger.info("Retrieving comments from YouTube")

        comments = []
        next_page_token = None

        while True:
            logger.debug("Fetching comments page")

            response_data = self.fetch_comments_page(
                video_id,
                page_token=next_page_token,
                api_key=api_key,
            )

            for item in response_data["items"]:
                # Process top-level comment
                top_level_comment = self._format_comment(
                    item["snippet"]["topLevelComment"],
                    additional_data,
                )
                comments.append(top_level_comment)

                # Process replies
                if "replies" in item:
                    for reply in item["replies"]["comments"]:
                        reply_comment = self._format_comment(reply, additional_data)
                        comments.append(reply_comment)

            next_page_token = response_data.get("nextPageToken")

            if not next_page_token:
                logger.info("All comments retrieved", total_comments=len(comments))
                break

        return comments

    def batch_detect_sentiment(self, comments: list[dict]) -> list[dict]:
        """Batch detect sentiment of comments using Amazon SageMaker."""

        for i, batch in enumerate(batched(comments, 100), 1):
            logger.info(
                "Detecting sentiment for batch of comments",
                batch_size=len(batch),
                batch_number=i,
            )
            texts = [comment["text_display"] for comment in batch]

            response = sagemaker_runtime.invoke_endpoint(
                EndpointName=SAGEMAKER_ENDPOINT_NAME,
                ContentType="application/json",
                Body=json.dumps({"inputs": texts}),
            )

            result = json.loads(response["Body"].read())

            for comment, sentiment in zip(batch, result):
                comment["sentiment"] = sentiment["label"]
                comment["sentiment_score"] = sentiment["score"]

        return result

    @tracer.capture_method
    def upload_comments_to_s3(self, comments: list[dict], video_id: str) -> str:
        """Upload comments to an S3 bucket and return the S3 key."""

        logger.info("Uploading comments to S3")
        s3_key = f"data/{video_id}.json"
        body = "\n".join([json.dumps(comment) for comment in comments])

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=body,
            ContentType="application/json",
            ContentEncoding="utf8",
        )

        logger.info("Comments uploaded to S3", bucket_name=BUCKET_NAME, s3_key=s3_key)
        return s3_key

    @tracer.capture_method
    def remove_comments_from_s3(self, video_id: str):
        """Delete comments for a given video."""

        logger.info("Removing comments from S3")
        s3.delete_object(Bucket=BUCKET_NAME, Key=f"data/{video_id}.json")
        logger.info("Deleted comments from S3")


class Action(str, Enum):
    ADD = "ADD"
    REMOVE = "REMOVE"


class Event(BaseModel):
    video_id: str
    action: Action
    execution_id: str


processor = YoutubeCommentProcessor()


@event_parser(model=Event)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: Event, context: LambdaContext) -> dict:
    """AWS Lambda handler for processing video comments."""

    video_id = event.video_id
    action = event.action
    execution_id = event.execution_id

    logger.append_keys(
        video_id=video_id,
        action=action,
        execution_id=execution_id,
    )

    match action:
        case Action.ADD:
            logger.info("Processing ADD action")
            api_key = parameters.get_secret(YOUTUBE_API_KEY_SECRET_NAME)

            additional_data = {
                "execution_id": execution_id,
                "fetched_at": datetime.now().isoformat(),
            }

            # Retrieve comments from YouTube
            comments = processor.retrieve_comments_from_youtube(
                video_id, api_key, additional_data=additional_data
            )

            # Detect sentiment of comments
            comments_with_sentiment = processor.batch_detect_sentiment(comments)

            # Upload comments to S3
            s3_uri = processor.upload_comments_to_s3(comments_with_sentiment, video_id)

            logger.info("ADD action completed")
            return {"action": action, "video_id": video_id, "s3_uri": s3_uri}

        case Action.REMOVE:
            logger.info("Processing REMOVE action")

            # Remove comments from S3
            processor.remove_comments_from_s3(video_id)

            logger.info("REMOVE action completed")
            return {"action": action, "video_id": video_id}
