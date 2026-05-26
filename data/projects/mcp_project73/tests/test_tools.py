"""Unit tests for Vocabulary Lookup tools."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.telegram_tools import (
    check_authorization,
    detect_input_type,
    load_config,
    receive_telegram_message,
    reject_unauthorized_user,
    send_telegram_reply,
    set_photo_text,
    set_text_input,
    set_voice_text,
)
from mcp_server.tools.media_tools import download_audio, download_image, get_photo_file, get_voice_file
from mcp_server.tools.notion_tools import save_vocabulary_to_notion


class TestReceiveTelegramMessage(unittest.TestCase):
    def test_text_message_structure(self) -> None:
        result = json.loads(receive_telegram_message(text="phenomenon", input_type="text"))
        msg = result["message"]
        self.assertEqual(msg["text"], "phenomenon")
        self.assertIn("update_id", result)

    def test_voice_message_structure(self) -> None:
        result = json.loads(receive_telegram_message(input_type="voice", audio_file_id="voice_001"))
        msg = result["message"]
        self.assertIn("voice", msg)
        self.assertEqual(msg["voice"]["file_id"], "voice_001")

    def test_photo_message_structure(self) -> None:
        result = json.loads(receive_telegram_message(input_type="photo", photo_file_id="photo_001"))
        msg = result["message"]
        self.assertIn("photo", msg)
        self.assertEqual(msg["photo"][0]["file_id"], "photo_001")

    def test_custom_chat_id(self) -> None:
        result = json.loads(receive_telegram_message(text="hello", input_type="text", chat_id="9999999"))
        self.assertEqual(str(result["message"]["chat"]["id"]), "9999999")


class TestLoadConfig(unittest.TestCase):
    def test_returns_required_keys(self) -> None:
        result = json.loads(load_config())
        for key in ("TELEGRAM_CHAT_ID", "TELEGRAM_BOT_TOKEN", "NOTION_VOCABULARY_DB_ID", "TARGET_LANGUAGE"):
            self.assertIn(key, result)

    def test_target_language_default(self) -> None:
        result = json.loads(load_config())
        self.assertIsInstance(result["TARGET_LANGUAGE"], str)
        self.assertGreater(len(result["TARGET_LANGUAGE"]), 0)


class TestCheckAuthorization(unittest.TestCase):
    def _msg(self, chat_id: str) -> str:
        return receive_telegram_message(text="test", input_type="text", chat_id=chat_id)

    def _cfg(self, authorized_id: str) -> str:
        return json.dumps({"TELEGRAM_CHAT_ID": authorized_id, "TARGET_LANGUAGE": "Traditional Chinese",
                           "TELEGRAM_BOT_TOKEN": "t", "NOTION_VOCABULARY_DB_ID": "db"})

    def test_authorized_user(self) -> None:
        msg = self._msg("8308632587")
        cfg = self._cfg("8308632587")
        result = json.loads(check_authorization(msg, cfg))
        self.assertTrue(result["authorized"])

    def test_unauthorized_user(self) -> None:
        msg = self._msg("9999999")
        cfg = self._cfg("8308632587")
        result = json.loads(check_authorization(msg, cfg))
        self.assertFalse(result["authorized"])
        self.assertEqual(result["chat_id"], "9999999")


class TestDetectInputType(unittest.TestCase):
    def test_detects_text(self) -> None:
        msg = receive_telegram_message(text="quibble", input_type="text")
        result = json.loads(detect_input_type(msg))
        self.assertEqual(result["input_type"], "text")
        self.assertEqual(result["content"], "quibble")
        self.assertIsNone(result["file_id"])

    def test_detects_voice(self) -> None:
        msg = receive_telegram_message(input_type="voice", audio_file_id="v_001")
        result = json.loads(detect_input_type(msg))
        self.assertEqual(result["input_type"], "voice")
        self.assertEqual(result["file_id"], "v_001")

    def test_detects_photo(self) -> None:
        msg = receive_telegram_message(input_type="photo", photo_file_id="p_001")
        result = json.loads(detect_input_type(msg))
        self.assertEqual(result["input_type"], "photo")
        self.assertEqual(result["file_id"], "p_001")


class TestRejectUnauthorizedUser(unittest.TestCase):
    def test_creates_rejection_file(self) -> None:
        result = json.loads(reject_unauthorized_user("9999999"))
        self.assertEqual(result["status"], "rejected")
        self.assertIn("not authorized", result["message"])
        self.assertTrue(os.path.exists(result["file"]))


class TestSendTelegramReply(unittest.TestCase):
    def test_saves_reply_file(self) -> None:
        result = json.loads(send_telegram_reply("8308632587", "📖 phenomenon\nDefinition: ..."))
        self.assertEqual(result["status"], "mock_sent")
        self.assertTrue(os.path.exists(result["file"]))

    def test_preview_truncated(self) -> None:
        long_msg = "x" * 200
        result = json.loads(send_telegram_reply("8308632587", long_msg))
        self.assertLessEqual(len(result["message_preview"]), 120)


class TestSetInputNormalisers(unittest.TestCase):
    def test_set_text_input(self) -> None:
        msg = receive_telegram_message(text="serendipity", input_type="text")
        result = json.loads(set_text_input(msg))
        self.assertEqual(result["chat_input"], "serendipity")
        self.assertEqual(result["type"], "text")

    def test_set_voice_text(self) -> None:
        transcription = json.dumps({"text": "ephemeral", "mock": True, "source_file": "x.oga"})
        result = json.loads(set_voice_text(transcription))
        self.assertEqual(result["chat_input"], "ephemeral")
        self.assertEqual(result["type"], "voice")

    def test_set_photo_text(self) -> None:
        analysis = json.dumps({"content": "quibble", "source_file": "img.png"})
        result = json.loads(set_photo_text(analysis))
        self.assertEqual(result["chat_input"], "quibble")
        self.assertEqual(result["type"], "photo")


class TestMediaTools(unittest.TestCase):
    def test_get_voice_file_structure(self) -> None:
        result = json.loads(get_voice_file("voice_abc123"))
        self.assertTrue(result["ok"])
        self.assertIn("file_path", result["result"])
        self.assertIn("voice_abc123", result["result"]["file_path"])

    def test_download_audio_creates_file(self) -> None:
        result = json.loads(download_audio("voice/test_voice.oga"))
        self.assertTrue(os.path.exists(result["local_path"]))
        self.assertTrue(result["mock"])
        self.assertGreater(result["size_bytes"], 0)

    def test_get_photo_file_structure(self) -> None:
        result = json.loads(get_photo_file("photo_xyz789"))
        self.assertTrue(result["ok"])
        self.assertIn("file_path", result["result"])

    def test_download_image_creates_png(self) -> None:
        result = json.loads(download_image("photos/test_photo.jpg"))
        self.assertTrue(os.path.exists(result["local_path"]))
        self.assertEqual(result["mime_type"], "image/png")
        self.assertTrue(result["mock"])
        # Valid PNG starts with the PNG signature
        with open(result["local_path"], "rb") as f:
            header = f.read(8)
        self.assertEqual(header, b"\x89PNG\r\n\x1a\n")


class TestAITools(unittest.TestCase):
    def test_transcribe_audio_mock(self) -> None:
        os.environ["MOCK_AUDIO_TRANSCRIPTION"] = "true"
        # Create a temp placeholder audio file
        with tempfile.NamedTemporaryFile(suffix=".oga", delete=False) as tmp:
            tmp.write(b"OggS" + b"\x00" * 24)
            tmp_path = tmp.name
        try:
            from mcp_server.tools.ai_tools import transcribe_audio
            result = json.loads(transcribe_audio(tmp_path))
            self.assertIn("text", result)
            self.assertIsInstance(result["text"], str)
            self.assertGreater(len(result["text"]), 0)
            self.assertTrue(result["mock"])
        finally:
            os.unlink(tmp_path)

    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_dictionary_agent_mock(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = json.dumps({
            "word": "phenomenon",
            "definition": "something remarkable or unusual",
            "translation": "現象",
            "part_of_speech": "noun",
            "example_sentence": "Gravity is a natural phenomenon.",
            "example_translation": "重力是一種自然現象。",
        })
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=mock_msg)]
        )
        from mcp_server.tools.ai_tools import dictionary_agent
        result = json.loads(dictionary_agent("phenomenon", "Traditional Chinese"))
        self.assertIn("output", result)
        out = result["output"]
        self.assertEqual(out["word"], "phenomenon")
        self.assertIn("definition", out)
        self.assertIn("translation", out)

    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_dictionary_agent_spellcheck(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = json.dumps({
            "word": "quibble",
            "definition": "to argue about trivial matters",
            "translation": "為瑣事爭論",
            "part_of_speech": "verb",
            "example_sentence": "They always quibble over small details.",
            "example_translation": "他們總是為小細節爭論。",
        })
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=mock_msg)]
        )
        from mcp_server.tools.ai_tools import dictionary_agent
        result = json.loads(dictionary_agent("guibble", "Traditional Chinese"))
        self.assertEqual(result["output"]["word"], "quibble")

    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_analyze_image_mock(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = "ephemeral"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=mock_msg)]
        )
        # Create a real grey PNG for the test
        img_result = json.loads(download_image("photos/mock_test.jpg"))
        from mcp_server.tools.ai_tools import analyze_image
        result = json.loads(analyze_image(img_result["local_path"]))
        self.assertIn("content", result)
        self.assertIsInstance(result["content"], str)


class TestNotionTools(unittest.TestCase):
    def test_save_creates_json_and_csv(self) -> None:
        result = json.loads(save_vocabulary_to_notion(
            word="serendipity",
            definition="the occurrence of fortunate events by chance",
            translation="意外發現美好事物的能力",
            part_of_speech="noun",
            example_sentence="Finding that rare book was pure serendipity.",
            example_translation="找到那本罕見的書純屬意外之喜。",
            notion_db_id="test_db",
        ))
        self.assertEqual(result["status"], "mock_saved")
        self.assertEqual(result["word"], "serendipity")
        self.assertTrue(os.path.exists(result["json_file"]))
        self.assertTrue(os.path.exists(result["csv_file"]))

    def test_save_appends_to_json(self) -> None:
        save_vocabulary_to_notion(
            word="ephemeral", definition="lasting a very short time", translation="短暫的",
            part_of_speech="adjective", example_sentence="Fame can be ephemeral.",
            example_translation="名聲可能是短暫的。", notion_db_id="test_db",
        )
        with open("results/outputs/vocabulary.json", encoding="utf-8") as f:
            vocab = json.load(f)
        words = [e["word"] for e in vocab]
        self.assertIn("ephemeral", words)

    def test_save_csv_has_header(self) -> None:
        import csv
        with open("results/outputs/vocabulary.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
        self.assertIn("word", headers)
        self.assertIn("definition", headers)
        self.assertIn("translation", headers)


if __name__ == "__main__":
    unittest.main()
