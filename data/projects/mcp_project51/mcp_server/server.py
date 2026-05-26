"""
MCP Server — User Review Aggregation

Registers all tools via @mcp.tool() and runs on stdio transport.

CRITICAL: Every logger in this file MUST be file-only (console_output=False).
Any stdout/stderr output from the server process breaks the MCP stdio protocol.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the project root is on sys.path so imports work when launched as a subprocess
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP

from mcp_server.tools.utils.logging_decorator import setup_logging
from mcp_server.tools.scraper_tools import tool_scrape_amazon_reviews, tool_format_reviews
from mcp_server.tools.ai_tools import tool_analyze_sentiment, tool_summarize_reviews
from mcp_server.tools.storage_tools import (
    tool_get_urls_from_csv,
    tool_store_result_to_csv,
    tool_send_alert,
)

# File-only logger — never touches stdio
logger = setup_logging("logs/server.log", console_output=False)
logger.info("Initializing MCP server 'UserReviewAggregation'")

mcp = FastMCP(
    name="UserReviewAggregation",
    instructions=(
        "Tools for automated Amazon review scraping, sentiment analysis, "
        "summarization, local storage, and alerting. "
        "Run in mock_mode=True to work without any external API keys."
    ),
)

# ---------------------------------------------------------------------------
# Register tools using @mcp.tool()
# Each function is a thin wrapper that delegates to the actual implementation
# so we can keep rich docstrings and type hints in the tool modules.
# ---------------------------------------------------------------------------

@mcp.tool()
async def tool_get_urls_from_csv(
    csv_path: str = "data/urls.csv",
    url_column: str = "url",
) -> list[str]:
    """
    Read product URLs from a local CSV file.

    Replaces n8n node: "Get row(s) in sheet" (Google Sheets → local CSV).

    Args:
        csv_path:   Path to the CSV file. Auto-created with sample data if missing.
        url_column: Header name of the URL column (default: "url").

    Returns:
        List of URL strings.
    """
    from mcp_server.tools.storage_tools import tool_get_urls_from_csv as _impl
    return await _impl(csv_path=csv_path, url_column=url_column)


@mcp.tool()
async def tool_scrape_amazon_reviews(
    url: str,
    mock_mode: bool = True,
) -> str:
    """
    Scrape Amazon product reviews for a given URL (local BeautifulSoup scraping).

    Args:
        url:        Amazon product page URL.
        mock_mode:  Return synthetic reviews without any network call.

    Returns:
        JSON string of the scraped response.
    """
    from mcp_server.tools.scraper_tools import tool_scrape_amazon_reviews as _impl
    result = await _impl(url=url, mock_mode=mock_mode)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def tool_format_reviews(
    decodo_response: str,
    source_url: str,
) -> str:
    """
    Transform raw scraped JSON into clean "author - rating - content" text blocks.

    Args:
        decodo_response: JSON string returned by tool_scrape_amazon_reviews.
        source_url:      Product URL, carried forward for downstream tools.

    Returns:
        JSON string: {"reviews": str, "url": str, "review_count": int}
    """
    from mcp_server.tools.scraper_tools import tool_format_reviews as _impl
    result = await _impl(decodo_response=decodo_response, source_url=source_url)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def tool_analyze_sentiment(
    reviews: str,
    base_url: str = "",
    api_key: str = "",
    model_name: str = "gpt-5.1",
    mock_mode: bool = True,
) -> str:
    """
    Classify overall sentiment of review text as positive / neutral / negative.

    Args:
        reviews:    Formatted review text (from tool_format_reviews).
        base_url:   OpenAI-compatible API base URL.
        api_key:    API key.
        model_name: Model name to use.
        mock_mode:  Heuristic result; no API call made.

    Returns:
        JSON string:
        {"sentimentAnalysis": {"category": str, "confidence": float, "reasoning": str},
         "reviews": str}
    """
    from mcp_server.tools.ai_tools import tool_analyze_sentiment as _impl
    result = await _impl(
        reviews=reviews,
        base_url=base_url,
        api_key=api_key,
        model_name=model_name,
        mock_mode=mock_mode,
    )
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def tool_summarize_reviews(
    reviews: str,
    base_url: str = "",
    api_key: str = "",
    model_name: str = "gpt-5.1",
    mock_mode: bool = True,
) -> str:
    """
    Generate a concise executive summary of customer reviews.

    Args:
        reviews:    Formatted review text (from tool_format_reviews).
        base_url:   OpenAI-compatible API base URL.
        api_key:    API key.
        model_name: Model name to use.
        mock_mode:  Return a static placeholder; no API call made.

    Returns:
        JSON string: {"output": {"text": str}}
    """
    from mcp_server.tools.ai_tools import tool_summarize_reviews as _impl
    result = await _impl(
        reviews=reviews,
        base_url=base_url,
        api_key=api_key,
        model_name=model_name,
        mock_mode=mock_mode,
    )
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def tool_store_result_to_csv(
    url: str,
    sentiment: str,
    reviews_text: str,
    csv_path: str = "results/outputs/review_aggregations.csv",
) -> str:
    """
    Append a review aggregation record to a local CSV file.

    Replaces n8n node: "Store to Sheet" (Google Sheets → local CSV).

    Args:
        url:          Product URL analysed.
        sentiment:    Detected sentiment category.
        reviews_text: Formatted review text.
        csv_path:     Destination CSV path.

    Returns:
        JSON string: {"status": str, "csv_path": str, "record": dict}
    """
    from mcp_server.tools.storage_tools import tool_store_result_to_csv as _impl
    result = await _impl(
        url=url,
        sentiment=sentiment,
        reviews_text=reviews_text,
        csv_path=csv_path,
    )
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def tool_send_alert(
    url: str,
    sentiment: str,
    summary_text: str,
    telegram_bot_token: str = "",
    telegram_chat_id: str = "",
    alert_sentiments: str = '["positive","neutral","negative"]',
) -> str:
    """
    Send a review alert to the log file and optionally to Telegram.

    Replaces n8n node: "Alert Group" (Telegram).
    Telegram credentials are optional — alert always written to log + JSONL file.

    Args:
        url:                  Product URL analysed.
        sentiment:            Detected sentiment category.
        summary_text:         Executive summary text.
        telegram_bot_token:   Telegram Bot token (optional).
        telegram_chat_id:     Target chat / group ID (optional).
        alert_sentiments:     JSON array of sentiments that trigger alerts.

    Returns:
        JSON string: {"status": str, "channels": list[str], "message": str}
    """
    from mcp_server.tools.storage_tools import tool_send_alert as _impl
    sentiments: list[str] = json.loads(alert_sentiments)
    result = await _impl(
        url=url,
        sentiment=sentiment,
        summary_text=summary_text,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        alert_sentiments=sentiments,
    )
    return json.dumps(result, ensure_ascii=False)


logger.info("All tools registered. MCP server ready.")

if __name__ == "__main__":
    logger.info("Starting MCP server on stdio transport")
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
