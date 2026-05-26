"""Tools for stock sample data, splitting, and keyword setting."""

from .utils.log_decorator import log_mcp_call

SAMPLE_STOCKS: list[dict] = [
    {"ticker": "NVDA", "name": "NVIDIA Corporation", "market_cap": "≈ $3.6T"},
    {"ticker": "MSFT", "name": "Microsoft Corporation", "market_cap": "≈ $3.6T"},
    {"ticker": "AAPL", "name": "Apple Inc.", "market_cap": "≈ $3.0T"},
    {"ticker": "AMZN", "name": "Amazon.com Inc.", "market_cap": "≈ $2.2T"},
    {"ticker": "GOOGL", "name": "Alphabet Inc.", "market_cap": "≈ $1.9T"},
    {"ticker": "META", "name": "Meta Platforms Inc.", "market_cap": "≈ $1.5T"},
    {"ticker": "BRK.B", "name": "Berkshire Hathaway Inc.", "market_cap": "≈ $1.1T"},
    {"ticker": "TSLA", "name": "Tesla Inc.", "market_cap": "≈ $830B"},
    {"ticker": "UNH", "name": "UnitedHealth Group Inc.", "market_cap": "≈ $450B"},
    {"ticker": "JNJ", "name": "Johnson & Johnson", "market_cap": "≈ $450B"},
]


@log_mcp_call("tool", "get_sample_data")
def get_sample_data() -> list[dict]:
    """Return the list of top 10 US stocks to track.

    Returns:
        List of dicts with ticker, name, market_cap.
    """
    return SAMPLE_STOCKS


@log_mcp_call("tool", "split_and_set_keywords")
def split_and_set_keywords(stocks: list[dict]) -> list[dict]:
    """Split stock array and extract ticker as keyword for scraping.

    Args:
        stocks: List of stock dicts with ticker field.

    Returns:
        List of dicts each with a 'keyword' field set to the ticker.
    """
    return [{"keyword": stock["ticker"]} for stock in stocks]
