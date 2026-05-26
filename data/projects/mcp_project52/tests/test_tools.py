"""
Unit tests for all MCP tool functions.

These tests call tool functions directly (no MCP client / server required).
External API calls are mocked so the test suite runs offline.

Run with:
    uv run pytest tests/ -v
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


# ── Processing tools ──────────────────────────────────────────────────────────

class TestProcessPubdate(unittest.TestCase):
    def test_iso_passthrough(self):
        from mcp_server.tools.processing_tools import tool_process_pubdate

        entries = [{"pubDate": "2025-04-10T08:00:00+00:00", "title": "A"}]
        result = tool_process_pubdate(entries)
        self.assertEqual(len(result), 1)
        self.assertIn("2025-04-10", result[0]["pubDate"])

    def test_rfc2822_conversion(self):
        from mcp_server.tools.processing_tools import tool_process_pubdate

        entries = [{"pubDate": "Thu, 10 Apr 2025 08:00:00 +0000", "title": "B"}]
        result = tool_process_pubdate(entries)
        self.assertIn("2025-04-10", result[0]["pubDate"])

    def test_empty_pubdate(self):
        from mcp_server.tools.processing_tools import tool_process_pubdate

        entries = [{"pubDate": "", "title": "C"}]
        result = tool_process_pubdate(entries)
        self.assertEqual(result[0]["pubDate"], "")


class TestFilterByDate(unittest.TestCase):
    def _make_entry(self, days_ago: int) -> dict:
        dt = datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
        return {"pubDate": dt.isoformat(), "link": f"ENDPOINT_PLACEHOLDER"}

    def test_keeps_recent(self):
        from mcp_server.tools.processing_tools import tool_filter_by_date

        entries = [self._make_entry(5)]
        result = tool_filter_by_date(entries, days_back=10)
        self.assertEqual(len(result), 1)

    def test_drops_old(self):
        from mcp_server.tools.processing_tools import tool_filter_by_date

        entries = [self._make_entry(15)]
        result = tool_filter_by_date(entries, days_back=10)
        self.assertEqual(len(result), 0)

    def test_mixed(self):
        from mcp_server.tools.processing_tools import tool_filter_by_date

        entries = [self._make_entry(3), self._make_entry(11)]
        result = tool_filter_by_date(entries, days_back=10)
        self.assertEqual(len(result), 1)


class TestFilterUniqueLinks(unittest.TestCase):
    def test_keeps_unique(self):
        from mcp_server.tools.processing_tools import tool_filter_unique_links

        entries = [
            {"link": "ENDPOINT_PLACEHOLDER", "pubDate": "2025-04-10T00:00:00+00:00"},
            {"link": "ENDPOINT_PLACEHOLDER", "pubDate": "2025-04-11T00:00:00+00:00"},
            {"link": "ENDPOINT_PLACEHOLDER", "pubDate": "2025-04-10T00:00:00+00:00"},  # duplicate
        ]
        result = tool_filter_unique_links(entries)
        links = [e["link"] for e in result]
        self.assertIn("ENDPOINT_PLACEHOLDER", links)
        self.assertNotIn("ENDPOINT_PLACEHOLDER", links)

    def test_all_unique(self):
        from mcp_server.tools.processing_tools import tool_filter_unique_links

        entries = [
            {"link": "ENDPOINT_PLACEHOLDER"},
            {"link": "ENDPOINT_PLACEHOLDER"},
        ]
        result = tool_filter_unique_links(entries)
        self.assertEqual(len(result), 2)


class TestExtractPubdateLink(unittest.TestCase):
    def test_projection(self):
        from mcp_server.tools.processing_tools import tool_extract_pubdate_link

        entries = [
            {"pubDate": "2025-04-10T00:00:00+00:00", "link": "ENDPOINT_PLACEHOLDER", "title": "Extra"},
        ]
        result = tool_extract_pubdate_link(entries)
        self.assertEqual(set(result[0].keys()), {"pubDate", "link"})


class TestCleanHtmlContent(unittest.TestCase):
    def test_strips_tags(self):
        from mcp_server.tools.processing_tools import tool_clean_html_content

        entries = [{"content:encoded": "<p>Hello <b>World</b></p>", "link": "x"}]
        result = tool_clean_html_content(entries)
        self.assertIn("Hello", result[0]["cleanedContent"])
        self.assertNotIn("<p>", result[0]["cleanedContent"])

    def test_extracts_meta_description(self):
        from mcp_server.tools.processing_tools import tool_clean_html_content

        html = '<meta name="description" content="This is the description">'
        entries = [{"content:encoded": html, "link": "x"}]
        result = tool_clean_html_content(entries)
        self.assertEqual(result[0]["cleanedContent"], "This is the description")

    def test_empty_content(self):
        from mcp_server.tools.processing_tools import tool_clean_html_content

        entries = [{"content:encoded": "", "link": "x"}]
        result = tool_clean_html_content(entries)
        self.assertEqual(result[0]["cleanedContent"], "No content extracted")

    def test_removes_scripts(self):
        from mcp_server.tools.processing_tools import tool_clean_html_content

        html = "<script>var x = 1;</script><p>Article body</p>"
        entries = [{"content:encoded": html, "link": "x"}]
        result = tool_clean_html_content(entries)
        self.assertNotIn("var x", result[0]["cleanedContent"])
        self.assertIn("Article body", result[0]["cleanedContent"])


class TestRestoreFullData(unittest.TestCase):
    def test_restores_duplicates(self):
        from mcp_server.tools.processing_tools import tool_restore_full_data

        full_entries = [
            {"link": "ENDPOINT_PLACEHOLDER", "title": "Full A", "content:encoded": "<p>Rich content</p>"},
            {"link": "ENDPOINT_PLACEHOLDER", "title": "Full B", "content:encoded": "<p>B content</p>"},
        ]
        # merged_entries: link A appears twice (once from initial_links, once from rss)
        merged_entries = [
            {"link": "ENDPOINT_PLACEHOLDER", "pubDate": "2025-04-10"},
            {"link": "ENDPOINT_PLACEHOLDER", "pubDate": "2025-04-10"},  # duplicate → candidate
        ]
        result = tool_restore_full_data(merged_entries, full_entries)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Full A")


# ── RSS tools ──────────────────────────────────────────────────────────────────

class TestRssRead(unittest.TestCase):
    @patch("feedparser.parse")
    def test_parse_entries(self, mock_parse: MagicMock):
        from mcp_server.tools.rss_tools import tool_rss_read

        mock_entry = MagicMock()
        mock_entry.title = "Test Title"
        mock_entry.link = "ENDPOINT_PLACEHOLDER"
        mock_entry.author = "Author"
        mock_entry.summary = "<p>Summary text</p>"
        mock_entry.published_parsed = (2025, 4, 10, 8, 0, 0, 3, 100, 0)
        mock_entry.content = [{"value": "<p>Full content</p>"}]

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]
        mock_parse.return_value = mock_feed

        result = tool_rss_read("ENDPOINT_PLACEHOLDER")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Test Title")
        self.assertEqual(result[0]["link"], "ENDPOINT_PLACEHOLDER")
        self.assertIn("2025-04-10", result[0]["pubDate"])

    @patch("feedparser.parse")
    def test_empty_feed(self, mock_parse: MagicMock):
        from mcp_server.tools.rss_tools import tool_rss_read

        mock_feed = MagicMock()
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        result = tool_rss_read("ENDPOINT_PLACEHOLDER")
        self.assertEqual(result, [])


# ── AI tools ───────────────────────────────────────────────────────────────────

class TestClassifyRelevance(unittest.TestCase):
    def test_mock_mode(self):
        from mcp_server.tools.ai_tools import tool_classify_relevance

        result = tool_classify_relevance(
            title="AI 读书笔记", cleaned_content="关于 AI 的内容", use_mock=True
        )
        self.assertEqual(result["category"], "relevant")
        self.assertTrue(result["kept"])

    @patch("mcp_server.tools.ai_tools._get_client")
    def test_relevant_response(self, mock_client_factory: MagicMock):
        from mcp_server.tools.ai_tools import tool_classify_relevance

        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = '{"category": "relevant"}'
        mock_client_factory.return_value.chat.completions.create.return_value = mock_completion

        result = tool_classify_relevance(
            title="AI 文章", cleaned_content="内容", use_mock=False
        )
        self.assertEqual(result["category"], "relevant")
        self.assertTrue(result["kept"])

    @patch("mcp_server.tools.ai_tools._get_client")
    def test_not_relevant_response(self, mock_client_factory: MagicMock):
        from mcp_server.tools.ai_tools import tool_classify_relevance

        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = '{"category": "not_relevant"}'
        mock_client_factory.return_value.chat.completions.create.return_value = mock_completion

        result = tool_classify_relevance(
            title="招生通知", cleaned_content="招生信息", use_mock=False
        )
        self.assertFalse(result["kept"])


class TestSummarizeArticle(unittest.TestCase):
    def test_mock_mode(self):
        from mcp_server.tools.ai_tools import tool_summarize_article

        result = tool_summarize_article(
            cleaned_content="内容",
            article_url="ENDPOINT_PLACEHOLDER",
            title="测试文章",
            use_mock=True,
        )
        self.assertIn("text", result)
        self.assertIn("ENDPOINT_PLACEHOLDER", result["text"])

    @patch("mcp_server.tools.ai_tools._get_client")
    def test_real_call(self, mock_client_factory: MagicMock):
        from mcp_server.tools.ai_tools import tool_summarize_article

        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "# 摘要\n这是一篇关于 AI 的文章。"
        mock_client_factory.return_value.chat.completions.create.return_value = mock_completion

        result = tool_summarize_article(
            cleaned_content="AI 相关内容",
            article_url="ENDPOINT_PLACEHOLDER",
            title="AI 文章",
            use_mock=False,
        )
        self.assertIn("摘要", result["text"])


# ── Notion tools ───────────────────────────────────────────────────────────────

class TestCreateNotionPage(unittest.TestCase):
    def test_mock_mode(self):
        from mcp_server.tools.notion_tools import tool_create_notion_page

        result = tool_create_notion_page(
            article_url="ENDPOINT_PLACEHOLDER",
            summary="测试摘要",
            fetched_at="2025-04-10T08:00:00+00:00",
            use_mock=True,
        )
        self.assertIn("page_id", result)
        self.assertEqual(result["page_id"], "mock-page-id-0000")

    @patch("mcp_server.tools.notion_tools._get_client")
    def test_real_call(self, mock_client_factory: MagicMock):
        from mcp_server.tools.notion_tools import tool_create_notion_page

        mock_response = {"id": "abc-123", "url": "ENDPOINT_PLACEHOLDER"}
        mock_client_factory.return_value.pages.create.return_value = mock_response

        result = tool_create_notion_page(
            article_url="ENDPOINT_PLACEHOLDER",
            summary="摘要内容",
            fetched_at="2025-04-10T08:00:00+00:00",
            use_mock=False,
        )
        self.assertEqual(result["page_id"], "abc-123")


# ── Google Sheets tools (mock only – avoid real API calls) ────────────────────

class TestSheetsMockCoverage(unittest.TestCase):
    """Smoke-test that tool functions are importable and callable in isolation."""

    def test_save_relevant_article_mock(self):
        """Verify that save_relevant_article calls the Sheets API correctly."""
        from mcp_server.tools.sheets_tools import tool_save_relevant_article

        with patch("mcp_server.tools.sheets_tools._get_sheets_service") as mock_svc:
            mock_sheets = MagicMock()
            mock_svc.return_value = mock_sheets
            mock_sheets.spreadsheets.return_value.values.return_value.append.return_value.execute.return_value = {
                "updates": {"updatedRange": "Relevant Articles!A2"}
            }

            result = tool_save_relevant_article(
                article_url="ENDPOINT_PLACEHOLDER",
                title="Test",
                summary="摘要",
                summarized="YES",
                fetched_at="2025-04-10T08:00:00+00:00",
                publish_date="2025-04-10",
            )
            self.assertIn("appended_range", result)


if __name__ == "__main__":
    unittest.main()