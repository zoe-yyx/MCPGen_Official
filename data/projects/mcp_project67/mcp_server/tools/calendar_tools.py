"""Calendar tools: schedule interview on Google Calendar (mocked)."""

import json
import uuid
from datetime import datetime, timedelta, timezone

from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "schedule_interview")
def schedule_interview(candidate_name: str, position: str, days_from_now: int = 3) -> str:
    """Schedule a Google Calendar interview event (mocked).

    Creates an event scheduled 'days_from_now' days in the future, 1 hour duration.

    Args:
        candidate_name: Name of the candidate for the event title.
        position: Position being interviewed for.
        days_from_now: Days from now to schedule (default 3).

    Returns:
        JSON string with calendar event details including hangoutLink and event ID.
    """
    now = datetime.now(timezone.utc)
    start = now + timedelta(days=days_from_now)
    # Set to 10 AM
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1)

    event_id = uuid.uuid4().hex[:16]
    hangout_link = f"ENDPOINT_PLACEHOLDER).hex[:12]}"

    result = {
        "kind": "calendar#event",
        "id": event_id,
        "status": "confirmed",
        "htmlLink": f"ENDPOINT_PLACEHOLDER",
        "hangoutLink": hangout_link,
        "summary": f"Interview: {candidate_name} - {position}",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }
    return json.dumps(result)
