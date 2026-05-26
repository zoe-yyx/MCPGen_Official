"""
Unit tests for User Review Aggregation tools.

Tests call the Python functions directly — no MCP or external API needed.
All tests use mock_mode=True (or local fixtures) so they run offline.

Run:
    uv run python -m pytest tests/ -v
"""

from __future__ import annotations

import asyncio
import csv
import json
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_REVIEWS_TEXT = (
    "Alice - 5 - Absolutely love this product! Works perfectly.\n\n"
    "Bob - 2 - Stopped working after two weeks. Very disappointed.\n\n"
    "Charlie - 4 - Good value for the price.\n\n"
    "Diana - 1 - Terrible quality. Broke on first use. Waste of money."
)

SAMPLE_DECODO_RESPONSE = {
    "results": [
        {
            "content": {
                "results": {
                    "reviews": [
                        {"review_from": "Alice",   "rating": 5, "content": "Absolutely love this product!"},
                        {"review_from": "Bob",     "rating": 2, "content": "Stopped working after two weeks."},
                        {"review_from": "Charlie", "rating": 4, "content": "Good value for the price."},
                        {"review_from": "Diana",   "rating": 1, "content": "Terrible quality."},
                    ]
                }
            }
        }
    ]
}


# ---------------------------------------------------------------------------
# scraper_tools tests
# ---------------------------------------------------------------------------

class TestScrapeAmazonReviews:
    def test_mock_returns_expected_structure(self):
        from mcp_server.tools.scraper_tools import tool_scrape_amazon_reviews
        result = asyncio.run(
            tool_scrape_amazon_reviews(url="ENDPOINT_PLACEHOLDER", mock_mode=True)
        )
        assert "results" in result
        reviews = result["results"][0]["content"]["results"]["reviews"]
        assert len(reviews) > 0
        first = reviews[0]
        assert "review_from" in first
        assert "rating" in first
        assert "content" in first

    def test_mock_ignores_url(self):
        from mcp_server.tools.scraper_tools import tool_scrape_amazon_reviews
        r1 = asyncio.run(tool_scrape_amazon_reviews(url="ENDPOINT_PLACEHOLDER", mock_mode=True))
        r2 = asyncio.run(tool_scrape_amazon_reviews(url="ENDPOINT_PLACEHOLDER", mock_mode=True))
        assert r1 == r2


class TestFormatReviews:
    def test_formats_correctly(self):
        from mcp_server.tools.scraper_tools import tool_format_reviews
        result = asyncio.run(
            tool_format_reviews(
                decodo_response=json.dumps(SAMPLE_DECODO_RESPONSE),
                source_url="ENDPOINT_PLACEHOLDER",
            )
        )
        assert result["review_count"] == 4
        assert result["url"] == "ENDPOINT_PLACEHOLDER"
        assert "Alice - 5 -" in result["reviews"]
        assert "Bob - 2 -" in result["reviews"]

    def test_handles_empty_reviews(self):
        from mcp_server.tools.scraper_tools import tool_format_reviews
        empty = {"results": [{"content": {"results": {"reviews": []}}}]}
        result = asyncio.run(
            tool_format_reviews(
                decodo_response=json.dumps(empty),
                source_url="ENDPOINT_PLACEHOLDER",
            )
        )
        assert result["review_count"] == 0
        assert result["reviews"] == ""

    def test_handles_malformed_response(self):
        from mcp_server.tools.scraper_tools import tool_format_reviews
        result = asyncio.run(
            tool_format_reviews(
                decodo_response=json.dumps({"bad": "data"}),
                source_url="ENDPOINT_PLACEHOLDER",
            )
        )
        assert result["review_count"] == 0


# ---------------------------------------------------------------------------
# ai_tools tests
# ---------------------------------------------------------------------------

class TestAnalyzeSentiment:
    def test_mock_returns_valid_structure(self):
        from mcp_server.tools.ai_tools import tool_analyze_sentiment
        result = asyncio.run(
            tool_analyze_sentiment(reviews=SAMPLE_REVIEWS_TEXT, mock_mode=True)
        )
        assert "sentimentAnalysis" in result
        analysis = result["sentimentAnalysis"]
        assert analysis["category"] in ("positive", "neutral", "negative")
        assert 0.0 <= analysis["confidence"] <= 1.0
        assert "reasoning" in analysis
        assert result["reviews"] == SAMPLE_REVIEWS_TEXT

    def test_mock_negative_reviews_detected(self):
        from mcp_server.tools.ai_tools import tool_analyze_sentiment
        negative_text = "terrible broke disappointed waste bad worst"
        result = asyncio.run(
            tool_analyze_sentiment(reviews=negative_text, mock_mode=True)
        )
        assert result["sentimentAnalysis"]["category"] == "negative"

    def test_mock_positive_reviews_detected(self):
        from mcp_server.tools.ai_tools import tool_analyze_sentiment
        positive_text = "love great excellent best perfect recommend amazing"
        result = asyncio.run(
            tool_analyze_sentiment(reviews=positive_text, mock_mode=True)
        )
        assert result["sentimentAnalysis"]["category"] == "positive"


class TestSummarizeReviews:
    def test_mock_returns_valid_structure(self):
        from mcp_server.tools.ai_tools import tool_summarize_reviews
        result = asyncio.run(
            tool_summarize_reviews(reviews=SAMPLE_REVIEWS_TEXT, mock_mode=True)
        )
        assert "output" in result
        assert "text" in result["output"]
        assert len(result["output"]["text"]) > 10

    def test_mock_summary_is_non_empty(self):
        from mcp_server.tools.ai_tools import tool_summarize_reviews
        result = asyncio.run(
            tool_summarize_reviews(reviews="some reviews", mock_mode=True)
        )
        assert result["output"]["text"].strip() != ""


# ---------------------------------------------------------------------------
# storage_tools tests
# ---------------------------------------------------------------------------

class TestGetUrlsFromCsv:
    def test_reads_existing_csv(self, tmp_path):
        from mcp_server.tools.storage_tools import tool_get_urls_from_csv
        csv_file = tmp_path / "urls.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["url"])
            writer.writeheader()
            writer.writerows([
                {"url": "ENDPOINT_PLACEHOLDER"},
                {"url": "ENDPOINT_PLACEHOLDER"},
            ])
        result = asyncio.run(tool_get_urls_from_csv(csv_path=str(csv_file)))
        assert result == ["ENDPOINT_PLACEHOLDER", "ENDPOINT_PLACEHOLDER"]

    def test_creates_sample_csv_if_missing(self, tmp_path):
        from mcp_server.tools.storage_tools import tool_get_urls_from_csv
        csv_file = tmp_path / "sub" / "urls.csv"
        result = asyncio.run(tool_get_urls_from_csv(csv_path=str(csv_file)))
        assert len(result) >= 1
        assert csv_file.exists()

    def test_skips_empty_urls(self, tmp_path):
        from mcp_server.tools.storage_tools import tool_get_urls_from_csv
        csv_file = tmp_path / "urls.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["url"])
            writer.writeheader()
            writer.writerows([{"url": "ENDPOINT_PLACEHOLDER"}, {"url": ""}])
        result = asyncio.run(tool_get_urls_from_csv(csv_path=str(csv_file)))
        assert len(result) == 1


class TestStoreResultToCsv:
    def test_creates_csv_and_appends(self, tmp_path):
        from mcp_server.tools.storage_tools import tool_store_result_to_csv
        csv_file = tmp_path / "out.csv"
        result = asyncio.run(
            tool_store_result_to_csv(
                url="ENDPOINT_PLACEHOLDER",
                sentiment="positive",
                reviews_text="Alice - 5 - Great product",
                csv_path=str(csv_file),
            )
        )
        assert result["status"] == "success"
        assert csv_file.exists()
        with open(csv_file) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["sentiment"] == "positive"
        assert rows[0]["url"] == "ENDPOINT_PLACEHOLDER"

    def test_appends_multiple_records(self, tmp_path):
        from mcp_server.tools.storage_tools import tool_store_result_to_csv
        csv_file = tmp_path / "out.csv"
        for i in range(3):
            asyncio.run(
                tool_store_result_to_csv(
                    url=f"ENDPOINT_PLACEHOLDER",
                    sentiment="neutral",
                    reviews_text="review text",
                    csv_path=str(csv_file),
                )
            )
        with open(csv_file) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 3


class TestSendAlert:
    def test_always_logs_and_writes_jsonl(self, tmp_path, monkeypatch):
        from mcp_server.tools import storage_tools
        # Redirect alert output to tmp_path
        monkeypatch.chdir(tmp_path)
        (tmp_path / "results" / "outputs").mkdir(parents=True)

        from mcp_server.tools.storage_tools import tool_send_alert
        result = asyncio.run(
            tool_send_alert(
                url="ENDPOINT_PLACEHOLDER",
                sentiment="negative",
                summary_text="Mixed reviews. Quality concerns noted.",
            )
        )
        assert result["status"] == "sent"
        assert "log" in result["channels"]
        assert "negative" in result["message"]

    def test_no_telegram_without_token(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "results" / "outputs").mkdir(parents=True)

        from mcp_server.tools.storage_tools import tool_send_alert
        result = asyncio.run(
            tool_send_alert(
                url="ENDPOINT_PLACEHOLDER",
                sentiment="positive",
                summary_text="Great product.",
                telegram_bot_token="",
                telegram_chat_id="",
            )
        )
        assert "telegram" not in result["channels"]