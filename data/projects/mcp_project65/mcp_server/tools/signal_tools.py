"""Signal processing tools: calculate trading signals, assign priority, route by priority.

Converted from n8n Code nodes (JavaScript → Python).
"""

import json

from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "calculate_trading_signals")
def calculate_trading_signals(merged_data: str) -> str:
    """Calculate trading signals from merged RSI + price data.

    Classifies momentum (oversold/overbought), compares volume vs average,
    and determines action: PREPARE_BUY, WATCH, or WAIT.

    Args:
        merged_data: JSON string containing list of [rsi_data, price_data].

    Returns:
        JSON string with computed trading signals.
    """
    items = json.loads(merged_data)

    # Extract RSI
    rsi: float | None = None
    for item in items:
        meta = item.get("meta", {})
        indicator = meta.get("indicator", {})
        if indicator and "RSI" in indicator.get("name", ""):
            rsi = float(item["values"][0]["rsi"])
            break

    # Extract price data
    price: float | None = None
    volume: int | None = None
    avg_volume: int | None = None
    symbol: str = "AAPL"
    for item in items:
        if "symbol" in item and "close" in item:
            symbol = item["symbol"]
            price = float(item["close"])
            volume = int(item["volume"])
            avg_volume = int(item["average_volume"])
            break

    # Momentum classification
    momentum = "UNKNOWN"
    if rsi is not None:
        if rsi < 30:
            momentum = "OVERSOLD"
        elif rsi < 35:
            momentum = "NEAR_OVERSOLD"
        elif rsi < 60:
            momentum = "NEUTRAL"
        elif rsi < 70:
            momentum = "NEAR_OVERBOUGHT"
        else:
            momentum = "OVERBOUGHT"

    # Volume signal
    volume_signal = "NORMAL_VOLUME"
    if volume and avg_volume and volume > avg_volume:
        volume_signal = "HIGH_VOLUME"

    # Final action
    action = "WAIT"
    if momentum == "OVERSOLD":
        action = "PREPARE_BUY"
    elif momentum == "NEAR_OVERSOLD":
        action = "WATCH"

    result = {
        "symbol": symbol,
        "price": price,
        "rsi": rsi,
        "momentum": momentum,
        "volume": volume,
        "avgVolume": avg_volume,
        "volumeSignal": volume_signal,
        "action": action,
    }
    return json.dumps(result)


@log_mcp_call("tool", "assign_alert_priority")
def assign_alert_priority(signal_data: str) -> str:
    """Assign alert priority based on RSI and volume signal.

    - HIGH: RSI < 30 and HIGH_VOLUME → Telegram
    - MEDIUM: RSI < 40 or HIGH_VOLUME
    - LOW: otherwise

    Args:
        signal_data: JSON string with trading signal data (must include 'rsi', 'volumeSignal').

    Returns:
        JSON string with priority field added.
    """
    data = json.loads(signal_data)
    rsi = data.get("rsi", 50)
    volume_signal = data.get("volumeSignal", "NORMAL_VOLUME")

    priority = "LOW"
    if rsi < 30 and volume_signal == "HIGH_VOLUME":
        priority = "HIGH"
    elif rsi < 40 or volume_signal == "HIGH_VOLUME":
        priority = "MEDIUM"

    data["priority"] = priority
    return json.dumps(data)


@log_mcp_call("tool", "route_by_priority")
def route_by_priority(prioritized_data: str) -> str:
    """Route alert to the appropriate channel based on priority.

    HIGH priority → telegram, otherwise → slack.

    Args:
        prioritized_data: JSON string with 'priority' field.

    Returns:
        JSON string with 'route' field added ('telegram' or 'slack').
    """
    data = json.loads(prioritized_data)
    priority = data.get("priority", "LOW")
    data["route"] = "telegram" if priority == "HIGH" else "slack"
    return json.dumps(data)
