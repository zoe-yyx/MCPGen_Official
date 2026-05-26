"""
Scraper tools — replaces two n8n nodes:

  • "Scrape Reviews"      → tool_scrape_amazon_reviews  (local BeautifulSoup)
  • "Code in JavaScript"  → tool_format_reviews

No external scraper API needed — uses httpx + BeautifulSoup for local scraping.
mock_mode=True (default) returns synthetic data without any network call.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from mcp_server.tools.utils.logging_decorator import setup_logging, log_tool_call

logger = setup_logging("logs/server.log", console_output=False)

# ---------------------------------------------------------------------------
# Request headers to mimic a normal browser
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

# ---------------------------------------------------------------------------
# Mock data helpers
# ---------------------------------------------------------------------------

_MOCK_REVIEWS: list[dict[str, Any]] = [
    {"review_from": "Alice",   "rating": 5, "content": "Absolutely love this product! Works perfectly out of the box."},
    {"review_from": "Bob",     "rating": 2, "content": "Stopped working after two weeks. Very disappointed."},
    {"review_from": "Charlie", "rating": 4, "content": "Good value for the price. Delivery was fast too."},
    {"review_from": "Diana",   "rating": 1, "content": "Terrible quality. Broke on first use. Waste of money."},
    {"review_from": "Eve",     "rating": 5, "content": "Best purchase this year. Highly recommend to everyone!"},
]

_MOCK_DECODO_RESPONSE: dict[str, Any] = {
    "results": [
        {
            "content": {
                "results": {
                    "reviews": _MOCK_REVIEWS
                }
            }
        }
    ]
}


# ---------------------------------------------------------------------------
# Local scraping helper
# ---------------------------------------------------------------------------

def _parse_amazon_reviews(html: str) -> list[dict[str, Any]]:
    """Parse Amazon product page HTML and extract review data."""
    soup = BeautifulSoup(html, "html.parser")
    reviews: list[dict[str, Any]] = []

    # Amazon review blocks are typically in divs with data-hook="review"
    review_divs = soup.select('[data-hook="review"]')

    for div in review_divs:
        # Author name
        author_el = div.select_one('[data-hook="review-author"]') or div.select_one(".a-profile-name")
        author = author_el.get_text(strip=True) if author_el else "Unknown"

        # Star rating (e.g. "4.0 out of 5 stars")
        rating_el = div.select_one('[data-hook="review-star-rating"]') or div.select_one(".review-rating")
        rating = 0
        if rating_el:
            rating_text = rating_el.get_text(strip=True)
            match = re.search(r"(\d+(?:\.\d+)?)", rating_text)
            if match:
                rating = int(float(match.group(1)))

        # Review body
        body_el = div.select_one('[data-hook="review-body"]')
        content = body_el.get_text(strip=True) if body_el else ""

        if content:
            reviews.append({
                "review_from": author,
                "rating": rating,
                "content": content,
            })

    return reviews


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@log_tool_call(logger)
async def tool_scrape_amazon_reviews(
    url: str,
    mock_mode: bool = True,
) -> dict[str, Any]:
    """
    Scrape Amazon product reviews for a given product URL.

    Uses local HTTP request + BeautifulSoup parsing (no external API needed).

    Args:
        url:        Amazon product page URL.
        mock_mode:  When True return synthetic data; no network call made.

    Returns:
        Response dict with standardized structure:
        {
          "results": [{
            "content": {
              "results": {
                "reviews": [{"review_from": str, "rating": int, "content": str}, ...]
              }
            }
          }]
        }
    """
    if mock_mode:
        logger.info(f"[MOCK] scrape_amazon_reviews | url={url}")
        return _MOCK_DECODO_RESPONSE

    logger.info(f"Scraping reviews locally | url={url}")
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=_HEADERS) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    reviews = _parse_amazon_reviews(resp.text)
    logger.info(f"Scraped {len(reviews)} review(s) from page")

    if not reviews:
        logger.warning("No reviews parsed from page — Amazon may have blocked the request or page structure changed")

    return {
        "results": [
            {
                "content": {
                    "results": {
                        "reviews": reviews
                    }
                }
            }
        ]
    }


@log_tool_call(logger)
async def tool_format_reviews(
    decodo_response: str,
    source_url: str,
) -> dict[str, Any]:
    """
    Transform raw scraped JSON into clean, newline-separated review text.

    Args:
        decodo_response: JSON string of the scraper response dict.
        source_url:      Product URL, carried forward for downstream steps.

    Returns:
        {
          "reviews": str,       # multi-line "author - rating - content" blocks
          "url": str,           # product URL
          "review_count": int
        }
    """
    data: dict[str, Any] = json.loads(decodo_response) if isinstance(decodo_response, str) else decodo_response

    try:
        raw: list[dict] = data["results"][0]["content"]["results"]["reviews"]
    except (KeyError, IndexError, TypeError):
        logger.warning("Could not parse reviews; using empty list")
        raw = []

    lines = [
        f"{r.get('review_from', 'Unknown')} - {r.get('rating', 'N/A')} - {r.get('content', '')}"
        for r in raw
    ]

    return {
        "reviews": "\n\n".join(lines),
        "url": source_url,
        "review_count": len(lines),
    }
