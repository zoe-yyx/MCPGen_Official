#!/usr/bin/env python
"""
run_workflow.py — AI Image to Professional Video Workflow

Replicates the n8n workflow using FastMCP Client:

Phase 1 — Contact Sheet Generation (NanoBanana ULTRA mock)
  Step 1 : Read image records (status = nanobanana_done)
  Step 2 : Download source image from local storage
  Step 3 : Upload image to get public URL (mock tmpfiles)
  Step 4 : Build contact-sheet prompt
  Step 5 : Generate 2x3 contact sheet (mock NanoBanana ULTRA)
  Step 6 : Poll generation result
  Step 7 : Save contact sheet to Drive (mock)
  Step 8 : Update record → status = contact_done

Phase 2 — Video Creation & Publishing (Kling AI + Blotato mock)
  Step 9 : Read image records (status = contact_done)
  Step 10: Get contact-sheet dimensions
  Step 11: Crop into 4 frames (top-left, top-center, top-right, bottom-left)
  Step 12: Upload 4 cropped frames (mock tmpfiles)
  Step 13: Generate 3 video clips (mock Kling)
  Step 14: Poll 3 video results
  Step 15: Merge 3 videos (mock FFmpeg)
  Step 16: Update record → status = video_done
  Step 17: Upload media (mock Blotato)
  Step 18: Create social post (mock YouTube)
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client
from PIL import Image

from mcp_server.tools.utils.log_decorator import setup_logging

load_dotenv()
logger = setup_logging("logs/workflow.log")

CSV_PATH = os.getenv("IMAGE_CSV_PATH", "data/images.csv")
SOURCE_DIR = os.getenv("SOURCE_IMAGE_DIR", "data/source_images")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(result) -> dict | list:
    if not result.content:
        return []
    return json.loads(result.content[0].text)


def _parse_text(result) -> str:
    if not result.content:
        return ""
    return result.content[0].text


def ensure_sample_data() -> None:
    """Create sample CSV and a placeholder source image if they don't exist."""
    os.makedirs(SOURCE_DIR, exist_ok=True)
    os.makedirs("results/outputs", exist_ok=True)
    os.makedirs("results/metrics", exist_ok=True)

    # Create sample image if missing
    sample_img = Path(SOURCE_DIR) / "sample_fashion.png"
    if not sample_img.exists():
        img = Image.new("RGB", (600, 900), (45, 45, 60))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        # Draw a simple fashion silhouette placeholder
        draw.rectangle([200, 100, 400, 250], fill=(180, 140, 100))  # head
        draw.rectangle([150, 250, 450, 600], fill=(60, 60, 90))     # body
        draw.rectangle([150, 600, 280, 850], fill=(40, 40, 70))     # left leg
        draw.rectangle([320, 600, 450, 850], fill=(40, 40, 70))     # right leg
        draw.text((180, 50), "Fashion Model", fill=(255, 255, 255))
        draw.text((180, 870), "Sample Image", fill=(150, 150, 150))
        img.save(sample_img, "PNG")
        logger.info(f"Created sample image: {sample_img}")

    # Create CSV if missing
    csv_path = Path(CSV_PATH)
    os.makedirs(csv_path.parent, exist_ok=True)
    if not csv_path.exists():
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "status", "image_source", "image_nanobanana",
                "image_contactsheet", "image_atlas", "final_video",
            ])
            writer.writerow([
                "1", "nanobanana_done", "sample_fashion.png", "", "", "", "",
            ])
        logger.info(f"Created sample CSV: {csv_path}")


def reset_csv() -> None:
    """Reset CSV so every run starts fresh."""
    csv_path = Path(CSV_PATH)
    if csv_path.exists():
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "status", "image_source", "image_nanobanana",
                "image_contactsheet", "image_atlas", "final_video",
            ])
            writer.writerow([
                "1", "nanobanana_done", "sample_fashion.png", "", "", "", "",
            ])
    logger.info("CSV reset — all records set to nanobanana_done.")


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

async def run_workflow() -> None:
    ensure_sample_data()
    reset_csv()

    logger.info(f"{'=' * 60}")
    logger.info("  AI Image to Professional Video Workflow")
    logger.info(f"  NanoBanana Ultra + Kling AI (mock mode)")
    logger.info(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 60}")

    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info(f"\nAvailable tools ({len(tools)}):")
        for t in tools:
            logger.info(f"  - {t.name}")

        # ==================================================================
        # PHASE 1 — Contact Sheet Generation
        # ==================================================================
        logger.info(f"\n{'=' * 60}")
        logger.info("PHASE 1 — Contact Sheet Generation (NanoBanana ULTRA)")
        logger.info(f"{'=' * 60}")

        # Step 1: Read image records
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 1] Reading image records (status=nanobanana_done) ...")
        result = await client.call_tool("get_image_records", {"status_filter": "nanobanana_done"})
        records = _parse(result)
        logger.info(f"  -> Found {len(records)} record(s)")

        if not records:
            logger.info("No records to process. Workflow complete.")
            return

        record = records[0]
        record_id = record["id"]
        image_source = record["image_source"]

        # Step 2: Download source image
        logger.info(f"\n{'~' * 40}")
        logger.info(f"[Step 2] Downloading source image: {image_source} ...")
        result = await client.call_tool("download_source_image", {"image_filename": image_source})
        source_path = _parse_text(result)
        logger.info(f"  -> Path: {source_path}")

        # Step 3: Upload to get public URL
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 3] Uploading image for public URL (mock tmpfiles) ...")
        result = await client.call_tool("upload_image_public", {"image_path": source_path})
        upload_info = _parse(result)
        public_url = upload_info["url"]
        logger.info(f"  -> Public URL: {public_url}")

        # Step 4: Build contact-sheet prompt
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 4] Building contact-sheet prompt ...")
        result = await client.call_tool("build_contact_sheet_prompt", {})
        prompt = _parse_text(result)
        logger.info(f"  -> Prompt: {prompt[:80]}...")

        # Step 5: Generate contact sheet
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 5] Generating 2x3 contact sheet (mock NanoBanana ULTRA) ...")
        result = await client.call_tool("generate_contact_sheet", {"source_image_path": source_path})
        gen_result = _parse(result)
        prediction_id = gen_result["prediction_id"]
        contact_sheet_path = gen_result["local_path"]
        logger.info(f"  -> Prediction ID: {prediction_id}")
        logger.info(f"  -> Contact sheet: {contact_sheet_path}")

        # Step 6: Poll generation result
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 6] Polling generation result ...")
        result = await client.call_tool("poll_generation_result", {"prediction_id": prediction_id})
        poll_result = _parse(result)
        atlas_url = poll_result["outputs"][0] if poll_result.get("outputs") else ""
        logger.info(f"  -> Status: {poll_result['status']}")
        logger.info(f"  -> Atlas URL: {atlas_url}")

        # Step 7: Save contact sheet to Drive
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 7] Saving contact sheet to Drive (mock) ...")
        result = await client.call_tool("save_to_drive", {
            "image_path": contact_sheet_path,
            "drive_filename": f"contact_sheet_{record_id}.png",
        })
        drive_result = _parse(result)
        drive_link = drive_result["webContentLink"]
        logger.info(f"  -> Drive link: {drive_link}")

        # Step 8: Update record → contact_done
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 8] Updating record status → contact_done ...")
        await client.call_tool("update_record", {
            "match_field": "id",
            "match_value": record_id,
            "updates_json": json.dumps({
                "status": "contact_done",
                "image_contactsheet": drive_link,
                "image_atlas": atlas_url,
            }),
        })
        logger.info("  -> updated")

        # ==================================================================
        # PHASE 2 — Video Creation & Publishing
        # ==================================================================
        logger.info(f"\n{'=' * 60}")
        logger.info("PHASE 2 — Video Creation & Publishing (Kling AI)")
        logger.info(f"{'=' * 60}")

        # Step 9: Re-read records with contact_done
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 9] Reading records (status=contact_done) ...")
        result = await client.call_tool("get_image_records", {"status_filter": "contact_done"})
        records = _parse(result)
        logger.info(f"  -> Found {len(records)} record(s)")

        if not records:
            logger.info("No contact_done records. Skipping Phase 2.")
            return

        record = records[0]

        # Step 10: Get contact-sheet dimensions
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 10] Getting contact-sheet dimensions ...")
        result = await client.call_tool("get_image_info", {"image_path": contact_sheet_path})
        img_info = _parse(result)
        sheet_w = img_info["width"]
        sheet_h = img_info["height"]
        cell_w = sheet_w // 3
        cell_h = sheet_h // 2
        logger.info(f"  -> Sheet: {sheet_w}x{sheet_h}, Cell: {cell_w}x{cell_h}")

        # Step 11: Crop into 4 frames
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 11] Cropping contact sheet into frames ...")
        crop_specs = [
            ("top_left", 0, 0),
            ("top_center", cell_w, 0),
            ("top_right", cell_w * 2, 0),
            ("bottom_left", 0, cell_h),
        ]
        crop_paths: dict[str, str] = {}
        for name, x, y in crop_specs:
            result = await client.call_tool("crop_image", {
                "image_path": contact_sheet_path,
                "x": x, "y": y,
                "width": cell_w, "height": cell_h,
                "output_name": f"crop_{name}.png",
            })
            crop_paths[name] = _parse_text(result)
            logger.info(f"  -> {name}: {crop_paths[name]}")

        # Step 12: Upload 4 cropped frames
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 12] Uploading cropped frames (mock tmpfiles) ...")
        crop_urls: dict[str, str] = {}
        for name, path in crop_paths.items():
            result = await client.call_tool("upload_image_public", {"image_path": path})
            info = _parse(result)
            crop_urls[name] = info["url"]
            logger.info(f"  -> {name}: {crop_urls[name]}")

        # Step 13: Generate 3 video clips
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 13] Generating 3 video clips (mock Kling AI) ...")
        clip_pairs = [
            (1, "top_left", "top_center"),
            (2, "top_center", "top_right"),
            (3, "top_right", "bottom_left"),
        ]
        video_urls: list[str] = []
        for clip_idx, start_name, end_name in clip_pairs:
            result = await client.call_tool("generate_video_clip", {
                "start_image_path": crop_paths[start_name],
                "end_image_path": crop_paths[end_name],
                "clip_index": clip_idx,
            })
            clip_result = _parse(result)
            video_urls.append(clip_result["mock_video_url"])
            logger.info(f"  -> Clip {clip_idx}: {clip_result['mock_video_url']}")

        # Step 14: Poll 3 video results
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 14] Polling video generation results ...")
        for i, url in enumerate(video_urls, 1):
            pred_id = url.split("/")[-1].replace(".mp4", "")
            result = await client.call_tool("poll_video_result", {"prediction_id": pred_id})
            poll = _parse(result)
            logger.info(f"  -> Clip {i}: {poll['status']}")

        # Step 15: Merge 3 videos
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 15] Merging 3 video clips (mock FFmpeg) ...")
        result = await client.call_tool("merge_videos", {
            "video_urls_json": json.dumps(video_urls),
        })
        merge_result = _parse(result)
        final_video_url = merge_result["video_url"]
        logger.info(f"  -> Final video: {final_video_url}")

        # Step 16: Update record → video_done
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 16] Updating record status → video_done ...")
        await client.call_tool("update_record", {
            "match_field": "id",
            "match_value": record_id,
            "updates_json": json.dumps({
                "status": "video_done",
                "final_video": final_video_url,
            }),
        })
        logger.info("  -> updated")

        # Step 17: Upload media
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 17] Uploading media (mock Blotato) ...")
        result = await client.call_tool("upload_media", {"video_url": final_video_url})
        media_result = _parse(result)
        media_url = media_result["url"]
        logger.info(f"  -> Media URL: {media_url}")

        # Step 18: Create social post
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 18] Creating social post (mock YouTube via Blotato) ...")
        result = await client.call_tool("create_social_post", {
            "platform": "youtube",
            "media_url": media_url,
            "title": "AI Fashion Video — NanoBanana Ultra + Kling",
            "description": "Professional fashion video generated from a single image.",
        })
        post_result = _parse(result)
        logger.info(f"  -> Post ID: {post_result['post_id']}")
        logger.info(f"  -> Platform: {post_result['platform']}")
        logger.info(f"  -> Status: {post_result['status']}")

    # Save metrics
    metrics = {
        "workflow": "AI Image to Professional Video",
        "timestamp": datetime.now().isoformat(),
        "phases_completed": 2,
        "steps_completed": 18,
        "records_processed": 1,
        "contact_sheet_generated": True,
        "video_clips_generated": 3,
        "final_video_merged": True,
        "social_post_created": True,
    }
    os.makedirs("results/metrics", exist_ok=True)
    with open("results/metrics/run_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"\n{'=' * 60}")
    logger.info("  Workflow complete.")
    logger.info(f"  Steps: 18/18")
    logger.info(f"  Metrics: results/metrics/run_metrics.json")
    logger.info(f"  Outputs: results/outputs/")
    logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_workflow())
