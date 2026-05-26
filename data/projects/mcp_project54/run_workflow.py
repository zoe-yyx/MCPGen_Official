"""Smart Inventory Replenishment Workflow.

Steps match workflow.json step_id order:
  1  schedule_trigger            — cron-like kick-off
  2  fetch_inventory             — warehouse stock levels
  3  fetch_sales_velocity        — 30-day sales data
  4  merge_inventory_and_sales   — join by product_id
  5  ai_demand_forecasting       — GPT forecast per product
  6  parse_ai_response           — extract structured forecast
  7  filter_reorder_needed       — keep should_reorder=True only
  8  create_purchase_order       — generate PO document
  9  send_po_to_supplier         — mock supplier API POST
  10 log_to_erp                  — mock ERP log
  11 save_to_database            — SQLite insert
  12 send_notification_email     — mock email notification
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from fastmcp import Client

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/workflow.log")


def extract_text(result) -> str:
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return block.text
    return str(result)


async def main() -> None:
    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info("Server started with %d tools registered", len(tools))
        logger.info("=" * 60)
        logger.info("Smart Inventory Replenishment — Purchase Order Pipeline")
        logger.info("=" * 60)

        # Step 1: Schedule Trigger
        step1_raw = extract_text(await client.call_tool("schedule_trigger", {}))
        step1 = json.loads(step1_raw)
        logger.info("Step 1: trigger fired at %.0f", step1["triggered_at"])

        # Step 2: Fetch Current Inventory
        step2_raw = extract_text(await client.call_tool("fetch_inventory", {}))
        step2 = json.loads(step2_raw)
        logger.info("Step 2: fetched %d inventory items", step2["total_products"])

        # Step 3: Fetch Sales Velocity
        step3_raw = extract_text(await client.call_tool("fetch_sales_velocity", {"days": 30}))
        step3 = json.loads(step3_raw)
        logger.info("Step 3: fetched sales for %d products (days=30)", step3["total_products"])

        # Step 4: Merge Inventory & Sales Data
        step4_raw = extract_text(await client.call_tool("merge_inventory_and_sales", {
            "inventory_json": step2_raw,
            "sales_json": step3_raw,
        }))
        step4 = json.loads(step4_raw)
        merged_items = step4["merged"]
        logger.info("Step 4: merged %d products", step4["count"])

        # Steps 5–12: per-product processing
        po_index = 0
        total_pos = 0
        total_spend = 0.0

        for item in merged_items:
            item_json = json.dumps(item)
            logger.info("-" * 50)
            logger.info("  Processing: %s (%s) | stock=%d reorder_pt=%d",
                        item["product_name"], item["product_id"],
                        item["current_stock"], item["reorder_point"])

            # Step 5: AI Demand Forecasting
            step5_raw = extract_text(await client.call_tool("ai_demand_forecasting", {
                "product_data_json": item_json,
            }))
            step5 = json.loads(step5_raw)
            forecast = step5.get("forecast", {})
            logger.info("  Step 5: AI forecast → should_reorder=%s qty=%d confidence=%s",
                        forecast.get("should_reorder"),
                        forecast.get("recommended_quantity", 0),
                        forecast.get("confidence_level"))

            # Step 6: Parse AI Response
            step6_raw = extract_text(await client.call_tool("parse_ai_response", {
                "ai_response_json": step5_raw,
                "original_item_json": item_json,
            }))
            step6 = json.loads(step6_raw)

            # Step 7: Filter: Reorder Needed
            step7_raw = extract_text(await client.call_tool("filter_reorder_needed", {
                "parsed_item_json": step6_raw,
            }))
            step7 = json.loads(step7_raw)

            if not step7["passes"]:
                logger.info("  Step 7: SKIP — no reorder needed for %s", item["product_id"])
                continue

            logger.info("  Step 7: PASS — reorder needed for %s", item["product_id"])

            # Step 8: Create Purchase Order
            step8_raw = extract_text(await client.call_tool("create_purchase_order", {
                "item_json": step6_raw,
                "index": po_index,
            }))
            step8 = json.loads(step8_raw)
            po_index += 1
            logger.info("  Step 8: PO created → %s (qty=%d total=$%.2f)",
                        step8["po_number"], step8["quantity"], step8["total_cost"])

            # Step 9: Send PO to Supplier
            step9_raw = extract_text(await client.call_tool("send_po_to_supplier", {
                "po_json": step8_raw,
            }))
            step9 = json.loads(step9_raw)
            logger.info("  Step 9: supplier confirmation → %s", step9["po_id"])

            # Step 10: Log to ERP System
            step10_raw = extract_text(await client.call_tool("log_to_erp", {
                "po_json": step8_raw,
            }))
            step10 = json.loads(step10_raw)
            logger.info("  Step 10: ERP logged → %s", step10["erp_record_id"])

            # Step 11: Save to Database
            step11_raw = extract_text(await client.call_tool("save_to_database", {
                "po_json": step8_raw,
            }))
            step11 = json.loads(step11_raw)
            logger.info("  Step 11: DB saved → row_id=%s", step11["row_id"])

            # Step 12: Send Notification Email
            step12_raw = extract_text(await client.call_tool("send_notification_email", {
                "po_json": step8_raw,
            }))
            step12 = json.loads(step12_raw)
            logger.info("  Step 12: email sent → %s", step12["to"])

            total_pos += 1
            total_spend += step8["total_cost"]

        logger.info("=" * 60)
        logger.info("Pipeline complete: %d purchase order(s) created", total_pos)
        logger.info("Total procurement spend: $%.2f", total_spend)
        logger.info("Results saved to results/outputs/")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Workflow failed: %s", e, exc_info=True)
        raise
