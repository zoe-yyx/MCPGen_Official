"""Unit tests for Threads Video Downloader tools."""

import csv
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.form_tools import submit_form
from mcp_server.tools.threads_tools import check_video_exists, fetch_threads_video_data
from mcp_server.tools.download_tools import download_video_file
from mcp_server.tools.drive_tools import set_sharing_permissions, upload_video_to_drive
from mcp_server.tools.sheets_tools import (
    log_failure_to_sheets,
    log_success_to_sheets,
    wait_before_logging_failure,
)


class TestFormTools(unittest.TestCase):
    def test_submit_form_returns_url(self) -> None:
        result = json.loads(submit_form("ENDPOINT_PLACEHOLDER"))
        self.assertEqual(result["URL"], "ENDPOINT_PLACEHOLDER")

    def test_submit_form_strips_whitespace(self) -> None:
        result = json.loads(submit_form("  ENDPOINT_PLACEHOLDER  "))
        self.assertFalse(result["URL"].startswith(" "))

    def test_submit_form_has_timestamp(self) -> None:
        result = json.loads(submit_form("ENDPOINT_PLACEHOLDER"))
        self.assertIn("submitted_at", result)
        self.assertGreater(result["submitted_at"], 0)

    def test_submit_form_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            submit_form("")

    def test_submit_form_whitespace_only_raises(self) -> None:
        with self.assertRaises(ValueError):
            submit_form("   ")


class TestThreadsTools(unittest.TestCase):
    def test_fetch_valid_threads_url(self) -> None:
        result = json.loads(fetch_threads_video_data("ENDPOINT_PLACEHOLDER"))
        self.assertEqual(result["status"], "ok")
        self.assertGreater(len(result["video_urls"]), 0)
        self.assertTrue(result["video_urls"][0]["download_url"].endswith(".mp4"))

    def test_fetch_invalid_url_returns_empty(self) -> None:
        result = json.loads(fetch_threads_video_data("ENDPOINT_PLACEHOLDER"))
        self.assertEqual(result["status"], "no_video")
        self.assertEqual(result["video_urls"], [])

    def test_fetch_returns_multiple_qualities(self) -> None:
        result = json.loads(fetch_threads_video_data("ENDPOINT_PLACEHOLDER"))
        qualities = [v["quality"] for v in result["video_urls"]]
        self.assertIn("HD", qualities)

    def test_check_video_exists_true(self) -> None:
        api_resp = fetch_threads_video_data("ENDPOINT_PLACEHOLDER")
        result = json.loads(check_video_exists(api_resp))
        self.assertTrue(result["has_video"])
        self.assertIsNotNone(result["download_url"])
        self.assertIn(".mp4", result["download_url"])

    def test_check_video_exists_false(self) -> None:
        api_resp = json.dumps({"status": "no_video", "video_urls": [], "source": "ENDPOINT_PLACEHOLDER"})
        result = json.loads(check_video_exists(api_resp))
        self.assertFalse(result["has_video"])
        self.assertIsNone(result["download_url"])

    def test_check_video_exists_empty_url_in_list(self) -> None:
        api_resp = json.dumps({"video_urls": [{"download_url": ""}], "source": "x"})
        result = json.loads(check_video_exists(api_resp))
        self.assertFalse(result["has_video"])

    def test_check_returns_video_count(self) -> None:
        api_resp = fetch_threads_video_data("ENDPOINT_PLACEHOLDER")
        result = json.loads(check_video_exists(api_resp))
        self.assertGreater(result["video_count"], 0)


class TestDownloadTools(unittest.TestCase):
    _MOCK_URL = "ENDPOINT_PLACEHOLDER"

    def test_download_creates_file(self) -> None:
        result = json.loads(download_video_file(self._MOCK_URL))
        self.assertTrue(os.path.exists(result["local_path"]))

    def test_download_returns_mp4_filename(self) -> None:
        result = json.loads(download_video_file(self._MOCK_URL))
        self.assertTrue(result["filename"].endswith(".mp4"))

    def test_download_has_mp4_signature(self) -> None:
        result = json.loads(download_video_file(self._MOCK_URL))
        with open(result["local_path"], "rb") as f:
            header = f.read(8)
        # MP4 ftyp box: 4-byte size + 'ftyp'
        self.assertIn(b"ftyp", header)

    def test_download_positive_size(self) -> None:
        result = json.loads(download_video_file(self._MOCK_URL))
        self.assertGreater(result["size_bytes"], 0)

    def test_download_is_mock(self) -> None:
        result = json.loads(download_video_file(self._MOCK_URL))
        self.assertTrue(result["mock"])


class TestDriveTools(unittest.TestCase):
    def _get_local_path(self) -> str:
        result = json.loads(download_video_file("ENDPOINT_PLACEHOLDER"))
        return result["local_path"]

    def test_upload_returns_file_id(self) -> None:
        local = self._get_local_path()
        result = json.loads(upload_video_to_drive(local, "test_video.mp4"))
        self.assertIn("id", result)
        self.assertIsInstance(result["id"], str)
        self.assertGreater(len(result["id"]), 0)

    def test_upload_returns_web_view_link(self) -> None:
        local = self._get_local_path()
        result = json.loads(upload_video_to_drive(local, "test.mp4"))
        self.assertIn("drive.google.com", result["webViewLink"])
        self.assertIn(result["id"], result["webViewLink"])

    def test_upload_creates_local_copy(self) -> None:
        local = self._get_local_path()
        result = json.loads(upload_video_to_drive(local, "copy_test.mp4"))
        self.assertTrue(os.path.exists(result["local_path"]))

    def test_upload_is_mock(self) -> None:
        local = self._get_local_path()
        result = json.loads(upload_video_to_drive(local))
        self.assertTrue(result["mock"])

    def test_set_sharing_returns_permission_id(self) -> None:
        local = self._get_local_path()
        upload = json.loads(upload_video_to_drive(local, "share_test.mp4"))
        result = json.loads(set_sharing_permissions(upload["id"]))
        self.assertIn("id", result)
        self.assertEqual(result["type"], "anyone")
        self.assertEqual(result["role"], "reader")

    def test_set_sharing_returns_link(self) -> None:
        result = json.loads(set_sharing_permissions("fake_file_id_001"))
        self.assertIn("drive.google.com", result["sharing_url"])
        self.assertIn("fake_file_id_001", result["sharing_url"])

    def test_set_sharing_status(self) -> None:
        result = json.loads(set_sharing_permissions("abc123"))
        self.assertEqual(result["status"], "mock_set")


class TestSheetsTools(unittest.TestCase):
    def test_wait_before_logging(self) -> None:
        result = json.loads(wait_before_logging_failure(1))
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["waited_seconds"], 1)

    def test_log_success_appends_entry(self) -> None:
        url = "ENDPOINT_PLACEHOLDER"
        drive_url = "ENDPOINT_PLACEHOLDER"
        result = json.loads(log_success_to_sheets(url, drive_url))
        self.assertEqual(result["status"], "appended")
        self.assertEqual(result["row"]["URL"], url)
        self.assertEqual(result["row"]["Drive_URL"], drive_url)
        self.assertEqual(result["row"]["status"], "success")

    def test_log_failure_appends_na(self) -> None:
        url = "ENDPOINT_PLACEHOLDER"
        result = json.loads(log_failure_to_sheets(url))
        self.assertEqual(result["status"], "appended")
        self.assertEqual(result["row"]["Drive_URL"], "N/A")
        self.assertEqual(result["row"]["status"], "failed")

    def test_log_creates_csv(self) -> None:
        log_success_to_sheets("ENDPOINT_PLACEHOLDER", "ENDPOINT_PLACEHOLDER")
        self.assertTrue(os.path.exists("results/outputs/download_log.csv"))

    def test_log_csv_has_headers(self) -> None:
        log_success_to_sheets("ENDPOINT_PLACEHOLDER", "ENDPOINT_PLACEHOLDER")
        with open("results/outputs/download_log.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.assertIn("URL", reader.fieldnames or [])
            self.assertIn("Drive_URL", reader.fieldnames or [])
            self.assertIn("status", reader.fieldnames or [])

    def test_log_creates_json(self) -> None:
        log_success_to_sheets("ENDPOINT_PLACEHOLDER", "ENDPOINT_PLACEHOLDER")
        self.assertTrue(os.path.exists("results/outputs/download_log.json"))

    def test_log_json_contains_entry(self) -> None:
        url = "ENDPOINT_PLACEHOLDER"
        log_success_to_sheets(url, "ENDPOINT_PLACEHOLDER")
        with open("results/outputs/download_log.json", encoding="utf-8") as f:
            entries = json.load(f)
        urls = [e["URL"] for e in entries]
        self.assertIn(url, urls)


if __name__ == "__main__":
    unittest.main()
