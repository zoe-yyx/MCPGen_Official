#!/usr/bin/env python
"""
run_workflow.py — Multi-Asset Daily Market Snapshot

Replicates the n8n workflow using FastMCP Client:

  Step 1  : Set market assets (Indices, Forex, Commodities)
  Step 2  : Split assets into individual symbols
  Step 3  : Fetch Indices prices (SPY, QQQ, DIA)
  Step 4  : Fetch Forex prices (EUR/USD, USD/INR, GBP/USD, USD/JPY)
  Step 5  : Fetch Commodities prices (XAU/USD, USO)
  Step 6  : Validate all API responses
  Step 7  : Handle API errors (log + alert)
  Step 8  : Normalize market data
  Step 9  : Generate AI market insights (gpt-4.1-mini)
  Step 10 : Parse AI output into structured sections
  Step 11 : Log daily report to CSV (mock Google Sheets)
  Step 12 : Send market summary email (mock Gmail)
  Step 13 : Save run metrics
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from fastmcp import Client

from mcp_server.tools.utils.log_decorator import setup_logging

load_dotenv()
logger = setup_logging("logs/workflow.log")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(result) -> dict | list:
    if not result.content:
        return []
    return json.loads(result.content[0].text)


def _parse_text(result) -> str:
    if not result.content:
        return ""
    return result.content[0].text


async def _fetch_batch(client, symbols: list[dict], label: str) -> list[dict]:
    """Fetch prices for a batch of symbols, return raw API responses."""
    responses: list[dict] = []
    for i, sym in enumerate(symbols, 1):
        symbol = sym["symbol"]
        logger.info(f"  [{i}/{len(symbols)}] Fetching {symbol} ...")
        result = await client.call_tool("fetch_asset_price", {"symbol": symbol})
        response = _parse(result)
        responses.append({"symbol": symbol, "response": response})
        logger.info(f"           -> fetched")
    logger.info(f"  -> {label}: {len(responses)} symbols fetched")
    return responses


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

async def run_workflow() -> None:
    logger.info(f"{'=' * 60}")
    logger.info("  Multi-Asset Daily Market Snapshot")
    logger.info(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 60}")

    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info(f"\nAvailable tools ({len(tools)}):")
        for t in tools:
            logger.info(f"  - {t.name}")

        # Step 1: Set market assets
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 1] Setting market assets ...")
        result = await client.call_tool("set_market_assets", {})
        assets = _parse(result)
        logger.info(f"  -> Indices: {assets['Indices']}")
        logger.info(f"  -> Forex: {assets['Forex']}")
        logger.info(f"  -> Commodities: {assets['Commodities']}")

        # Step 2: Split into individual symbols
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 2] Splitting assets into symbols ...")
        result = await client.call_tool("split_assets_symbols", {
            "assets_json": json.dumps(assets),
        })
        symbols = _parse(result)
        logger.info(f"  -> {len(symbols)} symbols to fetch")
        for s in symbols:
            logger.info(f"     {s['asset_class']}: {s['symbol']}")

        # Group symbols by asset class
        indices = [s for s in symbols if s["asset_class"] == "Indices"]
        forex = [s for s in symbols if s["asset_class"] == "Forex"]
        commodities = [s for s in symbols if s["asset_class"] == "Commodities"]

        all_fetched: list[dict] = []

        # Step 3: Fetch Indices prices
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 3] Fetching Indices prices (SPY, QQQ, DIA) ...")
        all_fetched.extend(await _fetch_batch(client, indices, "Indices"))

        # Step 4: Fetch Forex prices
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 4] Fetching Forex prices (EUR/USD, USD/INR, GBP/USD, USD/JPY) ...")
        all_fetched.extend(await _fetch_batch(client, forex, "Forex"))

        # Step 5: Fetch Commodities prices
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 5] Fetching Commodities prices (XAU/USD, USO) ...")
        all_fetched.extend(await _fetch_batch(client, commodities, "Commodities"))

        # Step 6: Validate all API responses
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 6] Validating all API responses ...")
        raw_responses: list[dict] = []
        errors: list[dict] = []

        for item in all_fetched:
            symbol = item["symbol"]
            response = item["response"]
            result = await client.call_tool("validate_api_response", {
                "response_json": json.dumps(response),
            })
            validation = _parse(result)

            if validation["valid"]:
                raw_responses.append(validation)
                logger.info(f"  {symbol}: OK")
            else:
                errors.append({"symbol": symbol, **response})
                logger.info(f"  {symbol}: ERROR - {response.get('message', 'Unknown')}")

        logger.info(f"  -> {len(raw_responses)} valid, {len(errors)} failed")

        # Step 7: Handle API errors (log + alert)
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 7] Handling API errors ...")
        if errors:
            for err in errors:
                sym = err["symbol"]
                await client.call_tool("log_api_error", {
                    "symbol": sym,
                    "status": err.get("status", "error"),
                    "message": err.get("message", "Unknown API error"),
                })
                await client.call_tool("send_error_alert", {
                    "symbol": sym,
                    "status": err.get("status", "error"),
                    "message": err.get("message", "Unknown API error"),
                })
                logger.info(f"  {sym}: error logged & alert sent")
            logger.info(f"  -> {len(errors)} errors handled")
        else:
            logger.info("  -> No errors to handle")

        if not raw_responses:
            logger.info("No valid data. Workflow aborted.")
            return

        # Step 8: Normalize market data
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 8] Normalizing market data ...")
        result = await client.call_tool("normalize_market_data", {
            "raw_responses_json": json.dumps(raw_responses),
        })
        normalized = _parse(result)
        market_data = normalized["market_data"]
        logger.info(f"  -> {len(market_data)} assets normalized")
        for md in market_data:
            if md.get("status") == "success":
                logger.info(f"     {md['symbol']}: {md['price']:.4f} ({md['change_percent']:+.2f}% {md['trend']})")

        # Step 9: Generate AI market insights
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 9] Generating AI market insights (gpt-4.1-mini) ...")
        result = await client.call_tool("generate_market_insights", {
            "market_data_json": json.dumps(market_data, indent=2),
        })
        ai_text = _parse_text(result)
        logger.info(f"  -> AI response: {len(ai_text)} chars")
        logger.info(f"  -> Preview: {ai_text[:150]}...")

        # Step 10: Parse AI output
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 10] Parsing AI output into structured report ...")
        result = await client.call_tool("parse_ai_output", {"ai_text": ai_text})
        report = _parse(result)
        logger.info(f"  -> Summary: {report.get('market_summary', '')[:80]}...")
        logger.info(f"  -> Movers: {len(report.get('key_movers', []))} items")
        logger.info(f"  -> Sentiment: {report.get('risk_sentiment', '')}")
        logger.info(f"  -> Insight: {report.get('insight', '')[:80]}...")
        logger.info(f"  -> Outlook: {report.get('outlook', '')[:80]}...")

        # Step 11: Log daily report
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 11] Logging daily report to CSV (mock Google Sheets) ...")
        result = await client.call_tool("log_daily_report", {
            "report_json": json.dumps(report),
            "total_assets": len(market_data),
        })
        logger.info(f"  -> {_parse_text(result)}")

        # Step 12: Send market email
        logger.info(f"\n{'~' * 40}")
        logger.info("[Step 12] Sending market summary email (mock Gmail) ...")
        result = await client.call_tool("send_market_email", {
            "report_json": json.dumps(report),
        })
        email_result = _parse(result)
        logger.info(f"  -> Status: {email_result['status']}")
        logger.info(f"  -> File: {email_result['file_path']}")

    # Step 13: Save run metrics
    logger.info(f"\n{'~' * 40}")
    logger.info("[Step 13] Saving run metrics ...")
    metrics = {
        "workflow": "Multi-Asset Daily Market Snapshot",
        "timestamp": datetime.now().isoformat(),
        "total_symbols": len(symbols),
        "successful_fetches": len(raw_responses),
        "failed_fetches": len(errors),
        "assets_normalized": len(market_data),
        "ai_model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "report_logged": True,
        "email_sent": True,
    }
    os.makedirs("results/metrics", exist_ok=True)
    with open("results/metrics/run_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"  -> Saved to results/metrics/run_metrics.json")

    logger.info(f"\n{'=' * 60}")
    logger.info("  Workflow complete.")
    logger.info(f"  Assets: {len(market_data)}/{len(symbols)}")
    logger.info(f"  Metrics: results/metrics/run_metrics.json")
    logger.info(f"  Email: results/outputs/market_email.txt")
    logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_workflow())
