from fastmcp import FastMCP

from tools.sheets_tools import google_sheets_trigger
from tools.scheduling_tools import calculate_next_slot, create_calendar_event
from tools.ai_tools import generate_interview_email
from tools.email_tools import send_gmail
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")
logger.info("Initializing MCP server 'InterviewScheduler'")

mcp = FastMCP("InterviewScheduler")

# Register all tools
mcp.tool()(google_sheets_trigger)
mcp.tool()(calculate_next_slot)
mcp.tool()(create_calendar_event)
mcp.tool()(generate_interview_email)
mcp.tool()(send_gmail)

logger.info("MCP server initialized with all tools registered.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")
