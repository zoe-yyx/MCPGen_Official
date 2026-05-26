import logging
from fastmcp import FastMCP
from tools.data_tools import fetch_crypto_prices, fetch_stock_prices, combine_market_data
from tools.analysis_tools import (
    calculate_technical_indicators,
    call_ai_signal_prediction,
    analyze_signals_confidence,
    validate_signal_filter,
)
from tools.notification_tools import (
    generate_alert_message,
    send_slack_notification,
    send_email_alert,
    send_sms_alert,
)
from tools.storage_tools import store_trade_signal, route_by_action, log_trade_execution
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")
logger.info("Initializing MCP server 'TradingAlertBot'")

mcp = FastMCP("TradingAlertBot")

# Data tools
mcp.tool()(fetch_crypto_prices)
mcp.tool()(fetch_stock_prices)
mcp.tool()(combine_market_data)

# Analysis tools
mcp.tool()(calculate_technical_indicators)
mcp.tool()(call_ai_signal_prediction)
mcp.tool()(analyze_signals_confidence)
mcp.tool()(validate_signal_filter)

# Notification tools
mcp.tool()(generate_alert_message)
mcp.tool()(send_slack_notification)
mcp.tool()(send_email_alert)
mcp.tool()(send_sms_alert)

# Storage tools
mcp.tool()(store_trade_signal)
mcp.tool()(route_by_action)
mcp.tool()(log_trade_execution)

logger.info("MCP server initialized with all tools.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")
