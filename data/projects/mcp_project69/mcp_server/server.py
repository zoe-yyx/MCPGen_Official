from fastmcp import FastMCP

from tools.webhook_tools import receive_uptime_webhook, check_heartbeat_status
from tools.command_tools import extract_service_name, route_command, parse_update_summary
from tools.docker_tools import (
    get_docker_logs, restart_docker_container,
    check_restart_success, docker_ps, run_docker_update,
)
from tools.ai_tools import analyze_logs_with_ai
from tools.notification_tools import (
    send_ok_notification, send_error_notification,
    send_analyzing_status, send_log_analysis,
    send_restart_message, send_restart_success, send_restart_failed,
    send_docker_status, send_update_started, send_update_result,
)
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")
logger.info("Initializing MCP server 'DockerManagementBot'")

mcp = FastMCP("DockerManagementBot")

# Webhook monitoring tools
mcp.tool()(receive_uptime_webhook)
mcp.tool()(check_heartbeat_status)

# Command parsing tools
mcp.tool()(extract_service_name)
mcp.tool()(route_command)
mcp.tool()(parse_update_summary)

# Docker operation tools
mcp.tool()(get_docker_logs)
mcp.tool()(restart_docker_container)
mcp.tool()(check_restart_success)
mcp.tool()(docker_ps)
mcp.tool()(run_docker_update)

# AI analysis tool
mcp.tool()(analyze_logs_with_ai)

# Notification tools (Telegram mock)
mcp.tool()(send_ok_notification)
mcp.tool()(send_error_notification)
mcp.tool()(send_analyzing_status)
mcp.tool()(send_log_analysis)
mcp.tool()(send_restart_message)
mcp.tool()(send_restart_success)
mcp.tool()(send_restart_failed)
mcp.tool()(send_docker_status)
mcp.tool()(send_update_started)
mcp.tool()(send_update_result)

logger.info("MCP server initialized with 20 tools registered.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")
