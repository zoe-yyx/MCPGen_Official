"""AI Trading Alert Bot - MCP Workflow Runner.

Executes the workflow steps via fastmcp Client, matching step IDs in workflow.json.
Processes each asset through the full pipeline: fetch → analyze → AI predict → alert.
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

        # ── step_1: fetch_crypto_prices ──
        logger.info("[step_1] Fetching cryptocurrency prices...")
        step_1_result = await client.call_tool("fetch_crypto_prices", {})
        step_1 = json.loads(step_1_result.data) if isinstance(step_1_result.data, str) else step_1_result.data
        logger.info(f"[step_1] Got {len(step_1)} crypto records")

        # ── step_2: fetch_stock_prices ──
        logger.info("[step_2] Fetching stock prices...")
        step_2_result = await client.call_tool("fetch_stock_prices", {})
        step_2 = json.loads(step_2_result.data) if isinstance(step_2_result.data, str) else step_2_result.data
        logger.info(f"[step_2] Got {len(step_2)} stock records")

        # ── step_3: combine_market_data ──
        logger.info("[step_3] Combining market data...")
        step_3_result = await client.call_tool("combine_market_data", {
            "crypto_data": step_1,
            "stock_data": step_2,
        })
        step_3 = json.loads(step_3_result.data) if isinstance(step_3_result.data, str) else step_3_result.data
        logger.info(f"[step_3] Combined {len(step_3)} assets")

        # Process each asset through the pipeline
        for asset in step_3:
            symbol = asset.get("symbol", "UNKNOWN")
            logger.info(f"\n{'='*40} Processing {symbol} {'='*40}")

            # ── step_4: calculate_technical_indicators ──
            logger.info(f"[step_4] Calculating technical indicators for {symbol}...")
            step_4_result = await client.call_tool("calculate_technical_indicators", {
                "market_item": asset,
            })
            step_4 = json.loads(step_4_result.data) if isinstance(step_4_result.data, str) else step_4_result.data
            logger.info(f"[step_4] Trend: {step_4.get('trend', {})}")

            # ── step_5: call_ai_signal_prediction ──
            logger.info(f"[step_5] Calling AI signal prediction for {symbol}...")
            step_5_result = await client.call_tool("call_ai_signal_prediction", {
                "technical_data": step_4,
            })
            step_5 = json.loads(step_5_result.data) if isinstance(step_5_result.data, str) else step_5_result.data
            logger.info(f"[step_5] AI signal: {step_5.get('signal')} confidence: {step_5.get('confidence')}")

            # ── step_6: analyze_signals_confidence ──
            logger.info(f"[step_6] Analyzing signal confidence for {symbol}...")
            step_6_result = await client.call_tool("analyze_signals_confidence", {
                "ai_response": step_5,
            })
            step_6 = json.loads(step_6_result.data) if isinstance(step_6_result.data, str) else step_6_result.data
            logger.info(f"[step_6] Action: {step_6.get('action')} Alert: {step_6.get('alertLevel')}")

            # ── step_7: validate_signal_filter ──
            logger.info(f"[step_7] Validating signal for {symbol}...")
            step_7_result = await client.call_tool("validate_signal_filter", {
                "signal_data": step_6,
            })
            step_7_raw = step_7_result.data
            if isinstance(step_7_raw, str):
                step_7 = json.loads(step_7_raw) if step_7_raw.strip() != "null" else None
            else:
                step_7 = step_7_raw

            if step_7 is None:
                logger.info(f"[step_7] Signal filtered out for {symbol} (HOLD / low confidence)")
                continue

            logger.info(f"[step_7] Signal passed filter for {symbol}")

            # ── step_8: store_trade_signal ──
            logger.info(f"[step_8] Storing trade signal for {symbol}...")
            step_8_result = await client.call_tool("store_trade_signal", {
                "signal_data": step_7,
            })
            step_8 = json.loads(step_8_result.data) if isinstance(step_8_result.data, str) else step_8_result.data
            logger.info(f"[step_8] Signal stored: {step_8.get('status')}")

            # ── step_9: route_by_action ──
            logger.info(f"[step_9] Routing by action for {symbol}...")
            step_9_result = await client.call_tool("route_by_action", {
                "signal_data": step_7,
            })
            step_9 = json.loads(step_9_result.data) if isinstance(step_9_result.data, str) else step_9_result.data
            logger.info(f"[step_9] Route: {step_9.get('route')}")

            # ── step_10: generate_alert_message ──
            logger.info(f"[step_10] Generating alert messages for {symbol}...")
            step_10_result = await client.call_tool("generate_alert_message", {
                "signal": step_9,
            })
            step_10 = json.loads(step_10_result.data) if isinstance(step_10_result.data, str) else step_10_result.data
            logger.info(f"[step_10] Alert messages generated")

            # ── step_11: send_slack_notification ──
            logger.info(f"[step_11] Sending Slack notification for {symbol}...")
            step_11_result = await client.call_tool("send_slack_notification", {
                "alert_data": step_10,
            })
            step_11 = json.loads(step_11_result.data) if isinstance(step_11_result.data, str) else step_11_result.data
            logger.info(f"[step_11] Slack: {step_11.get('status')}")

            # ── step_12: send_email_alert ──
            logger.info(f"[step_12] Sending email alert for {symbol}...")
            step_12_result = await client.call_tool("send_email_alert", {
                "alert_data": step_10,
            })
            step_12 = json.loads(step_12_result.data) if isinstance(step_12_result.data, str) else step_12_result.data
            logger.info(f"[step_12] Email: {step_12.get('status')}")

            # ── step_13: send_sms_alert ──
            logger.info(f"[step_13] Sending SMS alert for {symbol}...")
            step_13_result = await client.call_tool("send_sms_alert", {
                "alert_data": step_10,
            })
            step_13 = json.loads(step_13_result.data) if isinstance(step_13_result.data, str) else step_13_result.data
            logger.info(f"[step_13] SMS: {step_13.get('status')}")

            # ── step_14: log_trade_execution ──
            logger.info(f"[step_14] Logging trade execution for {symbol}...")
            step_14_result = await client.call_tool("log_trade_execution", {
                "signal_data": step_10,
            })
            step_14 = json.loads(step_14_result.data) if isinstance(step_14_result.data, str) else step_14_result.data
            logger.info(f"[step_14] Logged: {step_14}")

        logger.info("\n" + "=" * 60)
        logger.info("Workflow completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
