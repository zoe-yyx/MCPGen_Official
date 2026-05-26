"""Email tools - mock Gmail send operations for leave notifications."""

import json
import os
from datetime import datetime

from .utils.log_decorator import get_logger, log_mcp_call

logger = get_logger()

EMAIL_LOG_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "results", "outputs", "emails.json"
)


def _append_email(email_record: dict) -> None:
    path = os.path.abspath(EMAIL_LOG_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing: list = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []
    existing.append(email_record)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


@log_mcp_call("tool")
def send_ooo_reminder_email(
    to_email: str,
    employee_name: str,
    start_date: str,
    end_date: str,
) -> str:
    """Send an Out-of-Office setup reminder email to an employee (mock Gmail).

    Args:
        to_email: Recipient email address.
        employee_name: Name of the employee.
        start_date: Leave start date (YYYY-MM-DD).
        end_date: Leave end date (YYYY-MM-DD).

    Returns:
        Confirmation string indicating email was sent.
    """
    subject = "Leave Reminder – Please Enable Out of Office"
    body = (
        f"Hi {employee_name},\n\n"
        f"Our records show your leave from {start_date} to {end_date}.\n\n"
        f"Please make sure to:\n"
        f"• Update your Slack status to \"Out of Office\"\n"
        f"• Inform your team if needed\n\n"
        f"Regards,\nHR Automation System"
    )
    email_record = {
        "type": "ooo_reminder",
        "to": to_email,
        "subject": subject,
        "body": body,
        "sent_at": datetime.utcnow().isoformat(),
    }
    _append_email(email_record)
    logger.info(f"[EMAIL MOCK] OOO reminder sent to {to_email}")
    return f"OOO reminder email sent to {to_email} (subject: {subject})"


@log_mcp_call("tool")
def send_welcome_back_email(
    to_email: str,
    employee_name: str,
    end_date: str,
) -> str:
    """Send a Welcome Back email to an employee returning from leave (mock Gmail).

    Args:
        to_email: Recipient email address.
        employee_name: Name of the employee.
        end_date: Leave end date (YYYY-MM-DD).

    Returns:
        Confirmation string indicating email was sent.
    """
    subject = "Welcome Back – Leave Completed"
    body = (
        f"Hi {employee_name},\n\n"
        f"Our records show your leave ended on {end_date}.\n\n"
        f"Welcome Back !!\n\n"
        f"Have a productive day!\n\n"
        f"HR Leave Automation System"
    )
    email_record = {
        "type": "welcome_back",
        "to": to_email,
        "subject": subject,
        "body": body,
        "sent_at": datetime.utcnow().isoformat(),
    }
    _append_email(email_record)
    logger.info(f"[EMAIL MOCK] Welcome back email sent to {to_email}")
    return f"Welcome back email sent to {to_email} (subject: {subject})"
