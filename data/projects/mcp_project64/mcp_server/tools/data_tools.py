"""Tools for data transformation (splitting, timestamp conversion, etc.)."""

import json
from datetime import datetime, timezone
from typing import Any
from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "split_events")
def split_events(series_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Split the events array from series data into individual event records.

    Args:
        series_data: The series response containing an 'events' list.

    Returns:
        List of individual event dicts with id and closed status.
    """
    events = series_data.get("events", [])
    return [{"id": e["id"], "closed": e.get("closed", False)} for e in events]


@log_mcp_call("tool", "extract_tokens_and_endtime")
def extract_tokens_and_endtime(event_data: dict[str, Any]) -> dict[str, Any]:
    """Extract UP/DOWN token IDs, market ID, and end time from event data.

    Args:
        event_data: The event response containing markets list.

    Returns:
        dict with MarketId, EndTime, TokenUp, TokenDw.
    """
    market = event_data.get("markets", [{}])[0]
    clob_ids_raw = market.get("clobTokenIds", "[]")
    if isinstance(clob_ids_raw, str):
        clob_ids = json.loads(clob_ids_raw)
    else:
        clob_ids = clob_ids_raw
    return {
        "MarketId": market.get("id", ""),
        "EndTime": market.get("endDate", ""),
        "TokenUp": clob_ids[0] if len(clob_ids) > 0 else "",
        "TokenDw": clob_ids[1] if len(clob_ids) > 1 else "",
    }


@log_mcp_call("tool", "convert_endtime_to_unix")
def convert_endtime_to_unix(end_time_str: str) -> int:
    """Convert an ISO date string to a Unix timestamp.

    Args:
        end_time_str: ISO-format datetime string (e.g. '2025-01-12T13:00:00Z').

    Returns:
        Unix timestamp as integer.
    """
    dt = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
    return int(dt.timestamp())


@log_mcp_call("tool", "set_start_time")
def set_start_time(end_time_unix: int, duration_seconds: int = 3600) -> dict[str, int]:
    """Calculate start time by subtracting duration from end time.

    Args:
        end_time_unix: End time as Unix timestamp.
        duration_seconds: Duration in seconds (default 3600 = 1 hour).

    Returns:
        dict with EndTimeUnix and StartTimeUnix.
    """
    return {
        "EndTimeUnix": end_time_unix,
        "StartTimeUnix": end_time_unix - duration_seconds,
    }


@log_mcp_call("tool", "split_prices_and_timestamps")
def split_prices_and_timestamps(history_data: dict[str, Any]) -> dict[str, list]:
    """Split price history into separate timestamp and price arrays.

    Args:
        history_data: dict with 'history' list of {t, p} entries.

    Returns:
        dict with 't' (timestamps) and 'p' (prices) arrays.
    """
    history = history_data.get("history", [])
    return {
        "t": [item["t"] for item in history],
        "p": [item["p"] for item in history],
    }
