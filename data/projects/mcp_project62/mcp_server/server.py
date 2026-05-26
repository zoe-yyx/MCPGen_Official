import logging
from fastmcp import FastMCP
from tools.data_tools import get_sample_data, split_and_set_keywords
from tools.scraping_tools import (
    scrape_financial_times,
    get_scraping_progress,
    get_snapshot_data,
)
from tools.analysis_tools import aggregate_data, create_summary
from tools.notification_tools import save_to_sheets, send_email
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")
logger.info("Initializing MCP server 'StockMonitor'")

mcp = FastMCP("StockMonitor")

# Data tools
mcp.tool()(get_sample_data)
mcp.tool()(split_and_set_keywords)

# Scraping tools
mcp.tool()(scrape_financial_times)
mcp.tool()(get_scraping_progress)
mcp.tool()(get_snapshot_data)

# Analysis tools
mcp.tool()(aggregate_data)
mcp.tool()(create_summary)

# Notification tools
mcp.tool()(save_to_sheets)
mcp.tool()(send_email)

logger.info("MCP server initialized with all tools.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")
