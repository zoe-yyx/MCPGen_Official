"""Download tools — mock Threads video file download."""

import hashlib
import json
import os
import time

from mcp_server.tools.utils.log_decorator import log_mcp_call

# Minimal valid MP4 ftyp box (ISO Base Media file format signature)
_MOCK_MP4_HEADER = (
    b"\x00\x00\x00\x20ftypisom"
    b"\x00\x00\x02\x00"
    b"isomiso2avc1mp41"
    + b"\x00" * 128
)


@log_mcp_call(operation_type="tool")
def download_video_file(download_url: str) -> str:
    """Mock download of a Threads video from the provided URL.

    Creates a placeholder MP4 file in results/outputs/ and returns its local path.
    In production this would stream-download the real video bytes.
    """
    os.makedirs("results/outputs", exist_ok=True)

    video_id = hashlib.md5(download_url.encode()).hexdigest()[:16]
    filename = f"threads_video_{video_id}.mp4"
    local_path = os.path.join("results", "outputs", filename)

    with open(local_path, "wb") as f:
        f.write(_MOCK_MP4_HEADER)

    return json.dumps({
        "download_url": download_url,
        "local_path": local_path,
        "filename": filename,
        "size_bytes": len(_MOCK_MP4_HEADER),
        "content_type": "video/mp4",
        "downloaded_at": int(time.time()),
        "mock": True,
    })
