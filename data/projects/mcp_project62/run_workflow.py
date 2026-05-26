"""Daily Stock Monitor with AI Summary Email - MCP Workflow Runner.

Executes the workflow steps via fastmcp Client, matching step IDs in workflow.json.
"""

import asyncio
import json
from fastmcp import Client
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/workflow.log")


async def main() -> None:
    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info("Available tools:")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description}")
        logger.info("-" * 60)

        # ── step_1: get_sample_data ──
        logger.info("[step_1] Getting sample stock data...")
        step_1_result = await client.call_tool("get_sample_data", {})
        step_1 = json.loads(step_1_result.data) if isinstance(step_1_result.data, str) else step_1_result.data
        logger.info(f"[step_1] Got {len(step_1)} stocks")

        # ── step_2: split_and_set_keywords ──
        logger.info("[step_2] Splitting and setting keywords...")
        step_2_result = await client.call_tool("split_and_set_keywords", {
            "stocks": step_1,
        })
        step_2 = json.loads(step_2_result.data) if isinstance(step_2_result.data, str) else step_2_result.data
        logger.info(f"[step_2] Set {len(step_2)} keywords")

        # ── step_3: scrape_financial_times ──
        logger.info("[step_3] Triggering Financial Times scraper...")
        step_3_result = await client.call_tool("scrape_financial_times", {
            "keywords": step_2,
        })
        step_3 = json.loads(step_3_result.data) if isinstance(step_3_result.data, str) else step_3_result.data
        logger.info(f"[step_3] Got {len(step_3)} snapshot IDs")

        # ── step_4: get_scraping_progress ──
        logger.info("[step_4] Checking scraping progress...")
        step_4_result = await client.call_tool("get_scraping_progress", {
            "snapshot_ids": step_3,
        })
        step_4 = json.loads(step_4_result.data) if isinstance(step_4_result.data, str) else step_4_result.data
        all_ready = all(s["status"] == "ready" for s in step_4)
        logger.info(f"[step_4] All ready: {all_ready}")

        # ── step_5: get_snapshot_data ──
        logger.info("[step_5] Getting snapshot data...")
        step_5_result = await client.call_tool("get_snapshot_data", {
            "snapshot_ids": step_3,
        })
        step_5 = json.loads(step_5_result.data) if isinstance(step_5_result.data, str) else step_5_result.data
        logger.info(f"[step_5] Got data for {len(step_5)} stocks")

        # ── step_6: save_to_sheets (parallel with step_7 in n8n) ──
        logger.info("[step_6] Saving to Google Sheets (mock)...")
        step_6_result = await client.call_tool("save_to_sheets", {
            "stock_data": step_5,
        })
        step_6 = json.loads(step_6_result.data) if isinstance(step_6_result.data, str) else step_6_result.data
        logger.info(f"[step_6] Saved: {step_6['message']}")

        # ── step_7: aggregate_data ──
        logger.info("[step_7] Aggregating data...")
        step_7_result = await client.call_tool("aggregate_data", {
            "stock_items": step_5,
        })
        step_7 = json.loads(step_7_result.data) if isinstance(step_7_result.data, str) else step_7_result.data
        logger.info(f"[step_7] Aggregated {len(step_7['data'])} items")

        # ── step_8: create_summary (AI) ──
        logger.info("[step_8] Creating AI summary...")
        step_8_result = await client.call_tool("create_summary", {
            "aggregated_data": step_7,
        })
        step_8 = json.loads(step_8_result.data) if isinstance(step_8_result.data, str) else step_8_result.data
        logger.info(f"[step_8] Summary generated with subject: {step_8.get('subject', 'N/A')}")

        # ── step_9: send_email ──
        logger.info("[step_9] Sending email (mock)...")
        step_9_result = await client.call_tool("send_email", {
            "subject": step_8.get("subject", "Daily Stock Report"),
            "html_content": step_8.get("html", ""),
            "send_to": "EMAIL_PLACEHOLDER",
        })
        step_9 = json.loads(step_9_result.data) if isinstance(step_9_result.data, str) else step_9_result.data
        logger.info(f"[step_9] Email sent: {step_9['message']}")

        logger.info("=" * 60)
        logger.info("Workflow completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
