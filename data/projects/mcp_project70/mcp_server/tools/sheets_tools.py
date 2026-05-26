"""Google Sheets mock tools for mcp_project70 — archive approved ideas."""

import csv
import json
import os
from datetime import datetime

from .utils.log_decorator import log_mcp_call

_SHEETS_FILE = "results/outputs/archived_ideas.csv"
_SHEETS_COLUMNS = [
    "Date Added",
    "Idea Title",
    "Status",
    "Recommended Nodes",
    "Key Challenges",
    "Improvement Ideas",
    "Alternatives",
    "Source Task ID",
]


def _ensure_sheet() -> None:
    os.makedirs("results/outputs", exist_ok=True)
    if not os.path.exists(_SHEETS_FILE):
        with open(_SHEETS_FILE, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=_SHEETS_COLUMNS).writeheader()


@log_mcp_call("tool", "archive_to_sheets")
def archive_to_sheets(
    idea_title: str,
    nodes: str,
    challenges,
    improvements,
    alternatives,
    source_task_id: str,
) -> str:
    """Append an approved idea row to the mock Google Sheets CSV.

    Accepts string OR list for challenges/improvements/alternatives
    (LLM sometimes returns bulleted lists); lists are joined with newlines.
    """
    def _norm(v):
        if isinstance(v, list):
            return "\n".join(str(x) for x in v)
        return str(v) if v is not None else ""
    challenges = _norm(challenges)
    improvements = _norm(improvements)
    alternatives = _norm(alternatives)
    _ensure_sheet()
    now = datetime.utcnow().isoformat() + "Z"
    row = {
        "Date Added": now,
        "Idea Title": idea_title,
        "Status": "Approved",
        "Recommended Nodes": nodes,
        "Key Challenges": challenges,
        "Improvement Ideas": improvements,
        "Alternatives": alternatives,
        "Source Task ID": source_task_id,
    }
    with open(_SHEETS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_SHEETS_COLUMNS)
        writer.writerow(row)

    result = {
        "status": "mock_appended",
        "file": _SHEETS_FILE,
        "row": row,
    }
    return json.dumps(result)
