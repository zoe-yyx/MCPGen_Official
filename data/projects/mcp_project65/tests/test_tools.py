"""Unit tests for trade alert dispatcher tools.

Tests tool functions directly without MCP, simulating n8n node calls.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.data_tools import fetch_rsi, fetch_price_volume, merge_api_responses
from mcp_server.tools.signal_tools import (
    calculate_trading_signals,
    assign_alert_priority,
    route_by_priority,
)
from mcp_server.tools.notification_tools import send_telegram, send_slack, send_error_email


class TestDataTools(unittest.TestCase):
    """Tests for data collection tools."""

    def test_fetch_rsi(self) -> None:
        result = json.loads(fetch_rsi("AAPL", "5min", 14))
        self.assertEqual(result["meta"]["symbol"], "AAPL")
        self.assertIn("RSI", result["meta"]["indicator"]["name"])
        self.assertEqual(result["status"], "ok")
        rsi_val = float(result["values"][0]["rsi"])
        self.assertGreaterEqual(rsi_val, 0)
        self.assertLessEqual(rsi_val, 100)

    def test_fetch_price_volume(self) -> None:
        result = json.loads(fetch_price_volume("AAPL"))
        self.assertEqual(result["symbol"], "AAPL")
        self.assertIn("close", result)
        self.assertIn("volume", result)
        self.assertIn("average_volume", result)

    def test_merge_api_responses(self) -> None:
        rsi_data = fetch_rsi("AAPL")
        price_data = fetch_price_volume("AAPL")
        merged = json.loads(merge_api_responses(rsi_data, price_data))
        self.assertIsInstance(merged, list)
        self.assertEqual(len(merged), 2)


class TestSignalTools(unittest.TestCase):
    """Tests for signal processing tools."""

    def _make_merged_data(self, rsi_value: float, volume: int, avg_volume: int) -> str:
        rsi_item = {
            "meta": {"indicator": {"name": "RSI (14)", "time_period": 14}},
            "values": [{"datetime": "2026-01-01 10:00:00", "rsi": str(rsi_value)}],
        }
        price_item = {
            "symbol": "AAPL",
            "close": "185.50",
            "volume": str(volume),
            "average_volume": str(avg_volume),
        }
        return json.dumps([rsi_item, price_item])

    def test_oversold_high_volume(self) -> None:
        merged = self._make_merged_data(25.0, 80_000_000, 60_000_000)
        result = json.loads(calculate_trading_signals(merged))
        self.assertEqual(result["momentum"], "OVERSOLD")
        self.assertEqual(result["volumeSignal"], "HIGH_VOLUME")
        self.assertEqual(result["action"], "PREPARE_BUY")

    def test_neutral_normal_volume(self) -> None:
        merged = self._make_merged_data(50.0, 40_000_000, 60_000_000)
        result = json.loads(calculate_trading_signals(merged))
        self.assertEqual(result["momentum"], "NEUTRAL")
        self.assertEqual(result["volumeSignal"], "NORMAL_VOLUME")
        self.assertEqual(result["action"], "WAIT")

    def test_near_oversold(self) -> None:
        merged = self._make_merged_data(32.0, 50_000_000, 60_000_000)
        result = json.loads(calculate_trading_signals(merged))
        self.assertEqual(result["momentum"], "NEAR_OVERSOLD")
        self.assertEqual(result["action"], "WATCH")

    def test_assign_priority_high(self) -> None:
        data = json.dumps({"rsi": 25, "volumeSignal": "HIGH_VOLUME", "action": "PREPARE_BUY"})
        result = json.loads(assign_alert_priority(data))
        self.assertEqual(result["priority"], "HIGH")

    def test_assign_priority_medium(self) -> None:
        data = json.dumps({"rsi": 35, "volumeSignal": "NORMAL_VOLUME", "action": "WATCH"})
        result = json.loads(assign_alert_priority(data))
        self.assertEqual(result["priority"], "MEDIUM")

    def test_assign_priority_low(self) -> None:
        data = json.dumps({"rsi": 55, "volumeSignal": "NORMAL_VOLUME", "action": "WAIT"})
        result = json.loads(assign_alert_priority(data))
        self.assertEqual(result["priority"], "LOW")

    def test_route_high_to_telegram(self) -> None:
        data = json.dumps({"priority": "HIGH", "output": "test"})
        result = json.loads(route_by_priority(data))
        self.assertEqual(result["route"], "telegram")

    def test_route_low_to_slack(self) -> None:
        data = json.dumps({"priority": "LOW", "output": "test"})
        result = json.loads(route_by_priority(data))
        self.assertEqual(result["route"], "slack")


class TestNotificationTools(unittest.TestCase):
    """Tests for notification tools (mocked file output)."""

    def test_send_telegram(self) -> None:
        data = json.dumps({"priority": "HIGH", "output": "Buy signal", "action": "PREPARE_BUY"})
        result = json.loads(send_telegram(data))
        self.assertEqual(result["status"], "sent_mock")
        self.assertEqual(result["channel"], "telegram")
        self.assertTrue(os.path.exists(result["file"]))

    def test_send_slack(self) -> None:
        data = json.dumps({"output": "Market update"})
        result = json.loads(send_slack(data))
        self.assertEqual(result["status"], "sent_mock")
        self.assertEqual(result["channel"], "slack")
        self.assertTrue(os.path.exists(result["file"]))

    def test_send_error_email(self) -> None:
        result = json.loads(send_error_email("TestNode", "Something failed"))
        self.assertEqual(result["status"], "sent_mock")
        self.assertEqual(result["channel"], "email")
        self.assertTrue(os.path.exists(result["file"]))


class TestAITools(unittest.TestCase):
    """Tests for AI summary tool (mocked OpenAI call)."""

    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_generate_ai_summary(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = "AAPL Market Update\n• RSI at 28\n• Action: PREPARE_BUY"
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        from mcp_server.tools.ai_tools import generate_ai_summary

        signal = json.dumps({
            "symbol": "AAPL", "price": 185.0, "rsi": 28.0,
            "momentum": "OVERSOLD", "volume": 80000000,
            "avgVolume": 60000000, "volumeSignal": "HIGH_VOLUME",
            "action": "PREPARE_BUY",
        })
        result = json.loads(generate_ai_summary(signal))
        self.assertIn("output", result)
        self.assertIn("AAPL", result["output"])


if __name__ == "__main__":
    unittest.main()
