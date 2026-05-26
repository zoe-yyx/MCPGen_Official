"""LINE messaging mock tools for mcp_project71."""

import json
import os
import uuid
from datetime import datetime

from .utils.log_decorator import log_mcp_call

# Sample user messages for demo
_SAMPLE_MESSAGES = [
    "商品名: プレミアムコーヒー / ターゲット: 30代ビジネスマン / キャッチコピー: 朝の一杯が、仕事を変える。",
    "商品名: スマートウォッチ / ターゲット: フィットネス愛好家 / キャッチコピー: あなたの健康を、腕に巻く。",
]


@log_mcp_call("tool", "receive_line_webhook")
def receive_line_webhook(
    message: str = _SAMPLE_MESSAGES[0],
    user_id: str = "U1234567890abcdef",
    reply_token: str = "",
) -> str:
    """Simulate receiving a LINE webhook event with a text message."""
    if not reply_token:
        reply_token = f"mock-reply-token-{uuid.uuid4().hex[:12]}"

    webhook_body = {
        "destination": "U0a2c3d4e5f6",
        "events": [
            {
                "type": "message",
                "mode": "active",
                "timestamp": int(datetime.now().timestamp() * 1000),
                "source": {"type": "user", "userId": user_id},
                "replyToken": reply_token,
                "message": {
                    "id": f"msg-{uuid.uuid4().hex[:8]}",
                    "type": "text",
                    "text": message,
                },
            }
        ],
    }
    return json.dumps({"body": webhook_body})


@log_mcp_call("tool", "extract_line_data")
def extract_line_data(webhook_json: str) -> str:
    """Parse LINE webhook to extract replyToken, userId, and message text."""
    data = json.loads(webhook_json)
    body = data.get("body", data)
    events = body.get("events", [])
    if not events:
        raise ValueError("No LINE events found in webhook")
    event = events[0]
    return json.dumps({
        "reply_token": event["replyToken"],
        "user_id": event["source"]["userId"],
        "message": event["message"]["text"],
        "timestamp": event["timestamp"],
    })


@log_mcp_call("tool", "send_line_reply")
def send_line_reply(reply_token: str, image_url: str) -> str:
    """Mock LINE reply: save the reply payload to results/outputs/."""
    payload = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "image",
                "originalContentUrl": image_url,
                "previewImageUrl": image_url,
            }
        ],
    }
    os.makedirs("results/outputs", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"results/outputs/line_reply_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return json.dumps({
        "status": "mock_sent",
        "type": "line_image_reply",
        "image_url": image_url,
        "reply_token": reply_token,
        "file": out_path,
    })
