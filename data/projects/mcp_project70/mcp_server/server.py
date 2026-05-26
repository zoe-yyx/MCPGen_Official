"""MCP Server for Turn Google Tasks into n8n Plans with Slack Approval & Archiving."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastmcp import FastMCP

from mcp_server.tools.tasks_tools import get_new_ideas, filter_processed, mark_as_notified
from mcp_server.tools.ai_tools import ai_solution_architect
from mcp_server.tools.slack_tools import slack_review_approve, check_approval
from mcp_server.tools.sheets_tools import archive_to_sheets
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")

mcp = FastMCP("GoogleTasksN8nPlanner")

mcp.tool()(get_new_ideas)
mcp.tool()(filter_processed)
mcp.tool()(mark_as_notified)
mcp.tool()(ai_solution_architect)
mcp.tool()(slack_review_approve)
mcp.tool()(check_approval)
mcp.tool()(archive_to_sheets)

if __name__ == "__main__":
    logger.info("Starting GoogleTasksN8nPlanner MCP server...")
    mcp.run("stdio")
