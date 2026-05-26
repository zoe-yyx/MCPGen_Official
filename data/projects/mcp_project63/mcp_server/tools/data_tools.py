"""Tools for fetching and combining market data (mock CoinGecko & Alpha Vantage)."""

from .utils.log_decorator import log_mcp_call

MOCK_CRYPTO_DATA: list[dict] = [
    {
        "symbol": "bitcoin",
        "price": 48500.0,
        "change_24h": 6.80,
        "volume_24h": 45000000000,
        "market_cap": 950000000000,
    },
    {
        "symbol": "ethereum",
        "price": 2680.0,
        "change_24h": 5.20,
        "volume_24h": 22000000000,
        "market_cap": 322000000000,
    },
]

MOCK_STOCK_DATA: list[dict] = [
    {
        "symbol": "AAPL",
        "price": 162.0,
        "change_24h": 4.50,
        "volume_24h": 85000000,
        "market_cap": 2500000000000,
    },
    {
        "symbol": "GOOGL",
        "price": 88.0,
        "change_24h": -5.60,
        "volume_24h": 68000000,
        "market_cap": 1100000000000,
    },
]


@log_mcp_call("tool", "fetch_crypto_prices")
def fetch_crypto_prices() -> list[dict]:
    """Fetch cryptocurrency prices from mock CoinGecko API.

    Returns:
        List of crypto price records with symbol, price, change_24h, volume_24h, market_cap.
    """
    return MOCK_CRYPTO_DATA


@log_mcp_call("tool", "fetch_stock_prices")
def fetch_stock_prices() -> list[dict]:
    """Fetch stock prices from mock Alpha Vantage API.

    Returns:
        List of stock price records with symbol, price, change_24h, volume_24h, market_cap.
    """
    return MOCK_STOCK_DATA


@log_mcp_call("tool", "combine_market_data")
def combine_market_data(crypto_data: list[dict], stock_data: list[dict]) -> list[dict]:
    """Combine cryptocurrency and stock market data into a single list.

    Args:
        crypto_data: List of crypto price records.
        stock_data: List of stock price records.

    Returns:
        Combined list of all market data records.
    """
    return crypto_data + stock_data
