"""Tools for technical analysis, AI signal prediction, and signal confidence analysis."""

import json
import math
import os
import random
import time
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from .utils.log_decorator import log_mcp_call

load_dotenv()

# Mock historical prices for technical indicator calculation
# 20-day historical data with clear trends for meaningful RSI/MACD:
# bitcoin: strong consistent uptrend → expect BUY
# ethereum: strong consistent uptrend → expect BUY
# AAPL: strong uptrend → expect BUY
# GOOGL: strong consistent downtrend → expect SELL
HISTORICAL_PRICES: dict[str, list[float]] = {
    "bitcoin": [
        35000, 35500, 36200, 36800, 37500, 38200, 38900, 39500,
        40200, 41000, 41800, 42500, 43200, 44000, 44800, 45500,
        46200, 47000, 47800, 48500,
    ],
    "ethereum": [
        1950, 2000, 2050, 2100, 2150, 2200, 2250, 2300,
        2340, 2380, 2420, 2450, 2480, 2510, 2540, 2570,
        2600, 2630, 2660, 2680,
    ],
    "AAPL": [
        135, 137, 139, 141, 143, 145, 147, 148,
        149, 151, 152, 154, 155, 156, 157, 158,
        159, 160, 161, 162,
    ],
    "GOOGL": [
        120, 118, 116, 114, 112, 110, 108, 106,
        104, 102, 100, 99, 97, 96, 94, 93,
        91, 90, 89, 88,
    ],
}


def _calculate_sma(prices: list[float], period: int) -> float | None:
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def _calculate_ema(prices: list[float], period: int) -> float | None:
    if period <= 0 or len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for i in range(period, len(prices)):
        ema = prices[i] * k + ema * (1 - k)
    return ema


def _calculate_rsi(prices: list[float], period: int = 14) -> float | None:
    if len(prices) < period + 1:
        return None
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = sum(d for d in deltas[:period] if d > 0)
    losses = sum(-d for d in deltas[:period] if d < 0)
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period, len(deltas)):
        g = deltas[i] if deltas[i] > 0 else 0
        l = -deltas[i] if deltas[i] < 0 else 0
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    rs = avg_gain / (avg_loss or 1)
    return 100 - (100 / (1 + rs))


def _calculate_macd(prices: list[float]) -> dict | None:
    ema12 = _calculate_ema(prices, min(12, len(prices) - 1))
    ema26 = _calculate_ema(prices, min(26, len(prices) - 1))
    if ema12 is None or ema26 is None:
        return None
    macd_val = ema12 - ema26
    return {"macd": macd_val, "signal": macd_val * 0.7}


def _calculate_bollinger(prices: list[float], period: int = 20, std_dev: int = 2) -> dict | None:
    actual_period = min(period, len(prices))
    if actual_period < 2:
        return None
    sma = _calculate_sma(prices, actual_period)
    if sma is None:
        return None
    sl = prices[-actual_period:]
    variance = sum((p - sma) ** 2 for p in sl) / actual_period
    stdev = math.sqrt(variance)
    return {"upper": sma + stdev * std_dev, "middle": sma, "lower": sma - stdev * std_dev}


@log_mcp_call("tool", "calculate_technical_indicators")
def calculate_technical_indicators(market_item: dict) -> dict:
    """Calculate technical indicators (RSI, MACD, SMA, EMA, Bollinger) for a single asset.

    Args:
        market_item: Dict with symbol, price, change_24h, volume_24h, market_cap.

    Returns:
        Dict with original data plus technicalIndicators and trend analysis.
    """
    symbol = market_item.get("symbol", "UNKNOWN")
    current_price = market_item.get("price", 0)
    history = HISTORICAL_PRICES.get(symbol, HISTORICAL_PRICES.get(symbol.lower(), [current_price]))

    sma50 = _calculate_sma(history, min(50, len(history)))
    sma200 = _calculate_sma(history, min(200, len(history)))
    ema12 = _calculate_ema(history, min(12, len(history) - 1)) if len(history) > 1 else current_price
    rsi = _calculate_rsi(history) or 50.0
    macd = _calculate_macd(history) or {"macd": 0, "signal": 0}
    bb = _calculate_bollinger(history) or {
        "upper": current_price * 1.05,
        "middle": current_price,
        "lower": current_price * 0.95,
    }

    if sma50 is None:
        sma50 = _calculate_sma(history, max(1, len(history) - 1)) or current_price
    if sma200 is None:
        sma200 = _calculate_sma(history, max(1, len(history) - 1)) or current_price

    return {
        "symbol": symbol,
        "currentPrice": current_price,
        "priceChange24h": market_item.get("change_24h", 0),
        "volume24h": market_item.get("volume_24h", 0),
        "marketCap": market_item.get("market_cap", 0),
        "technicalIndicators": {
            "sma50": round(sma50, 2),
            "sma200": round(sma200, 2),
            "ema12": round(ema12, 2) if ema12 else None,
            "rsi": round(rsi, 2),
            "macd": round(macd["macd"], 2),
            "macdSignal": round(macd["signal"], 2),
            "bollingerUpper": round(bb["upper"], 2),
            "bollingerMiddle": round(bb["middle"], 2),
            "bollingerLower": round(bb["lower"], 2),
        },
        "trend": {
            "shortTerm": "BULLISH" if current_price > sma50 else "BEARISH",
            "longTerm": "BULLISH" if sma50 > sma200 else "BEARISH",
            "rsiStatus": "OVERBOUGHT" if rsi > 70 else ("OVERSOLD" if rsi < 30 else "NEUTRAL"),
            "macdTrend": "BULLISH" if macd["macd"] > macd["signal"] else "BEARISH",
        },
        "timestamp": datetime.now().isoformat(),
    }


@log_mcp_call("tool", "call_ai_signal_prediction")
def call_ai_signal_prediction(technical_data: dict) -> dict:
    """Use LLM to predict buy/sell/hold signal based on technical indicators.

    Args:
        technical_data: Dict with symbol, price, technicalIndicators, trend.

    Returns:
        Dict with symbol, currentPrice, signal, confidence, reasoning.
    """
    api_key = os.getenv("API_KEY", "")
    base_url = os.getenv("BASE_URL", "")
    model = os.getenv("MODEL", "gpt-5.1")

    client = OpenAI(api_key=api_key, base_url=base_url)

    system_prompt = (
        "You are a quantitative trading AI model. Analyze the technical indicators and market data, "
        "then predict a trading signal.\n\n"
        "Rules:\n"
        "- Use the exact numbers provided\n"
        "- Output ONLY valid JSON\n"
        "- signal must be one of: BUY, SELL, HOLD\n"
        "- confidence must be a float between 0.0 and 1.0\n"
        "- reasoning must be a concise explanation\n\n"
        "Output format:\n"
        '{"signal": "BUY|SELL|HOLD", "confidence": 0.XX, "reasoning": "explanation"}'
    )

    user_prompt = (
        f"Symbol: {technical_data['symbol']}\n"
        f"Current Price: {technical_data['currentPrice']}\n"
        f"24h Change: {technical_data['priceChange24h']}%\n"
        f"Volume 24h: {technical_data['volume24h']}\n\n"
        f"Technical Indicators:\n{json.dumps(technical_data['technicalIndicators'], indent=2)}\n\n"
        f"Trend Analysis:\n{json.dumps(technical_data['trend'], indent=2)}\n\n"
        "Predict the trading signal."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )

    raw = response.choices[0].message.content
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.strip().startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            cleaned = "\n".join(json_lines)
        parsed = json.loads(cleaned)
        return {
            "symbol": technical_data["symbol"],
            "currentPrice": technical_data["currentPrice"],
            "signal": parsed.get("signal", "HOLD"),
            "confidence": float(parsed.get("confidence", 0.5)),
            "reasoning": parsed.get("reasoning", "No reasoning provided"),
        }
    except (json.JSONDecodeError, Exception):
        return {
            "symbol": technical_data["symbol"],
            "currentPrice": technical_data["currentPrice"],
            "signal": "HOLD",
            "confidence": 0.5,
            "reasoning": f"Failed to parse AI response: {raw[:200]}",
        }


@log_mcp_call("tool", "analyze_signals_confidence")
def analyze_signals_confidence(ai_response: dict) -> dict:
    """Analyze AI signals, calculate confidence scores, determine action and risk.

    Args:
        ai_response: Dict with symbol, currentPrice, signal, confidence, reasoning.

    Returns:
        Dict with signalId, action, confidence, riskLevel, recommendation, validation flags.
    """
    signal = ai_response.get("signal", "HOLD")
    confidence = ai_response.get("confidence", 0.5)
    reasoning = ai_response.get("reasoning", "Insufficient data")
    current_price = ai_response.get("currentPrice", 0)

    buy_threshold = 0.65
    sell_threshold = 0.65

    action = "HOLD"
    action_confidence = confidence
    risk_level = "LOW"

    if signal == "BUY" and confidence >= buy_threshold:
        action = "BUY"
        risk_level = "LOW" if confidence > 0.85 else "MEDIUM"
    elif signal == "SELL" and confidence >= sell_threshold:
        action = "SELL"
        risk_level = "LOW" if confidence > 0.85 else "MEDIUM"

    position_size = 0 if action == "HOLD" else round(action_confidence * 100)

    alert_level = "INFO"
    if action != "HOLD" and action_confidence > 0.80:
        alert_level = "CRITICAL"
    elif action != "HOLD" and action_confidence > 0.70:
        alert_level = "HIGH"
    elif action != "HOLD":
        alert_level = "MEDIUM"

    signal_id = f"SIG-{int(time.time())}-{random.randint(10000, 99999)}"

    return {
        "signalId": signal_id,
        "symbol": ai_response.get("symbol", "UNKNOWN"),
        "currentPrice": current_price,
        "action": action,
        "confidence": round(action_confidence, 4),
        "riskLevel": risk_level,
        "positionSize": position_size,
        "alertLevel": alert_level,
        "aiReasoning": reasoning,
        "recommendation": {
            "action": action,
            "entryPrice": current_price,
            "targetPrice": current_price * 1.05 if action == "BUY" else (current_price * 0.95 if action == "SELL" else current_price),
            "stopLoss": current_price * 0.98 if action == "BUY" else (current_price * 1.02 if action == "SELL" else current_price),
            "profitTarget": current_price * 1.10 if action == "BUY" else (current_price * 0.90 if action == "SELL" else current_price),
            "timeframe": "15m-1h",
        },
        "isValidSignal": action != "HOLD",
        "shouldAlert": action != "HOLD" and action_confidence >= 0.5,
        "shouldExecute": action != "HOLD" and action_confidence >= 0.75,
        "timestamp": datetime.now().isoformat(),
    }


@log_mcp_call("tool", "validate_signal_filter")
def validate_signal_filter(signal_data: dict) -> dict | None:
    """Filter signals - only pass through those that should trigger alerts.

    Args:
        signal_data: Dict with shouldAlert flag and signal details.

    Returns:
        The signal_data if shouldAlert is True, else None.
    """
    if signal_data.get("shouldAlert", False):
        return signal_data
    return None
