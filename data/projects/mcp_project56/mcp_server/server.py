import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP
from tools.file_tools import (
    search_local_files,
    retrieve_file,
    detect_file_type,
    extract_pdf_text,
    extract_text_file,
    extract_markdown_file,
    map_to_text,
)
from tools.graph_tools import save_to_graph, query_knowledge_base
from tools.chat_tools import chat_with_knowledge_base, clear_memory
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")
logger.info("Initializing MCP server 'GraphRAG-Chat'")

mcp = FastMCP("GraphRAG-Chat")

# Register file tools
mcp.tool()(search_local_files)
mcp.tool()(retrieve_file)
mcp.tool()(detect_file_type)
mcp.tool()(extract_pdf_text)
mcp.tool()(extract_text_file)
mcp.tool()(extract_markdown_file)
mcp.tool()(map_to_text)

# Register graph tools
mcp.tool()(save_to_graph)
mcp.tool()(query_knowledge_base)

# Register chat tools
mcp.tool()(chat_with_knowledge_base)
mcp.tool()(clear_memory)

logger.info("MCP server initialized with all tools registered.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")
