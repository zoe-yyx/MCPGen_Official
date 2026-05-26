import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastmcp import FastMCP
from tools.template_tools import (
    list_templates,
    get_template_metadata,
    copy_template,
    fill_document,
    generate_download_link,
)
from tools.doc_process_tools import (
    verify_user_choice,
    format_user_data,
    formatting_correction,
)
from tools.agent_tools import chat_with_doc_agent, reset_conversation
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")
logger.info("Initializing MCP server 'DocAgent'")

mcp = FastMCP("DocAgent")

# Template management tools
mcp.tool()(list_templates)
mcp.tool()(get_template_metadata)
mcp.tool()(copy_template)
mcp.tool()(fill_document)
mcp.tool()(generate_download_link)

# DocProcess subworkflow tools
mcp.tool()(verify_user_choice)
mcp.tool()(format_user_data)
mcp.tool()(formatting_correction)

# Agent tools
mcp.tool()(chat_with_doc_agent)
mcp.tool()(reset_conversation)

logger.info("MCP server 'DocAgent' initialized with all tools.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
