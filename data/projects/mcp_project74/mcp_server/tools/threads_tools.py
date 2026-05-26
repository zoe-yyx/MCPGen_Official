"""Threads tools — mock Threads Downloader RapidAPI and video existence check."""

import hashlib
import json
import time

from mcp_server.tools.utils.log_decorator import log_mcp_call

# URLs matching this pattern produce a successful mock API response
_VALID_HOSTS = ("threads.net", "www.threads.net", "threads.com")


@log_mcp_call(operation_type="tool")
def fetch_threads_video_data(url: str) -> str:
    """Mock POST to threads-downloader1.p.rapidapi.com/threads.php.

    Returns video metadata including download URLs when the URL looks valid,
    or an empty video_urls list when no video is found.
    """
    is_threads_url = any(host in url.lower() for host in _VALID_HOSTS)

    if is_threads_url:
        video_id = hashlib.md5(url.encode()).hexdigest()[:16]
        return json.dumps({
            "status": "ok",
            "source": url,
            "video_urls": [
                {
                    "download_url": f"ENDPOINT_PLACEHOLDER",
                    "quality": "HD",
                    "size": "5.2 MB",
                },
                {
                    "download_url": f"ENDPOINT_PLACEHOLDER",
                    "quality": "SD",
                    "size": "2.1 MB",
                },
            ],
            "thumbnail": f"ENDPOINT_PLACEHOLDER",
            "author": "mock_user",
            "caption": "Check out this amazing video! #threads",
            "retrieved_at": int(time.time()),
        })
    else:
        return json.dumps({
            "status": "no_video",
            "source": url,
            "video_urls": [],
            "error": "No video found or invalid Threads URL",
            "retrieved_at": int(time.time()),
        })


@log_mcp_call(operation_type="tool")
def check_video_exists(api_response_json: str) -> str:
    """Check whether the Threads API response contains a valid download URL.

    Maps to the n8n IF node that tests video_urls[0].download_url is not empty.
    Returns has_video=True/False plus the first download URL if available.
    """
    data = json.loads(api_response_json)
    video_urls = data.get("video_urls", [])
    first_url = video_urls[0].get("download_url", "").strip() if video_urls else ""
    has_video = bool(first_url)
    return json.dumps({
        "has_video": has_video,
        "download_url": first_url if has_video else None,
        "quality": video_urls[0].get("quality") if has_video else None,
        "video_count": len(video_urls),
        "source_url": data.get("source", ""),
    })
