"""MCP Server for Threads Video Downloader & Google Drive Logger."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastmcp import FastMCP

from mcp_server.tools.utils.log_decorator import setup_logging
from mcp_server.tools.form_tools import submit_form
from mcp_server.tools.threads_tools import check_video_exists, fetch_threads_video_data
from mcp_server.tools.download_tools import download_video_file
from mcp_server.tools.drive_tools import set_sharing_permissions, upload_video_to_drive
from mcp_server.tools.sheets_tools import (
    log_failure_to_sheets,
    log_success_to_sheets,
    wait_before_logging_failure,
)

logger = setup_logging("logs/server.log")
logger.info("Starting ThreadsDownloader MCP server...")

mcp = FastMCP("ThreadsDownloader")

# Step 1 — Form Trigger
mcp.tool()(submit_form)
# Step 2 — Fetch video metadata from RapidAPI
mcp.tool()(fetch_threads_video_data)
# Step 3 — Check if a video download URL was returned
mcp.tool()(check_video_exists)
# Step 4 — Download video file (success path)
mcp.tool()(download_video_file)
# Step 5 — Upload to Google Drive
mcp.tool()(upload_video_to_drive)
# Step 6 — Set sharing permissions
mcp.tool()(set_sharing_permissions)
# Step 7 — Log success to Google Sheets
mcp.tool()(log_success_to_sheets)
# Step 8 — Wait before logging failure (failure path)
mcp.tool()(wait_before_logging_failure)
# Step 9 — Log failure to Google Sheets
mcp.tool()(log_failure_to_sheets)

if __name__ == "__main__":
    mcp.run("stdio")
