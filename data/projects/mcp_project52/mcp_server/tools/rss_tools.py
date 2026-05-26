"""
RSS feed tools – mirrors the "RSS Read" node in the n8n workflow.

Fetches and parses an RSS/Atom feed from a given URL, normalising each entry
into a flat dict compatible with the rest of the pipeline.
"""

from __future__ import annotations

import re
import ssl
from datetime import datetime, timezone
from typing import Any

import feedparser

from mcp_server.tools.utils.logging_decorator import log_tool_call, setup_logging

logger = setup_logging("logs/server.log", console_output=False)


@log_tool_call(logger)
def tool_rss_read(rss_feed_url: str, ignore_ssl: bool = False) -> list[dict[str, Any]]:
    """
    Fetch and parse an RSS/Atom feed.

    Args:
        rss_feed_url: Full URL of the RSS feed.
        ignore_ssl:   If True, disable SSL certificate verification.

    Returns:
        List of entry dicts, each containing:
          title, link, pubDate (ISO-8601 string), author, creator,
          content, content:encoded, content:encodedSnippet, contentSnippet
    """
    if ignore_ssl:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        feed = feedparser.parse(rss_feed_url, handlers=[])
    else:
        feed = feedparser.parse(rss_feed_url)

    entries: list[dict[str, Any]] = []
    for entry in feed.entries:
        pub_date = _parse_pub_date(entry)
        content_encoded = _get_content_encoded(entry)
        content_snippet = _strip_html(content_encoded)[:500] if content_encoded else ""

        entries.append(
            {
                "title": getattr(entry, "title", ""),
                "link": getattr(entry, "link", ""),
                "pubDate": pub_date,
                "author": getattr(entry, "author", ""),
                "creator": getattr(entry, "author", ""),
                "content": getattr(entry, "summary", ""),
                "content:encoded": content_encoded,
                "content:encodedSnippet": content_snippet,
                "contentSnippet": content_snippet,
                "itunes": "",
            }
        )

    logger.info("Fetched %d entries from %s", len(entries), rss_feed_url)
    return entries


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_pub_date(entry: Any) -> str:
    """Return a normalised ISO-8601 pubDate string, or empty string."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return ""


def _get_content_encoded(entry: Any) -> str:
    """Extract the richest available content body."""
    if hasattr(entry, "content") and entry.content:
        return entry.content[0].get("value", "")
    if hasattr(entry, "summary"):
        return entry.summary
    return ""


def _strip_html(html: str) -> str:
    """Naive HTML tag stripper for snippet generation."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()