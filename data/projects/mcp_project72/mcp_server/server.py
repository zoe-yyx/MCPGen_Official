"""MCP Server for AI Hotel Receptionist via WhatsApp."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastmcp import FastMCP

from mcp_server.tools.whatsapp_tools import receive_whatsapp_message, check_message, send_whatsapp_reply
from mcp_server.tools.redis_tools import check_user_model, store_user_model
from mcp_server.tools.model_tools import decide_model
from mcp_server.tools.hotel_data_tools import get_pricing, execute_sql_query
from mcp_server.tools.ai_tools import ai_hotel_agent
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/server.log")

mcp = FastMCP("HotelReceptionistBot")

mcp.tool()(receive_whatsapp_message)
mcp.tool()(check_message)
mcp.tool()(check_user_model)
mcp.tool()(decide_model)
mcp.tool()(store_user_model)
mcp.tool()(get_pricing)
mcp.tool()(execute_sql_query)
mcp.tool()(ai_hotel_agent)
mcp.tool()(send_whatsapp_reply)

if __name__ == "__main__":
    logger.info("Starting HotelReceptionistBot MCP server...")
    mcp.run("stdio")
