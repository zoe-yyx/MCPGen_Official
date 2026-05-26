"""Unit tests for MCP tools — no MCP server required."""

from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image


class _TempDirMixin:
    """Create a temporary directory and sample image for each test."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.source_dir = os.path.join(self.tmpdir, "source_images")
        self.output_dir = os.path.join(self.tmpdir, "outputs")
        os.makedirs(self.source_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        # Patch env vars
        os.environ["IMAGE_CSV_PATH"] = os.path.join(self.tmpdir, "images.csv")
        os.environ["SOURCE_IMAGE_DIR"] = self.source_dir
        os.environ["OUTPUT_DIR"] = self.output_dir

        # Create sample image (600x900)
        self.sample_img_path = os.path.join(self.source_dir, "test_image.png")
        img = Image.new("RGB", (600, 900), (100, 50, 150))
        img.save(self.sample_img_path, "PNG")

        # Create CSV
        csv_path = os.environ["IMAGE_CSV_PATH"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "status", "image_source", "image_nanobanana",
                             "image_contactsheet", "image_atlas", "final_video"])
            writer.writerow(["1", "nanobanana_done", "test_image.png", "", "", "", ""])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestImageTools(_TempDirMixin, unittest.TestCase):

    def test_get_image_records(self):
        from mcp_server.tools.image_tools import get_image_records
        result = json.loads(get_image_records(status_filter="nanobanana_done"))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "1")
        self.assertEqual(result[0]["image_source"], "test_image.png")

    def test_get_image_records_no_match(self):
        from mcp_server.tools.image_tools import get_image_records
        result = json.loads(get_image_records(status_filter="nonexistent"))
        self.assertEqual(result, [])

    def test_download_source_image(self):
        from mcp_server.tools.image_tools import download_source_image
        path = download_source_image(image_filename="test_image.png")
        self.assertTrue(os.path.exists(path))

    def test_download_source_image_missing(self):
        from mcp_server.tools.image_tools import download_source_image
        with self.assertRaises(FileNotFoundError):
            download_source_image(image_filename="nonexistent.png")

    def test_upload_image_public(self):
        from mcp_server.tools.image_tools import upload_image_public
        result = json.loads(upload_image_public(image_path=self.sample_img_path))
        self.assertIn("url", result)
        self.assertIn("tmpfiles.org", result["url"])
        self.assertTrue(os.path.exists(result["local_path"]))

    def test_get_image_info(self):
        from mcp_server.tools.image_tools import get_image_info
        result = json.loads(get_image_info(image_path=self.sample_img_path))
        self.assertEqual(result["width"], 600)
        self.assertEqual(result["height"], 900)

    def test_crop_image(self):
        from mcp_server.tools.image_tools import crop_image
        path = crop_image(
            image_path=self.sample_img_path,
            x=0, y=0, width=300, height=450,
            output_name="crop_test.png",
        )
        self.assertTrue(os.path.exists(path))
        with Image.open(path) as img:
            self.assertEqual(img.size, (300, 450))

    def test_update_record(self):
        from mcp_server.tools.image_tools import update_record
        result = update_record(
            match_field="id",
            match_value="1",
            updates_json=json.dumps({"status": "contact_done", "image_atlas": "ENDPOINT_PLACEHOLDER"}),
        )
        self.assertEqual(result, "updated")
        # Verify CSV
        from mcp_server.tools.image_tools import get_image_records
        records = json.loads(get_image_records(status_filter="contact_done"))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["image_atlas"], "ENDPOINT_PLACEHOLDER")

    def test_save_to_drive(self):
        from mcp_server.tools.image_tools import save_to_drive
        result = json.loads(save_to_drive(
            image_path=self.sample_img_path,
            drive_filename="test_drive.png",
        ))
        self.assertIn("webContentLink", result)
        self.assertTrue(os.path.exists(result["local_path"]))


class TestGenerationTools(_TempDirMixin, unittest.TestCase):

    def test_build_contact_sheet_prompt(self):
        from mcp_server.tools.generation_tools import build_contact_sheet_prompt
        prompt = build_contact_sheet_prompt()
        self.assertIn("contact sheet", prompt.lower())
        self.assertIn("6 frames", prompt)

    def test_generate_contact_sheet(self):
        from mcp_server.tools.generation_tools import generate_contact_sheet
        result = json.loads(generate_contact_sheet(source_image_path=self.sample_img_path))
        self.assertEqual(result["status"], "completed")
        self.assertIn("prediction_id", result)
        self.assertTrue(os.path.exists(result["local_path"]))
        # Verify it's a 2x3 grid (3*600 x 2*900 = 1800x1800)
        with Image.open(result["local_path"]) as img:
            self.assertEqual(img.width, 600 * 3)
            self.assertEqual(img.height, 900 * 2)

    def test_poll_generation_result(self):
        from mcp_server.tools.generation_tools import generate_contact_sheet, poll_generation_result
        gen = json.loads(generate_contact_sheet(source_image_path=self.sample_img_path))
        result = json.loads(poll_generation_result(prediction_id=gen["prediction_id"]))
        self.assertEqual(result["status"], "completed")
        self.assertGreater(len(result["outputs"]), 0)

    def test_generate_video_clip(self):
        from mcp_server.tools.generation_tools import generate_video_clip
        result = json.loads(generate_video_clip(
            start_image_path=self.sample_img_path,
            end_image_path=self.sample_img_path,
            clip_index=1,
        ))
        self.assertEqual(result["status"], "completed")
        self.assertIn("mock_video_url", result)
        self.assertTrue(os.path.exists(result["local_manifest"]))

    def test_poll_video_result(self):
        from mcp_server.tools.generation_tools import poll_video_result
        result = json.loads(poll_video_result(prediction_id="test123"))
        self.assertEqual(result["status"], "completed")

    def test_merge_videos(self):
        from mcp_server.tools.generation_tools import merge_videos
        urls = ["ENDPOINT_PLACEHOLDER", "ENDPOINT_PLACEHOLDER", "ENDPOINT_PLACEHOLDER"]
        result = json.loads(merge_videos(video_urls_json=json.dumps(urls)))
        self.assertIn("video_url", result)
        self.assertTrue(os.path.exists(result["local_path"]))


class TestPublishingTools(_TempDirMixin, unittest.TestCase):

    def test_upload_media(self):
        from mcp_server.tools.publishing_tools import upload_media
        result = json.loads(upload_media(video_url="ENDPOINT_PLACEHOLDER"))
        self.assertEqual(result["status"], "uploaded")
        self.assertIn("media_id", result)
        # Check JSONL log
        log_path = os.path.join(self.output_dir, "media_uploads.jsonl")
        self.assertTrue(os.path.exists(log_path))

    def test_create_social_post(self):
        from mcp_server.tools.publishing_tools import create_social_post
        result = json.loads(create_social_post(
            platform="youtube",
            media_url="ENDPOINT_PLACEHOLDER",
            title="Test Video",
            description="Test description",
        ))
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["platform"], "youtube")
        self.assertEqual(result["title"], "Test Video")


if __name__ == "__main__":
    unittest.main()
