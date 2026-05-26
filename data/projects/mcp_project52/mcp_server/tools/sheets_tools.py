"""
Google Sheets tools – mirrors the three googleSheets nodes in the n8n workflow:

  • read_initial_links   → "Read Initial Links"   (sheet: Save Initial Links)
  • read_rss_links       → "Read RSS Links"        (sheet: Read RSS Links)
  • save_initial_data    → "Save Initial Data"     (appendOrUpdate by link)
  • save_relevant_article→ "Google Sheets – Add relevant article" (append)

Authentication: Service-Account JSON key pointed to by GOOGLE_SERVICE_ACCOUNT_JSON,
or OAuth token via GOOGLE_TOKEN_JSON (for local testing with user credentials).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp_server.tools.utils.logging_decorator import log_tool_call, setup_logging

logger = setup_logging("logs/server.log", console_output=False)

# ── Google Sheets constants ────────────────────────────────────────────────────
SPREADSHEET_ID = os.getenv(
    "GOOGLE_SPREADSHEET_ID", "12HW0_goHSaO2QpqLTYxNpEWePBK4o0nsniyAx-hkkXE"
)
SHEET_SAVE_INITIAL = os.getenv("SHEET_SAVE_INITIAL", "Save Initial Links")
SHEET_READ_RSS = os.getenv("SHEET_READ_RSS", "Read RSS Links")
SHEET_RELEVANT = os.getenv("SHEET_RELEVANT", "Relevant Articles")
SCOPES = ["ENDPOINT_PLACEHOLDER"]

# ── Local file storage directory (fallback when Google credentials not set) ───
_LOCAL_DATA_DIR = Path("results/local_data")
_LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _use_local_storage() -> bool:
    """Return True if Google credentials are not configured."""
    return not (os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("GOOGLE_TOKEN_JSON"))


def _local_path(sheet_name: str) -> Path:
    """Return path to a local JSON file that mirrors a Google Sheet."""
    safe_name = sheet_name.replace(" ", "_").lower()
    return _LOCAL_DATA_DIR / f"{safe_name}.json"


def _read_local(sheet_name: str) -> list[dict[str, Any]]:
    """Read rows from a local JSON file."""
    p = _local_path(sheet_name)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return []


def _write_local(sheet_name: str, rows: list[dict[str, Any]]) -> None:
    """Write rows to a local JSON file."""
    p = _local_path(sheet_name)
    p.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Auth helper ────────────────────────────────────────────────────────────────

def _get_sheets_service() -> Any:
    """Build and return an authenticated Sheets API service object."""
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    token_json = os.getenv("GOOGLE_TOKEN_JSON")

    if sa_json:
        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    elif token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    else:
        raise EnvironmentError(
            "Neither GOOGLE_SERVICE_ACCOUNT_JSON nor GOOGLE_TOKEN_JSON is set."
        )
    return build("sheets", "v4", credentials=creds)


# ── Tool functions ─────────────────────────────────────────────────────────────

@log_tool_call(logger)
def tool_read_initial_links(
    spreadsheet_id: str = SPREADSHEET_ID,
    sheet_name: str = SHEET_SAVE_INITIAL,
) -> list[dict[str, Any]]:
    """
    Read all rows from the 'Save Initial Links' sheet.

    Returns:
        List of dicts with keys: link, title, pubDate (may contain more columns).
    """
    if _use_local_storage():
        logger.info("Using local file storage for read_initial_links")
        return _read_local(sheet_name)

    service = _get_sheets_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=sheet_name)
        .execute()
    )
    rows = result.get("values", [])
    if not rows:
        return []
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:]]


@log_tool_call(logger)
def tool_read_rss_links(
    spreadsheet_id: str = SPREADSHEET_ID,
    sheet_name: str = SHEET_READ_RSS,
) -> list[dict[str, Any]]:
    """
    Read all RSS feed URLs from the 'Read RSS Links' sheet.

    Returns:
        List of dicts, each containing at minimum: rss_feed_url
    """
    if _use_local_storage():
        logger.info("Using local file storage for read_rss_links")
        return _read_local(sheet_name)

    service = _get_sheets_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=sheet_name)
        .execute()
    )
    rows = result.get("values", [])
    if not rows:
        return []
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:]]


@log_tool_call(logger)
def tool_save_initial_data(
    rows: list[dict[str, Any]],
    spreadsheet_id: str = SPREADSHEET_ID,
    sheet_name: str = SHEET_SAVE_INITIAL,
) -> dict[str, Any]:
    """
    Append-or-update rows in 'Save Initial Links', matched by the 'link' column.

    Each dict in *rows* should contain: link, title, pubDate.

    Returns:
        Summary dict with keys: updated_count, appended_count.
    """
    if _use_local_storage():
        existing = _read_local(sheet_name)
        existing_links = {r.get("link", "") for r in existing}
        updated, appended = 0, 0
        for row_data in rows:
            link = row_data.get("link", "")
            if link in existing_links:
                existing = [row_data if r.get("link") == link else r for r in existing]
                updated += 1
            else:
                existing.append(row_data)
                appended += 1
        _write_local(sheet_name, existing)
        logger.info("Local save_initial_data: updated=%d, appended=%d", updated, appended)
        return {"updated_count": updated, "appended_count": appended}

    service = _get_sheets_service()

    # Read existing data to detect duplicates
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=sheet_name)
        .execute()
    )
    existing_rows = result.get("values", [])
    headers: list[str] = existing_rows[0] if existing_rows else ["pubDate", "title", "link"]
    existing_links: set[str] = set()
    link_col_idx = headers.index("link") if "link" in headers else 2

    for r in existing_rows[1:]:
        if len(r) > link_col_idx:
            existing_links.add(r[link_col_idx])

    to_append: list[list[str]] = []
    to_update: list[tuple[int, list[str]]] = []

    for i, row_data in enumerate(rows):
        link = row_data.get("link", "")
        values = [
            row_data.get("pubDate", ""),
            row_data.get("title", ""),
            link,
        ]
        if link in existing_links:
            # find row index (1-based, +1 for header)
            for j, existing in enumerate(existing_rows[1:], start=2):
                if len(existing) > link_col_idx and existing[link_col_idx] == link:
                    to_update.append((j, values))
                    break
        else:
            to_append.append(values)

    appended = 0
    if to_append:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": to_append},
        ).execute()
        appended = len(to_append)

    updated = 0
    for row_idx, values in to_update:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A{row_idx}",
            valueInputOption="USER_ENTERED",
            body={"values": [values]},
        ).execute()
        updated += 1

    return {"updated_count": updated, "appended_count": appended}


@log_tool_call(logger)
def tool_save_relevant_article(
    article_url: str,
    title: str,
    summary: str,
    summarized: str,
    fetched_at: str,
    publish_date: str,
    spreadsheet_id: str = SPREADSHEET_ID,
    sheet_name: str = SHEET_RELEVANT,
) -> dict[str, Any]:
    """
    Append one relevant article row to the 'Relevant Articles' sheet.

    Returns:
        Dict with key: appended_range (the range where data was written).
    """
    if _use_local_storage():
        existing = _read_local(sheet_name)
        existing.append({
            "article_url": article_url,
            "summarized": summarized,
            "title": title,
            "summary": summary,
            "fetched_at": fetched_at,
            "publish_date": publish_date,
        })
        _write_local(sheet_name, existing)
        logger.info("Local save_relevant_article: %s", article_url[:60])
        return {"appended_range": f"local:{sheet_name}"}

    service = _get_sheets_service()
    values = [[article_url, summarized, title, summary, fetched_at, publish_date]]
    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
        .execute()
    )
    return {"appended_range": result.get("updates", {}).get("updatedRange", "")}