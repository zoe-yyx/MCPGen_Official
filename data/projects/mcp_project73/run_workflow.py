"""Vocabulary Lookup Workflow via Telegram.

Simulates Telegram bot interactions for English vocabulary lookup.
Steps match workflow.json step_id order:
  1  receive_telegram_message  — simulate incoming Telegram message
  2  load_config               — load TELEGRAM_CHAT_ID, TARGET_LANGUAGE, etc.
  3  check_authorization       — verify sender is authorized
  4  reject_unauthorized_user  — (branch) reject if not authorized
  5  detect_input_type         — route: text / voice / photo
  6  set_text_input            — (text branch) normalise to chat_input
  7  get_voice_file            — (voice branch) resolve file_id
  8  download_audio            — download voice file
  9  transcribe_audio          — Whisper transcription
  10 set_voice_text            — normalise transcription to chat_input
  11 get_photo_file            — (photo branch) resolve file_id
  12 download_image            — download photo file
  13 analyze_image             — GPT vision OCR
  14 set_photo_text            — normalise OCR result to chat_input
  15 dictionary_agent          — GPT spell-check + structured vocabulary lookup
  16 send_telegram_reply       — mock Telegram reply
  17 save_vocabulary_to_notion — mock Notion save (local JSON + CSV)
"""

import asyncio
import json
import os
import sys

from fastmcp import Client

sys.path.insert(0, os.path.dirname(__file__))
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/workflow.log")

DEMO_SESSIONS = [
    {"input_type": "text", "content": "phenomenon", "chat_id": None},
    {"input_type": "text", "content": "guibble", "chat_id": None},       # misspelling → quibble
    {"input_type": "voice", "audio_file_id": "voice_abc123", "chat_id": None},
    {"input_type": "photo", "photo_file_id": "photo_xyz789", "chat_id": None},
    {"input_type": "text", "content": "serendipity", "chat_id": "9999999"},  # unauthorized
]


def extract_text(result) -> str:
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return block.text
    return str(result)


def _format_reply(output: dict) -> str:
    return (
        f"📖 {output.get('word', 'N/A')}\n\n"
        f"Part of speech: {output.get('part_of_speech', 'N/A')}\n"
        f"Definition: {output.get('definition', 'N/A')}\n"
        f"Translation: {output.get('translation', 'N/A')}\n\n"
        f"Example: {output.get('example_sentence', 'N/A')}\n"
        f"{output.get('example_translation', 'N/A')}"
    )


async def handle_message(client: Client, session: dict) -> None:
    """Run the full 17-step vocabulary workflow for one Telegram message."""
    input_type = session["input_type"]
    logger.info("-" * 55)
    logger.info("Input [%s]: %s", input_type, session.get("content") or session.get("audio_file_id") or session.get("photo_file_id"))

    # Step 1: Receive Telegram Message
    step1_kwargs: dict = {"input_type": input_type}
    if input_type == "text":
        step1_kwargs["text"] = session["content"]
    elif input_type == "voice":
        step1_kwargs["audio_file_id"] = session["audio_file_id"]
    elif input_type == "photo":
        step1_kwargs["photo_file_id"] = session["photo_file_id"]
    if session.get("chat_id"):
        step1_kwargs["chat_id"] = session["chat_id"]

    step1 = extract_text(await client.call_tool("receive_telegram_message", step1_kwargs))

    # Step 2: Load Config
    step2 = extract_text(await client.call_tool("load_config", {}))
    step2_data = json.loads(step2)
    logger.info("Step 2: Config loaded (TARGET_LANGUAGE=%s)", step2_data["TARGET_LANGUAGE"])

    # Step 3: Authorize User
    step3 = extract_text(await client.call_tool("check_authorization", {
        "telegram_message_json": step1,
        "config_json": step2,
    }))
    step3_data = json.loads(step3)
    logger.info("Step 3: authorized=%s chat_id=%s", step3_data["authorized"], step3_data["chat_id"])

    if not step3_data["authorized"]:
        # Step 4: Reject Unauthorized User
        step4 = extract_text(await client.call_tool("reject_unauthorized_user", {
            "chat_id": step3_data["chat_id"],
        }))
        step4_data = json.loads(step4)
        logger.info("Step 4: Rejected → %s", step4_data["message"])
        return

    # Step 5: Detect Input Type
    step5 = extract_text(await client.call_tool("detect_input_type", {
        "telegram_message_json": step1,
    }))
    step5_data = json.loads(step5)
    logger.info("Step 5: input_type=%s", step5_data["input_type"])

    # Steps 6 / 7-10 / 11-14 — branch by input type
    if step5_data["input_type"] == "text":
        # Step 6: Set Text Input
        step6 = extract_text(await client.call_tool("set_text_input", {
            "telegram_message_json": step1,
        }))
        chat_input_data = json.loads(step6)

    elif step5_data["input_type"] == "voice":
        # Step 7: Get Voice File
        step7 = extract_text(await client.call_tool("get_voice_file", {
            "file_id": step5_data["file_id"],
        }))
        step7_data = json.loads(step7)

        # Step 8: Download Audio
        step8 = extract_text(await client.call_tool("download_audio", {
            "file_path": step7_data["result"]["file_path"],
        }))
        step8_data = json.loads(step8)
        logger.info("Step 8: audio saved → %s", step8_data["local_path"])

        # Step 9: Transcribe Audio
        step9 = extract_text(await client.call_tool("transcribe_audio", {
            "local_audio_path": step8_data["local_path"],
        }))
        step9_data = json.loads(step9)
        logger.info("Step 9: transcribed → '%s'", step9_data["text"])

        # Step 10: Set Voice Text
        step10 = extract_text(await client.call_tool("set_voice_text", {
            "transcription_json": step9,
        }))
        chat_input_data = json.loads(step10)

    elif step5_data["input_type"] == "photo":
        # Step 11: Get Photo File
        step11 = extract_text(await client.call_tool("get_photo_file", {
            "file_id": step5_data["file_id"],
        }))
        step11_data = json.loads(step11)

        # Step 12: Download Image
        step12 = extract_text(await client.call_tool("download_image", {
            "file_path": step11_data["result"]["file_path"],
        }))
        step12_data = json.loads(step12)
        logger.info("Step 12: image saved → %s", step12_data["local_path"])

        # Step 13: Analyze Image
        logger.info("Step 13: running GPT vision OCR...")
        step13 = extract_text(await client.call_tool("analyze_image", {
            "local_image_path": step12_data["local_path"],
        }))
        step13_data = json.loads(step13)
        logger.info("Step 13: extracted text → '%s'", step13_data["content"])

        # Step 14: Set Photo Text
        step14 = extract_text(await client.call_tool("set_photo_text", {
            "analysis_json": step13,
        }))
        chat_input_data = json.loads(step14)

    else:
        logger.warning("Unknown input type: %s — skipping", step5_data["input_type"])
        return

    logger.info("chat_input='%s' (type=%s)", chat_input_data["chat_input"], chat_input_data["type"])

    # Step 15: Dictionary Agent
    logger.info("Step 15: running dictionary agent...")
    step15 = extract_text(await client.call_tool("dictionary_agent", {
        "chat_input": chat_input_data["chat_input"],
        "target_language": step2_data["TARGET_LANGUAGE"],
    }))
    step15_data = json.loads(step15)
    vocab = step15_data["output"]
    logger.info("Step 15: word='%s' pos=%s", vocab.get("word"), vocab.get("part_of_speech"))

    # Step 16: Send Telegram Reply
    reply_text = _format_reply(vocab)
    step16 = extract_text(await client.call_tool("send_telegram_reply", {
        "chat_id": step3_data["chat_id"],
        "message_text": reply_text,
    }))
    step16_data = json.loads(step16)
    logger.info("Step 16: reply sent → '%s'", step16_data["message_preview"])

    # Step 17: Save to Notion
    step17 = extract_text(await client.call_tool("save_vocabulary_to_notion", {
        "word": vocab.get("word", ""),
        "definition": vocab.get("definition", ""),
        "translation": vocab.get("translation", ""),
        "part_of_speech": vocab.get("part_of_speech", ""),
        "example_sentence": vocab.get("example_sentence", ""),
        "example_translation": vocab.get("example_translation", ""),
        "notion_db_id": step2_data["NOTION_VOCABULARY_DB_ID"],
    }))
    step17_data = json.loads(step17)
    logger.info("Step 17: saved '%s' → %s", step17_data["word"], step17_data["json_file"])

    logger.info("Bot reply:\n%s", reply_text)


async def main() -> None:
    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info("Server started with %d tools registered", len(tools))
        logger.info("=" * 55)
        logger.info("VocabularyBot — English Vocabulary Lookup")
        logger.info("=" * 55)

        for session in DEMO_SESSIONS:
            await handle_message(client, session)

        logger.info("=" * 55)
        logger.info("All demo sessions completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Workflow failed: %s", e, exc_info=True)
        raise
