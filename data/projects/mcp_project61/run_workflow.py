"""Gold vs Equity Performance Comparison Tracker - MCP Workflow Runner.

Executes the workflow steps via fastmcp Client, matching step IDs in workflow.json.
"""

import asyncio
import json
from datetime import datetime
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

        # ── step_1: set_analysis_parameters ──
        logger.info("[step_1] Setting analysis parameters...")
        step_1_result = await client.call_tool("set_analysis_parameters", {
            "start_date": "2026-03-01",
            "end_date": "2026-03-10",
            "threshold": 5.0,
        })
        step_1 = json.loads(step_1_result.data) if isinstance(step_1_result.data, str) else step_1_result.data
        logger.info(f"[step_1] Result: {step_1}")

        # ── step_2: fetch_gold_prices ──
        logger.info("[step_2] Fetching gold prices...")
        step_2_result = await client.call_tool("fetch_gold_prices", {})
        step_2 = json.loads(step_2_result.data) if isinstance(step_2_result.data, str) else step_2_result.data
        logger.info(f"[step_2] Fetched {len(step_2)} gold records")

        # ── step_3: fetch_equity_prices ──
        logger.info("[step_3] Fetching equity prices...")
        step_3_result = await client.call_tool("fetch_equity_prices", {})
        step_3 = json.loads(step_3_result.data) if isinstance(step_3_result.data, str) else step_3_result.data
        logger.info(f"[step_3] Fetched {len(step_3)} equity records")

        # ── step_4: merge_market_data ──
        logger.info("[step_4] Merging market data...")
        step_4_result = await client.call_tool("merge_market_data", {
            "gold_data": step_2,
            "equity_data": step_3,
            "start_date": step_1["startDate"],
            "end_date": step_1["endDate"],
        })
        step_4 = json.loads(step_4_result.data) if isinstance(step_4_result.data, str) else step_4_result.data
        logger.info(f"[step_4] Merged {len(step_4)} records")

        # ── step_5: calculate_performance_metrics (parallel with step_6) ──
        logger.info("[step_5] Calculating performance metrics...")
        step_5_result = await client.call_tool("calculate_performance_metrics", {
            "market_data": step_4,
        })
        step_5 = json.loads(step_5_result.data) if isinstance(step_5_result.data, str) else step_5_result.data
        logger.info(f"[step_5] Result: {step_5}")

        # ── step_6: generate_chart (parallel with step_5 in n8n, sequential here) ──
        logger.info("[step_6] Generating chart...")
        step_6_result = await client.call_tool("generate_chart", {
            "market_data": step_4,
        })
        step_6 = json.loads(step_6_result.data) if isinstance(step_6_result.data, str) else step_6_result.data
        logger.info(f"[step_6] Chart URL generated")

        # ── step_7: generate_ai_investment_insights ──
        logger.info("[step_7] Generating AI investment insights...")
        step_7_result = await client.call_tool("generate_ai_investment_insights", {
            "metrics": step_5,
        })
        step_7 = step_7_result.data if isinstance(step_7_result.data, str) else json.dumps(step_7_result.data)
        logger.info(f"[step_7] AI raw output received")

        # ── step_8: parse_ai_output ──
        logger.info("[step_8] Parsing AI output...")
        step_8_result = await client.call_tool("parse_ai_output", {
            "raw_output": step_7,
        })
        step_8 = json.loads(step_8_result.data) if isinstance(step_8_result.data, str) else step_8_result.data
        logger.info(f"[step_8] Parsed AI output: {step_8}")

        # ── step_9: combine_ai_chart_data ──
        logger.info("[step_9] Combining AI + chart data...")
        step_9_result = await client.call_tool("combine_ai_chart_data", {
            "ai_data": step_8,
            "chart_data": step_6,
        })
        step_9 = json.loads(step_9_result.data) if isinstance(step_9_result.data, str) else step_9_result.data
        logger.info(f"[step_9] Data combined")

        # ── step_10: generate_final_report ──
        logger.info("[step_10] Generating final HTML report...")
        step_10_result = await client.call_tool("generate_final_report", {
            "combined_data": step_9,
        })
        step_10 = json.loads(step_10_result.data) if isinstance(step_10_result.data, str) else step_10_result.data
        logger.info(f"[step_10] HTML report generated")

        # ── step_11: check_performance_gap ──
        logger.info("[step_11] Checking performance gap...")
        step_11_result = await client.call_tool("check_performance_gap", {
            "difference": step_5["difference"],
            "threshold": step_1["threshold"],
        })
        step_11 = json.loads(step_11_result.data) if isinstance(step_11_result.data, str) else step_11_result.data
        logger.info(f"[step_11] Gap exceeds threshold: {step_11['gap_exceeds_threshold']}")

        # ── step_12 / step_13: conditional email ──
        if not step_11["gap_exceeds_threshold"]:
            # step_12: send_report_email (gap within threshold)
            logger.info("[step_12] Sending standard report email...")
            step_12_result = await client.call_tool("send_report_email", {
                "html_content": step_10["html"],
                "subject": f"Gold vs Equity Report ({datetime.now().isoformat()})",
            })
            step_12 = json.loads(step_12_result.data) if isinstance(step_12_result.data, str) else step_12_result.data
            logger.info(f"[step_12] Report email: {step_12}")
        else:
            # step_13: send_alert_email (gap exceeds threshold)
            logger.info("[step_13] Sending alert email...")
            step_13_result = await client.call_tool("send_alert_email", {
                "html_content": step_10["html"],
                "subject": "ALERT: Significant Performance Gap",
            })
            step_13 = json.loads(step_13_result.data) if isinstance(step_13_result.data, str) else step_13_result.data
            logger.info(f"[step_13] Alert email: {step_13}")

        # ── step_14: store_report_history ──
        logger.info("[step_14] Storing report history...")
        step_14_result = await client.call_tool("store_report_history", {
            "date": datetime.now().isoformat(),
            "winner": step_8.get("winner", "N/A"),
            "summary": step_8.get("summary", "N/A"),
            "report": step_8.get("reason", "N/A"),
        })
        step_14 = json.loads(step_14_result.data) if isinstance(step_14_result.data, str) else step_14_result.data
        logger.info(f"[step_14] History stored: {step_14}")

        logger.info("=" * 60)
        logger.info("Workflow completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
