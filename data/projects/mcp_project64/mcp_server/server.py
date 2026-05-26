import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastmcp import FastMCP
from tools.polymarket_api_tools import (
    find_event_id_from_slug,
    find_series_id_from_event,
    find_all_events_for_series,
    fetch_up_down_tokens,
    fetch_price_history,
)
from tools.data_tools import (
    split_events,
    extract_tokens_and_endtime,
    convert_endtime_to_unix,
    set_start_time,
    split_prices_and_timestamps,
)
from tools.storage_tools import (
    register_event,
    fetch_unprocessed_events,
    store_tokens_and_endtime,
    check_market_closed,
    mark_event_processed,
    store_in_supabase,
)
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")
logger.info("Initializing MCP server 'PolymarketPriceCollector'")

mcp = FastMCP("PolymarketPriceCollector")

# Register API tools
mcp.tool()(find_event_id_from_slug)
mcp.tool()(find_series_id_from_event)
mcp.tool()(find_all_events_for_series)
mcp.tool()(fetch_up_down_tokens)
mcp.tool()(fetch_price_history)

# Register data transformation tools
mcp.tool()(split_events)
mcp.tool()(extract_tokens_and_endtime)
mcp.tool()(convert_endtime_to_unix)
mcp.tool()(set_start_time)
mcp.tool()(split_prices_and_timestamps)

# Register storage tools
mcp.tool()(register_event)
mcp.tool()(fetch_unprocessed_events)
mcp.tool()(store_tokens_and_endtime)
mcp.tool()(check_market_closed)
mcp.tool()(mark_event_processed)
mcp.tool()(store_in_supabase)

logger.info("MCP server initialized with all tools.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")
