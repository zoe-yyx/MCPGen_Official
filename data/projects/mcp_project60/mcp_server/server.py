"""FastMCP server — Multi-Asset Daily Market Snapshot."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

# Load .env from project root so env vars are available in subprocess
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

from tools.market_tools import (
    set_market_assets,
    split_assets_symbols,
    fetch_asset_price,
    validate_api_response,
    normalize_market_data,
)
from tools.ai_tools import (
    generate_market_insights,
    parse_ai_output,
)
from tools.report_tools import (
    log_daily_report,
    send_market_email,
    log_api_error,
    send_error_alert,
)
from tools.utils.log_decorator import setup_logging

# File-only logging to keep stdio clean for MCP JSON-RPC
logger = setup_logging("logs/server.log")
logger.handlers = [h for h in logger.handlers if not hasattr(h, "stream")]

mcp = FastMCP("MarketSnapshot")

# Market data tools
mcp.tool()(set_market_assets)
mcp.tool()(split_assets_symbols)
mcp.tool()(fetch_asset_price)
mcp.tool()(validate_api_response)
mcp.tool()(normalize_market_data)

# AI analysis tools
mcp.tool()(generate_market_insights)
mcp.tool()(parse_ai_output)

# Report tools
mcp.tool()(log_daily_report)
mcp.tool()(send_market_email)
mcp.tool()(log_api_error)
mcp.tool()(send_error_alert)

logger.info("MarketSnapshot MCP server initialized with 11 tools.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    mcp.run("stdio")
