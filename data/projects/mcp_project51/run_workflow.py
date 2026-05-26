"""
run_workflow.py — User Review Aggregation

Replicates the n8n workflow execution order:

  Schedule Trigger
       ↓
  Get row(s) in sheet   → tool_get_urls_from_csv
       ↓
  [Loop over each URL]
       ↓
  Scrape Reviews        → tool_scrape_amazon_reviews  (local BeautifulSoup)
       ↓
  Format Reviews        → tool_format_reviews
       ↓
  Sentiment Analyzer    → tool_analyze_sentiment
       ↙               ↘
Store to Sheet      Summarize Reviews
tool_store_result   tool_summarize_reviews
_to_csv                  ↓
                    Alert Group → tool_send_alert
       ↘               ↙
      [next URL in loop]

Run:
    uv run python run_workflow.py
    uv run python run_workflow.py --real-api     # use actual LLM API + live scraping
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client

from mcp_server.tools.utils.logging_decorator import setup_logging

load_dotenv()

# Workflow runner logger — console_output=True is safe here (not an MCP server)
logger = setup_logging("logs/workflow.log", console_output=True)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _build_config(mock_mode: bool) -> dict:
    return {
        "mock_mode": mock_mode,
        # LLM API (OpenAI-compatible)
        "base_url":         _env("OPENAI_BASE_URL"),
        "api_key":          _env("OPENAI_API_KEY"),
        "sentiment_model":  _env("SENTIMENT_MODEL", "gpt-5.1"),
        "summary_model":    _env("SUMMARY_MODEL",   "gpt-5.1"),
        # Telegram (optional)
        "telegram_token":   _env("TELEGRAM_BOT_TOKEN"),
        "telegram_chat_id": _env("TELEGRAM_CHAT_ID"),
        # Local storage
        "url_csv":          _env("URL_CSV_PATH", "data/urls.csv"),
        "results_csv":      _env("RESULTS_CSV_PATH", "results/outputs/review_aggregations.csv"),
    }


# ---------------------------------------------------------------------------
# Helpers for parsing tool results
# ---------------------------------------------------------------------------

def _parse(result) -> dict:
    """Extract dict from a fastmcp CallToolResult."""
    raw = result.content[0].text
    return json.loads(raw)


def _parse_list(result) -> list:
    raw = result.content[0].text
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

async def run_workflow(mock_mode: bool = True) -> None:
    cfg = _build_config(mock_mode)
    mode_label = "MOCK" if mock_mode else "REAL"
    logger.info(f"{'='*60}")
    logger.info(f"  User Review Aggregation Workflow — {mode_label} mode")
    logger.info(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*60}")

    async with Client("mcp_server/server.py") as client:

        # ------------------------------------------------------------------
        # Step 1 — Get row(s) in sheet  →  tool_get_urls_from_csv
        # ------------------------------------------------------------------
        logger.info("\n[Step 1] Loading product URLs …")
        url_result = await client.call_tool(
            "tool_get_urls_from_csv",
            {"csv_path": cfg["url_csv"], "url_column": "url"},
        )
        urls: list[str] = _parse_list(url_result)
        logger.info(f"  → {len(urls)} URL(s) loaded")

        if not urls:
            logger.warning("No URLs found — workflow complete (nothing to process).")
            return

        # ------------------------------------------------------------------
        # Step 2 — Loop over items  (n8n: splitInBatches)
        # ------------------------------------------------------------------
        metrics: list[dict] = []

        for idx, url in enumerate(urls, start=1):
            logger.info(f"\n{'─'*50}")
            logger.info(f"[URL {idx}/{len(urls)}] {url}")

            try:
                # Step 3 — Scrape Reviews  →  tool_scrape_amazon_reviews
                logger.info("  [Step 3] Scraping reviews …")
                scrape_result = await client.call_tool(
                    "tool_scrape_amazon_reviews",
                    {
                        "url": url,
                        "mock_mode": cfg["mock_mode"],
                    },
                )
                scraped_json: str = scrape_result.content[0].text

                # Step 4 — Format Reviews  →  tool_format_reviews
                logger.info("  [Step 4] Formatting reviews …")
                fmt_result = await client.call_tool(
                    "tool_format_reviews",
                    {"decodo_response": scraped_json, "source_url": url},
                )
                fmt = _parse(fmt_result)
                reviews_text: str = fmt["reviews"]
                review_count: int = fmt["review_count"]
                logger.info(f"  → {review_count} review(s) formatted")

                # Step 5 — Sentiment Analyzer  →  tool_analyze_sentiment
                logger.info("  [Step 5] Analysing sentiment …")
                sentiment_result = await client.call_tool(
                    "tool_analyze_sentiment",
                    {
                        "reviews": reviews_text,
                        "base_url":    cfg["base_url"],
                        "api_key":     cfg["api_key"],
                        "model_name":  cfg["sentiment_model"],
                        "mock_mode":   cfg["mock_mode"],
                    },
                )
                sent_data = _parse(sentiment_result)
                sentiment_category: str = sent_data["sentimentAnalysis"]["category"]
                logger.info(f"  → Sentiment: {sentiment_category}")

                # Step 6a — Store to Sheet  →  tool_store_result_to_csv
                logger.info("  [Step 6a] Storing result to CSV …")
                await client.call_tool(
                    "tool_store_result_to_csv",
                    {
                        "url":          url,
                        "sentiment":    sentiment_category,
                        "reviews_text": reviews_text,
                        "csv_path":     cfg["results_csv"],
                    },
                )

                # Step 6b — Summarize Reviews  →  tool_summarize_reviews
                logger.info("  [Step 6b] Summarizing reviews …")
                summary_result = await client.call_tool(
                    "tool_summarize_reviews",
                    {
                        "reviews":     reviews_text,
                        "base_url":    cfg["base_url"],
                        "api_key":     cfg["api_key"],
                        "model_name":  cfg["summary_model"],
                        "mock_mode":   cfg["mock_mode"],
                    },
                )
                summary_data = _parse(summary_result)
                summary_text: str = summary_data["output"]["text"]

                # Step 7 — Alert Group  →  tool_send_alert
                logger.info("  [Step 7] Sending alert …")
                alert_result = await client.call_tool(
                    "tool_send_alert",
                    {
                        "url":                  url,
                        "sentiment":            sentiment_category,
                        "summary_text":         summary_text,
                        "telegram_bot_token":   cfg["telegram_token"],
                        "telegram_chat_id":     cfg["telegram_chat_id"],
                        "alert_sentiments":     '["positive","neutral","negative"]',
                    },
                )
                alert_data = _parse(alert_result)
                logger.info(f"  → Alert sent via: {alert_data['channels']}")

                metrics.append({
                    "url": url,
                    "sentiment": sentiment_category,
                    "review_count": review_count,
                    "status": "success",
                })

            except Exception as exc:
                logger.error(f"  ✗ Failed for {url}: {type(exc).__name__}: {exc}")
                metrics.append({"url": url, "status": "error", "error": str(exc)})

        # ------------------------------------------------------------------
        # Save run metrics
        # ------------------------------------------------------------------
        metrics_path = Path("results/metrics/run_metrics.json")
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        run_summary = {
            "run_at": datetime.now().isoformat(),
            "mode": mode_label,
            "total_urls": len(urls),
            "success": sum(1 for m in metrics if m["status"] == "success"),
            "error": sum(1 for m in metrics if m["status"] == "error"),
            "details": metrics,
        }
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(run_summary, f, indent=2, ensure_ascii=False)

        logger.info(f"\n{'='*60}")
        logger.info(f"  Workflow complete.")
        logger.info(f"  Success: {run_summary['success']} / {run_summary['total_urls']}")
        logger.info(f"  Metrics: {metrics_path}")
        logger.info(f"  Results: {cfg['results_csv']}")
        logger.info(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="User Review Aggregation Workflow")
    parser.add_argument(
        "--real-api",
        action="store_true",
        help="Use real LLM API + live scraping (requires .env credentials)",
    )
    args = parser.parse_args()
    asyncio.run(run_workflow(mock_mode=not args.real_api))
