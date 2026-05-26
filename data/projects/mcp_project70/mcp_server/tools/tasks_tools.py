"""Google Tasks mock tools for mcp_project70."""

import json
import os
from datetime import datetime

from .utils.log_decorator import log_mcp_call

# Mock Google Tasks data store
_TASKS_DB: dict[str, dict] = {
    "task_001": {
        "id": "task_001",
        "title": "Build an automated email digest from Gmail using n8n",
        "notes": "",
        "status": "needsAction",
        "due": "2026-05-20T09:00:00Z",
        "updated": "2026-05-17T10:00:00Z",
    },
    "task_002": {
        "id": "task_002",
        "title": "Sync Notion database rows to Google Sheets automatically",
        "notes": "",
        "status": "needsAction",
        "due": "2026-05-21T09:00:00Z",
        "updated": "2026-05-17T11:00:00Z",
    },
    "task_003": {
        "id": "task_003",
        "title": "Monitor website uptime and send Slack alerts on downtime",
        "notes": "✅ Processed",
        "status": "needsAction",
        "due": "2026-05-18T09:00:00Z",
        "updated": "2026-05-16T08:00:00Z",
    },
    "task_004": {
        "id": "task_004",
        "title": "Auto-post scheduled tweets from a Google Sheets calendar",
        "notes": "",
        "status": "needsAction",
        "due": "2026-05-22T09:00:00Z",
        "updated": "2026-05-17T12:00:00Z",
    },
    "task_005": {
        "id": "task_005",
        "title": "Scrape job listings and save new ones to Airtable daily",
        "notes": "",
        "status": "needsAction",
        "due": "2026-05-23T09:00:00Z",
        "updated": "2026-05-17T13:00:00Z",
    },
}


@log_mcp_call("tool", "get_new_ideas")
def get_new_ideas(limit: int = 5) -> str:
    """Fetch up to `limit` tasks from the mock Google Tasks list."""
    tasks = list(_TASKS_DB.values())[:limit]
    return json.dumps({
        "tasks": tasks,
        "count": len(tasks),
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    })


@log_mcp_call("tool", "filter_processed")
def filter_processed(tasks_json: str) -> str:
    """Filter out tasks whose notes contain '✅ Processed'."""
    data = json.loads(tasks_json)
    tasks = data.get("tasks", [])
    filtered = [t for t in tasks if "✅ Processed" not in (t.get("notes") or "")]
    return json.dumps({
        "tasks": filtered,
        "count": len(filtered),
        "skipped": len(tasks) - len(filtered),
    })


@log_mcp_call("tool", "mark_as_notified")
def mark_as_notified(task_id: str) -> str:
    """Update a task's notes to '✅ Processed' in the mock store and save to results."""
    if task_id in _TASKS_DB:
        _TASKS_DB[task_id]["notes"] = "✅ Processed"
        _TASKS_DB[task_id]["updated"] = datetime.utcnow().isoformat() + "Z"

    result = {
        "task_id": task_id,
        "notes": "✅ Processed",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "status": "mock_updated",
    }

    os.makedirs("results/outputs", exist_ok=True)
    out_path = f"results/outputs/task_notified_{task_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return json.dumps(result)
