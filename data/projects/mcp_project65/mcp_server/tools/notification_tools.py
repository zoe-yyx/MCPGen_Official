"""Notification tools: send alerts to Telegram, Slack, and Gmail (all mocked)."""

import json
import os
from datetime import datetime, timezone

from .utils.log_decorator import log_mcp_call

MOCK_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "results", "outputs")


def _ensure_output_dir() -> str:
    os.makedirs(MOCK_DIR, exist_ok=True)
    return MOCK_DIR


@log_mcp_call("tool", "send_telegram")
def send_telegram(alert_data: str) -> str:
    """Send a high-priority trade alert to Telegram (mocked: saved to local file).

    Args:
        alert_data: JSON string with 'priority', 'output', 'action' fields.

    Returns:
        JSON string confirming the message was saved.
    """
    data = json.loads(alert_data)
    priority = data.get("priority", "HIGH")
    output = data.get("output", "")
    action = data.get("action", "")

    message = (
        f"🚨 *Trade Alert – {priority} Priority*\n\n"
        f"{output}\n\n"
        f"_Action:_ {action}"
    )

    out_dir = _ensure_output_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(out_dir, f"telegram_alert_{ts}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(message)

    return json.dumps({"status": "sent_mock", "channel": "telegram", "file": filepath})


@log_mcp_call("tool", "send_slack")
def send_slack(alert_data: str) -> str:
    """Send a low/medium priority trade alert to Slack (mocked: saved to local file).

    Args:
        alert_data: JSON string with 'output' field.

    Returns:
        JSON string confirming the message was saved.
    """
    data = json.loads(alert_data)
    message = data.get("output", "")

    out_dir = _ensure_output_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(out_dir, f"slack_alert_{ts}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(message)

    return json.dumps({"status": "sent_mock", "channel": "slack", "file": filepath})


@log_mcp_call("tool", "send_error_email")
def send_error_email(error_node: str, error_message: str) -> str:
    """Send an error alert email via Gmail (mocked: saved to local file).

    Args:
        error_node: Name of the node that failed.
        error_message: Error description.

    Returns:
        JSON string confirming the email was saved.
    """
    ts_iso = datetime.now(timezone.utc).isoformat()
    body = (
        f"🚨 *Workflow Error Alert*\n"
        f"*Error Node:* {error_node}\n"
        f"*Error Message:* {error_message}\n"
        f"*Timestamp:* {ts_iso}\n\n"
        f"Please investigate immediately."
    )

    out_dir = _ensure_output_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(out_dir, f"error_email_{ts}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"To: {os.getenv('GMAIL_RECIPIENT', 'EMAIL_PLACEHOLDER')}\n")
        f.write(f"Subject: Workflow Error Alert\n\n")
        f.write(body)

    return json.dumps({"status": "sent_mock", "channel": "email", "file": filepath})
