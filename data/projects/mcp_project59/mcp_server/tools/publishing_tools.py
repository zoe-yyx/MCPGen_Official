"""Publishing tools — mock Blotato media upload and YouTube post creation."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime

from .utils.log_decorator import log_mcp_call

def _output_dir() -> str:
    return os.getenv("OUTPUT_DIR", "results/outputs")


@log_mcp_call("tool")
def upload_media(video_url: str) -> str:
    """Mock Blotato media upload.

    Args:
        video_url: URL of the video to upload.

    Returns:
        JSON with ``media_id`` and ``url``.
    """
    media_id = uuid.uuid4().hex[:10]
    result = {
        "media_id": media_id,
        "url": f"ENDPOINT_PLACEHOLDER",
        "source_url": video_url,
        "status": "uploaded",
    }

    # Persist upload record
    os.makedirs(_output_dir(), exist_ok=True)
    log_path = os.path.join(_output_dir(), "media_uploads.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result) + "\n")

    return json.dumps(result)


@log_mcp_call("tool")
def create_social_post(
    platform: str,
    media_url: str,
    title: str,
    description: str,
) -> str:
    """Mock creating a social-media post (YouTube via Blotato).

    Args:
        platform: Target platform (e.g. ``youtube``).
        media_url: URL of the uploaded media.
        title: Post / video title.
        description: Post body or video description.

    Returns:
        JSON with ``post_id``, ``platform``, ``status``.
    """
    post_id = uuid.uuid4().hex[:10]
    result = {
        "post_id": post_id,
        "platform": platform,
        "title": title,
        "description": description,
        "media_url": media_url,
        "status": "published",
        "privacy": "private",
        "created_at": datetime.now().isoformat(),
    }

    os.makedirs(_output_dir(), exist_ok=True)
    log_path = os.path.join(_output_dir(), "social_posts.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result) + "\n")

    return json.dumps(result)
