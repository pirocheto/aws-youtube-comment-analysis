from __future__ import annotations

import typing

import requests
from aws_lambda_powertools.utilities import parameters

if typing.TYPE_CHECKING:
    from typing import Generator


from aws_lambda_powertools import Logger, Tracer

# YouTube API settings
YOUTUBE_API_KEY_SECRET_NAME = "dev/YouTubeAPIKey"  # noqa: S105
YOUTUBE_API_URL = "https://youtube.googleapis.com/youtube/v3/commentThreads"

logger = Logger()
tracer = Tracer()


@tracer.capture_method
def fetch_page(
    video_id: str,
    page_token: str | None = None,
) -> dict:
    """Fetch a single page of YouTube comments."""

    logger.info("Fetching comments page")
    api_key = parameters.get_secret(YOUTUBE_API_KEY_SECRET_NAME)

    headers = {"Accept": "application/json"}
    params = {
        "part": "snippet,replies",
        "key": api_key,
        "order": "time",
        "maxResults": 100,
        "moderationStatus": "published",
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


@tracer.capture_method
def get_data(video_id: str) -> Generator[dict, None, None]:
    """Fetch all comments for a YouTube video."""

    next_page_token = None

    while True:
        data = fetch_page(video_id, next_page_token)
        comments = data["items"]

        for comment in comments:
            yield comment

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
