"""Image management tools — CSV records, image I/O, cropping.

Mocks Google Sheets / Google Drive / tmpfiles with local file operations.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image

from .utils.log_decorator import log_mcp_call

# ---------------------------------------------------------------------------
# Paths (read at call time so tests can override via os.environ)
# ---------------------------------------------------------------------------

def _csv_path() -> str:
    return os.getenv("IMAGE_CSV_PATH", "data/images.csv")

def _source_dir() -> str:
    return os.getenv("SOURCE_IMAGE_DIR", "data/source_images")

def _output_dir() -> str:
    return os.getenv("OUTPUT_DIR", "results/outputs")


# ---------------------------------------------------------------------------
# CSV helpers (mock Google Sheets)
# ---------------------------------------------------------------------------

@log_mcp_call("tool")
def get_image_records(status_filter: str) -> str:
    """Read image records from CSV, return rows matching *status_filter*.

    Args:
        status_filter: Only return rows where ``status`` equals this value.

    Returns:
        JSON list of matching row dicts.
    """
    rows: list[dict] = []
    with open(_csv_path(), "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("status", "").strip() == status_filter:
                rows.append(row)
    return json.dumps(rows, ensure_ascii=False)


@log_mcp_call("tool")
def update_record(match_field: str, match_value: str, updates_json: str) -> str:
    """Update a CSV row where *match_field* == *match_value*.

    Args:
        match_field: Column name to match on.
        match_value: Value to match.
        updates_json: JSON dict of ``{column: new_value}`` pairs.

    Returns:
        ``"updated"`` on success.
    """
    updates: dict = json.loads(updates_json)
    rows: list[dict] = []
    with open(_csv_path(), "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            if row.get(match_field, "").strip() == match_value:
                row.update(updates)
            rows.append(row)
    # add any new columns from updates
    for k in updates:
        if k not in fieldnames:
            fieldnames.append(k)
    with open(_csv_path(), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return "updated"


# ---------------------------------------------------------------------------
# Image I/O (mock Google Drive / tmpfiles)
# ---------------------------------------------------------------------------

@log_mcp_call("tool")
def download_source_image(image_filename: str) -> str:
    """Load a source image from the local data folder (mock Google Drive).

    Args:
        image_filename: File name inside ``data/source_images/``.

    Returns:
        Absolute path to the image file.
    """
    src = Path(_source_dir()) / image_filename
    if not src.exists():
        raise FileNotFoundError(f"Source image not found: {src}")
    return str(src.resolve())


@log_mcp_call("tool")
def upload_image_public(image_path: str) -> str:
    """Mock tmpfiles upload — copy image to outputs and return a fake public URL.

    Args:
        image_path: Local path to the image file.

    Returns:
        JSON with ``url`` (mock public URL) and ``local_path``.
    """
    os.makedirs(_output_dir(), exist_ok=True)
    stem = Path(image_path).stem
    ext = Path(image_path).suffix or ".png"
    dest_name = f"{stem}_{uuid.uuid4().hex[:8]}{ext}"
    dest = Path(_output_dir()) / dest_name
    shutil.copy2(image_path, dest)
    mock_url = f"ENDPOINT_PLACEHOLDER"
    return json.dumps({"url": mock_url, "local_path": str(dest.resolve())})


@log_mcp_call("tool")
def get_image_info(image_path: str) -> str:
    """Get image dimensions.

    Args:
        image_path: Path to an image file.

    Returns:
        JSON with ``width``, ``height``, ``format``.
    """
    with Image.open(image_path) as img:
        return json.dumps({
            "width": img.width,
            "height": img.height,
            "format": img.format or "PNG",
        })


@log_mcp_call("tool")
def crop_image(image_path: str, x: int, y: int, width: int, height: int, output_name: str) -> str:
    """Crop a region from an image and save it.

    Args:
        image_path: Source image path.
        x: Left pixel coordinate.
        y: Top pixel coordinate.
        width: Crop width in pixels.
        height: Crop height in pixels.
        output_name: Output file name (saved in _output_dir()).

    Returns:
        Path to the cropped image.
    """
    os.makedirs(_output_dir(), exist_ok=True)
    with Image.open(image_path) as img:
        box = (x, y, x + width, y + height)
        cropped = img.crop(box)
        dest = Path(_output_dir()) / output_name
        cropped.save(dest, "PNG")
    return str(dest.resolve())


@log_mcp_call("tool")
def save_to_drive(image_path: str, drive_filename: str) -> str:
    """Mock Google Drive upload — copy file to outputs.

    Args:
        image_path: Local path to the file.
        drive_filename: Destination file name.

    Returns:
        JSON with ``webContentLink`` (mock URL) and ``local_path``.
    """
    os.makedirs(_output_dir(), exist_ok=True)
    dest = Path(_output_dir()) / drive_filename
    shutil.copy2(image_path, dest)
    mock_link = f"ENDPOINT_PLACEHOLDER"
    return json.dumps({"webContentLink": mock_link, "local_path": str(dest.resolve())})
