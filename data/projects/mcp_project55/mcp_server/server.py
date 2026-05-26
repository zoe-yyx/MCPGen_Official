import logging
from fastmcp import FastMCP
from tools.sheets_tools import get_form_responses, read_ticket_rows, append_scan_result
from tools.processing_tools import select_latest_item, set_ticket_code
from tools.validation_tools import validate_ticket
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")
logger.info("Initializing MCP server 'QRTicketValidator'")

mcp = FastMCP("QRTicketValidator")

mcp.tool()(get_form_responses)
mcp.tool()(read_ticket_rows)
mcp.tool()(append_scan_result)
mcp.tool()(select_latest_item)
mcp.tool()(set_ticket_code)
mcp.tool()(validate_ticket)

logger.info("MCP server initialized with 6 tools.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
