from fastmcp import FastMCP

from tools.leave_tools import (
    fetch_leave_records,
    validate_normalize_leave_data,
    mark_leave_as_active,
    mark_leave_as_inactive,
)
from tools.notification_tools import notify_hr_channel, notify_hr_leave_reset
from tools.email_tools import send_ooo_reminder_email, send_welcome_back_email
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")
logger.info("Initializing MCP server 'EmployeeLeaveAlerts'")

mcp = FastMCP("EmployeeLeaveAlerts")

mcp.tool()(fetch_leave_records)
mcp.tool()(validate_normalize_leave_data)
mcp.tool()(mark_leave_as_active)
mcp.tool()(mark_leave_as_inactive)
mcp.tool()(notify_hr_channel)
mcp.tool()(notify_hr_leave_reset)
mcp.tool()(send_ooo_reminder_email)
mcp.tool()(send_welcome_back_email)

logger.info("MCP server initialized with 8 tools registered.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")
