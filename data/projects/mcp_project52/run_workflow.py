"""
run_workflow.py – WeChat Article Classifier & Summarizer
=========================================================
Executes the full 15-step pipeline via the FastMCP client:

  Step 1  – Read initial links (local storage / Google Sheets)
  Step 2  – Read RSS feed URLs (local storage / Google Sheets)
  Step 3  – Fetch each RSS feed (mock data when --mock)
  Step 4  – Normalise pubDate
  Step 5  – Filter to last 10 days
  Step 6  – Passthrough set node
  Step 7  – Save date-filtered entries back to storage
  Step 8  – Project to pubDate+link for dedup
  Step 9  – Filter unique links
  Step 10 – Restore full RSS data for new links
  Step 11 – Clean HTML content
  Step 12 – Classify relevance (AI)
  Step 13 – Summarize relevant articles (AI)
  Step 14 – Save to storage (Relevant Articles)
  Step 15 – Create Notion page (local storage / Notion API)

Usage::

    uv run python run_workflow.py               # all 15 steps, real RSS feeds
    uv run python run_workflow.py --mock        # all 15 steps, mock RSS data
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client

load_dotenv()

from mcp_server.tools.utils.logging_decorator import setup_logging

logger = setup_logging("logs/workflow.log", console_output=True)

RESULTS_DIR = Path("results/outputs")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

STEP_COUNT = 0


# ── helpers ────────────────────────────────────────────────────────────────────

def step(name: str) -> None:
    """Log a numbered step."""
    global STEP_COUNT
    STEP_COUNT += 1
    logger.info("[Step %d] %s", STEP_COUNT, name)


async def call(client: Client, tool: str, **kwargs) -> any:
    """Call an MCP tool and unwrap the result."""
    result = await client.call_tool(tool, kwargs)
    if not result.content:
        return []
    raw = result.content[0].text
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


# ── main pipeline ──────────────────────────────────────────────────────────────

async def run_pipeline(use_mock: bool = False) -> None:
    global STEP_COUNT
    STEP_COUNT = 0

    logger.info("=" * 60)
    logger.info("Starting WeChat Article Summarizer Workflow (mock_rss=%s)", use_mock)
    logger.info("=" * 60)

    async with Client("mcp_server/server.py") as client:

        # ── Step 1: Read initial links ─────────────────────────────────────────
        step("Read initial links from storage")
        initial_links = await call(client, "tool_read_initial_links")
        if not initial_links and use_mock:
            # Seed with mock data on first run
            mock_date = (datetime.now(tz=timezone.utc) - timedelta(days=5)).isoformat()
            initial_links = [
                {"link": "ENDPOINT_PLACEHOLDER", "pubDate": mock_date, "title": "Mock Existing"},
            ]
        logger.info("  -> %d initial links loaded", len(initial_links))

        # ── Step 2: Read RSS feed URLs ─────────────────────────────────────────
        step("Read RSS feed URLs from storage")
        rss_sources = await call(client, "tool_read_rss_links")
        if not rss_sources and use_mock:
            rss_sources = [
                {"rss_feed_url": "ENDPOINT_PLACEHOLDER"},
            ]
        logger.info("  -> %d RSS sources loaded", len(rss_sources))

        # ── Step 3: Fetch each RSS feed ────────────────────────────────────────
        step("Fetch RSS feeds" + (" (mock data)" if use_mock else ""))
        all_rss_entries: list[dict] = []
        for source in rss_sources:
            url = source.get("rss_feed_url", "")
            if not url:
                continue
            logger.info("  Fetching RSS: %s", url)
            try:
                if use_mock:
                    entries = _mock_rss_entries()
                else:
                    entries = await call(client, "tool_rss_read", rss_feed_url=url, ignore_ssl=False)
                logger.info("    -> %d entries fetched", len(entries))
                all_rss_entries.extend(entries)
            except Exception as exc:
                logger.warning("  RSS fetch error for %s: %s", url, exc)
        logger.info("  Total RSS entries fetched: %d", len(all_rss_entries))

        # ── Step 4: Normalise pubDate ──────────────────────────────────────────
        step("Normalise pubDate")
        normalised_entries = await call(
            client, "tool_process_pubdate", entries=all_rss_entries
        )
        logger.info("  -> %d entries normalised", len(normalised_entries))

        # ── Step 5: Filter by date ─────────────────────────────────────────────
        step("Filter entries from last 10 days")
        date_filtered = await call(
            client, "tool_filter_by_date", entries=normalised_entries, days_back=10
        )
        logger.info("  -> %d entries pass date filter", len(date_filtered))

        # ── Step 6: Passthrough set node ───────────────────────────────────────
        step("Set filtered data (passthrough)")
        filtered_data = await call(client, "tool_set_filtered_data", entries=date_filtered)
        logger.info("  -> %d entries retained", len(filtered_data))

        # ── Step 7: Save to storage ────────────────────────────────────────────
        step("Save filtered entries to storage")
        save_result = await call(
            client, "tool_save_initial_data", rows=filtered_data
        )
        logger.info("  -> Save result: %s", save_result)

        # ── Step 8: Project to pubDate+link ────────────────────────────────────
        step("Project to pubDate+link for deduplication")
        link_projections = await call(
            client, "tool_extract_pubdate_link", entries=filtered_data
        )
        initial_projections = [
            {"pubDate": r.get("pubDate", ""), "link": r.get("link", "")}
            for r in initial_links
        ]
        merged_for_dedup = initial_projections + link_projections
        logger.info("  -> %d entries for dedup check", len(merged_for_dedup))

        # ── Step 9: Filter unique links ────────────────────────────────────────
        step("Filter unique (new) links")
        unique_links = await call(
            client, "tool_filter_unique_links", entries=merged_for_dedup
        )
        logger.info("  -> %d new unique links to process", len(unique_links))

        # ── Step 10: Restore full data ─────────────────────────────────────────
        step("Restore full article data for new links")
        if unique_links:
            merged_full = initial_links + filtered_data
            full_articles = await call(
                client,
                "tool_restore_full_data",
                merged_entries=merged_full,
                full_entries=filtered_data,
            )
            if not full_articles:
                logger.info("  Restore returned empty - using filtered_data directly")
                unique_link_set = {u["link"] for u in unique_links}
                full_articles = [e for e in filtered_data if e.get("link") in unique_link_set]
        else:
            full_articles = []
        logger.info("  -> %d articles with full data", len(full_articles))

        # ── Step 11: Clean HTML content ───────────────────────────────────────
        step("Clean HTML content")
        MAX_RELEVANT = 3
        relevant_articles: list[dict] = []

        for article in full_articles:
            link = article.get("link", "")
            title = article.get("title", "")
            logger.info("  Processing: %s", title[:70])

            cleaned_list = await call(
                client, "tool_clean_html_content", entries=[article]
            )
            cleaned = cleaned_list[0] if cleaned_list else article
            cleaned_content = cleaned.get("cleanedContent", "")

            # ── Step 12: Classify relevance (AI) ──────────────────────────────
            classification = await call(
                client,
                "tool_classify_relevance",
                title=title,
                cleaned_content=cleaned_content,
            )
            if not classification.get("kept", False):
                logger.info("  -> NOT relevant, skipping")
                continue

            if len(relevant_articles) >= MAX_RELEVANT:
                logger.info("  -> Relevant but already reached %d limit, stopping", MAX_RELEVANT)
                break

            logger.info("  -> Relevant! Generating summary...")

            # ── Step 13: Summarize (AI) ────────────────────────────────────────
            summary_result = await call(
                client,
                "tool_summarize_article",
                cleaned_content=cleaned_content,
                article_url=link,
                title=title,
            )
            summary_text = summary_result.get("text", "") if isinstance(summary_result, dict) else str(summary_result)

            pub_date_raw = article.get("pubDate", "")
            fetched_at = datetime.now(tz=timezone.utc).isoformat()

            try:
                pub_date_fmt = datetime.fromisoformat(
                    pub_date_raw.replace("Z", "+00:00")
                ).strftime("%Y-%m-%d")
            except Exception:
                pub_date_fmt = pub_date_raw[:10] if pub_date_raw else ""

            relevant_articles.append({
                "article_url": link,
                "title": title,
                "summary": summary_text,
                "summarized": "YES",
                "fetched_at": fetched_at,
                "publish_date": pub_date_fmt,
            })

        if not full_articles:
            logger.info("  No new articles to process")

        # ── Step 12: Classify relevance (AI) ──────────────────────────────────
        step("Classify relevance (AI)")
        logger.info("  -> %d articles classified, %d relevant", len(full_articles), len(relevant_articles))

        # ── Step 13: Summarize articles (AI) ──────────────────────────────────
        step("Summarize articles (AI)")
        logger.info("  -> %d summaries generated", len(relevant_articles))

        # ── Step 14: Save relevant articles to storage ────────────────────────
        step("Save relevant articles to storage")
        for art in relevant_articles:
            sheets_result = await call(
                client,
                "tool_save_relevant_article",
                article_url=art["article_url"],
                title=art["title"],
                summary=art["summary"],
                summarized=art["summarized"],
                fetched_at=art["fetched_at"],
                publish_date=art["publish_date"],
            )
            logger.info("  Sheets/Local: %s", sheets_result)
        if not relevant_articles:
            logger.info("  No relevant articles to save")

        # ── Step 15: Create Notion pages ──────────────────────────────────────
        step("Create Notion pages")
        for art in relevant_articles:
            notion_result = await call(
                client,
                "tool_create_notion_page",
                article_url=art["article_url"],
                summary=art["summary"],
                fetched_at=art["fetched_at"],
            )
            logger.info("  Notion/Local: %s", notion_result)
        if not relevant_articles:
            logger.info("  No pages to create")

        _save_results(relevant_articles, use_mock)
        logger.info("=" * 60)
        logger.info("Workflow complete. %d steps executed. %d relevant articles.", STEP_COUNT, len(relevant_articles))
        logger.info("=" * 60)


# ── Mock data ──────────────────────────────────────────────────────────────────

def _mock_rss_entries() -> list[dict]:
    """Return a small set of fake RSS entries for testing."""
    now = datetime.now(tz=timezone.utc)
    date1 = (now - timedelta(days=2)).isoformat()
    date2 = (now - timedelta(days=1)).isoformat()

    return [
        {
            "title": "欧阳良宜：AI 时代的读书笔记方法论",
            "link": "ENDPOINT_PLACEHOLDER",
            "pubDate": date1,
            "author": "TestAuthor",
            "creator": "TestAuthor",
            "content": "<p>这是一篇关于 AI 辅助读书笔记的文章。</p>",
            "content:encoded": "<p>这是一篇关于 AI 辅助读书笔记的文章，探讨了超级个体的成长路径。</p>",
            "content:encodedSnippet": "这是一篇关于 AI 辅助读书笔记的文章",
            "contentSnippet": "这是一篇关于 AI 辅助读书笔记的文章",
            "itunes": "",
        },
        {
            "title": "招生通知：2025 年秋季班开始报名",
            "link": "ENDPOINT_PLACEHOLDER",
            "pubDate": date2,
            "author": "SchoolAdmin",
            "creator": "SchoolAdmin",
            "content": "<p>2025 年秋季班招生通知。</p>",
            "content:encoded": "<p>2025 年秋季班招生通知，欢迎报名。</p>",
            "content:encodedSnippet": "2025 年秋季班招生通知",
            "contentSnippet": "2025 年秋季班招生通知",
            "itunes": "",
        },
    ]


# ── Results persistence ────────────────────────────────────────────────────────

def _save_results(articles: list[dict], use_mock: bool) -> None:
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    mode = "mock" if use_mock else "real"
    out_path = RESULTS_DIR / f"workflow_result_{mode}_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"timestamp": ts, "mode": mode, "articles": articles}, f, ensure_ascii=False, indent=2)
    logger.info("Results saved to %s", out_path)


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WeChat Article Summarizer Workflow")
    parser.add_argument(
        "--mock", action="store_true",
        help="Use mock RSS data (AI + local storage still run for real)",
    )
    args = parser.parse_args()
    asyncio.run(run_pipeline(use_mock=args.mock))
