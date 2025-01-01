import json
import os
from datetime import datetime

import boto3
import requests
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools.utilities.parser import event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel

BUCKET_NAME = os.getenv("BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "AWS_DEFAULT_REGION")
YOUTUBE_API_URL = "https://youtube.googleapis.com/youtube/v3/commentThreads"

tracer = Tracer()
logger = Logger()
metrics = Metrics()

s3 = boto3.client("s3", region_name=AWS_REGION)
comprehend = boto3.client("comprehend", region_name=AWS_REGION)


class YouTubeCommentsProcessor:
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

        logger.info(
            {
                "message": "Fetched comments page",
                "video_id": video_id,
                "page_token": page_token,
                "status_code": response.status_code,
            }
        )

        if response.status_code != 200:
            raise ValueError(f"API Error: {response.json()}")

        return response.json()

    @staticmethod
    def format_comment(comment_data: dict) -> dict:
        """Format a single comment for storage."""

        author_channel_id = (
            comment_data["snippet"].get("authorChannelId", {}).get("value")
        )

        return {
            "id": comment_data["id"],
            **comment_data["snippet"],
            "authorChannelId": author_channel_id,
            "parentId": comment_data.get("parentId"),
        }

    @tracer.capture_method
    def retrieve_all_comments(self, video_id: str, api_key: str) -> list[dict]:
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
                    item["snippet"]["topLevelComment"]
                )

                logger.debug(
                    {
                        "message": "Processing comment",
                        "comment": top_level_comment,
                    }
                )

                comments.append(top_level_comment)

                # Process replies
                if "replies" in item:
                    for reply in item["replies"]["comments"]:
                        reply_comment = self.format_comment(reply)

                        logger.debug(
                            {
                                "message": "Processing reply",
                                "comment": reply_comment,
                            }
                        )

                        comments.append(reply_comment)

            next_page_token = response_data.get("nextPageToken")
            if not next_page_token:
                break

        logger.info(
            {
                "message": "Retrieved all comments",
                "video_id": video_id,
                "total_comments": len(comments),
            }
        )

        return comments

    @tracer.capture_method
    def upload_comments_to_s3(self, comments: list[dict], video_id: str) -> str:
        """Upload comments to an S3 bucket and return the S3 key."""

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S.%f")
        s3_key = f"landing/{video_id}-{timestamp}.json"

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(comments),
            ContentType="application/json",
            ContentEncoding="utf8",
        )

        return s3_key

    @tracer.capture_method
    def batch_detect_sentiment(
        self, comments: list[dict], batch_size: int = 25
    ) -> list[dict]:
        """Detect sentiment for a batch of comments."""

        for i in range(0, len(comments), batch_size):
            batch = comments[i : i + batch_size]

            logger.info(
                {
                    "message": "Detecting sentiment for batch",
                    "batch_size": len(batch),
                    "items_range": f"{i+1} - {i+len(batch)}",
                }
            )

            response = comprehend.batch_detect_sentiment(
                TextList=[comment["textDisplay"] for comment in batch],
                LanguageCode="fr",
            )

            for idx, sentiment in enumerate(response["ResultList"]):
                comments[i + idx] |= {
                    "sentiment": sentiment["Sentiment"],
                    "sentimentScorePositive": sentiment["SentimentScore"]["Positive"],
                    "sentimentScoreNegative": sentiment["SentimentScore"]["Negative"],
                    "sentimentScoreNeutral": sentiment["SentimentScore"]["Neutral"],
                }

                logger.debug(
                    {
                        "message": "Processed sentiment",
                        "comment": comments[i + idx],
                    }
                )

        return comments


processor = YouTubeCommentsProcessor()


class Event(BaseModel):
    video_id: str


@event_parser(model=Event)
@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Event, context: LambdaContext) -> dict:
    """AWS Lambda handler for processing video comments."""

    # Retrieve video ID from the event
    video_id = event.video_id

    # Initialize the processor with the API key
    api_key = parameters.get_secret("test/YoutubeSentimentAnalysis")

    # Retrieve and process comments
    comments = processor.retrieve_all_comments(video_id, api_key)

    # Batch detect sentiment
    comments_with_sentiment = processor.batch_detect_sentiment(comments)

    # Upload comments to S3
    s3_key = processor.upload_comments_to_s3(comments_with_sentiment, video_id)

    # Build and return the response
    return {
        "video_id": video_id,
        "total_comments": len(comments_with_sentiment),
        "output": {
            "bucket_name": BUCKET_NAME,
            "bucket_key": s3_key,
            "s3_uri": f"s3://{BUCKET_NAME}/{s3_key}",
        },
    }
