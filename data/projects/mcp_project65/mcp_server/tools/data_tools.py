"""Data collection tools: fetch RSI, fetch price/volume, merge responses.

These mock the TwelveData API calls from the original n8n workflow.
"""

import json
import os
import random
from datetime import datetime, timezone

from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "fetch_rsi")
def fetch_rsi(symbol: str = "AAPL", interval: str = "5min", time_period: int = 14) -> str:
    """Fetch RSI indicator data for a stock symbol (mocked TwelveData API).

    Args:
        symbol: Stock ticker symbol.
        interval: Time interval for RSI calculation.
        time_period: RSI period length.

    Returns:
        JSON string with RSI data.
    """
    mock_rsi = round(random.uniform(20.0, 75.0), 4)
    result = {
        "meta": {
            "symbol": symbol,
            "interval": interval,
            "currency": "USD",
            "exchange_timezone": "America/New_York",
            "exchange": "NASDAQ",
            "type": "Common Stock",
            "indicator": {
                "name": f"RSI ({time_period})",
                "time_period": time_period,
            },
        },
        "values": [
            {
                "datetime": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "rsi": str(mock_rsi),
            }
        ],
        "status": "ok",
    }
    return json.dumps(result)


@log_mcp_call("tool", "fetch_price_volume")
def fetch_price_volume(symbol: str = "AAPL") -> str:
    """Fetch real-time price and volume data for a stock symbol (mocked TwelveData API).

    Args:
        symbol: Stock ticker symbol.

    Returns:
        JSON string with price and volume data.
    """
    base_price = 185.0
    price = round(base_price + random.uniform(-5.0, 5.0), 2)
    volume = random.randint(30_000_000, 90_000_000)
    avg_volume = random.randint(50_000_000, 70_000_000)

    result = {
        "symbol": symbol,
        "name": "Apple Inc",
        "exchange": "NASDAQ",
        "currency": "USD",
        "datetime": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "open": str(round(price - random.uniform(0, 2), 2)),
        "high": str(round(price + random.uniform(0, 3), 2)),
        "low": str(round(price - random.uniform(0, 3), 2)),
        "close": str(price),
        "volume": str(volume),
        "previous_close": str(round(price - random.uniform(-2, 2), 2)),
        "change": str(round(random.uniform(-2, 2), 2)),
        "percent_change": str(round(random.uniform(-1.5, 1.5), 4)),
        "average_volume": str(avg_volume),
        "is_market_open": False,
        "fifty_two_week": {
            "low": "140.00",
            "high": "200.00",
        },
    }
    return json.dumps(result)


@log_mcp_call("tool", "merge_api_responses")
def merge_api_responses(rsi_data: str, price_data: str) -> str:
    """Merge RSI and price/volume API responses into a single data stream.

    Args:
        rsi_data: JSON string from fetch_rsi.
        price_data: JSON string from fetch_price_volume.

    Returns:
        JSON string containing both RSI and price data as a list.
    """
    rsi = json.loads(rsi_data)
    price = json.loads(price_data)
    return json.dumps([rsi, price])
