"""Email tools: send interview invitation email via Gmail (mocked)."""

import json
import os
from datetime import datetime, timezone

from .utils.log_decorator import log_mcp_call

MOCK_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "results", "outputs")


def _ensure_output_dir() -> str:
    os.makedirs(MOCK_DIR, exist_ok=True)
    return MOCK_DIR


@log_mcp_call("tool", "send_gmail")
def send_gmail(recipient_email: str, subject: str, body: str) -> str:
    """Send an email via Gmail (mocked: saved to local file).

    Args:
        recipient_email: Email address of the recipient.
        subject: Email subject line.
        body: Email body content.

    Returns:
        JSON string confirming the email was saved.
    """
    out_dir = _ensure_output_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = recipient_email.replace("@", "_at_").replace(".", "_")
    filepath = os.path.join(out_dir, f"email_{safe_name}_{ts}.txt")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"To: {recipient_email}\n")
        f.write(f"Subject: {subject}\n")
        f.write(f"Date: {datetime.now(timezone.utc).isoformat()}\n")
        f.write("-" * 40 + "\n\n")
        f.write(body)

    return json.dumps({
        "status": "sent_mock",
        "channel": "gmail",
        "recipient": recipient_email,
        "subject": subject,
        "file": filepath,
    })
