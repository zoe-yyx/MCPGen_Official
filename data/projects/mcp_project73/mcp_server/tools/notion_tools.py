"""Notion tools — mock Notion database persistence for vocabulary entries."""

import csv
import json
import os
import time

from mcp_server.tools.utils.log_decorator import log_mcp_call

_VOCAB_JSON = "results/outputs/vocabulary.json"
_VOCAB_CSV = "results/outputs/vocabulary.csv"


@log_mcp_call(operation_type="tool")
def save_vocabulary_to_notion(
    word: str,
    definition: str,
    translation: str,
    part_of_speech: str,
    example_sentence: str,
    example_translation: str,
    notion_db_id: str = "mock_db",
) -> str:
    """Save a vocabulary entry to Notion (mock — appended to local JSON and CSV files)."""
    os.makedirs("results/outputs", exist_ok=True)

    entry = {
        "word": word,
        "definition": definition,
        "translation": translation,
        "part_of_speech": part_of_speech,
        "example_sentence": example_sentence,
        "example_translation": example_translation,
        "notion_db_id": notion_db_id,
        "saved_at": int(time.time()),
    }

    existing: list = []
    if os.path.exists(_VOCAB_JSON):
        with open(_VOCAB_JSON, encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []
    existing.append(entry)
    with open(_VOCAB_JSON, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    write_header = not os.path.exists(_VOCAB_CSV)
    with open(_VOCAB_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(entry.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(entry)

    return json.dumps({
        "status": "mock_saved",
        "notion_db_id": notion_db_id,
        "word": word,
        "json_file": _VOCAB_JSON,
        "csv_file": _VOCAB_CSV,
    }, ensure_ascii=False)
