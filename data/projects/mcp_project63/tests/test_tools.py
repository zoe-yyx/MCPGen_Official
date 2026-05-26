"""Unit tests for MCP tools - direct function calls without MCP server."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.data_tools import (
    fetch_crypto_prices,
    fetch_stock_prices,
    combine_market_data,
)
from mcp_server.tools.analysis_tools import (
    calculate_technical_indicators,
    analyze_signals_confidence,
    validate_signal_filter,
)
from mcp_server.tools.notification_tools import (
    generate_alert_message,
    send_slack_notification,
    send_email_alert,
    send_sms_alert,
)
from mcp_server.tools.storage_tools import (
    store_trade_signal,
    route_by_action,
    log_trade_execution,
)


class TestDataTools(unittest.TestCase):
    def test_fetch_crypto_prices(self):
        result = fetch_crypto_prices()
        self.assertEqual(len(result), 2)
        self.assertIn("symbol", result[0])
        self.assertIn("price", result[0])

    def test_fetch_stock_prices(self):
        result = fetch_stock_prices()
        self.assertEqual(len(result), 2)
        self.assertIn("symbol", result[0])

    def test_combine_market_data(self):
        crypto = fetch_crypto_prices()
        stocks = fetch_stock_prices()
        result = combine_market_data(crypto, stocks)
        self.assertEqual(len(result), 4)


class TestAnalysisTools(unittest.TestCase):
    def test_calculate_technical_indicators(self):
        item = {"symbol": "bitcoin", "price": 48500, "change_24h": 6.80, "volume_24h": 45000000000, "market_cap": 950000000000}
        result = calculate_technical_indicators(item)
        self.assertIn("technicalIndicators", result)
        self.assertIn("trend", result)
        self.assertIn("rsi", result["technicalIndicators"])
        self.assertIn("macd", result["technicalIndicators"])
        self.assertEqual(result["symbol"], "bitcoin")

    def test_calculate_technical_indicators_unknown(self):
        item = {"symbol": "UNKNOWN", "price": 100, "change_24h": 0, "volume_24h": 0, "market_cap": 0}
        result = calculate_technical_indicators(item)
        self.assertIn("technicalIndicators", result)

    def test_analyze_signals_confidence_buy(self):
        ai_resp = {"symbol": "BTC", "currentPrice": 43400, "signal": "BUY", "confidence": 0.85, "reasoning": "Strong bullish"}
        result = analyze_signals_confidence(ai_resp)
        self.assertEqual(result["action"], "BUY")
        self.assertTrue(result["shouldAlert"])
        self.assertIn("signalId", result)

    def test_analyze_signals_confidence_hold(self):
        ai_resp = {"symbol": "BTC", "currentPrice": 43400, "signal": "HOLD", "confidence": 0.5, "reasoning": "Neutral"}
        result = analyze_signals_confidence(ai_resp)
        self.assertEqual(result["action"], "HOLD")
        self.assertFalse(result["isValidSignal"])

    def test_analyze_signals_confidence_low_buy(self):
        ai_resp = {"symbol": "BTC", "currentPrice": 43400, "signal": "BUY", "confidence": 0.4, "reasoning": "Weak"}
        result = analyze_signals_confidence(ai_resp)
        self.assertEqual(result["action"], "HOLD")

    def test_validate_signal_filter_pass(self):
        signal = {"shouldAlert": True, "action": "BUY", "symbol": "BTC"}
        result = validate_signal_filter(signal)
        self.assertIsNotNone(result)

    def test_validate_signal_filter_block(self):
        signal = {"shouldAlert": False, "action": "HOLD", "symbol": "BTC"}
        result = validate_signal_filter(signal)
        self.assertIsNone(result)


class TestNotificationTools(unittest.TestCase):
    def setUp(self):
        self.signal = {
            "signalId": "SIG-TEST-001",
            "symbol": "BTC",
            "currentPrice": 43400.0,
            "action": "BUY",
            "confidence": 0.85,
            "riskLevel": "LOW",
            "positionSize": 85,
            "alertLevel": "CRITICAL",
            "aiReasoning": "Strong bullish momentum",
            "recommendation": {
                "action": "BUY",
                "entryPrice": 43400.0,
                "targetPrice": 45570.0,
                "stopLoss": 42532.0,
                "profitTarget": 47740.0,
                "timeframe": "15m-1h",
            },
            "timestamp": "2026-04-22T12:00:00",
        }

    def test_generate_alert_message(self):
        result = generate_alert_message(self.signal)
        self.assertIn("alertMessages", result)
        self.assertIn("slack", result["alertMessages"])
        self.assertIn("email", result["alertMessages"])
        self.assertIn("sms", result["alertMessages"])
        self.assertIn("BUY", result["alertMessages"]["slack"])

    def test_send_slack_notification(self):
        alert = generate_alert_message(self.signal)
        result = send_slack_notification(alert)
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["channel"], "slack")
        if os.path.exists(result["saved_to"]):
            os.remove(result["saved_to"])

    def test_send_email_alert(self):
        alert = generate_alert_message(self.signal)
        result = send_email_alert(alert)
        self.assertEqual(result["status"], "sent")
        if os.path.exists(result["saved_to"]):
            os.remove(result["saved_to"])

    def test_send_sms_alert(self):
        alert = generate_alert_message(self.signal)
        result = send_sms_alert(alert)
        self.assertEqual(result["status"], "sent")
        if os.path.exists(result["saved_to"]):
            os.remove(result["saved_to"])


class TestStorageTools(unittest.TestCase):
    def test_store_trade_signal(self):
        signal = {"signalId": "SIG-TEST", "symbol": "BTC", "action": "BUY", "currentPrice": 43400, "confidence": 0.85, "riskLevel": "LOW", "alertLevel": "CRITICAL", "timestamp": "2026-04-22T12:00:00"}
        result = store_trade_signal(signal)
        self.assertEqual(result["status"], "stored")
        if os.path.exists(result["saved_to"]):
            os.remove(result["saved_to"])

    def test_route_by_action(self):
        signal = {"action": "BUY", "symbol": "BTC"}
        result = route_by_action(signal)
        self.assertEqual(result["route"], "BUY Signal")

    def test_log_trade_execution(self):
        signal = {"signalId": "SIG-TEST", "symbol": "BTC", "action": "BUY", "currentPrice": 43400, "confidence": 0.85}
        result = log_trade_execution(signal)
        self.assertTrue(result["success"])
        self.assertIn("cumulativeStats", result)


if __name__ == "__main__":
    unittest.main()
