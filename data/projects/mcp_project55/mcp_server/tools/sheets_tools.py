"""Mock Google Sheets operations - local JSON file storage.

Replaces: Sheets Update Trigger, Read Trigger Sheet Rows,
          Append Scan Results, Read Form Responses Sheet,
          Append to Scan Results Sheet.
"""

import json
import os
from dotenv import load_dotenv
from .utils.log_decorator import log_mcp_call

load_dotenv()

TICKET_DB_PATH = os.getenv("TICKET_DB_PATH", "data/tickets.json")
SCAN_RESULTS_PATH = os.getenv("SCAN_RESULTS_PATH", "data/scan_results.json")
FORM_RESPONSES_PATH = os.getenv("FORM_RESPONSES_PATH", "data/form_responses.json")


def _read_json(path: str) -> list[dict]:
    """Read a JSON file and return list of records."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, data: list[dict]) -> None:
    """Write list of records to a JSON file."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@log_mcp_call("tool", "get_form_responses")
def get_form_responses() -> list[dict]:
    """Read all form responses from the mock Google Sheets (form_responses.json).

    Simulates: Sheets Update Trigger / Read Form Responses Sheet.

    Returns:
        List of form response records, each with Timestamp, QR code, NAMA fields.
    """
    return _read_json(FORM_RESPONSES_PATH)


@log_mcp_call("tool", "read_ticket_rows")
def read_ticket_rows(ticket_code: str) -> list[dict]:
    """Look up ticket rows by ticket code from the ticket database.

    Simulates: Read Trigger Sheet Rows (Google Sheets lookup with filter TIKET=ticket_code).

    Args:
        ticket_code: The ticket code to search for (matched against TIKET field).

    Returns:
        List of matching ticket records. Empty list if no match found.
    """
    tickets = _read_json(TICKET_DB_PATH)
    return [t for t in tickets if t.get("TIKET") == ticket_code]


@log_mcp_call("tool", "append_scan_result")
def append_scan_result(
    ticket_id: str,
    nama: str,
    email: str,
    no_hp: str,
    tiket: str,
    status: str,
    ukuran_jersey: str,
    golongan_darah: str,
) -> dict:
    """Append a scan result record to the scan results sheet.

    Simulates: Append Scan Results / Append to Scan Results Sheet (Google Sheets append).

    Args:
        ticket_id: The ticket ID (or "-" if invalid).
        nama: Participant name (or "-" if invalid).
        email: Participant email (or "-" if invalid).
        no_hp: Phone number (or "-" if invalid).
        tiket: The ticket code.
        status: Validation status ("VALID" or "TIDAK VALID").
        ukuran_jersey: Jersey size (or "-" if invalid).
        golongan_darah: Blood type (or "-" if invalid).

    Returns:
        The appended record.
    """
    record = {
        "ID": ticket_id,
        "NAMA": nama,
        "EMAIL": email,
        "NO HP": no_hp,
        "TIKET": tiket,
        "STATUS": status,
        "UKURAN JERSEY": ukuran_jersey,
        "GOLONGAN DARAH": golongan_darah,
    }
    results = _read_json(SCAN_RESULTS_PATH)
    results.append(record)
    _write_json(SCAN_RESULTS_PATH, results)
    return record
