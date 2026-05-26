"""Unit tests for MCP tools - direct function calls without MCP server."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.data_tools import get_sample_data, split_and_set_keywords
from mcp_server.tools.scraping_tools import (
    scrape_financial_times,
    get_scraping_progress,
    get_snapshot_data,
)
from mcp_server.tools.analysis_tools import aggregate_data
from mcp_server.tools.notification_tools import save_to_sheets, send_email


class TestDataTools(unittest.TestCase):
    def test_get_sample_data(self):
        result = get_sample_data()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 10)
        self.assertIn("ticker", result[0])
        self.assertIn("name", result[0])
        self.assertIn("market_cap", result[0])

    def test_split_and_set_keywords(self):
        stocks = get_sample_data()
        result = split_and_set_keywords(stocks)
        self.assertEqual(len(result), 10)
        self.assertIn("keyword", result[0])
        self.assertEqual(result[0]["keyword"], "NVDA")


class TestScrapingTools(unittest.TestCase):
    def setUp(self):
        stocks = get_sample_data()
        self.keywords = split_and_set_keywords(stocks)

    def test_scrape_financial_times(self):
        result = scrape_financial_times(self.keywords)
        self.assertEqual(len(result), 10)
        self.assertIn("snapshot_id", result[0])
        self.assertIn("ticker", result[0])
        self.assertTrue(result[0]["snapshot_id"].startswith("s_mock_"))

    def test_get_scraping_progress(self):
        snapshots = scrape_financial_times(self.keywords)
        result = get_scraping_progress(snapshots)
        self.assertEqual(len(result), 10)
        for item in result:
            self.assertEqual(item["status"], "ready")

    def test_get_snapshot_data(self):
        snapshots = scrape_financial_times(self.keywords)
        result = get_snapshot_data(snapshots)
        self.assertEqual(len(result), 10)
        self.assertIn("ticker", result[0])
        self.assertIn("price", result[0])
        self.assertIn("change_percent", result[0])
        self.assertIn("sentiment", result[0])
        self.assertIn("headline", result[0])
        self.assertIn("scraped_at", result[0])


class TestAnalysisTools(unittest.TestCase):
    def test_aggregate_data(self):
        items = [{"ticker": "NVDA", "price": 142.5}, {"ticker": "AAPL", "price": 198.7}]
        result = aggregate_data(items)
        self.assertIn("data", result)
        self.assertEqual(len(result["data"]), 2)


class TestNotificationTools(unittest.TestCase):
    def test_save_to_sheets(self):
        data = [{"ticker": "NVDA", "price": 142.5}]
        result = save_to_sheets(data)
        self.assertEqual(result["status"], "saved")
        self.assertEqual(result["rows"], 1)
        if os.path.exists(result["saved_to"]):
            os.remove(result["saved_to"])

    def test_send_email(self):
        result = send_email("Test Subject", "<h1>Test</h1>", "EMAIL_PLACEHOLDER")
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["to"], "EMAIL_PLACEHOLDER")
        self.assertEqual(result["subject"], "Test Subject")
        if os.path.exists(result["saved_to"]):
            os.remove(result["saved_to"])


if __name__ == "__main__":
    unittest.main()
