"""Smart Trade Alert Dispatcher Workflow.

Executes the trade alert workflow via MCP server using fastmcp Client.
Steps follow the same order as the n8n workflow:
1. Fetch RSI Indicator
2. Fetch Price & Volume Data
3. Merge API Responses
4. Calculate Trading Signals
5. Generate AI Summary
6. Assign Alert Priority
7. Route by Priority
8/9. Send to Telegram (HIGH) or Slack (LOW/MEDIUM)
"""

import asyncio
import json
import os
import sys

from fastmcp import Client

sys.path.insert(0, os.path.dirname(__file__))
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/workflow.log")


def extract_text(result) -> str:
    """Extract text content from MCP tool result."""
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return block.text
    if hasattr(result, "data"):
        return str(result.data)
    return str(result)


async def main() -> None:
    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info("Available tools:")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description}")
        logger.info("-" * 60)

        # ── Step 1: Fetch RSI Indicator ──
        logger.info("Step 1: Fetching RSI Indicator...")
        step1_result = await client.call_tool("fetch_rsi", {
            "symbol": "AAPL",
            "interval": "5min",
            "time_period": 14,
        })
        step1_data = extract_text(step1_result)
        logger.info(f"Step 1 result: {step1_data[:200]}")

        # ── Step 2: Fetch Price & Volume Data ──
        logger.info("Step 2: Fetching Price & Volume Data...")
        step2_result = await client.call_tool("fetch_price_volume", {
            "symbol": "AAPL",
        })
        step2_data = extract_text(step2_result)
        logger.info(f"Step 2 result: {step2_data[:200]}")

        # ── Step 3: Merge API Responses ──
        logger.info("Step 3: Merging API Responses...")
        step3_result = await client.call_tool("merge_api_responses", {
            "rsi_data": step1_data,
            "price_data": step2_data,
        })
        step3_data = extract_text(step3_result)
        logger.info(f"Step 3 result: {step3_data[:200]}")

        # ── Step 4: Calculate Trading Signals ──
        logger.info("Step 4: Calculating Trading Signals...")
        step4_result = await client.call_tool("calculate_trading_signals", {
            "merged_data": step3_data,
        })
        step4_data = extract_text(step4_result)
        logger.info(f"Step 4 result: {step4_data}")

        # ── Step 5: Generate AI Summary ──
        logger.info("Step 5: Generating AI Summary...")
        step5_result = await client.call_tool("generate_ai_summary", {
            "signal_data": step4_data,
        })
        step5_data = extract_text(step5_result)
        logger.info(f"Step 5 result: {step5_data[:300]}")

        # ── Step 6: Assign Alert Priority ──
        logger.info("Step 6: Assigning Alert Priority...")
        step6_result = await client.call_tool("assign_alert_priority", {
            "signal_data": step5_data,
        })
        step6_data = extract_text(step6_result)
        logger.info(f"Step 6 result: {step6_data[:300]}")

        # ── Step 7: Route by Priority ──
        logger.info("Step 7: Routing by Priority...")
        step7_result = await client.call_tool("route_by_priority", {
            "prioritized_data": step6_data,
        })
        step7_data = extract_text(step7_result)
        logger.info(f"Step 7 result: {step7_data[:300]}")

        # ── Step 8/9: Send Alert based on route ──
        routed = json.loads(step7_data)
        route = routed.get("route", "slack")

        if route == "telegram":
            # Step 8: Send to Telegram (High Priority)
            logger.info("Step 8: Sending HIGH priority alert to Telegram...")
            step8_result = await client.call_tool("send_telegram", {
                "alert_data": step7_data,
            })
            step8_data = extract_text(step8_result)
            logger.info(f"Step 8 result: {step8_data}")
        else:
            # Step 9: Send to Slack (Low/Medium Priority)
            logger.info("Step 9: Sending LOW/MEDIUM priority alert to Slack...")
            step9_result = await client.call_tool("send_slack", {
                "alert_data": step7_data,
            })
            step9_data = extract_text(step9_result)
            logger.info(f"Step 9 result: {step9_data}")

        logger.info("=" * 60)
        logger.info("Workflow completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        raise
