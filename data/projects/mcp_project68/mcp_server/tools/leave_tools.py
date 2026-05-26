"""Leave record tools - mock Google Sheets operations for employee leave data."""

import json
import os
from datetime import date, datetime
from typing import Any

from .utils.log_decorator import get_logger, log_mcp_call

logger = get_logger()

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "leave_records.json")


def _load_records() -> list[dict[str, Any]]:
    path = os.path.abspath(DATA_FILE)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_records(records: list[dict[str, Any]]) -> None:
    path = os.path.abspath(DATA_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


@log_mcp_call("tool")
def fetch_leave_records() -> str:
    """Fetch all employee leave records from local mock storage (simulates Google Sheets read).

    Returns:
        JSON string list of leave record dicts with keys:
        Employee Email, Name, Start Date, End Date, Status, Last Updated.
    """
    records = _load_records()
    return json.dumps(records)


@log_mcp_call("tool")
def validate_normalize_leave_data(records_json: str) -> str:
    """Validate and normalize leave records, computing activation/reset flags for today.

    Args:
        records_json: JSON string list of raw leave records.

    Returns:
        JSON string list of normalized records with fields:
        email, name, startDate, endDate, returnDate, currentStatus, today,
        isWithinLeave, isLeaveEnded, needsActivation, needsReset.
        Records with missing/invalid data are excluded.
    """
    raw: list[dict[str, Any]] = json.loads(records_json)
    today = date.today()

    normalized = []
    for item in raw:
        email = item.get("Employee Email", "").strip()
        name = item.get("Name", "").strip()
        start_raw = item.get("Start Date", "").strip()
        end_raw = item.get("End Date", "").strip()
        status = item.get("Status", "Inactive").strip()

        if not email or not start_raw or not end_raw:
            continue

        try:
            start_date = datetime.strptime(start_raw, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_raw, "%Y-%m-%d").date()
        except ValueError:
            continue

        is_within_leave = start_date <= today <= end_date
        is_leave_ended = today > end_date

        normalized.append({
            "email": email,
            "name": name,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "returnDate": end_date.isoformat(),
            "currentStatus": status,
            "today": today.isoformat(),
            "isWithinLeave": is_within_leave,
            "isLeaveEnded": is_leave_ended,
            "needsActivation": is_within_leave and status != "Active",
            "needsReset": is_leave_ended and status == "Active",
        })

    return json.dumps(normalized)


@log_mcp_call("tool")
def mark_leave_as_active(email: str, today: str) -> str:
    """Update leave record status to Active in local mock storage (simulates Google Sheets update).

    Args:
        email: Employee email address to match.
        today: Today's date string (YYYY-MM-DD) for Last Updated field.

    Returns:
        Success message string.
    """
    records = _load_records()
    updated = False
    for record in records:
        if record.get("Employee Email", "").strip().lower() == email.strip().lower():
            record["Status"] = "Active"
            record["Last Updated"] = today
            updated = True
            break
    if updated:
        _save_records(records)
        return f"Leave record for {email} marked as Active."
    return f"No matching record found for {email}."


@log_mcp_call("tool")
def mark_leave_as_inactive(email: str, today: str) -> str:
    """Update leave record status to Inactive in local mock storage (simulates Google Sheets update).

    Args:
        email: Employee email address to match.
        today: Today's date string (YYYY-MM-DD) for Last Updated field.

    Returns:
        Success message string.
    """
    records = _load_records()
    updated = False
    for record in records:
        if record.get("Employee Email", "").strip().lower() == email.strip().lower():
            record["Status"] = "Inactive"
            record["Last Updated"] = today
            updated = True
            break
    if updated:
        _save_records(records)
        return f"Leave record for {email} marked as Inactive."
    return f"No matching record found for {email}."
