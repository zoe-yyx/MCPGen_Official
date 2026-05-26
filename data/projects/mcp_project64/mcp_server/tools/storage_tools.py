"""Tools for mock local storage (replacing Supabase and n8n data tables)."""

import os
from typing import Any
from dotenv import load_dotenv
from .utils.log_decorator import log_mcp_call
from .utils.mock_storage import (
    insert_record,
    load_table,
    query_records,
    update_records,
    save_table,
)

load_dotenv()

EVENT_TABLE_PATH = os.getenv("MOCK_EVENT_TABLE", "data/event_table.json")
SUPABASE_TABLE_PATH = os.getenv("MOCK_SUPABASE_TABLE", "data/supabase_table.json")


@log_mcp_call("tool", "register_event")
def register_event(event_id: str, closed: bool) -> dict[str, Any]:
    """Register a single event into the local event table.

    Args:
        event_id: The Polymarket event ID.
        closed: Whether the market is closed.

    Returns:
        The inserted record.
    """
    record = {
        "EventId": event_id,
        "Closed": str(closed).lower(),
        "Processed": False,
        "MarketId": "",
        "EndTime": "",
        "TokenUp": "",
        "TokenDw": "",
    }
    # Avoid duplicates
    existing = load_table(EVENT_TABLE_PATH)
    for r in existing:
        if r["EventId"] == event_id:
            return r
    return insert_record(EVENT_TABLE_PATH, record)


@log_mcp_call("tool", "fetch_unprocessed_events")
def fetch_unprocessed_events(limit: int = 100) -> list[dict[str, Any]]:
    """Fetch unprocessed events from the local event table.

    Args:
        limit: Maximum number of events to return.

    Returns:
        List of unprocessed event records.
    """
    return query_records(
        EVENT_TABLE_PATH,
        filter_fn=lambda r: not r.get("Processed", False),
        limit=limit,
    )


@log_mcp_call("tool", "store_tokens_and_endtime")
def store_tokens_and_endtime(
    event_id: str, market_id: str, end_time: str, token_up: str, token_dw: str
) -> int:
    """Store UP/DOWN token IDs and end time for an event.

    Args:
        event_id: The event ID to update.
        market_id: The market ID.
        end_time: The end time string.
        token_up: The UP token ID.
        token_dw: The DOWN token ID.

    Returns:
        Number of updated records.
    """
    return update_records(
        EVENT_TABLE_PATH,
        "EventId",
        event_id,
        {
            "MarketId": market_id,
            "EndTime": end_time,
            "TokenUp": token_up,
            "TokenDw": token_dw,
        },
    )


@log_mcp_call("tool", "check_market_closed")
def check_market_closed(event_id: str) -> dict[str, Any]:
    """Check if a market is closed and return event data.

    Args:
        event_id: The event ID to check.

    Returns:
        dict with 'is_closed' bool and full event record.
    """
    records = query_records(
        EVENT_TABLE_PATH,
        filter_fn=lambda r: r.get("EventId") == event_id,
        limit=1,
    )
    if not records:
        return {"is_closed": False, "event": {}}
    record = records[0]
    return {
        "is_closed": record.get("Closed", "false") == "true",
        "event": record,
    }


@log_mcp_call("tool", "mark_event_processed")
def mark_event_processed(event_id: str) -> int:
    """Mark an event as processed in the local event table.

    Args:
        event_id: The event ID to mark.

    Returns:
        Number of updated records.
    """
    return update_records(EVENT_TABLE_PATH, "EventId", event_id, {"Processed": True})


@log_mcp_call("tool", "store_in_supabase")
def store_in_supabase(
    event_id: str, prices: list, timestamps: list
) -> dict[str, Any]:
    """Store price data into the mock Supabase table (local JSON).

    Args:
        event_id: The event ID.
        prices: List of price values.
        timestamps: List of timestamp values.

    Returns:
        The inserted record.
    """
    record = {
        "EventId": event_id,
        "price": prices,
        "time_of_price": timestamps,
    }
    return insert_record(SUPABASE_TABLE_PATH, record)
