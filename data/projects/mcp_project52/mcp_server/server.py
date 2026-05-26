"""
MCP Server – Classify and Summarize WeChat Articles

Registers all tool functions from the tools/ package with FastMCP
and starts the server over stdio (required for MCP JSON-RPC protocol).

IMPORTANT: All logging in this file and every imported tool module must be
file-only (console_output=False).  Any print/stdout output breaks the
stdio JSON-RPC channel.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when invoked as a subprocess
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from fastmcp import FastMCP

from mcp_server.tools.utils.logging_decorator import setup_logging

# Server-level logger (file only)
logger = setup_logging("logs/server.log", console_output=False)
logger.info("Initialising MCP server 'WeChatArticleSummarizer'")

# ── Import tool functions ──────────────────────────────────────────────────────
from mcp_server.tools.sheets_tools import (
    tool_read_initial_links,
    tool_read_rss_links,
    tool_save_initial_data,
    tool_save_relevant_article,
)
from mcp_server.tools.rss_tools import tool_rss_read
from mcp_server.tools.processing_tools import (
    tool_process_pubdate,
    tool_filter_by_date,
    tool_extract_pubdate_link,
    tool_filter_unique_links,
    tool_restore_full_data,
    tool_clean_html_content,
    tool_set_filtered_data,
)
from mcp_server.tools.ai_tools import (
    tool_classify_relevance,
    tool_summarize_article,
)
from mcp_server.tools.notion_tools import tool_create_notion_page

# ── Create FastMCP app ─────────────────────────────────────────────────────────
mcp = FastMCP(
    "WeChatArticleSummarizer",
    instructions=(
        "Classify and summarize WeChat articles from RSS feeds. "
        "Reads feed URLs from Google Sheets, filters by date and uniqueness, "
        "classifies relevance with GPT-4.1-nano, generates Chinese summaries, "
        "and saves results to Google Sheets and Notion."
    ),
)

# ── Register tools ─────────────────────────────────────────────────────────────
# Google Sheets I/O
mcp.tool()(tool_read_initial_links)
mcp.tool()(tool_read_rss_links)
mcp.tool()(tool_save_initial_data)
mcp.tool()(tool_save_relevant_article)

# RSS
mcp.tool()(tool_rss_read)

# Data processing
mcp.tool()(tool_process_pubdate)
mcp.tool()(tool_filter_by_date)
mcp.tool()(tool_extract_pubdate_link)
mcp.tool()(tool_filter_unique_links)
mcp.tool()(tool_restore_full_data)
mcp.tool()(tool_clean_html_content)
mcp.tool()(tool_set_filtered_data)

# AI
mcp.tool()(tool_classify_relevance)
mcp.tool()(tool_summarize_article)

# Notion
mcp.tool()(tool_create_notion_page)

logger.info("Registered %d tools", 15)

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")