import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP
from tools.leads_tools import (
    get_leads,
    filter_unresearched_leads,
    update_lead_research,
    update_lead_status,
    get_email_template,
    get_services,
    save_email_draft,
    encode_company_url,
    save_send_link,
)
from tools.research_tools import search_internet, research_company
from tools.email_tools import draft_sales_email
from tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log", console_output=False)
logger.info("Initializing MCP server 'LeadsToSales'")

mcp = FastMCP("LeadsToSales")

# Leads tools
mcp.tool()(get_leads)
mcp.tool()(filter_unresearched_leads)
mcp.tool()(update_lead_research)
mcp.tool()(update_lead_status)
mcp.tool()(get_email_template)
mcp.tool()(get_services)
mcp.tool()(save_email_draft)
mcp.tool()(encode_company_url)
mcp.tool()(save_send_link)

# Research tools
mcp.tool()(search_internet)
mcp.tool()(research_company)

# Email tools
mcp.tool()(draft_sales_email)

logger.info("MCP server initialized with all tools registered.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user (KeyboardInterrupt)")
