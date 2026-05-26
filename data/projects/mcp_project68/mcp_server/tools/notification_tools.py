"""Notification tools - mock Slack channel notifications."""

import json
import os
from datetime import datetime

from .utils.log_decorator import get_logger, log_mcp_call

logger = get_logger()

SLACK_LOG_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "results", "outputs", "slack_notifications.json"
)


def _append_slack_message(message: dict) -> None:
    path = os.path.abspath(SLACK_LOG_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing: list = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []
    existing.append(message)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


@log_mcp_call("tool")
def notify_hr_channel(
    employee_name: str,
    employee_email: str,
    start_date: str,
    end_date: str,
) -> str:
    """Send a leave-activated notification to the HR Slack channel (mock).

    Args:
        employee_name: Full name of the employee going on leave.
        employee_email: Email address of the employee.
        start_date: Leave start date (YYYY-MM-DD).
        end_date: Leave end date (YYYY-MM-DD).

    Returns:
        Confirmation string indicating the message was sent.
    """
    text = (
        f"📅 Leave Activated\n\n"
        f"Employee: {employee_name}\n"
        f"Email: {employee_email}\n"
        f"Leave Period: {start_date} → {end_date}\n\n"
        f"Reminder email sent to employee."
    )
    message = {
        "type": "leave_activated",
        "channel": "alerting-channel",
        "timestamp": datetime.utcnow().isoformat(),
        "text": text,
        "employee_email": employee_email,
    }
    _append_slack_message(message)
    logger.info(f"[SLACK MOCK] HR channel notified - leave activated for {employee_name}")
    return f"Slack notification sent for leave activation: {employee_name} ({start_date} → {end_date})"


@log_mcp_call("tool")
def notify_hr_leave_reset(
    employee_name: str,
    employee_email: str,
    start_date: str,
    end_date: str,
) -> str:
    """Send a leave-completed/return notification to the HR Slack channel (mock).

    Args:
        employee_name: Full name of the returning employee.
        employee_email: Email address of the employee.
        start_date: Leave start date (YYYY-MM-DD).
        end_date: Leave end date (YYYY-MM-DD).

    Returns:
        Confirmation string indicating the message was sent.
    """
    text = (
        f"🔄 Leave Completed\n\n"
        f"Employee: {employee_name}\n"
        f"Email: {employee_email}\n"
        f"Leave Period: {start_date} → {end_date}\n\n"
        f"Employee has returned from leave.\n"
        f"Status reset automatically."
    )
    message = {
        "type": "leave_completed",
        "channel": "alerting-channel",
        "timestamp": datetime.utcnow().isoformat(),
        "text": text,
        "employee_email": employee_email,
    }
    _append_slack_message(message)
    logger.info(f"[SLACK MOCK] HR channel notified - leave reset for {employee_name}")
    return f"Slack notification sent for leave reset: {employee_name} ({start_date} → {end_date})"
