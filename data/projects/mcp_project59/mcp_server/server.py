"""FastMCP server — AI Image to Professional Video Workflow.

Registers all tools for image management, AI generation (mock), and publishing.
"""

from __future__ import annotations

from fastmcp import FastMCP

from tools.image_tools import (
    get_image_records,
    update_record,
    download_source_image,
    upload_image_public,
    get_image_info,
    crop_image,
    save_to_drive,
)
from tools.generation_tools import (
    build_contact_sheet_prompt,
    generate_contact_sheet,
    poll_generation_result,
    generate_video_clip,
    poll_video_result,
    merge_videos,
)
from tools.publishing_tools import (
    upload_media,
    create_social_post,
)
from tools.utils.log_decorator import setup_logging

# File-only logging — never print to stdout (breaks MCP stdio protocol)
logger = setup_logging("logs/server.log")
# Remove console handler to keep stdio clean for MCP JSON-RPC
logger.handlers = [h for h in logger.handlers if not hasattr(h, "stream")]

mcp = FastMCP("ImageToVideo")

# Image management tools
mcp.tool()(get_image_records)
mcp.tool()(update_record)
mcp.tool()(download_source_image)
mcp.tool()(upload_image_public)
mcp.tool()(get_image_info)
mcp.tool()(crop_image)
mcp.tool()(save_to_drive)

# AI generation tools (mock)
mcp.tool()(build_contact_sheet_prompt)
mcp.tool()(generate_contact_sheet)
mcp.tool()(poll_generation_result)
mcp.tool()(generate_video_clip)
mcp.tool()(poll_video_result)
mcp.tool()(merge_videos)

# Publishing tools (mock)
mcp.tool()(upload_media)
mcp.tool()(create_social_post)

logger.info("ImageToVideo MCP server initialized with 15 tools.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    mcp.run("stdio")
