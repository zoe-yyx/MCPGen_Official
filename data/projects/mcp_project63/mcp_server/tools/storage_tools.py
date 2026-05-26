"""Tools for storing trade signals (mock PostgreSQL) and logging execution."""

import json
import os
from datetime import datetime
from .utils.log_decorator import log_mcp_call

# In-memory cumulative stats
_cumulative_stats: dict = {
    "totalSignals": 0,
    "buySignals": 0,
    "sellSignals": 0,
    "totalAlerts": 0,
    "lastSignal": None,
    "averageConfidence": 0.0,
}


@log_mcp_call("tool", "store_trade_signal")
def store_trade_signal(signal_data: dict) -> dict:
    """Mock storing trade signal in PostgreSQL (saves locally as JSON).

    Args:
        signal_data: Dict with signal details to store.

    Returns:
        Dict confirming signal was stored.
    """
    output_dir = "results/metrics"
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, "trading_signals.json")

    history: list[dict] = []
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                history = []

    record = {
        "signalId": signal_data.get("signalId"),
        "symbol": signal_data.get("symbol"),
        "action": signal_data.get("action"),
        "currentPrice": signal_data.get("currentPrice"),
        "confidence": signal_data.get("confidence"),
        "riskLevel": signal_data.get("riskLevel"),
        "alertLevel": signal_data.get("alertLevel"),
        "timestamp": signal_data.get("timestamp"),
    }
    history.append(record)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    return {"status": "stored", "saved_to": filepath, "record": record}


@log_mcp_call("tool", "route_by_action")
def route_by_action(signal_data: dict) -> dict:
    """Route signal by action type (BUY/SELL). In mock, just passes through with route label.

    Args:
        signal_data: Dict with action field.

    Returns:
        Signal data with added route field.
    """
    action = signal_data.get("action", "HOLD")
    return {**signal_data, "route": f"{action} Signal"}


@log_mcp_call("tool", "log_trade_execution")
def log_trade_execution(signal_data: dict) -> dict:
    """Log successful trade signal execution and update cumulative stats.

    Args:
        signal_data: Dict with signal and alert delivery details.

    Returns:
        Dict with execution confirmation and cumulative stats.
    """
    global _cumulative_stats

    action = signal_data.get("action", "HOLD")
    if action == "BUY":
        _cumulative_stats["buySignals"] += 1
    elif action == "SELL":
        _cumulative_stats["sellSignals"] += 1
    _cumulative_stats["totalSignals"] += 1
    _cumulative_stats["totalAlerts"] += 1
    _cumulative_stats["lastSignal"] = datetime.now().isoformat()
    prev_avg = _cumulative_stats["averageConfidence"]
    _cumulative_stats["averageConfidence"] = (prev_avg + signal_data.get("confidence", 0)) / 2

    return {
        "success": True,
        "signalId": signal_data.get("signalId"),
        "action": action,
        "symbol": signal_data.get("symbol"),
        "currentPrice": signal_data.get("currentPrice"),
        "confidence": signal_data.get("confidence"),
        "timestamp": datetime.now().isoformat(),
        "cumulativeStats": {**_cumulative_stats},
        "alertsSent": {"slack": True, "email": True, "sms": True},
    }
