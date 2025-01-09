import json
import os
from datetime import datetime
from enum import Enum
from itertools import batched
from typing import TYPE_CHECKING

import boto3
import inflection
import requests
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools.utilities.parser import event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel

if TYPE_CHECKING:
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
        return response.json()

    @tracer.capture_method
    def format_comment(
        self,
        comment_data: dict,
        additional_data: dict = {},
    ) -> dict:
        """Format a single comment for storage."""

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

        return data

    @tracer.capture_method
    def retrieve_comments_from_youtube(
        self, video_id: str, api_key: str, additional_data: dict = None
    ) -> list[dict]:
        """Retrieve all comments for a given video."""

        comments = []
        next_page_token = None

        while True:
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
                break

        logger.info({"message": "Retrieved all comments", "video_id": video_id})
        return comments

    @tracer.capture_method
    def upload_comments_to_s3(self, comments: list[dict], video_id: str) -> str:
        """Upload comments to an S3 bucket and return the S3 key."""

        s3_key = f"data/{video_id}.json"
        body = "\n".join([json.dumps(comment) for comment in comments])

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=body,
            ContentType="application/json",
            ContentEncoding="utf8",
        )

    @tracer.capture_method
    def retrieve_comments_from_s3(self, video_id: str) -> list[dict]:
        """Retrieve comments from S3."""

        response = s3.get_object(Bucket=BUCKET_NAME, Key=f"data/{video_id}.json")
        comments = [
            json.loads(comment)
            for comment in response["Body"].read().decode("utf-8").split("\n")
        ]

        logger.info({"message": "Retrieved comments from S3", "video_id": video_id})
        return comments

    @tracer.capture_method
    def remove_comments_from_s3(self, video_id: str):
        """Delete comments for a given video."""

        # Delete comments from S3
        s3.delete_object(Bucket=BUCKET_NAME, Key=f"data/{video_id}.json")
        logger.info({"message": "Deleted comments from S3", "video_id": video_id})

    @tracer.capture_method
    def batch_detect_sentiment(
        self, comments: list[dict], batch_size: int = 25
    ) -> list[dict]:
        """Detect sentiment for a batch of comments."""

        comments_with_sentiment = []

        for batch in batched(comments, batch_size):
            logger.info(
                {"message": "Detecting sentiment for batch", "batch_size": len(batch)}
            )

            response = comprehend.batch_detect_sentiment(
                TextList=[comment["text_display"] for comment in batch],
                LanguageCode="fr",
            )

            for idx, sentiment in enumerate(response["ResultList"]):
                sentiment = {
                    "sentiment": sentiment["Sentiment"],
                    "sentiment_score_positive": sentiment["SentimentScore"]["Positive"],
                    "sentiment_score_negative": sentiment["SentimentScore"]["Negative"],
                    "sentiment_score_neutral": sentiment["SentimentScore"]["Neutral"],
                }

                comment = {**batch[idx], **sentiment}
                comments_with_sentiment.append(comment)
                logger.debug({"message": "Processed sentiment", "comment": comment})

        return comments_with_sentiment


class Action(str, Enum):
    INSERT = "INSERT"
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

    video_id = event.video_id
    action = event.action
    execution_id = event.execution_id

    match action:
        case Action.INSERT:
            try:
                # Initialize the processor with the API key
                api_key = parameters.get_secret(YOUTUBE_API_KEY_SECRET_NAME)

                # Retrieve and process comments
                additional_data = {
                    "execution_id": execution_id,
                    "fetched_at": datetime.now().isoformat(),
                }
                comments = handler.retrieve_comments_from_youtube(
                    video_id, api_key, additional_data=additional_data
                )

                # Batch detect sentiment
                comments_with_sentiment = handler.batch_detect_sentiment(comments)

                # Upload comments to S3
                handler.upload_comments_to_s3(comments_with_sentiment, video_id)

            except Exception as error:
                logger.exception(
                    {
                        "video_id": video_id,
                        "message": "Failed to process comments",
                        "error": str(error),
                    }
                )
                raise error

            return {
                "action": action,
                "video_id": video_id,
                "s3_uri": f"s3://{BUCKET_NAME}/data/{video_id}.json",
            }

        case Action.REMOVE:
            # Delete comments from S3
            handler.remove_comments_from_s3(video_id)
            logger.info({"message": "Deleted comments from S3", "video_id": video_id})

            return {"action": action, "video_id": video_id}
