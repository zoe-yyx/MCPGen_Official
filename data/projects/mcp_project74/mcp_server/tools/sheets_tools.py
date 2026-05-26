"""Google Sheets tools — mock logging of download results and wait node."""

import csv
import json
import os
import time

from mcp_server.tools.utils.log_decorator import log_mcp_call

_LOG_CSV = os.path.join("results", "outputs", "download_log.csv")
_LOG_JSON = os.path.join("results", "outputs", "download_log.json")
_CSV_FIELDS = ["URL", "Drive_URL", "status", "logged_at"]


def _append_to_log(url: str, drive_url: str, status: str) -> dict:
    os.makedirs("results/outputs", exist_ok=True)

    entry = {
        "URL": url,
        "Drive_URL": drive_url,
        "status": status,
        "logged_at": int(time.time()),
    }

    # Append to JSON log
    existing: list = []
    if os.path.exists(_LOG_JSON):
        with open(_LOG_JSON, encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []
    existing.append(entry)
    with open(_LOG_JSON, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    # Append to CSV log
    write_header = not os.path.exists(_LOG_CSV)
    with open(_LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(entry)

    return entry


@log_mcp_call(operation_type="tool")
def wait_before_logging_failure(seconds: int = 1) -> str:
    """Simulate the n8n Wait node pause before logging a failed download.

    In the original workflow this avoids timing issues; here it logs the wait.
    """
    # No real sleep — just record the intended wait duration
    return json.dumps({
        "status": "done",
        "waited_seconds": seconds,
        "note": "mock wait — no real delay applied",
        "timestamp": int(time.time()),
    })


@log_mcp_call(operation_type="tool")
def log_success_to_sheets(url: str, drive_url: str) -> str:
    """Log a successful download (URL + Drive link) to Google Sheets (mock → local CSV + JSON)."""
    entry = _append_to_log(url, drive_url, "success")
    return json.dumps({
        "status": "appended",
        "sheet": os.environ.get("GOOGLE_SHEETS_SHEET_NAME", "Sheet1"),
        "doc_id": os.environ.get("GOOGLE_SHEETS_DOC_ID", "mock_sheet_id"),
        "row": entry,
        "csv_file": _LOG_CSV,
        "json_file": _LOG_JSON,
    }, ensure_ascii=False)


@log_mcp_call(operation_type="tool")
def log_failure_to_sheets(url: str) -> str:
    """Log a failed download (URL + 'N/A') to Google Sheets (mock → local CSV + JSON)."""
    entry = _append_to_log(url, "N/A", "failed")
    return json.dumps({
        "status": "appended",
        "sheet": os.environ.get("GOOGLE_SHEETS_SHEET_NAME", "Sheet1"),
        "doc_id": os.environ.get("GOOGLE_SHEETS_DOC_ID", "mock_sheet_id"),
        "row": entry,
        "csv_file": _LOG_CSV,
        "json_file": _LOG_JSON,
    }, ensure_ascii=False)
