"""Unit tests for MCP tools — no MCP server required."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest


class _TempDirMixin:
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.environ["REPORTS_CSV"] = os.path.join(self.tmpdir, "reports.csv")
        os.environ["ERRORS_CSV"] = os.path.join(self.tmpdir, "errors.csv")
        os.environ["OUTPUT_DIR"] = os.path.join(self.tmpdir, "outputs")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestMarketTools(unittest.TestCase):

    def test_set_market_assets(self):
        from mcp_server.tools.market_tools import set_market_assets
        result = json.loads(set_market_assets())
        self.assertIn("SPY", result["Indices"])
        self.assertIn("EUR/USD", result["Forex"])
        self.assertIn("XAU/USD", result["Commodities"])

    def test_split_assets_symbols(self):
        from mcp_server.tools.market_tools import split_assets_symbols
        assets = {"Indices": "SPY,QQQ,DIA", "Forex": "EUR/USD,GBP/USD"}
        result = json.loads(split_assets_symbols(json.dumps(assets)))
        self.assertEqual(len(result), 5)
        symbols = [r["symbol"] for r in result]
        self.assertIn("SPY", symbols)
        self.assertIn("EUR/USD", symbols)

    def test_fetch_asset_price_success(self):
        from mcp_server.tools.market_tools import fetch_asset_price
        result = json.loads(fetch_asset_price("SPY"))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["meta"]["symbol"], "SPY")
        self.assertEqual(len(result["values"]), 1)

    def test_fetch_asset_price_unknown(self):
        from mcp_server.tools.market_tools import fetch_asset_price
        result = json.loads(fetch_asset_price("INVALID"))
        self.assertEqual(result["status"], "error")

    def test_validate_api_response_ok(self):
        from mcp_server.tools.market_tools import validate_api_response
        resp = {"status": "ok", "meta": {"symbol": "SPY"}, "values": []}
        result = json.loads(validate_api_response(json.dumps(resp)))
        self.assertTrue(result["valid"])

    def test_validate_api_response_error(self):
        from mcp_server.tools.market_tools import validate_api_response
        resp = {"status": "error", "message": "Rate limit"}
        result = json.loads(validate_api_response(json.dumps(resp)))
        self.assertFalse(result["valid"])

    def test_normalize_market_data(self):
        from mcp_server.tools.market_tools import normalize_market_data
        raw = [
            {
                "data": {
                    "status": "ok",
                    "meta": {"symbol": "SPY", "type": "Index"},
                    "values": [{"datetime": "2026-04-22", "open": "528.50", "high": "533.20", "low": "526.80", "close": "531.75"}],
                }
            }
        ]
        result = json.loads(normalize_market_data(json.dumps(raw)))
        md = result["market_data"]
        self.assertEqual(len(md), 1)
        self.assertEqual(md[0]["symbol"], "SPY")
        self.assertEqual(md[0]["status"], "success")
        self.assertIn("change_percent", md[0])
        self.assertIn("trend", md[0])

    def test_normalize_market_data_error(self):
        from mcp_server.tools.market_tools import normalize_market_data
        raw = [{"data": {"status": "error", "meta": {"symbol": "BAD"}, "message": "Fail"}}]
        result = json.loads(normalize_market_data(json.dumps(raw)))
        md = result["market_data"]
        self.assertEqual(md[0]["status"], "error")


class TestAITools(unittest.TestCase):

    def test_parse_ai_output(self):
        from mcp_server.tools.ai_tools import parse_ai_output
        sample_text = (
            "Market Summary:\n"
            "US equities rose broadly. SPY gained 0.62% while QQQ outperformed.\n\n"
            "Key Movers:\n"
            "- SPY: +0.62% Bullish\n"
            "- XAU/USD: +0.46% Bullish\n"
            "- USO: +0.58% Bullish\n"
            "- QQQ: +0.74% Bullish\n\n"
            "Risk Sentiment:\nRisk-on\n\n"
            "Actionable Insight:\n"
            "Watch for continuation above SPY 532 for further upside confirmation.\n\n"
            "Outlook:\n"
            "Mild bullish bias expected into next session."
        )
        result = json.loads(parse_ai_output(sample_text))
        self.assertIn("equities", result["market_summary"].lower())
        self.assertGreater(len(result["key_movers"]), 0)
        self.assertIn("Risk-on", result["risk_sentiment"])
        self.assertTrue(len(result["insight"]) > 0)
        self.assertTrue(len(result["outlook"]) > 0)

    def test_parse_ai_output_empty(self):
        from mcp_server.tools.ai_tools import parse_ai_output
        result = json.loads(parse_ai_output(""))
        self.assertEqual(result["market_summary"], "")
        self.assertEqual(result["key_movers"], [])


class TestReportTools(_TempDirMixin, unittest.TestCase):

    def test_log_daily_report(self):
        from mcp_server.tools.report_tools import log_daily_report
        report = {
            "market_summary": "Markets rose",
            "key_movers": ["SPY: +0.5%", "XAU/USD: +0.3%"],
            "risk_sentiment": "Risk-on",
            "insight": "Watch SPY 530.",
            "outlook": "Bullish bias.",
        }
        result = log_daily_report(json.dumps(report), total_assets=9)
        self.assertEqual(result, "logged")
        self.assertTrue(os.path.exists(os.environ["REPORTS_CSV"]))

    def test_send_market_email(self):
        from mcp_server.tools.report_tools import send_market_email
        report = {
            "market_summary": "Markets rose",
            "key_movers": ["SPY: +0.5%"],
            "risk_sentiment": "Risk-on",
            "insight": "Watch SPY.",
            "outlook": "Bullish.",
        }
        result = json.loads(send_market_email(json.dumps(report)))
        self.assertEqual(result["status"], "sent")
        self.assertTrue(os.path.exists(result["file_path"]))

    def test_log_api_error(self):
        from mcp_server.tools.report_tools import log_api_error
        result = json.loads(log_api_error(symbol="BAD", status="error", message="Not found"))
        self.assertEqual(result["status"], "FAILED")
        self.assertTrue(os.path.exists(os.environ["ERRORS_CSV"]))

    def test_send_error_alert(self):
        from mcp_server.tools.report_tools import send_error_alert
        result = json.loads(send_error_alert(symbol="BAD", status="error", message="Fail"))
        self.assertEqual(result["status"], "alert_sent")
        self.assertTrue(os.path.exists(result["file_path"]))


if __name__ == "__main__":
    unittest.main()
