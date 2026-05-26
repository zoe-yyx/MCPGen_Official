"""Scheduling tools: calculate next interview slot and create calendar event.

Converted from the n8n Code node (JavaScript → Python) and Google Calendar node (mocked).
"""

import json
import uuid
from datetime import datetime, timedelta

from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "calculate_next_slot")
def calculate_next_slot() -> str:
    """Calculate the next available interview time slot.

    Free slots: Monday, Wednesday, Friday at 3:00 PM.
    Always picks the nearest future slot (never today).

    Returns:
        JSON string with 'nextSlot' and 'endSlot' (1 hour duration),
        formatted as 'YYYY-MM-DD HH:MM:SS'.
    """
    now = datetime.now()

    # Available slots: day_of_week (0=Mon in Python) and hour
    slots = [
        {"day": 0, "hour": 15},  # Monday 3 PM
        {"day": 2, "hour": 15},  # Wednesday 3 PM
        {"day": 4, "hour": 15},  # Friday 3 PM
    ]

    min_diff: timedelta | None = None
    next_slot_date: datetime | None = None

    for slot in slots:
        days_until = (slot["day"] - now.weekday()) % 7
        # Always skip today
        if days_until == 0:
            days_until = 7

        slot_date = datetime(
            now.year, now.month, now.day,
            slot["hour"], 0, 0,
        ) + timedelta(days=days_until)

        diff = slot_date - now
        if min_diff is None or diff < min_diff:
            min_diff = diff
            next_slot_date = slot_date

    assert next_slot_date is not None
    end_slot_date = next_slot_date + timedelta(hours=1)

    result = {
        "nextSlot": next_slot_date.strftime("%Y-%m-%d %H:%M:%S"),
        "endSlot": end_slot_date.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return json.dumps(result)


@log_mcp_call("tool", "create_calendar_event")
def create_calendar_event(start_time: str, end_time: str, calendar_id: str = "EMAIL_PLACEHOLDER") -> str:
    """Create a Google Calendar event for the interview (mocked).

    Args:
        start_time: Event start time (YYYY-MM-DD HH:MM:SS).
        end_time: Event end time (YYYY-MM-DD HH:MM:SS).
        calendar_id: Google Calendar ID (ignored in mock).

    Returns:
        JSON string with event details including a mock htmlLink.
    """
    event_id = uuid.uuid4().hex[:16]
    html_link = f"ENDPOINT_PLACEHOLDER"

    result = {
        "kind": "calendar#event",
        "id": event_id,
        "status": "confirmed",
        "htmlLink": html_link,
        "summary": "Interview",
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
        "calendarId": calendar_id,
    }
    return json.dumps(result)
