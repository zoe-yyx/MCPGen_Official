import logging
import os
from fastmcp import FastMCP
from tools.data_tools import (
    set_analysis_parameters,
    fetch_gold_prices,
    fetch_equity_prices,
    merge_market_data,
)
from tools.analysis_tools import (
    calculate_performance_metrics,
    generate_ai_investment_insights,
    parse_ai_output,
)
from tools.report_tools import (
    generate_chart,
    combine_ai_chart_data,
    generate_final_report,
)
from tools.notification_tools import (
    check_performance_gap,
    send_report_email,
    send_alert_email,
    store_report_history,
)
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")
logger.info("Initializing MCP server 'GoldVsEquity'")

mcp = FastMCP("GoldVsEquity")

# Data tools
mcp.tool()(set_analysis_parameters)
mcp.tool()(fetch_gold_prices)
mcp.tool()(fetch_equity_prices)
mcp.tool()(merge_market_data)

# Analysis tools
mcp.tool()(calculate_performance_metrics)
mcp.tool()(generate_ai_investment_insights)
mcp.tool()(parse_ai_output)

# Report tools
mcp.tool()(generate_chart)
mcp.tool()(combine_ai_chart_data)
mcp.tool()(generate_final_report)

# Notification tools
mcp.tool()(check_performance_gap)
mcp.tool()(send_report_email)
mcp.tool()(send_alert_email)
mcp.tool()(store_report_history)

logger.info("MCP server initialized with all tools.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")
