"""
Data-processing tools – mirrors the transformation / code nodes in n8n:

  • tool_process_pubdate        → "pubDate Processing"      (Set node)
  • tool_filter_by_date         → "IF (Filter by Date)"     (IF node)
  • tool_extract_pubdate_link   → "pubDate&link Only"        (Set node)
  • tool_filter_unique_links    → "Filter Unique Links"      (Code node)
  • tool_restore_full_data      → "Restore Full Data with Code" (Code node)
  • tool_clean_html_content     → "Clean HTML Content"       (Code node)
  • tool_set_filtered_data      → "Filtered Data"            (Set node – passthrough)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp_server.tools.utils.logging_decorator import log_tool_call, setup_logging

logger = setup_logging("logs/server.log", console_output=False)


# ── pubDate normalisation ──────────────────────────────────────────────────────

@log_tool_call(logger)
def tool_process_pubdate(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Normalise pubDate to ISO-8601 format for every entry.

    Mirrors the n8n "pubDate Processing" Set node which calls
    ``new Date($json.pubDate).toISOString()``.

    Args:
        entries: Raw RSS entries.

    Returns:
        Entries with pubDate replaced by ISO-8601 string.
    """
    result = []
    for entry in entries:
        e = dict(entry)
        raw = e.get("pubDate", "")
        e["pubDate"] = _to_iso(raw)
        result.append(e)
    return result


@log_tool_call(logger)
def tool_set_filtered_data(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Passthrough Set node that keeps all fields as-is.

    Mirrors the n8n "Filtered Data" Set node (explicit field copy).

    Args:
        entries: Date-filtered entries.

    Returns:
        Same entries (identity transform, retains all fields).
    """
    return [dict(e) for e in entries]


# ── Date filter ────────────────────────────────────────────────────────────────

@log_tool_call(logger)
def tool_filter_by_date(
    entries: list[dict[str, Any]],
    days_back: int = 10,
) -> list[dict[str, Any]]:
    """
    Keep only entries whose pubDate is within the last *days_back* days.

    Mirrors the n8n "IF (Filter by Date)" node:
    ``new Date(pubDate).getTime() > Date.now() - 10 * 24 * 60 * 60 * 1000``

    Args:
        entries:   List of entries with a 'pubDate' field.
        days_back: Cutoff window in days (default 10).

    Returns:
        Filtered list of entries.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days_back)
    result = []
    for entry in entries:
        pub = _parse_dt(entry.get("pubDate", ""))
        if pub and pub > cutoff:
            result.append(entry)
    logger.info(
        "filter_by_date: %d → %d entries (cutoff %s)", len(entries), len(result), cutoff.date()
    )
    return result


# ── pubDate + link projection ──────────────────────────────────────────────────

@log_tool_call(logger)
def tool_extract_pubdate_link(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Project entries to {pubDate, link} only.

    Mirrors the n8n "pubDate&link Only" Set node used before deduplication.

    Args:
        entries: Full article entries.

    Returns:
        List of dicts with only pubDate and link keys.
    """
    return [{"pubDate": e.get("pubDate", ""), "link": e.get("link", "")} for e in entries]


# ── Deduplication ──────────────────────────────────────────────────────────────

@log_tool_call(logger)
def tool_filter_unique_links(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Keep only entries whose link appears exactly once across the input list.

    Mirrors the n8n "Filter Unique Links" Code node:
    entries that appear more than once are removed entirely (they already exist
    in the Google Sheet and need no further processing).

    Args:
        entries: Combined list of {pubDate, link} entries (initial + saved).

    Returns:
        Entries with unique links only.
    """
    from collections import Counter

    link_counts: Counter[str] = Counter(e.get("link", "") for e in entries)
    unique = [e for e in entries if link_counts[e.get("link", "")] == 1]
    logger.info(
        "filter_unique_links: %d → %d unique entries", len(entries), len(unique)
    )
    return unique


# ── Restore full data ──────────────────────────────────────────────────────────

@log_tool_call(logger)
def tool_restore_full_data(
    merged_entries: list[dict[str, Any]],
    full_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    From *merged_entries* (which may contain only {pubDate, link} slices from
    the initial-links sheet), restore the full RSS entry data from *full_entries*
    for links that appear more than once (meaning they exist in both sources).

    Mirrors the n8n "Restore Full Data with Code" Code node.

    Args:
        merged_entries: Combined stream after Merge1 (may be partial or full dicts).
        full_entries:   Original full RSS entries to use as the rich data source.

    Returns:
        Full-data entries ready for HTML cleaning.
    """
    # Build a lookup from link → full entry
    full_map: dict[str, dict[str, Any]] = {
        e.get("link", "").strip().lower(): e for e in full_entries
    }

    from collections import Counter
    link_counts: Counter[str] = Counter(
        e.get("link", "").strip().lower() for e in merged_entries
    )

    result: list[dict[str, Any]] = []
    seen: set[str] = set()

    for entry in merged_entries:
        link_key = entry.get("link", "").strip().lower()
        if link_counts[link_key] > 1 and link_key not in seen:
            seen.add(link_key)
            rich = full_map.get(link_key)
            if rich:
                result.append(rich)

    logger.info(
        "restore_full_data: %d merged → %d restored", len(merged_entries), len(result)
    )
    return result


# ── HTML cleaning ──────────────────────────────────────────────────────────────

@log_tool_call(logger)
def tool_clean_html_content(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Extract clean text from the HTML content field of each entry.

    Mirrors the n8n "Clean HTML Content" Code node:
    1. Try to extract <meta name="description"> content first.
    2. Otherwise strip scripts, styles, comments, and all tags.
    3. Mark as "No content extracted" if nothing found.

    Args:
        entries: Entries with a 'content' or 'content:encoded' field.

    Returns:
        Entries with an added 'cleanedContent' field.
    """
    result = []
    for entry in entries:
        e = dict(entry)
        raw_html = e.get("content:encoded") or e.get("content") or ""
        e["cleanedContent"] = _extract_text(raw_html)
        result.append(e)
    return result


# ── Private helpers ────────────────────────────────────────────────────────────

def _to_iso(raw: str) -> str:
    """Parse various date formats and return ISO-8601; return raw string on failure."""
    if not raw:
        return raw
    if raw.endswith("Z") or "+" in raw or raw.count("-") >= 3:
        # already ISO-ish
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
        except ValueError:
            pass
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    return raw


def _parse_dt(raw: str) -> datetime | None:
    """Parse an ISO-8601 date string into a timezone-aware datetime, or None."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _extract_text(html: str) -> str:
    """Clean HTML and return plain text; matches the n8n JS cleaning logic."""
    if not html:
        return "No content extracted"

    # 1. Try meta description
    m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html, re.I)
    if m and m.group(1).strip():
        return m.group(1).strip()

    # 2. Strip noise
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.I)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"window\.\S+", "", text)
    text = re.sub(r"[\s\n\r]+", " ", text).strip()

    return text if text else "No content extracted"