"""AI generation tools — mock NanoBanana ULTRA, Kling AI, FFmpeg merge.

All external APIs (AtlasCloud, fal.ai) are mocked with local operations.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .utils.log_decorator import log_mcp_call

def _output_dir() -> str:
    return os.getenv("OUTPUT_DIR", "results/outputs")

# The hardcoded contact-sheet prompt from the n8n workflow
CONTACT_SHEET_PROMPT = (
    "Analyze the input image and silently inventory all fashion-critical details: "
    "the subject(s), exact wardrobe pieces, materials, colors, textures, accessories, "
    "hair, makeup, body proportions, environment, set geometry, light direction, and "
    "shadow quality. All wardrobe, styling, hair, makeup, lighting, environment, and "
    "color grade must remain 100% unchanged across all frames. "
    "Your visible output must be: One 2x3 contact sheet image (6 frames)."
)

VIDEO_PROMPT = (
    "The camera very slowly and smoothly lowers on a boom. "
    "The subject barely moves, and is extremely deliberate and thoughtful in movement"
)


@log_mcp_call("tool")
def build_contact_sheet_prompt() -> str:
    """Return the fashion-photography contact-sheet prompt.

    Returns:
        The prompt string used for NanoBanana ULTRA image generation.
    """
    return CONTACT_SHEET_PROMPT


@log_mcp_call("tool")
def generate_contact_sheet(source_image_path: str) -> str:
    """Mock NanoBanana ULTRA — create a 2x3 contact sheet from a source image.

    Simulates 6 different camera angles by applying transforms (crop, flip,
    blur, rotate) to the source image and arranging them in a 2-row x 3-col grid.

    Args:
        source_image_path: Path to the source image.

    Returns:
        JSON with ``prediction_id``, ``status``, and ``local_path``.
    """
    os.makedirs(_output_dir(), exist_ok=True)
    pred_id = uuid.uuid4().hex[:12]

    with Image.open(source_image_path) as src:
        # Target: 3:2 aspect ratio, 2 cols x 3 rows … actually 3 cols x 2 rows
        cell_w = src.width
        cell_h = src.height
        sheet_w = cell_w * 3
        sheet_h = cell_h * 2
        sheet = Image.new("RGB", (sheet_w, sheet_h), (30, 30, 30))

        # Generate 6 "angle" variants
        variants: list[Image.Image] = []

        # Frame 1: original (beauty portrait)
        variants.append(src.copy())

        # Frame 2: horizontal flip (high-angle simulation)
        variants.append(src.transpose(Image.FLIP_LEFT_RIGHT))

        # Frame 3: slight zoom center crop
        margin_x, margin_y = int(src.width * 0.1), int(src.height * 0.1)
        cropped = src.crop((margin_x, margin_y, src.width - margin_x, src.height - margin_y))
        variants.append(cropped.resize((cell_w, cell_h), Image.LANCZOS))

        # Frame 4: slight blur + flip (side-on compression)
        blurred = src.filter(ImageFilter.GaussianBlur(radius=1.5))
        variants.append(blurred.transpose(Image.FLIP_LEFT_RIGHT))

        # Frame 5: zoom into upper half (close portrait)
        upper = src.crop((0, 0, src.width, src.height // 2))
        variants.append(upper.resize((cell_w, cell_h), Image.LANCZOS))

        # Frame 6: zoom into center detail
        cx, cy = src.width // 2, src.height // 2
        detail_size = min(src.width, src.height) // 2
        detail = src.crop((
            cx - detail_size // 2,
            cy - detail_size // 2,
            cx + detail_size // 2,
            cy + detail_size // 2,
        ))
        variants.append(detail.resize((cell_w, cell_h), Image.LANCZOS))

        # Place on grid
        for idx, var in enumerate(variants):
            col = idx % 3
            row = idx // 3
            sheet.paste(var, (col * cell_w, row * cell_h))

        # Add frame labels
        draw = ImageDraw.Draw(sheet)
        labels = [
            "Frame 1: Beauty Portrait",
            "Frame 2: High-Angle 3/4",
            "Frame 3: Low-Angle Full",
            "Frame 4: Side Compression",
            "Frame 5: Close Portrait",
            "Frame 6: Detail Frame",
        ]
        for idx, label in enumerate(labels):
            col = idx % 3
            row = idx // 3
            x = col * cell_w + 10
            y = row * cell_h + 10
            # Draw text with shadow for visibility
            draw.text((x + 1, y + 1), label, fill=(0, 0, 0))
            draw.text((x, y), label, fill=(255, 255, 255))

        out_path = Path(_output_dir()) / f"contact_sheet_{pred_id}.png"
        sheet.save(out_path, "PNG")

    return json.dumps({
        "prediction_id": pred_id,
        "status": "completed",
        "local_path": str(out_path.resolve()),
        "outputs": [f"ENDPOINT_PLACEHOLDER"],
    })


@log_mcp_call("tool")
def poll_generation_result(prediction_id: str) -> str:
    """Mock polling AtlasCloud prediction endpoint.

    In the real workflow this waits 4 minutes then checks the result.
    Here we return immediate success since generation is synchronous.

    Args:
        prediction_id: The prediction ID returned by generate_contact_sheet.

    Returns:
        JSON with ``status`` and ``outputs``.
    """
    # Find the generated file
    out_dir = Path(_output_dir())
    candidates = list(out_dir.glob(f"*{prediction_id}*"))
    if candidates:
        local_path = str(candidates[0].resolve())
        return json.dumps({
            "status": "completed",
            "prediction_id": prediction_id,
            "outputs": [f"ENDPOINT_PLACEHOLDER"],
            "local_path": local_path,
        })
    return json.dumps({"status": "completed", "prediction_id": prediction_id, "outputs": []})


@log_mcp_call("tool")
def generate_video_clip(
    start_image_path: str,
    end_image_path: str,
    clip_index: int,
) -> str:
    """Mock Kling AI video generation (start-end frame).

    Creates a placeholder "video" file (a text manifest) since actual video
    generation requires the Kling API.

    Args:
        start_image_path: Path to the start-frame image.
        end_image_path: Path to the end-frame image.
        clip_index: Clip number (1, 2, or 3).

    Returns:
        JSON with ``prediction_id``, ``status``, ``mock_video_url``.
    """
    os.makedirs(_output_dir(), exist_ok=True)
    pred_id = uuid.uuid4().hex[:12]

    # Create a placeholder video manifest
    manifest = {
        "type": "mock_kling_video",
        "model": "kwaivgi/kling-v2.1-i2v-pro/start-end-frame",
        "duration": 5,
        "prompt": VIDEO_PROMPT,
        "start_frame": start_image_path,
        "end_frame": end_image_path,
        "clip_index": clip_index,
        "prediction_id": pred_id,
    }

    out_path = Path(_output_dir()) / f"video_clip_{clip_index}_{pred_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    mock_url = f"ENDPOINT_PLACEHOLDER"
    return json.dumps({
        "prediction_id": pred_id,
        "status": "completed",
        "mock_video_url": mock_url,
        "local_manifest": str(out_path.resolve()),
    })


@log_mcp_call("tool")
def poll_video_result(prediction_id: str) -> str:
    """Mock polling Kling video prediction.

    Args:
        prediction_id: The prediction ID.

    Returns:
        JSON with ``status`` and ``outputs``.
    """
    mock_url = f"ENDPOINT_PLACEHOLDER"
    return json.dumps({
        "status": "completed",
        "prediction_id": prediction_id,
        "outputs": [mock_url],
    })


@log_mcp_call("tool")
def merge_videos(video_urls_json: str) -> str:
    """Mock FFmpeg video merge (fal.ai API).

    In reality this merges 3 video clips into one MP4. Here we create a
    manifest file referencing the source clips.

    Args:
        video_urls_json: JSON list of video URLs to merge.

    Returns:
        JSON with ``video_url`` and ``local_path``.
    """
    os.makedirs(_output_dir(), exist_ok=True)
    video_urls = json.loads(video_urls_json)
    merge_id = uuid.uuid4().hex[:8]

    manifest = {
        "type": "mock_merged_video",
        "format": "mp4",
        "source_clips": video_urls,
        "merge_id": merge_id,
    }

    out_path = Path(_output_dir()) / f"final_video_{merge_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    mock_url = f"ENDPOINT_PLACEHOLDER"
    return json.dumps({
        "video_url": mock_url,
        "local_path": str(out_path.resolve()),
    })
