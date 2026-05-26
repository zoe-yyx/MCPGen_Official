"""
Storage & notification tools — replaces three n8n nodes:

  • "Get row(s) in sheet" → tool_get_urls_from_csv
  • "Store to Sheet"      → tool_store_result_to_csv
  • "Alert Group"         → tool_send_alert

Google Sheets and Telegram are replaced with:
  - Local CSV files  (no external account needed)
  - Console / log-file alerts  (no Telegram token needed)

If TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are set in .env,
tool_send_alert will also post to Telegram.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from mcp_server.tools.utils.logging_decorator import setup_logging, log_tool_call

logger = setup_logging("logs/server.log", console_output=False)

# Default local storage paths
DEFAULT_URL_CSV = "data/urls.csv"
DEFAULT_RESULTS_CSV = "results/outputs/review_aggregations.csv"

TELEGRAM_API_BASE = "ENDPOINT_PLACEHOLDER"


# ---------------------------------------------------------------------------
# URL source tool
# ---------------------------------------------------------------------------

@log_tool_call(logger)
async def tool_get_urls_from_csv(
    csv_path: str = DEFAULT_URL_CSV,
    url_column: str = "url",
) -> list[str]:
    """
    Read product URLs from a local CSV file.

    n8n node: "Get row(s) in sheet"
    (Original read from Google Sheets; replaced with local CSV.)

    The CSV must have a header row. The *url_column* header is used to
    locate the URL field.

    Args:
        csv_path:   Path to the CSV file containing product URLs.
        url_column: Header name of the column holding URLs.

    Returns:
        List of URL strings.

    Example CSV (data/urls.csv):
        url
        ENDPOINT_PLACEHOLDER
        ENDPOINT_PLACEHOLDER
    """
    path = Path(csv_path)
    if not path.exists():
        # Create a sample file so the workflow can run out-of-the-box
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["url"])
            writer.writeheader()
            writer.writerows([
                {"url": "ENDPOINT_PLACEHOLDER"},
                {"url": "ENDPOINT_PLACEHOLDER"},
                {"url": "ENDPOINT_PLACEHOLDER"},
            ])
        logger.info(f"Sample URL file created at {path}")

    urls: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            val = row.get(url_column, "").strip()
            if val:
                urls.append(val)

    logger.info(f"Loaded {len(urls)} URLs from {csv_path}")
    return urls


# ---------------------------------------------------------------------------
# Result storage tool
# ---------------------------------------------------------------------------

@log_tool_call(logger)
async def tool_store_result_to_csv(
    url: str,
    sentiment: str,
    reviews_text: str,
    csv_path: str = DEFAULT_RESULTS_CSV,
) -> dict[str, Any]:
    """
    Append a review aggregation record to a local CSV file.

    n8n node: "Store to Sheet"
    (Original appended to Google Sheets; replaced with local CSV append.)

    Args:
        url:          Product URL that was analysed.
        sentiment:    Detected sentiment category.
        reviews_text: Formatted review text.
        csv_path:     Destination CSV file path.

    Returns:
        {"status": "success", "csv_path": str, "record": dict}
    """
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["timestamp", "url", "sentiment", "list_review"]
    write_header = not path.exists() or path.stat().st_size == 0

    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "url": url,
        "sentiment": sentiment,
        "list_review": reviews_text.replace("\n", " | "),
    }

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(record)

    logger.info(f"Stored result | url={url} | sentiment={sentiment} | file={csv_path}")
    return {"status": "success", "csv_path": str(path), "record": record}


# ---------------------------------------------------------------------------
# Alert tool
# ---------------------------------------------------------------------------

@log_tool_call(logger)
async def tool_send_alert(
    url: str,
    sentiment: str,
    summary_text: str,
    telegram_bot_token: str = "",
    telegram_chat_id: str = "",
    alert_sentiments: list[str] | None = None,
) -> dict[str, Any]:
    """
    Send a review alert — always to the log file, optionally to Telegram.

    n8n node: "Alert Group" (Telegram)
    (Telegram is optional; alert always written to log regardless.)

    Args:
        url:                Product URL that was analysed.
        sentiment:          Detected sentiment category.
        summary_text:       Executive summary from tool_summarize_reviews.
        telegram_bot_token: Telegram Bot API token (optional).
        telegram_chat_id:   Target chat/group ID (optional).
        alert_sentiments:   Sentiments that trigger an alert (default: all).
                            E.g. ["negative"] to alert only on negative reviews.

    Returns:
        {"status": str, "channels": list[str], "message": str}
    """
    if alert_sentiments is None:
        alert_sentiments = ["positive", "neutral", "negative"]

    date_str = datetime.now().strftime("%Y-%m-%d")
    message = (
        f"🚨 ALERT WARNING 🚨\n"
        f"Date: {date_str}\n"
        f"Sentiment: {sentiment}\n\n"
        f"URL: {url}\n\n"
        f"Summary: {summary_text}"
    )

    channels: list[str] = []

    # Always log the alert
    logger.warning(f"[ALERT] sentiment={sentiment} | url={url} | summary={summary_text[:120]}…")
    channels.append("log")

    # Write alert to a dedicated alerts file
    alert_path = Path("results/outputs/alerts.jsonl")
    alert_path.parent.mkdir(parents=True, exist_ok=True)
    with open(alert_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "sentiment": sentiment,
            "url": url,
            "summary": summary_text,
        }, ensure_ascii=False) + "\n")
    channels.append("alerts.jsonl")

    # Optional: real Telegram notification
    if telegram_bot_token and telegram_chat_id and sentiment in alert_sentiments:
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.post(
                    f"{TELEGRAM_API_BASE}/bot{telegram_bot_token}/sendMessage",
                    json={"chat_id": telegram_chat_id, "text": message, "parse_mode": "HTML"},
                )
                resp.raise_for_status()
            channels.append("telegram")
            logger.info(f"Telegram alert sent to chat_id={telegram_chat_id}")
        except Exception as exc:
            logger.warning(f"Telegram send failed: {exc}")

    return {"status": "sent", "channels": channels, "message": message}