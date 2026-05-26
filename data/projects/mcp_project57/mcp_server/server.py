import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP
from tools.booking_tools import (
    receive_booking,
    get_workflow_config,
    fetch_inventory,
    prepare_validation_input,
)
from tools.validation_tools import validate_ticket, route_by_risk_level
from tools.orchestration_tools import orchestrate_fan_experience, update_ticketing_system
from tools.notification_tools import (
    send_confirmation_email,
    alert_operations_team,
    log_audit_trail,
)
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log", console_output=False)
logger.info("Initializing MCP server 'ConcertTicketOps'")

mcp = FastMCP("ConcertTicketOps")

# Booking tools
mcp.tool()(receive_booking)
mcp.tool()(get_workflow_config)
mcp.tool()(fetch_inventory)
mcp.tool()(prepare_validation_input)

# Validation tools
mcp.tool()(validate_ticket)
mcp.tool()(route_by_risk_level)

# Orchestration tools
mcp.tool()(orchestrate_fan_experience)
mcp.tool()(update_ticketing_system)

# Notification tools
mcp.tool()(send_confirmation_email)
mcp.tool()(alert_operations_team)
mcp.tool()(log_audit_trail)

logger.info("MCP server initialized with all tools registered.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")
