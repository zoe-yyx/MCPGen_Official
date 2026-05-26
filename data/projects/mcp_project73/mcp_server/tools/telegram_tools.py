"""Telegram tools — mock Telegram Bot API for vocabulary lookup workflow."""

import json
import os
import time

from mcp_server.tools.utils.log_decorator import log_mcp_call


@log_mcp_call(operation_type="tool")
def receive_telegram_message(
    text: str | None = None,
    input_type: str = "text",
    audio_file_id: str | None = None,
    photo_file_id: str | None = None,
    chat_id: str | None = None,
) -> str:
    """Simulate an incoming Telegram webhook message (text, voice, or photo)."""
    sender_chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "8308632587")
    message: dict = {
        "message_id": int(time.time() * 1000) % 1_000_000,
        "from": {"id": int(sender_chat_id), "is_bot": False, "first_name": "User"},
        "chat": {"id": int(sender_chat_id), "type": "private"},
        "date": int(time.time()),
    }
    if input_type == "text" and text:
        message["text"] = text
    elif input_type == "voice" and audio_file_id:
        message["voice"] = {
            "file_id": audio_file_id,
            "duration": 3,
            "mime_type": "audio/ogg",
            "file_size": 12345,
        }
    elif input_type == "photo" and photo_file_id:
        message["photo"] = [
            {
                "file_id": photo_file_id,
                "file_unique_id": f"uniq_{photo_file_id}",
                "width": 200,
                "height": 200,
                "file_size": 5000,
            }
        ]
    return json.dumps({
        "update_id": int(time.time()) % 100_000,
        "message": message,
    })


@log_mcp_call(operation_type="tool")
def load_config() -> str:
    """Load workflow configuration values (TELEGRAM_CHAT_ID, TARGET_LANGUAGE, etc.)."""
    return json.dumps({
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", "8308632587"),
        "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN", "mock_bot_token"),
        "NOTION_VOCABULARY_DB_ID": os.environ.get("NOTION_VOCABULARY_DB_ID", "17677348359f80529dabe1fd2acdb75b"),
        "TARGET_LANGUAGE": os.environ.get("TARGET_LANGUAGE", "Traditional Chinese"),
    })


@log_mcp_call(operation_type="tool")
def check_authorization(telegram_message_json: str, config_json: str) -> str:
    """Check whether the sender's chat ID matches the authorized chat ID."""
    msg_data = json.loads(telegram_message_json)
    config = json.loads(config_json)
    chat_id = str(msg_data["message"]["chat"]["id"])
    authorized = chat_id == str(config["TELEGRAM_CHAT_ID"])
    return json.dumps({
        "authorized": authorized,
        "chat_id": chat_id,
        "reason": "chat_id_match" if authorized else "chat_id_mismatch",
    })


@log_mcp_call(operation_type="tool")
def detect_input_type(telegram_message_json: str) -> str:
    """Detect whether the Telegram message contains text, voice, or photo."""
    msg_data = json.loads(telegram_message_json)
    msg = msg_data["message"]
    if msg.get("text"):
        return json.dumps({
            "input_type": "text",
            "content": msg["text"],
            "file_id": None,
            "chat_id": str(msg["chat"]["id"]),
        })
    if msg.get("voice"):
        return json.dumps({
            "input_type": "voice",
            "content": None,
            "file_id": msg["voice"]["file_id"],
            "chat_id": str(msg["chat"]["id"]),
        })
    if msg.get("photo"):
        return json.dumps({
            "input_type": "photo",
            "content": None,
            "file_id": msg["photo"][-1]["file_id"],
            "chat_id": str(msg["chat"]["id"]),
        })
    return json.dumps({
        "input_type": "unknown",
        "content": None,
        "file_id": None,
        "chat_id": str(msg["chat"]["id"]),
    })


@log_mcp_call(operation_type="tool")
def reject_unauthorized_user(chat_id: str) -> str:
    """Send rejection notice to unauthorized Telegram user (mock — saved locally)."""
    os.makedirs("results/outputs", exist_ok=True)
    rejection = {
        "status": "rejected",
        "chat_id": chat_id,
        "message": "Sorry, you are not authorized to use this bot.",
        "timestamp": int(time.time()),
    }
    path = f"results/outputs/rejection_{chat_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rejection, f, indent=2)
    rejection["file"] = path
    return json.dumps(rejection)


@log_mcp_call(operation_type="tool")
def set_text_input(telegram_message_json: str) -> str:
    """Extract text from a Telegram text message and normalise to chat_input format."""
    msg_data = json.loads(telegram_message_json)
    text = msg_data["message"]["text"]
    return json.dumps({"chat_input": text, "type": "text"})


@log_mcp_call(operation_type="tool")
def set_voice_text(transcription_json: str) -> str:
    """Wrap Whisper transcription result into chat_input format."""
    data = json.loads(transcription_json)
    return json.dumps({"chat_input": data["text"], "type": "voice"})


@log_mcp_call(operation_type="tool")
def set_photo_text(analysis_json: str) -> str:
    """Wrap GPT image-analysis result into chat_input format."""
    data = json.loads(analysis_json)
    return json.dumps({"chat_input": data["content"], "type": "photo"})


@log_mcp_call(operation_type="tool")
def send_telegram_reply(chat_id: str, message_text: str) -> str:
    """Send vocabulary reply to a Telegram user (mock — saved to results/outputs/)."""
    os.makedirs("results/outputs", exist_ok=True)
    reply = {
        "status": "mock_sent",
        "chat_id": chat_id,
        "message": message_text,
        "message_preview": message_text[:120],
        "timestamp": int(time.time()),
    }
    path = f"results/outputs/telegram_reply_{chat_id}_{int(time.time())}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reply, f, indent=2, ensure_ascii=False)
    reply["file"] = path
    return json.dumps(reply, ensure_ascii=False)
