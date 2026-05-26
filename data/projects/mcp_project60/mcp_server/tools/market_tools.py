"""Market data tools — asset config, price fetching (mock), normalization."""

from __future__ import annotations

import json
import os
import random
from datetime import datetime, timedelta

from .utils.log_decorator import log_mcp_call

# ---------------------------------------------------------------------------
# Mock market data (replaces TwelveData API)
# ---------------------------------------------------------------------------

MOCK_PRICES: dict[str, dict] = {
    "SPY": {"type": "Index", "open": 528.50, "high": 533.20, "low": 526.80, "close": 531.75},
    "QQQ": {"type": "Index", "open": 448.30, "high": 453.10, "low": 446.90, "close": 451.60},
    "DIA": {"type": "Index", "open": 394.20, "high": 397.80, "low": 393.50, "close": 396.40},
    "EUR/USD": {"type": "Forex", "open": 1.0832, "high": 1.0871, "low": 1.0815, "close": 1.0856},
    "USD/INR": {"type": "Forex", "open": 83.42, "high": 83.58, "low": 83.30, "close": 83.51},
    "GBP/USD": {"type": "Forex", "open": 1.2715, "high": 1.2768, "low": 1.2698, "close": 1.2749},
    "USD/JPY": {"type": "Forex", "open": 154.82, "high": 155.30, "low": 154.50, "close": 154.65},
    "XAU/USD": {"type": "Commodity", "open": 2338.50, "high": 2355.80, "low": 2332.10, "close": 2349.20},
    "USO": {"type": "Commodity", "open": 78.20, "high": 79.10, "low": 77.85, "close": 78.65},
}


@log_mcp_call("tool")
def set_market_assets() -> str:
    """Return configured market asset groups.

    Returns:
        JSON with Indices, Forex, and Commodities symbol lists.
    """
    return json.dumps({
        "Indices": "SPY,QQQ,DIA",
        "Forex": "EUR/USD,USD/INR,GBP/USD,USD/JPY",
        "Commodities": "XAU/USD,USO",
    })


@log_mcp_call("tool")
def split_assets_symbols(assets_json: str) -> str:
    """Split grouped asset strings into individual symbol records.

    Args:
        assets_json: JSON with keys like Indices, Forex, Commodities
                     whose values are comma-separated symbol strings.

    Returns:
        JSON list of ``{asset_class, symbol}`` dicts.
    """
    data = json.loads(assets_json)
    output: list[dict] = []
    for asset_class, symbols_str in data.items():
        for symbol in symbols_str.split(","):
            symbol = symbol.strip()
            if symbol:
                output.append({"asset_class": asset_class, "symbol": symbol})
    return json.dumps(output)


@log_mcp_call("tool")
def fetch_asset_price(symbol: str) -> str:
    """Fetch price data for a single symbol (mock TwelveData API).

    Args:
        symbol: Asset symbol (e.g. ``SPY``, ``EUR/USD``, ``XAU/USD``).

    Returns:
        JSON with ``status``, ``meta``, and ``values`` matching TwelveData format.
    """
    base = MOCK_PRICES.get(symbol)
    if not base:
        return json.dumps({
            "status": "error",
            "message": f"Symbol not found: {symbol}",
            "meta": {"symbol": symbol},
        })

    # Add small random variation to make each run slightly different
    jitter = random.uniform(-0.002, 0.002)
    today = datetime.now().strftime("%Y-%m-%d")

    return json.dumps({
        "status": "ok",
        "meta": {
            "symbol": symbol,
            "type": base["type"],
            "interval": "1day",
        },
        "values": [
            {
                "datetime": today,
                "open": str(round(base["open"] * (1 + jitter), 4)),
                "high": str(round(base["high"] * (1 + jitter), 4)),
                "low": str(round(base["low"] * (1 + jitter), 4)),
                "close": str(round(base["close"] * (1 + jitter), 4)),
            }
        ],
    })


@log_mcp_call("tool")
def validate_api_response(response_json: str) -> str:
    """Check if API response status is 'ok'.

    Args:
        response_json: JSON string of the API response.

    Returns:
        JSON with ``valid`` (bool) and original data.
    """
    data = json.loads(response_json)
    is_valid = data.get("status") == "ok"
    return json.dumps({"valid": is_valid, "data": data})


@log_mcp_call("tool")
def normalize_market_data(raw_responses_json: str) -> str:
    """Normalize raw API responses into a clean market data array.

    Args:
        raw_responses_json: JSON list of TwelveData-style responses.

    Returns:
        JSON with ``market_data`` list of normalized records.
    """
    responses = json.loads(raw_responses_json)
    result: list[dict] = []

    for resp in responses:
        data = resp.get("data", resp)
        latest = None
        if "values" in data and data["values"]:
            latest = data["values"][0]

        if not latest:
            result.append({
                "symbol": data.get("meta", {}).get("symbol", "Unknown"),
                "status": data.get("status", "error"),
                "message": data.get("message", "No data received"),
            })
            continue

        open_val = float(latest["open"])
        close_val = float(latest["close"])
        change_pct = round(((close_val - open_val) / open_val) * 100, 2)

        result.append({
            "symbol": data["meta"]["symbol"],
            "asset_type": data["meta"]["type"],
            "price": close_val,
            "open": open_val,
            "high": float(latest["high"]),
            "low": float(latest["low"]),
            "date": latest["datetime"],
            "change_percent": change_pct,
            "trend": "Bullish" if change_pct > 0 else "Bearish",
            "status": "success",
        })

    return json.dumps({"market_data": result})
