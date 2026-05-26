"""
Notion tools – mirrors the "Create a database page" node in the n8n workflow.

Creates a new page in a Notion database with article_url (title property),
summary (rich_text), and fetched_at (rich_text).
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from mcp_server.tools.utils.logging_decorator import log_tool_call, setup_logging

logger = setup_logging("logs/server.log", console_output=False)

_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "22e79d55-2675-8055-a143-d55302c3c1b1")

# ── Local file storage (fallback when Notion token not set) ───────────────────
_LOCAL_DATA_DIR = Path("results/local_data")
_LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _use_local_storage() -> bool:
    token = os.getenv("NOTION_TOKEN", "")
    return not token or token.startswith("secret_xxx")


def _get_client() -> Any:
    from notion_client import Client
    token = os.environ["NOTION_TOKEN"]
    return Client(auth=token)


@log_tool_call(logger)
def tool_create_notion_page(
    article_url: str,
    summary: str,
    fetched_at: str,
    database_id: str = _DATABASE_ID,
    use_mock: bool = False,
) -> dict[str, Any]:
    """
    Create a new page in the Notion 'wechat' database.

    Mirrors the n8n "Create a database page" Notion node.
    Properties written:
      - article_url  (title property)
      - summary      (rich_text property)
      - fetched_at   (rich_text property)

    Args:
        article_url:  URL of the article (used as the page title).
        summary:      Slack-formatted Chinese summary text.
        fetched_at:   ISO timestamp of when the article was fetched.
        database_id:  Notion database UUID.
        use_mock:     If True, skip the API call and return a mock response.

    Returns:
        Dict with key: page_id (Notion page UUID of the created page).
    """
    if use_mock or _use_local_storage():
        # Save to local JSON file instead of calling Notion API
        local_file = _LOCAL_DATA_DIR / "notion_pages.json"
        existing = []
        if local_file.exists():
            existing = json.loads(local_file.read_text(encoding="utf-8"))
        page_id = str(uuid.uuid4())
        existing.append({
            "page_id": page_id,
            "article_url": article_url,
            "summary": summary,
            "fetched_at": fetched_at,
        })
        local_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        label = "Mock" if use_mock else "Local"
        logger.info("%s: saved Notion page for %s", label, article_url)
        return {"page_id": page_id, "url": f"local://notion/{page_id}"}

    client = _get_client()

    # Notion rich_text blocks are capped at 2000 chars per element
    def _rich_text(text: str) -> list[dict]:
        chunks = [text[i : i + 2000] for i in range(0, max(len(text), 1), 2000)]
        return [{"type": "text", "text": {"content": chunk}} for chunk in chunks]

    response = client.pages.create(
        parent={"database_id": database_id},
        properties={
            "article_url": {
                "title": [{"type": "text", "text": {"content": article_url[:2000]}}]
            },
            "summary": {"rich_text": _rich_text(summary)},
            "fetched_at": {"rich_text": _rich_text(fetched_at)},
        },
    )

    page_id: str = response.get("id", "")
    page_url: str = response.get("url", "")
    logger.info("Created Notion page: %s | url: %s", page_id, article_url[:60])
    return {"page_id": page_id, "url": page_url}