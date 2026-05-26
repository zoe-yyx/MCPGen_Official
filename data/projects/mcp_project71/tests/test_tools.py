"""Unit tests for Instant Ad Banner Generator tools."""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.line_tools import receive_line_webhook, extract_line_data, send_line_reply
from mcp_server.tools.ai_tools import extract_prompt_text
from mcp_server.tools.image_gen_tools import (
    submit_image_generation,
    wait_for_processing,
    check_job_status,
    wait_for_generation,
    parse_result,
)
from mcp_server.tools.storage_tools import upload_to_s3


class TestLineTools(unittest.TestCase):
    def test_receive_line_webhook_structure(self) -> None:
        result = json.loads(receive_line_webhook("テスト商品の広告", "Uabc123"))
        self.assertIn("body", result)
        events = result["body"]["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["message"]["text"], "テスト商品の広告")
        self.assertEqual(events[0]["source"]["userId"], "Uabc123")
        self.assertIn("replyToken", events[0])

    def test_receive_line_webhook_custom_reply_token(self) -> None:
        result = json.loads(receive_line_webhook("msg", reply_token="my-token"))
        self.assertEqual(result["body"]["events"][0]["replyToken"], "my-token")

    def test_extract_line_data(self) -> None:
        webhook = receive_line_webhook("商品広告メッセージ", "Uuser001", "token-xyz")
        result = json.loads(extract_line_data(webhook))
        self.assertEqual(result["user_id"], "Uuser001")
        self.assertEqual(result["reply_token"], "token-xyz")
        self.assertEqual(result["message"], "商品広告メッセージ")
        self.assertIn("timestamp", result)

    def test_extract_line_data_no_events_raises(self) -> None:
        bad_webhook = json.dumps({"body": {"events": []}})
        with self.assertRaises(ValueError):
            extract_line_data(bad_webhook)

    def test_send_line_reply(self) -> None:
        result = json.loads(send_line_reply("token-abc", "ENDPOINT_PLACEHOLDER"))
        self.assertEqual(result["status"], "mock_sent")
        self.assertEqual(result["type"], "line_image_reply")
        self.assertIn("file", result)
        self.assertTrue(os.path.exists(result["file"]))


class TestAITools(unittest.TestCase):
    def test_extract_prompt_text_gemini_format(self) -> None:
        response = json.dumps({
            "content": {"parts": [{"text": "Professional photography, coffee cup"}]},
            "raw_text": "Professional photography, coffee cup",
        })
        result = json.loads(extract_prompt_text(response, "Uabc"))
        self.assertEqual(result["prompt"], "Professional photography, coffee cup")
        self.assertEqual(result["user_id"], "Uabc")

    def test_extract_prompt_text_raw_fallback(self) -> None:
        response = json.dumps({"raw_text": "Marketing banner for coffee"})
        result = json.loads(extract_prompt_text(response))
        self.assertEqual(result["prompt"], "Marketing banner for coffee")

    def test_extract_prompt_text_strips_quotes(self) -> None:
        response = json.dumps({
            "content": {"parts": [{"text": "'Beautiful product shot'"}]},
            "raw_text": "'Beautiful product shot'",
        })
        result = json.loads(extract_prompt_text(response))
        self.assertNotIn("'", result["prompt"][:1])

    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_optimize_prompt_calls_gpt(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = (
            "Professional product photography, premium coffee cup, "
            "featuring Japanese text [朝の一杯が、仕事を変える。] in bold modern font, "
            "dark background, dramatic lighting, 8K resolution"
        )
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        from mcp_server.tools.ai_tools import optimize_prompt
        result = json.loads(optimize_prompt("商品名: コーヒー / キャッチコピー: 朝の一杯"))
        self.assertIn("content", result)
        text = result["content"]["parts"][0]["text"]
        self.assertIn("professional product photography", text.lower())


class TestImageGenTools(unittest.TestCase):
    def test_submit_image_generation_returns_ids(self) -> None:
        result = json.loads(submit_image_generation("Professional coffee banner"))
        self.assertEqual(result["code"], 200)
        self.assertIn("taskId", result["data"])
        self.assertIn("recordId", result["data"])
        self.assertTrue(result["data"]["taskId"].startswith("task-"))

    def test_wait_for_processing(self) -> None:
        result = json.loads(wait_for_processing(10))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["waited_seconds"], 10)

    def test_check_job_status_success(self) -> None:
        submit = json.loads(submit_image_generation("test prompt"))
        task_id = submit["data"]["taskId"]
        record_id = submit["data"]["recordId"]
        result = json.loads(check_job_status(task_id, record_id))
        self.assertEqual(result["code"], 200)
        self.assertEqual(result["data"]["state"], "success")
        self.assertIn("resultJson", result["data"])

    def test_wait_for_generation(self) -> None:
        result = json.loads(wait_for_generation(10))
        self.assertEqual(result["status"], "completed")

    def test_parse_result_success(self) -> None:
        submit = json.loads(submit_image_generation("test"))
        task_id = submit["data"]["taskId"]
        status_resp = check_job_status(task_id, "rec-123")
        result = json.loads(parse_result(status_resp))
        self.assertEqual(result["status"], "completed")
        self.assertIn("imageUrl", result)
        self.assertTrue(result["imageUrl"].startswith("http"))

    def test_parse_result_processing(self) -> None:
        processing_resp = json.dumps({
            "code": 200,
            "data": {"state": "processing", "taskId": "t1", "resultJson": "{}"},
        })
        result = json.loads(parse_result(processing_resp))
        self.assertEqual(result["status"], "processing")

    def test_parse_result_fail_raises(self) -> None:
        fail_resp = json.dumps({
            "code": 200,
            "data": {"state": "fail", "failMsg": "quota exceeded", "taskId": "t1"},
        })
        with self.assertRaises(RuntimeError):
            parse_result(fail_resp)


class TestStorageTools(unittest.TestCase):
    def test_upload_to_s3_missing_source(self) -> None:
        result = json.loads(upload_to_s3("nonexistent_file.png", "test-banner.png"))
        self.assertEqual(result["status"], "mock_uploaded")
        self.assertIn("s3.", result["Location"])
        self.assertTrue(os.path.exists(result["file"]))

    def test_upload_to_s3_existing_source(self) -> None:
        # Write a temp source file
        src = "results/outputs/_test_src.png"
        os.makedirs("results/outputs", exist_ok=True)
        with open(src, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")  # minimal PNG header

        result = json.loads(upload_to_s3(src, "_test_uploaded.png"))
        self.assertEqual(result["status"], "mock_uploaded")
        self.assertTrue(os.path.exists(result["file"]))

    def test_upload_to_s3_url_format(self) -> None:
        result = json.loads(upload_to_s3("no_file.png", "banner-123.png"))
        bucket = os.getenv("AWS_S3_BUCKET", "banners-bot-v7158")
        self.assertIn(bucket, result["Location"])
        self.assertIn("banner-123.png", result["Location"])


class TestEndToEndFlow(unittest.TestCase):
    """Integration test: chain LINE → extract → submit → check → parse → upload."""

    def test_full_local_chain(self) -> None:
        webhook = receive_line_webhook(
            "商品名: テスト / ターゲット: 若者 / キャッチコピー: 新時代へ。",
            "Utest001",
            "test-reply-token",
        )
        line_data = json.loads(extract_line_data(webhook))
        self.assertEqual(line_data["reply_token"], "test-reply-token")

        response = json.dumps({
            "content": {"parts": [{"text": "Modern product shot, youth fashion"}]},
            "raw_text": "Modern product shot, youth fashion",
        })
        prompt_data = json.loads(extract_prompt_text(response, line_data["user_id"]))
        self.assertIn("product shot", prompt_data["prompt"])

        submit = json.loads(submit_image_generation(prompt_data["prompt"]))
        task_id = submit["data"]["taskId"]
        status = json.loads(check_job_status(task_id, submit["data"]["recordId"]))
        parsed = json.loads(parse_result(json.dumps(status)))
        self.assertEqual(parsed["status"], "completed")

        s3 = json.loads(upload_to_s3("no_file.png"))
        reply = json.loads(send_line_reply(line_data["reply_token"], s3["Location"]))
        self.assertEqual(reply["status"], "mock_sent")


if __name__ == "__main__":
    unittest.main()
