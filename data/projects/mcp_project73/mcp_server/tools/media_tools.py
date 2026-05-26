"""Media tools — mock voice and photo file retrieval for Telegram vocabulary bot."""

import json
import os
import struct
import zlib

from mcp_server.tools.utils.log_decorator import log_mcp_call


@log_mcp_call(operation_type="tool")
def get_voice_file(file_id: str) -> str:
    """Mock Telegram getFile API call for a voice message file_id."""
    return json.dumps({
        "ok": True,
        "result": {
            "file_id": file_id,
            "file_unique_id": f"uniq_{file_id}",
            "file_size": 12345,
            "file_path": f"voice/{file_id}.oga",
        },
    })


@log_mcp_call(operation_type="tool")
def download_audio(file_path: str) -> str:
    """Mock download of a Telegram voice audio file. Returns path to local placeholder."""
    os.makedirs("results/outputs", exist_ok=True)
    safe_name = file_path.replace("/", "_").replace("\\", "_")
    local_path = f"results/outputs/audio_{safe_name}"
    # Minimal OGG signature placeholder — not a valid audio file but sufficient for mocking
    with open(local_path, "wb") as f:
        f.write(b"OggS" + b"\x00" * 24)
    return json.dumps({
        "file_path": file_path,
        "local_path": local_path,
        "size_bytes": os.path.getsize(local_path),
        "mock": True,
    })


@log_mcp_call(operation_type="tool")
def get_photo_file(file_id: str) -> str:
    """Mock Telegram getFile API call for a photo file_id."""
    return json.dumps({
        "ok": True,
        "result": {
            "file_id": file_id,
            "file_unique_id": f"uniq_{file_id}",
            "file_size": 54321,
            "file_path": f"photos/{file_id}.jpg",
        },
    })


@log_mcp_call(operation_type="tool")
def download_image(file_path: str) -> str:
    """Mock download of a Telegram photo. Returns path to a synthetic grey PNG."""
    os.makedirs("results/outputs", exist_ok=True)
    safe_name = file_path.replace("/", "_").replace("\\", "_")
    local_path = f"results/outputs/image_{safe_name}.png"
    png_data = _create_grey_png(100, 100)
    with open(local_path, "wb") as f:
        f.write(png_data)
    return json.dumps({
        "file_path": file_path,
        "local_path": local_path,
        "mime_type": "image/png",
        "size_bytes": len(png_data),
        "mock": True,
    })


def _create_grey_png(width: int, height: int) -> bytes:
    """Build a minimal valid PNG with a solid grey fill."""
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        body = chunk_type + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    row = b"\x00" + bytes([180, 180, 180] * width)  # filter byte + RGB grey
    idat = chunk(b"IDAT", zlib.compress(row * height, 9))
    iend = chunk(b"IEND", b"")
    return signature + ihdr + idat + iend
