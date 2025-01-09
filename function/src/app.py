from __future__ import annotations

import json
import os
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

import boto3
import inflection
import requests
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools.utilities.parser import event_parser
from pydantic import BaseModel

if TYPE_CHECKING:
    from aws_lambda_powertools.utilities.typing import LambdaContext
    from types_boto3_comprehend.client import ComprehendClient
    from types_boto3_s3.client import S3Client

BUCKET_NAME = os.getenv("BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
YOUTUBE_API_KEY_SECRET_NAME = os.getenv("YOUTUBE_API_KEY_SECRET_NAME")
YOUTUBE_API_URL = "https://youtube.googleapis.com/youtube/v3/commentThreads"

tracer = Tracer()
logger = Logger()
metrics = Metrics()

s3: S3Client = boto3.client("s3", region_name=AWS_REGION)
comprehend: ComprehendClient = boto3.client("comprehend", region_name=AWS_REGION)


class YouTubeCommentsHandler:
    @tracer.capture_method
    def fetch_comments_page(
        self,
        video_id: str,
        api_key: str,
        page_token: str = None,
    ) -> dict:
        """Fetch a single page of YouTube comments."""
        logger.info(
            {
                "message": "Fetching comments page",
                "video_id": video_id,
                "page_token": page_token,
            }
        )
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
            params=params,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        logger.debug(
            {"message": "YouTube API response received", "response": response.json()}
        )
        return response.json()

    @tracer.capture_method
    def format_comment(
        self,
        comment_data: dict,
        additional_data: dict = {},
    ) -> dict:
        """Format a single comment for storage."""
        logger.debug(
            {"message": "Formatting comment", "comment_id": comment_data.get("id")}
        )
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
            **additional_data,
            "parent_id": comment_data.get("parentId", "none"),
            "author_channel_id": author_channel_id,
        }

        logger.debug({"message": "Comment formatted", "comment_data": data})
        return data

    @tracer.capture_method
    def retrieve_comments_from_youtube(
        self, video_id: str, api_key: str, additional_data: dict = None
    ) -> list[dict]:
        """Retrieve all comments for a given video."""
        logger.info(
            {"message": "Retrieving comments from YouTube", "video_id": video_id}
        )
        comments = []
        next_page_token = None

        while True:
            logger.debug(
                {"message": "Fetching comments page", "page_token": next_page_token}
            )
            response_data = self.fetch_comments_page(
                video_id, page_token=next_page_token, api_key=api_key
            )

            for item in response_data["items"]:
                # Process top-level comment
                top_level_comment = self.format_comment(
                    item["snippet"]["topLevelComment"],
                    additional_data,
                )
                comments.append(top_level_comment)

                # Process replies
                if "replies" in item:
                    for reply in item["replies"]["comments"]:
                        reply_comment = self.format_comment(reply, additional_data)
                        comments.append(reply_comment)

            next_page_token = response_data.get("nextPageToken")
            if not next_page_token:
                logger.info(
                    {
                        "message": "All comments retrieved",
                        "video_id": video_id,
                        "total_comments": len(comments),
                    }
                )
                break

        return comments

    @tracer.capture_method
    def upload_comments_to_s3(self, comments: list[dict], video_id: str) -> str:
        """Upload comments to an S3 bucket and return the S3 key."""
        logger.info({"message": "Uploading comments to S3", "video_id": video_id})
        s3_key = f"data/{video_id}.json"
        body = "\n".join([json.dumps(comment) for comment in comments])

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=body,
            ContentType="application/json",
            ContentEncoding="utf8",
        )
        logger.info(
            {
                "message": "Comments uploaded to S3",
                "bucket_name": BUCKET_NAME,
                "s3_key": s3_key,
            }
        )
        return s3_key

    @tracer.capture_method
    def remove_comments_from_s3(self, video_id: str):
        """Delete comments for a given video."""
        logger.info({"message": "Removing comments from S3", "video_id": video_id})
        s3.delete_object(Bucket=BUCKET_NAME, Key=f"data/{video_id}.json")
        logger.info({"message": "Deleted comments from S3", "video_id": video_id})


class Action(str, Enum):
    ADD = "ADD"
    REMOVE = "REMOVE"


class Event(BaseModel):
    video_id: str
    action: Action
    execution_id: str


handler = YouTubeCommentsHandler()


@event_parser(model=Event)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Event, context: LambdaContext) -> dict:
    """AWS Lambda handler for processing video comments."""
    logger.info(
        {"message": "Lambda invoked", "event": event.dict(), "environment": ENVIRONMENT}
    )
    video_id = event.video_id
    action = event.action
    execution_id = event.execution_id

    match action:
        case Action.ADD:
            logger.info({"message": "Processing ADD action", "video_id": video_id})
            api_key = parameters.get_secret(YOUTUBE_API_KEY_SECRET_NAME)

            additional_data = {
                "execution_id": execution_id,
                "fetched_at": datetime.now().isoformat(),
            }
            comments = handler.retrieve_comments_from_youtube(
                video_id, api_key, additional_data=additional_data
            )
            comments_with_sentiment = handler.batch_detect_sentiment(comments)
            s3_uri = handler.upload_comments_to_s3(comments_with_sentiment, video_id)

            logger.info(
                {
                    "message": "ADD action completed",
                    "video_id": video_id,
                    "s3_uri": s3_uri,
                }
            )
            return {"action": action, "video_id": video_id, "s3_uri": s3_uri}

        case Action.REMOVE:
            logger.info({"message": "Processing REMOVE action", "video_id": video_id})
            handler.remove_comments_from_s3(video_id)
            logger.info({"message": "REMOVE action completed", "video_id": video_id})
            return {"action": action, "video_id": video_id}
