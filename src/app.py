import json
import os
from datetime import datetime
from itertools import batched

import boto3
import inflection
import requests
from 
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools.utilities.batch import (
    BatchProcessor,
    EventType,
    process_partial_response,
)
from aws_lambda_powertools.utilities.data_classes.dynamo_db_stream_event import (
    DynamoDBRecord,
    DynamoDBRecordEventName,
)
from aws_lambda_powertools.utilities.typing import LambdaContext

BUCKET_NAME = os.getenv("BUCKET_NAME")
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME")
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "test")
YOUTUBE_API_URL = "https://youtube.googleapis.com/youtube/v3/commentThreads"

processor = BatchProcessor(event_type=EventType.DynamoDBStreams)
tracer = Tracer()
logger = Logger()
metrics = Metrics()

s3 = boto3.client("s3", region_name=AWS_REGION)
comprehend = boto3.client("comprehend", region_name=AWS_REGION)
dynamodb = boto3.client("dynamodb", region_name=AWS_REGION)


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
            comment_data["snippet"].get("authorChannelId", {}).get("value", "none")
        )

        snippet_snake_case = {}
        for key, value in comment_data["snippet"].items():
            new_key = inflection.underscore(key)
            snippet_snake_case[new_key] = value

        data = {
            "id": comment_data["id"],
            **snippet_snake_case,
            "author_channel_id": author_channel_id,
            "parent_id": comment_data.get("parentId", "none"),
            "fetched_at": datetime.now().isoformat(),
        }

        return data

    @tracer.capture_method
    def retrieve_comments_from_youtube(self, video_id: str, api_key: str) -> list[dict]:
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

        s3_key = f"data/{video_id}.json"
        body = "\n".join([json.dumps(comment) for comment in comments])

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=body,
            ContentType="application/json",
            ContentEncoding="utf8",
        )

        return s3_key

    @tracer.capture_method
    def retrieve_comments_from_s3(self, video_id: str) -> list[dict]:
        """Retrieve comments from S3."""

        response = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=f"data/{video_id}.json",
        )
        comments = [
            json.loads(comment)
            for comment in response["Body"].read().decode("utf-8").split("\n")
        ]

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

        for batch in batched(comments, batch_size):
            logger.info(
                {
                    "message": "Detecting sentiment for batch",
                    "batch_size": len(batch),
                }
            )

            response = comprehend.batch_detect_sentiment(
                TextList=[comment["text_display"] for comment in batch],
                LanguageCode="fr",
            )

            for idx, sentiment in enumerate(response["ResultList"]):
                batch[idx] |= {
                    "sentiment": sentiment["Sentiment"],
                    "sentiment_score_positive": sentiment["SentimentScore"]["Positive"],
                    "sentiment_score_negative": sentiment["SentimentScore"]["Negative"],
                    "sentiment_score_neutral": sentiment["SentimentScore"]["Neutral"],
                }

                logger.debug(
                    {
                        "message": "Processed sentiment",
                        "comment": batch[idx],
                    }
                )


handler = YouTubeCommentsHandler()


@tracer.capture_method
def record_handler(record: DynamoDBRecord):
    """Process a single DynamoDB stream record."""

    # Retrieve video ID from the event
    video_id = record.dynamodb["Keys"]["video_id"]["S"]

    if record.event_name == DynamoDBRecordEventName.INSERT:
        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={"video_id": {"S": video_id}},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": {"S": "INSERTION_IN_PROGRESS"}},
        )

        try:
            # Initialize the processor with the API key
            secret_name = f"{ENVIRONMENT}/YoutubeSentimentAnalysis"
            api_key = parameters.get_secret(secret_name)

            # Retrieve and process comments
            comments = handler.retrieve_comments_from_youtube(video_id, api_key)

            # Batch detect sentiment
            comments_with_sentiment = handler.batch_detect_sentiment(comments)

            # Upload comments to S3
            s3_key = handler.upload_comments_to_s3(comments_with_sentiment, video_id)

        except Exception as error:
            logger.exception(
                {"message": "Failed to process comments", "error": str(error)}
            )

            # Update the DynamoDB item with the error message
            dynamodb.update_item(
                TableName=DYNAMODB_TABLE_NAME,
                Key={"video_id": {"S": video_id}},
                UpdateExpression="SET #status = :status, #error_message = :error_message, #completed_at = :completed_at",
                ExpressionAttributeNames={
                    "#status": "status",
                    "#error_message": "error_message",
                    "#completed_at": "completed_at",
                },
                ExpressionAttributeValues={
                    ":status": {"S": "INSERTION_FAILED"},
                    ":error_message": {"S": str(error)},
                    ":completed_at": {"S": datetime.now().isoformat()},
                },
            )

            raise error

        dynamodb.update_item(
            TableName=DYNAMODB_TABLE_NAME,
            Key={"video_id": {"S": video_id}},
            UpdateExpression="SET #status = :status, #result_file_url = :result_file_url, #total_comments = :total_comments, #completed_at = :completed_at",
            ExpressionAttributeNames={
                "#status": "status",
                "#result_file_url": "result_file_url",
                "#total_comments": "total_comments",
                "#completed_at": "completed_at",
            },
            ExpressionAttributeValues={
                ":status": {"S": "INSERTION_COMPLETED"},
                ":result_file_url": {"S": f"s3://{BUCKET_NAME}/{s3_key}"},
                ":total_comments": {"N": str(len(comments_with_sentiment))},
                ":completed_at": {"S": datetime.now().isoformat()},
            },
        )

        # Build and return the response
        return {
            "action": record.event_name,
            "video_id": video_id,
            "total_comments": len(comments_with_sentiment),
            "output": {
                "bucket_name": BUCKET_NAME,
                "bucket_key": s3_key,
                "s3_uri": f"s3://{BUCKET_NAME}/{s3_key}",
            },
        }

    if record.event_name == DynamoDBRecordEventName.REMOVE:
        # Retrieve and process comments
        comments = handler.retrieve_comments_from_s3(video_id)

        # Delete comments from S3
        handler.remove_comments_from_s3(video_id)

        logger.info(
            {
                "message": "Deleted comments from S3",
                "video_id": video_id,
                "total_comments": len(comments),
            }
        )

        # Build and return the response
        return {
            "action": record.event_name,
            "video_id": video_id,
            "total_comments": len(comments),
        }

    raise ValueError(f"Unsupported event name: {record.event_name}")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event, context: LambdaContext) -> dict:
    """AWS Lambda handler for processing video comments."""

    return process_partial_response(
        event=event,
        record_handler=record_handler,
        processor=processor,
        context=context,
    )
