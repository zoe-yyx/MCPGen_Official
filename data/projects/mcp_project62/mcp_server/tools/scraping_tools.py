"""Tools for Financial Times scraping via Bright Data (mocked)."""

import random
from datetime import datetime
from .utils.log_decorator import log_mcp_call

# Mock scraped data per ticker - simulates Financial Times scraping results
MOCK_SCRAPED_DATA: dict[str, dict] = {
    "NVDA": {
        "ticker": "NVDA",
        "name": "NVIDIA Corporation",
        "price": 142.50,
        "change_percent": 3.21,
        "sentiment": "positive",
        "headline": "NVIDIA reports record data center revenue amid AI boom",
        "sector": "Technology",
    },
    "MSFT": {
        "ticker": "MSFT",
        "name": "Microsoft Corporation",
        "price": 468.30,
        "change_percent": 0.85,
        "sentiment": "positive",
        "headline": "Microsoft Azure growth accelerates on AI workloads",
        "sector": "Technology",
    },
    "AAPL": {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "price": 198.70,
        "change_percent": -0.42,
        "sentiment": "neutral",
        "headline": "Apple faces headwinds in China as competition intensifies",
        "sector": "Technology",
    },
    "AMZN": {
        "ticker": "AMZN",
        "name": "Amazon.com Inc.",
        "price": 205.60,
        "change_percent": 1.54,
        "sentiment": "positive",
        "headline": "Amazon AWS expansion fuels optimistic outlook",
        "sector": "Consumer Discretionary",
    },
    "GOOGL": {
        "ticker": "GOOGL",
        "name": "Alphabet Inc.",
        "price": 178.90,
        "change_percent": -1.12,
        "sentiment": "negative",
        "headline": "Alphabet shares dip on antitrust ruling concerns",
        "sector": "Technology",
    },
    "META": {
        "ticker": "META",
        "name": "Meta Platforms Inc.",
        "price": 625.40,
        "change_percent": 2.08,
        "sentiment": "positive",
        "headline": "Meta ad revenue surges as Reels monetization gains traction",
        "sector": "Technology",
    },
    "BRK.B": {
        "ticker": "BRK.B",
        "name": "Berkshire Hathaway Inc.",
        "price": 485.20,
        "change_percent": 0.32,
        "sentiment": "neutral",
        "headline": "Berkshire Hathaway cash pile reaches new record high",
        "sector": "Financials",
    },
    "TSLA": {
        "ticker": "TSLA",
        "name": "Tesla Inc.",
        "price": 265.80,
        "change_percent": -2.45,
        "sentiment": "negative",
        "headline": "Tesla delivery numbers miss estimates amid growing competition",
        "sector": "Consumer Discretionary",
    },
    "UNH": {
        "ticker": "UNH",
        "name": "UnitedHealth Group Inc.",
        "price": 520.10,
        "change_percent": 0.67,
        "sentiment": "neutral",
        "headline": "UnitedHealth maintains steady growth in Medicare Advantage",
        "sector": "Healthcare",
    },
    "JNJ": {
        "ticker": "JNJ",
        "name": "Johnson & Johnson",
        "price": 158.40,
        "change_percent": -0.18,
        "sentiment": "neutral",
        "headline": "J&J pharma pipeline shows promise in late-stage trials",
        "sector": "Healthcare",
    },
}


@log_mcp_call("tool", "scrape_financial_times")
def scrape_financial_times(keywords: list[dict]) -> list[dict]:
    """Mock trigger Bright Data Financial Times scraper for given keywords.

    Args:
        keywords: List of dicts with 'keyword' field (stock tickers).

    Returns:
        List of snapshot_id dicts (one per keyword batch).
    """
    snapshot_ids = []
    for kw in keywords:
        ticker = kw["keyword"]
        snapshot_id = f"s_mock_{ticker.lower()}_{random.randint(10000, 99999)}"
        snapshot_ids.append({"snapshot_id": snapshot_id, "ticker": ticker})
    return snapshot_ids


@log_mcp_call("tool", "get_scraping_progress")
def get_scraping_progress(snapshot_ids: list[dict]) -> list[dict]:
    """Mock check scraping progress - always returns 'ready'.

    Args:
        snapshot_ids: List of dicts with snapshot_id.

    Returns:
        List of dicts with snapshot_id and status='ready'.
    """
    return [
        {"snapshot_id": s["snapshot_id"], "status": "ready", "ticker": s.get("ticker", "")}
        for s in snapshot_ids
    ]


@log_mcp_call("tool", "get_snapshot_data")
def get_snapshot_data(snapshot_ids: list[dict]) -> list[dict]:
    """Mock retrieve scraped data from Bright Data snapshots.

    Args:
        snapshot_ids: List of dicts with snapshot_id and ticker.

    Returns:
        List of scraped stock data dicts.
    """
    results = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for snap in snapshot_ids:
        ticker = snap.get("ticker", "")
        if ticker in MOCK_SCRAPED_DATA:
            data = {**MOCK_SCRAPED_DATA[ticker], "scraped_at": now}
        else:
            data = {
                "ticker": ticker,
                "name": ticker,
                "price": 100.0,
                "change_percent": 0.0,
                "sentiment": "neutral",
                "headline": f"No data available for {ticker}",
                "sector": "Unknown",
                "scraped_at": now,
            }
        results.append(data)
    return results
