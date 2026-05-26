"""Notification tools: send email, Slack notification, and webhook response (all mocked)."""

import json
import os
from datetime import datetime, timezone

from .utils.log_decorator import log_mcp_call

MOCK_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "results", "outputs")


def _ensure_output_dir() -> str:
    os.makedirs(MOCK_DIR, exist_ok=True)
    return MOCK_DIR


@log_mcp_call("tool", "send_candidate_email")
def send_candidate_email(to_email: str, from_email: str, subject: str, body: str) -> str:
    """Send recruitment email to candidate (mocked: saved to local file).

    Args:
        to_email: Recipient email address.
        from_email: Sender email address.
        subject: Email subject line.
        body: Email body text.

    Returns:
        JSON string confirming the email was saved.
    """
    out_dir = _ensure_output_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = to_email.replace("@", "_at_").replace(".", "_")
    filepath = os.path.join(out_dir, f"email_{safe_name}_{ts}.txt")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"From: {from_email}\n")
        f.write(f"To: {to_email}\n")
        f.write(f"Subject: {subject}\n")
        f.write(f"Date: {datetime.now(timezone.utc).isoformat()}\n")
        f.write("-" * 40 + "\n\n")
        f.write(body)

    return json.dumps({"status": "sent_mock", "channel": "email", "to": to_email, "file": filepath})


@log_mcp_call("tool", "send_slack_notification")
def send_slack_notification(
    candidate_name: str,
    position: str,
    match_score: int,
    status: str,
    recommendation: str,
    strengths: str,
    candidate_id: str = "",
) -> str:
    """Send Slack notification about candidate processing (mocked: saved to local file).

    Args:
        candidate_name: Candidate full name.
        position: Position applied for.
        match_score: AI match score.
        status: Qualification status.
        recommendation: AI recommendation.
        strengths: Key strengths text.
        candidate_id: Airtable record ID.

    Returns:
        JSON string confirming the notification was saved.
    """
    next_step = (
        "Interview Scheduled"
        if recommendation == "Interview"
        else "Next Step: Phone screening"
    )

    message = (
        f"🎯 *New Candidate Processed*\n\n"
        f"*Candidate:* {candidate_name}\n"
        f"*Position:* {position}\n"
        f"*Match Score:* {match_score}%\n"
        f"*Status:* {status}\n"
        f"*Recommendation:* {recommendation}\n\n"
        f"*Key Strengths:*\n{strengths}\n\n"
        f"📋 *{next_step}*"
    )

    out_dir = _ensure_output_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(out_dir, f"slack_notification_{ts}.txt")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(message)

    return json.dumps({"status": "sent_mock", "channel": "slack", "file": filepath})


@log_mcp_call("tool", "respond_webhook")
def respond_webhook(
    candidate_id: str,
    candidate_name: str,
    match_score: int,
    status: str,
    recommendation: str,
) -> str:
    """Generate the final webhook response (mocked).

    Args:
        candidate_id: Airtable record ID.
        candidate_name: Candidate name.
        match_score: AI match score.
        status: Qualification status.
        recommendation: AI recommendation.

    Returns:
        JSON string with the webhook response body.
    """
    return json.dumps({
        "success": True,
        "candidate_id": candidate_id,
        "name": candidate_name,
        "match_score": match_score,
        "status": status,
        "recommendation": recommendation,
        "message": "Application processed successfully",
    })
