"""Slack mock tools for mcp_project70 — sendAndWait approval simulation."""

import json
import os
from datetime import datetime

from dotenv import load_dotenv

from .utils.log_decorator import log_mcp_call

load_dotenv()


@log_mcp_call("tool", "slack_review_approve")
def slack_review_approve(slack_message: str, idea_title: str = "") -> str:
    """Mock Slack sendAndWait: save message and auto-approve based on env setting."""
    auto_approve = os.getenv("SLACK_AUTO_APPROVE", "true").lower() == "true"
    channel = os.getenv("SLACK_CHANNEL_ID", "C0123456789")
    timestamp = datetime.utcnow().isoformat() + "Z"

    payload = {
        "channel": channel,
        "message": slack_message,
        "idea_title": idea_title,
        "sent_at": timestamp,
        "buttons": ["Approve", "Regenerate"],
        "type": "slack_review",
        "status": "mock_sent",
    }

    os.makedirs("results/outputs", exist_ok=True)
    safe_title = idea_title[:40].replace(" ", "_").replace("/", "-") if idea_title else "unknown"
    out_path = f"results/outputs/slack_message_{safe_title}_{timestamp[:10]}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    result = {
        "data": {
            "approved": auto_approve,
            "response": "Approve" if auto_approve else "Regenerate",
            "channel": channel,
            "file": out_path,
            "status": "mock_sent",
        }
    }
    return json.dumps(result)


@log_mcp_call("tool", "check_approval")
def check_approval(slack_response_json: str) -> str:
    """Check whether the Slack review was approved."""
    data = json.loads(slack_response_json)
    inner = data.get("data", data)
    approved = bool(inner.get("approved", False))
    return json.dumps({
        "approved": approved,
        "route": "approved" if approved else "regenerate",
    })
