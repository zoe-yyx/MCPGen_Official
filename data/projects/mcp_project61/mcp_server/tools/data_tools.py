"""Tools for fetching and merging market data (mock Google Sheets)."""

import json
import os
from datetime import datetime
from .utils.log_decorator import log_mcp_call


# Mock data for gold prices
MOCK_GOLD_DATA: list[dict] = [
    {"Date": "March 1 2026", "Price": 2150.30},
    {"Date": "March 2 2026", "Price": 2155.10},
    {"Date": "March 3 2026", "Price": 2148.75},
    {"Date": "March 4 2026", "Price": 2162.40},
    {"Date": "March 5 2026", "Price": 2170.00},
    {"Date": "March 6 2026", "Price": 2165.50},
    {"Date": "March 7 2026", "Price": 2180.20},
    {"Date": "March 8 2026", "Price": 2175.60},
    {"Date": "March 9 2026", "Price": 2190.00},
    {"Date": "March 10 2026", "Price": 2195.80},
]

# Mock data for equity prices
MOCK_EQUITY_DATA: list[dict] = [
    {"Date": "March 1 2026", "Price": 5120.50},
    {"Date": "March 2 2026", "Price": 5135.20},
    {"Date": "March 3 2026", "Price": 5110.80},
    {"Date": "March 4 2026", "Price": 5145.60},
    {"Date": "March 5 2026", "Price": 5160.30},
    {"Date": "March 6 2026", "Price": 5155.00},
    {"Date": "March 7 2026", "Price": 5170.40},
    {"Date": "March 8 2026", "Price": 5168.90},
    {"Date": "March 9 2026", "Price": 5185.70},
    {"Date": "March 10 2026", "Price": 5200.10},
]


@log_mcp_call("tool", "set_analysis_parameters")
def set_analysis_parameters(
    start_date: str = "2026-03-01",
    end_date: str = "2026-03-10",
    threshold: float = 5.0,
) -> dict:
    """Set the analysis parameters for the performance comparison.

    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        threshold: Performance gap threshold (percentage) for alerts.

    Returns:
        Dictionary with startDate, endDate, threshold.
    """
    return {
        "startDate": start_date,
        "endDate": end_date,
        "threshold": threshold,
    }


@log_mcp_call("tool", "fetch_gold_prices")
def fetch_gold_prices() -> list[dict]:
    """Fetch gold price data from mock Google Sheets.

    Returns:
        List of dicts with Date and Price fields.
    """
    return MOCK_GOLD_DATA


@log_mcp_call("tool", "fetch_equity_prices")
def fetch_equity_prices() -> list[dict]:
    """Fetch equity price data from mock Google Sheets.

    Returns:
        List of dicts with Date and Price fields.
    """
    return MOCK_EQUITY_DATA


@log_mcp_call("tool", "merge_market_data")
def merge_market_data(
    gold_data: list[dict],
    equity_data: list[dict],
    start_date: str,
    end_date: str,
) -> list[dict]:
    """Merge gold and equity price data, filtering by date range.

    Args:
        gold_data: List of gold price records.
        equity_data: List of equity price records.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).

    Returns:
        List of merged records with date, goldPrice, equityPrice.
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    seen: set[str] = set()
    combined: list[dict] = []

    for i in range(min(len(gold_data), len(equity_data))):
        gold_row = gold_data[i]
        equity_row = equity_data[i]

        if not gold_row.get("Price") or not equity_row.get("Price"):
            continue

        clean_date = gold_row["Date"].replace(",", "").strip()
        current_dt = datetime.strptime(clean_date, "%B %d %Y")

        if clean_date in seen:
            continue
        seen.add(clean_date)

        if current_dt < start_dt or current_dt > end_dt:
            continue

        combined.append({
            "date": clean_date,
            "goldPrice": float(gold_row["Price"]),
            "equityPrice": float(equity_row["Price"]),
        })

    if not combined:
        return [{"error": "No market data found in selected date range"}]

    return combined
