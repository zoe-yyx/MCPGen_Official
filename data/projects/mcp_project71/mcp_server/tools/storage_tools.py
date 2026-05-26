"""Storage mock tools for mcp_project71 — image download and S3 upload."""

import json
import os
import struct
import time
import zlib
from datetime import datetime

import httpx

from .utils.log_decorator import log_mcp_call


def _create_minimal_png(width: int = 100, height: int = 100) -> bytes:
    """Create a minimal valid PNG with a solid blue-grey fill (no external deps)."""
    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        body = chunk_type + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">II", width, height) + bytes([8, 2, 0, 0, 0])
    ihdr = png_chunk(b"IHDR", ihdr_data)
    # Each row: filter byte (0=None) + RGB pixels
    row = b"\x00" + bytes([100, 116, 139] * width)  # steel-blue
    idat = png_chunk(b"IDAT", zlib.compress(row * height, 9))
    iend = png_chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


@log_mcp_call("tool", "download_image")
def download_image(image_url: str) -> str:
    """Download the generated image. Falls back to a placeholder PNG if the URL is unreachable."""
    os.makedirs("results/outputs", exist_ok=True)
    ts = int(time.time() * 1000)
    file_path = f"results/outputs/banner_{ts}.png"

    downloaded = False
    if image_url.startswith("http"):
        try:
            resp = httpx.get(image_url, follow_redirects=True, timeout=15.0)
            if resp.status_code == 200 and resp.content:
                with open(file_path, "wb") as f:
                    f.write(resp.content)
                downloaded = True
        except Exception:
            pass

    if not downloaded:
        # Generate a placeholder PNG locally
        png_bytes = _create_minimal_png(800, 800)
        with open(file_path, "wb") as f:
            f.write(png_bytes)

    file_size = os.path.getsize(file_path)
    return json.dumps({
        "file_path": file_path,
        "file_size": file_size,
        "source_url": image_url,
        "downloaded": downloaded,
        "content_type": "image/png",
    })


@log_mcp_call("tool", "upload_to_s3")
def upload_to_s3(file_path: str, filename: str = "") -> str:
    """Mock S3 upload: copy image to results/outputs/ and return a fake public URL."""
    import shutil

    bucket = os.getenv("AWS_S3_BUCKET", "banners-bot-v7158")
    region = os.getenv("AWS_REGION", "ap-northeast-1")

    if not filename:
        filename = f"banner-{int(time.time() * 1000)}.png"

    os.makedirs("results/outputs", exist_ok=True)
    dest_path = f"results/outputs/{filename}"

    if os.path.exists(file_path) and os.path.abspath(file_path) != os.path.abspath(dest_path):
        shutil.copy2(file_path, dest_path)
    elif not os.path.exists(file_path):
        # Create placeholder if source missing
        with open(dest_path, "wb") as f:
            f.write(_create_minimal_png(800, 800))

    fake_url = f"ENDPOINT_PLACEHOLDER"
    result = {
        "Location": fake_url,
        "Bucket": bucket,
        "Key": filename,
        "file": dest_path,
        "status": "mock_uploaded",
        "uploaded_at": datetime.now().isoformat() + "Z",
    }

    meta_path = dest_path.replace(".png", "_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return json.dumps(result)
