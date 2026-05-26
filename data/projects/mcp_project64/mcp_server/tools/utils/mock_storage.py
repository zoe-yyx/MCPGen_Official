"""Mock local JSON storage to replace Supabase and n8n data tables."""

import json
import os
import tempfile
from typing import Any


def _ensure_file(path: str) -> None:
    """Create the JSON file with an empty list if it doesn't exist."""
    dir_name = os.path.dirname(path) if os.path.dirname(path) else "."
    os.makedirs(dir_name, exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)


def load_table(path: str) -> list[dict[str, Any]]:
    """Load all records from a local JSON file."""
    _ensure_file(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return []
        return json.loads(content)


def save_table(path: str, data: list[dict[str, Any]]) -> None:
    """Save records to a local JSON file using atomic write (write to temp then rename)."""
    dir_name = os.path.dirname(path) if os.path.dirname(path) else "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # On Windows, need to remove target first
        if os.path.exists(path):
            os.remove(path)
        os.rename(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def insert_record(path: str, record: dict[str, Any]) -> dict[str, Any]:
    """Insert a single record into the table."""
    table = load_table(path)
    table.append(record)
    save_table(path, table)
    return record


def update_records(
    path: str, filter_key: str, filter_value: Any, updates: dict[str, Any]
) -> int:
    """Update records matching a filter. Returns number of updated records."""
    table = load_table(path)
    count = 0
    for record in table:
        if record.get(filter_key) == filter_value:
            record.update(updates)
            count += 1
    save_table(path, table)
    return count


def query_records(
    path: str,
    filter_fn: Any = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query records with optional filter function and limit."""
    table = load_table(path)
    if filter_fn:
        table = [r for r in table if filter_fn(r)]
    return table[:limit]
