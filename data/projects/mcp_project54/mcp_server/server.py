"""MCP Server for Smart Inventory Replenishment & Auto-Purchase Orders."""

import logging
import os
import sys

from dotenv import load_dotenv
from fastmcp import FastMCP

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
load_dotenv()

from mcp_server.tools.utils.log_decorator import setup_logging
from mcp_server.tools.inventory_tools import (
    fetch_inventory,
    fetch_sales_velocity,
    schedule_trigger,
)
from mcp_server.tools.data_tools import (
    create_purchase_order,
    filter_reorder_needed,
    merge_inventory_and_sales,
    parse_ai_response,
)
from mcp_server.tools.ai_tools import ai_demand_forecasting
from mcp_server.tools.supplier_tools import send_po_to_supplier
from mcp_server.tools.erp_tools import (
    log_to_erp,
    save_to_database,
    send_notification_email,
)

setup_logging("logs/server.log")
logger = logging.getLogger("mcp_server")

mcp = FastMCP("InventoryReplenishment")

mcp.tool()(schedule_trigger)
mcp.tool()(fetch_inventory)
mcp.tool()(fetch_sales_velocity)
mcp.tool()(merge_inventory_and_sales)
mcp.tool()(ai_demand_forecasting)
mcp.tool()(parse_ai_response)
mcp.tool()(filter_reorder_needed)
mcp.tool()(create_purchase_order)
mcp.tool()(send_po_to_supplier)
mcp.tool()(log_to_erp)
mcp.tool()(save_to_database)
mcp.tool()(send_notification_email)

logger.info("InventoryReplenishment MCP server starting with 12 tools")

if __name__ == "__main__":
    mcp.run("stdio")
