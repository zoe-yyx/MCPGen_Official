"""MCP Server for Instant Ad Banner Generator."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastmcp import FastMCP

from mcp_server.tools.line_tools import receive_line_webhook, extract_line_data, send_line_reply
from mcp_server.tools.ai_tools import optimize_prompt, extract_prompt_text
from mcp_server.tools.image_gen_tools import (
    submit_image_generation,
    wait_for_processing,
    check_job_status,
    wait_for_generation,
    parse_result,
)
from mcp_server.tools.storage_tools import download_image, upload_to_s3
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")

mcp = FastMCP("InstantAdBannerGenerator")

mcp.tool()(receive_line_webhook)
mcp.tool()(extract_line_data)
mcp.tool()(optimize_prompt)
mcp.tool()(extract_prompt_text)
mcp.tool()(submit_image_generation)
mcp.tool()(wait_for_processing)
mcp.tool()(check_job_status)
mcp.tool()(wait_for_generation)
mcp.tool()(parse_result)
mcp.tool()(download_image)
mcp.tool()(upload_to_s3)
mcp.tool()(send_line_reply)

if __name__ == "__main__":
    logger.info("Starting InstantAdBannerGenerator MCP server...")
    mcp.run("stdio")
