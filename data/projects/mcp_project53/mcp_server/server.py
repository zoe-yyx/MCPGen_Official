"""
MCP Server — Legal & Compliance Document Archiving
Registers all tools and starts the server on stdio.
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path when launched as a subprocess
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastmcp import FastMCP
from mcp_server.tools.utils.logging_decorator import setup_logging
from mcp_server.tools.validation_tools import tool_validate_and_enrich
from mcp_server.tools.storage_tools import (
    tool_check_duplicate,
    tool_find_or_create_folder,
    tool_upload_document,
    tool_find_employee_record,
    tool_upsert_employee_record,
)
from mcp_server.tools.notification_tools import (
    tool_upload_to_cdn,
    tool_send_confirmation_email,
    tool_build_final_response,
)

logger = setup_logging("logs/server.log", console_output=False)
logger.info("Initialising MCP server 'HR Contract Archiver'")

mcp = FastMCP(
    "HR Contract Archiver",
    instructions=(
        "Automates the entire HR contract archiving chain: "
        "validate → duplicate-check → CDN upload → local Drive storage → "
        "record upsert → email notification → audit response."
    ),
)

# ── Register tools ─────────────────────────────────────────────────────────────
mcp.tool()(tool_validate_and_enrich)
mcp.tool()(tool_check_duplicate)
mcp.tool()(tool_find_or_create_folder)
mcp.tool()(tool_upload_to_cdn)
mcp.tool()(tool_upload_document)
mcp.tool()(tool_find_employee_record)
mcp.tool()(tool_upsert_employee_record)
mcp.tool()(tool_send_confirmation_email)
mcp.tool()(tool_build_final_response)

logger.info("All tools registered. Server ready.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")