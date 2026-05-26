import os
import sys

from fastmcp import FastMCP

from tools.data_tools import fetch_rsi, fetch_price_volume, merge_api_responses
from tools.signal_tools import calculate_trading_signals, assign_alert_priority, route_by_priority
from tools.ai_tools import generate_ai_summary
from tools.notification_tools import send_telegram, send_slack, send_error_email
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")
logger.info("Initializing MCP server 'TradeAlertDispatcher'")

mcp = FastMCP("TradeAlertDispatcher")

# Register data collection tools
mcp.tool()(fetch_rsi)
mcp.tool()(fetch_price_volume)
mcp.tool()(merge_api_responses)

# Register signal processing tools
mcp.tool()(calculate_trading_signals)
mcp.tool()(assign_alert_priority)
mcp.tool()(route_by_priority)

# Register AI analysis tool
mcp.tool()(generate_ai_summary)

# Register notification tools
mcp.tool()(send_telegram)
mcp.tool()(send_slack)
mcp.tool()(send_error_email)

logger.info("MCP server initialized with all tools registered.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")
