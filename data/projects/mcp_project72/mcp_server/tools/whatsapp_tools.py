"""WhatsApp mock tools for mcp_project72 — hotel receptionist bot."""

import json
import os
import uuid
from datetime import datetime

from .utils.log_decorator import log_mcp_call

_DEMO_MESSAGES = [
    "What rooms are currently available?",
    "What is the price for a Suite room?",
    "Show me all bookings checking in today",
    "Is room 203 available?",
]


@log_mcp_call("tool", "receive_whatsapp_message")
def receive_whatsapp_message(
    message: str = _DEMO_MESSAGES[0],
    wa_id: str = "601234567890",
    phone_number: str = "601234567890",
) -> str:
    """Simulate a WhatsApp webhook event with a guest text message."""
    return json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "6012345678", "phone_number_id": "723548604171403"},
                    "contacts": [{"profile": {"name": "Hotel Guest"}, "wa_id": wa_id}],
                    "messages": [{
                        "from": phone_number,
                        "id": f"wamid.{uuid.uuid4().hex}",
                        "timestamp": str(int(datetime.now().timestamp())),
                        "text": {"body": message},
                        "type": "text",
                    }],
                },
                "field": "messages",
            }],
        }],
    })


@log_mcp_call("tool", "check_message")
def check_message(webhook_json: str) -> str:
    """Validate the WhatsApp webhook and extract message text. Returns empty if no text message."""
    data = json.loads(webhook_json)
    try:
        value = data["entry"][0]["changes"][0]["value"]
        messages = value.get("messages", [])
        if not messages:
            return json.dumps({"valid": False, "reason": "no messages"})
        msg = messages[0]
        if msg.get("type") != "text" or not msg.get("text", {}).get("body"):
            return json.dumps({"valid": False, "reason": "not a text message"})
        contacts = value.get("contacts", [{}])
        wa_id = contacts[0].get("wa_id", "unknown")
        return json.dumps({
            "valid": True,
            "message": msg["text"]["body"],
            "from_phone": msg["from"],
            "wa_id": wa_id,
            "message_id": msg["id"],
        })
    except (KeyError, IndexError) as e:
        return json.dumps({"valid": False, "reason": str(e)})


@log_mcp_call("tool", "send_whatsapp_reply")
def send_whatsapp_reply(recipient_phone: str, message_text: str) -> str:
    """Mock WhatsApp reply: save message to results/outputs/."""
    os.makedirs("results/outputs", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_phone,
        "type": "text",
        "text": {"preview_url": False, "body": message_text},
        "sent_at": ts,
    }
    out_path = f"results/outputs/whatsapp_reply_{recipient_phone}_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return json.dumps({
        "status": "mock_sent",
        "to": recipient_phone,
        "message_preview": message_text[:120],
        "file": out_path,
    })
