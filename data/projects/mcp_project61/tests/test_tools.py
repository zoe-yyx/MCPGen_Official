"""Unit tests for MCP tools - direct function calls without MCP server."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.data_tools import (
    set_analysis_parameters,
    fetch_gold_prices,
    fetch_equity_prices,
    merge_market_data,
)
from mcp_server.tools.analysis_tools import (
    calculate_performance_metrics,
    parse_ai_output,
)
from mcp_server.tools.report_tools import (
    generate_chart,
    combine_ai_chart_data,
    generate_final_report,
)
from mcp_server.tools.notification_tools import (
    check_performance_gap,
    send_report_email,
    send_alert_email,
    store_report_history,
)


class TestDataTools(unittest.TestCase):
    def test_set_analysis_parameters(self):
        result = set_analysis_parameters("2026-03-01", "2026-03-10", 5.0)
        self.assertEqual(result["startDate"], "2026-03-01")
        self.assertEqual(result["endDate"], "2026-03-10")
        self.assertEqual(result["threshold"], 5.0)

    def test_fetch_gold_prices(self):
        result = fetch_gold_prices()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIn("Date", result[0])
        self.assertIn("Price", result[0])

    def test_fetch_equity_prices(self):
        result = fetch_equity_prices()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIn("Date", result[0])
        self.assertIn("Price", result[0])

    def test_merge_market_data(self):
        gold = fetch_gold_prices()
        equity = fetch_equity_prices()
        result = merge_market_data(gold, equity, "2026-03-01", "2026-03-10")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIn("date", result[0])
        self.assertIn("goldPrice", result[0])
        self.assertIn("equityPrice", result[0])

    def test_merge_market_data_empty_range(self):
        gold = fetch_gold_prices()
        equity = fetch_equity_prices()
        result = merge_market_data(gold, equity, "2020-01-01", "2020-01-02")
        self.assertEqual(len(result), 1)
        self.assertIn("error", result[0])


class TestAnalysisTools(unittest.TestCase):
    def setUp(self):
        gold = fetch_gold_prices()
        equity = fetch_equity_prices()
        self.market_data = merge_market_data(gold, equity, "2026-03-01", "2026-03-10")

    def test_calculate_performance_metrics(self):
        result = calculate_performance_metrics(self.market_data)
        self.assertIn("goldReturn", result)
        self.assertIn("equityReturn", result)
        self.assertIn("difference", result)
        self.assertIn("winner", result)
        self.assertIn(result["winner"], ["Gold", "Equity", "Equal"])

    def test_calculate_performance_metrics_error(self):
        result = calculate_performance_metrics([{"error": "No data"}])
        self.assertIn("error", result)

    def test_parse_ai_output_valid(self):
        sample = json.dumps({
            "summary": "Gold outperformed",
            "winner": "Gold",
            "reason": "Higher returns",
            "investmentAdvice": "Buy gold",
            "goldAllocation": "60",
            "equityAllocation": "40",
            "strategy": "Balanced",
        })
        result = parse_ai_output(sample)
        self.assertEqual(result["winner"], "Gold")

    def test_parse_ai_output_invalid(self):
        result = parse_ai_output("not json at all")
        self.assertIn("error", result)

    def test_parse_ai_output_markdown_block(self):
        sample = '```json\n{"winner": "Equity", "summary": "test"}\n```'
        result = parse_ai_output(sample)
        self.assertEqual(result["winner"], "Equity")


class TestReportTools(unittest.TestCase):
    def setUp(self):
        gold = fetch_gold_prices()
        equity = fetch_equity_prices()
        self.market_data = merge_market_data(gold, equity, "2026-03-01", "2026-03-10")

    def test_generate_chart(self):
        result = generate_chart(self.market_data)
        self.assertIn("chartUrl", result)
        self.assertTrue(result["chartUrl"].startswith("ENDPOINT_PLACEHOLDER"))
        self.assertIn("labels", result)
        self.assertIn("gold", result)
        self.assertIn("equity", result)

    def test_generate_chart_error(self):
        result = generate_chart([{"error": "No data"}])
        self.assertEqual(result["chartUrl"], "")

    def test_combine_ai_chart_data(self):
        ai = {"winner": "Gold", "summary": "test"}
        chart = {"chartUrl": "ENDPOINT_PLACEHOLDER"}
        result = combine_ai_chart_data(ai, chart)
        self.assertEqual(result["winner"], "Gold")
        self.assertEqual(result["chartUrl"], "ENDPOINT_PLACEHOLDER")

    def test_generate_final_report(self):
        combined = {
            "winner": "Gold",
            "summary": "Gold wins",
            "reason": "Higher returns",
            "investmentAdvice": "Buy gold",
            "goldAllocation": "60",
            "equityAllocation": "40",
            "strategy": "Balanced",
            "chartUrl": "ENDPOINT_PLACEHOLDER",
        }
        result = generate_final_report(combined)
        self.assertIn("html", result)
        self.assertIn("Gold vs Equity Report", result["html"])


class TestNotificationTools(unittest.TestCase):
    def test_check_gap_exceeds(self):
        result = check_performance_gap("6.5", 5.0)
        self.assertTrue(result["gap_exceeds_threshold"])

    def test_check_gap_within(self):
        result = check_performance_gap("3.2", 5.0)
        self.assertFalse(result["gap_exceeds_threshold"])

    def test_send_report_email(self):
        result = send_report_email("<h1>Test</h1>", "Test Report")
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["type"], "report")
        # Cleanup
        if os.path.exists(result["saved_to"]):
            os.remove(result["saved_to"])

    def test_send_alert_email(self):
        result = send_alert_email("<h1>Alert</h1>", "Alert Subject")
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["type"], "alert")
        if os.path.exists(result["saved_to"]):
            os.remove(result["saved_to"])

    def test_store_report_history(self):
        result = store_report_history("2026-04-22", "Gold", "Gold wins", "Higher returns")
        self.assertEqual(result["status"], "stored")
        # Cleanup
        if os.path.exists(result["saved_to"]):
            os.remove(result["saved_to"])


if __name__ == "__main__":
    unittest.main()
