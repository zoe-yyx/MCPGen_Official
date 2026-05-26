"""
Run the Polymarket historical price collection workflow via MCP client.

Phase 1: Collect event IDs from a slug → register into local event table.
Phase 2: Batch-process unprocessed events → fetch prices → store locally.
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_server.tools.utils.log_decorator import setup_logging

load_dotenv()

logger = setup_logging("logs/workflow.log")

DEFAULT_SLUG = os.getenv("DEFAULT_SLUG", "bitcoin-up-or-down-january-12-8am-et")


def _extract_text(result) -> str:
    """Extract text content from an MCP tool result."""
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return block.text
    if hasattr(result, "data"):
        return str(result.data)
    return str(result)


def _parse_result(result) -> dict | list | str:
    """Parse MCP tool result into Python object."""
    text = _extract_text(result)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


async def phase1_collect_events(client: Client, slug: str) -> None:
    """Phase 1: Collect all event IDs from a Polymarket series slug."""
    logger.info(f"=== Phase 1: Collecting events for slug '{slug}' ===")

    # Step 1: provide slug (trigger - no tool call)
    logger.info(f"Step 1: Using slug = '{slug}'")

    # Step 2: Find event ID from slug
    logger.info("Step 2: Finding event ID from slug...")
    result = await client.call_tool("find_event_id_from_slug", {"slug": slug})
    market_data = _parse_result(result)
    if isinstance(market_data, str):
        logger.error(f"Failed to parse market data: {market_data}")
        return
    events_list = market_data.get("events", [])
    if not events_list:
        logger.error("No events found for this slug.")
        return
    first_event_id = events_list[0]["id"]
    logger.info(f"  Found event ID: {first_event_id}")

    # Step 3: Find series ID from event
    logger.info("Step 3: Finding series ID from event...")
    result = await client.call_tool("find_series_id_from_event", {"event_id": first_event_id})
    event_data = _parse_result(result)
    if isinstance(event_data, str):
        logger.error(f"Failed to parse event data: {event_data}")
        return
    series_list = event_data.get("series", [])
    if not series_list:
        logger.error("No series found for this event.")
        return
    series_id = series_list[0]["id"]
    logger.info(f"  Found series ID: {series_id}")

    # Step 4: Find all events for series
    logger.info("Step 4: Finding all events for series...")
    result = await client.call_tool("find_all_events_for_series", {"series_id": series_id})
    series_data = _parse_result(result)
    if isinstance(series_data, str):
        logger.error(f"Failed to parse series data: {series_data}")
        return

    # Step 5: Split events
    logger.info("Step 5: Splitting events...")
    result = await client.call_tool("split_events", {"series_data": series_data})
    events = _parse_result(result)
    if isinstance(events, str):
        logger.error(f"Failed to split events: {events}")
        return
    logger.info(f"  Found {len(events)} events in series")

    # Limit to first 20 closed events for practical execution
    closed_events = [e for e in events if e.get("closed")]
    events_to_register = closed_events[:20]
    logger.info(f"  Limiting to {len(events_to_register)} closed events for processing")

    # Step 6: Register events
    logger.info("Step 6: Registering events...")
    for event in events_to_register:
        result = await client.call_tool(
            "register_event",
            {"event_id": event["id"], "closed": event["closed"]},
        )
        logger.info(f"  Registered event {event['id']} (closed={event['closed']})")

    logger.info(f"=== Phase 1 complete: {len(events_to_register)} events registered ===")


async def phase2_collect_prices(client: Client) -> None:
    """Phase 2: Batch-process unprocessed closed events and fetch prices."""
    logger.info("=== Phase 2: Collecting price data ===")

    # Step 7: Fetch unprocessed events (only process 1 event)
    logger.info("Step 7: Fetching unprocessed events...")
    result = await client.call_tool("fetch_unprocessed_events", {"limit": 1})
    unprocessed = _parse_result(result)
    if isinstance(unprocessed, str):
        logger.error(f"Failed to fetch unprocessed events: {unprocessed}")
        return
    if not unprocessed:
        logger.info("  No more unprocessed events. Done!")
        return
    logger.info(f"  Found {len(unprocessed)} unprocessed event(s), processing first one")

    event = unprocessed[0]
    event_id = event["EventId"]
    logger.info(f"  Processing event {event_id}...")

    # Step 8: Fetch UP/DOWN tokens
    logger.info("  Step 8: Fetching UP/DOWN tokens...")
    result = await client.call_tool("fetch_up_down_tokens", {"event_id": event_id})
    token_data = _parse_result(result)
    if isinstance(token_data, str):
        logger.warning(f"    Failed to fetch tokens for {event_id}, marking processed.")
        await client.call_tool("mark_event_processed", {"event_id": event_id})
        return

    # Step 9: Extract and store tokens
    logger.info("  Step 9: Extracting and storing tokens...")
    result = await client.call_tool("extract_tokens_and_endtime", {"event_data": token_data})
    extracted = _parse_result(result)
    if isinstance(extracted, str):
        logger.warning(f"    Failed to extract tokens for {event_id}, marking processed.")
        await client.call_tool("mark_event_processed", {"event_id": event_id})
        return

    await client.call_tool(
        "store_tokens_and_endtime",
        {
            "event_id": event_id,
            "market_id": extracted["MarketId"],
            "end_time": extracted["EndTime"],
            "token_up": extracted["TokenUp"],
            "token_dw": extracted["TokenDw"],
        },
    )

    # Step 10: Check if market is closed
    logger.info("  Step 10: Checking if market is closed...")
    result = await client.call_tool("check_market_closed", {"event_id": event_id})
    closed_info = _parse_result(result)
    if isinstance(closed_info, str):
        logger.warning(f"    Failed to check closed status for {event_id}")
        await client.call_tool("mark_event_processed", {"event_id": event_id})
        return

    if not closed_info.get("is_closed", False):
        logger.info(f"    Market {event_id} is not closed, marking processed and skipping.")
        await client.call_tool("mark_event_processed", {"event_id": event_id})
        return

    # Step 11: Convert end time to Unix timestamp
    end_time_str = extracted.get("EndTime", "")
    if not end_time_str:
        logger.warning(f"    No EndTime for {event_id}, skipping.")
        await client.call_tool("mark_event_processed", {"event_id": event_id})
        return

    logger.info("  Step 11: Converting end time to Unix...")
    result = await client.call_tool("convert_endtime_to_unix", {"end_time_str": end_time_str})
    end_unix = _parse_result(result)
    if isinstance(end_unix, str):
        logger.warning(f"    Failed to convert time for {event_id}, skipping.")
        await client.call_tool("mark_event_processed", {"event_id": event_id})
        return

    # Step 12: Set start time
    logger.info("  Step 12: Setting start time...")
    result = await client.call_tool(
        "set_start_time",
        {"end_time_unix": end_unix, "duration_seconds": 3600},
    )
    time_range = _parse_result(result)

    # Step 13: Fetch price history
    token_up = extracted.get("TokenUp", "")
    if not token_up:
        logger.warning(f"    No TokenUp for {event_id}, skipping.")
        await client.call_tool("mark_event_processed", {"event_id": event_id})
        return

    logger.info("  Step 13: Fetching price history...")
    result = await client.call_tool(
        "fetch_price_history",
        {
            "token_id": token_up,
            "start_ts": time_range["StartTimeUnix"],
            "end_ts": time_range["EndTimeUnix"],
        },
    )
    history_data = _parse_result(result)
    if isinstance(history_data, str):
        logger.warning(f"    Failed to fetch prices for {event_id}, skipping.")
        await client.call_tool("mark_event_processed", {"event_id": event_id})
        return

    # Step 14: Split prices and timestamps
    logger.info("  Step 14: Splitting prices and timestamps...")
    result = await client.call_tool("split_prices_and_timestamps", {"history_data": history_data})
    split_data = _parse_result(result)
    if isinstance(split_data, str):
        logger.warning(f"    Failed to split prices for {event_id}")
        await client.call_tool("mark_event_processed", {"event_id": event_id})
        return

    # Step 15: Store in Supabase (mock)
    logger.info("  Step 15: Storing in mock Supabase...")
    await client.call_tool(
        "store_in_supabase",
        {
            "event_id": event_id,
            "prices": split_data.get("p", []),
            "timestamps": split_data.get("t", []),
        },
    )

    # Step 16: Mark as processed
    logger.info("  Step 16: Marking as processed...")
    await client.call_tool("mark_event_processed", {"event_id": event_id})
    logger.info(f"  Event {event_id} processed successfully!")

    logger.info("=== Phase 2 complete ===")


async def main() -> None:
    """Run the full Polymarket price collection workflow."""
    slug = DEFAULT_SLUG
    logger.info(f"Starting Polymarket price collection workflow with slug: {slug}")

    async with Client("mcp_server/server.py") as client:
        # List available tools
        tools = await client.list_tools()
        logger.info(f"Available tools ({len(tools)}):")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description}")
        logger.info("-" * 60)

        # Phase 1: Collect events
        await phase1_collect_events(client, slug)

        # Phase 2: Collect prices
        await phase2_collect_prices(client)

    logger.info("Workflow complete.")

    # Save summary to results
    os.makedirs("results/outputs", exist_ok=True)
    summary = {
        "slug": slug,
        "status": "completed",
        "event_table": os.getenv("MOCK_EVENT_TABLE", "data/event_table.json"),
        "supabase_table": os.getenv("MOCK_SUPABASE_TABLE", "data/supabase_table.json"),
    }
    with open("results/outputs/workflow_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    logger.info("Summary saved to results/outputs/workflow_summary.json")


if __name__ == "__main__":
    asyncio.run(main())
