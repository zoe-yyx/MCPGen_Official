"""Tools for template management (mock Google Drive + Apps Script)."""

import json
import os
import re
import shutil
import uuid
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from .utils.log_decorator import log_mcp_call

load_dotenv()

TEMPLATE_DIR = os.getenv("TEMPLATE_DIR", "data/templates")
GENERATED_DIR = os.getenv("GENERATED_DIR", "data/generated")


@log_mcp_call("tool", "list_templates")
def list_templates() -> list[dict[str, Any]]:
    """List all available document templates (mock Google Drive folder scan).

    Returns:
        List of dicts with id, name, description for each template.
    """
    catalog_path = os.path.join(TEMPLATE_DIR, "template_catalog.json")
    with open(catalog_path, "r", encoding="utf-8") as f:
        return json.load(f)


@log_mcp_call("tool", "get_template_metadata")
def get_template_metadata(template_id: str) -> dict[str, Any]:
    """Get metadata for a template: placeholders and conditional blocks.

    Args:
        template_id: The template ID (e.g. 'tpl_001').

    Returns:
        dict with 'metadata' containing title, placeholders[], conditionals[].
    """
    tpl_path = os.path.join(TEMPLATE_DIR, f"{template_id}.json")
    if not os.path.exists(tpl_path):
        return {"status": "ERROR", "message": f"Template '{template_id}' not found."}
    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = json.load(f)
    return {
        "status": "OK",
        "metadata": {
            "title": tpl["name"],
            "placeholders": tpl["placeholders"],
            "conditionals": tpl["conditionals"],
        },
    }


@log_mcp_call("tool", "copy_template")
def copy_template(template_id: str, title: str) -> dict[str, Any]:
    """Copy a template to the generated folder to create a working copy.

    Args:
        template_id: Source template ID.
        title: Title for the new document copy.

    Returns:
        dict with new_doc_id and title.
    """
    tpl_path = os.path.join(TEMPLATE_DIR, f"{template_id}.json")
    if not os.path.exists(tpl_path):
        return {"status": "ERROR", "message": f"Template '{template_id}' not found."}
    os.makedirs(GENERATED_DIR, exist_ok=True)
    new_id = f"doc_{uuid.uuid4().hex[:8]}"
    dest_path = os.path.join(GENERATED_DIR, f"{new_id}.json")
    shutil.copy2(tpl_path, dest_path)
    # Update the copied file with new id and title
    with open(dest_path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    doc["id"] = new_id
    doc["original_template_id"] = template_id
    doc["copy_title"] = title
    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    return {"status": "OK", "id": new_id, "name": title}


@log_mcp_call("tool", "fill_document")
def fill_document(doc_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Fill a copied document with user data, replacing placeholders and handling conditionals.

    Args:
        doc_id: The copied document ID.
        data: dict with placeholder values and 'blocks' for conditional sections.

    Returns:
        dict with status ('OK' or 'ERROR'), and optionally missing/unknown lists.
    """
    doc_path = os.path.join(GENERATED_DIR, f"{doc_id}.json")
    if not os.path.exists(doc_path):
        return {"status": "ERROR", "message": f"Document '{doc_id}' not found."}

    with open(doc_path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    content: str = doc["content"]
    placeholders: list[str] = doc["placeholders"]
    conditionals: list[dict] = doc.get("conditionals", [])
    blocks: dict = data.get("blocks", {})

    # Check for missing mandatory placeholders
    missing = [p for p in placeholders if p not in data]
    if missing:
        return {"status": "ERROR", "message": "Placeholder validation failed", "missing": missing}

    # Check for unknown keys (not in placeholders or blocks)
    known_keys = set(placeholders) | {"blocks"}
    unknown = [k for k in data if k not in known_keys]
    if unknown:
        return {"status": "ERROR", "message": "Unknown placeholders found", "unknown": unknown}

    # Process conditional blocks
    for cond in conditionals:
        flag = cond["flag"]
        block_data = blocks.get(flag, {})
        include = block_data.get("include", False)
        start_tag = f"[[{flag}:START]]"
        end_tag = f"[[{flag}:END]]"
        if start_tag in content and end_tag in content:
            if include:
                # Fill inner placeholders and keep block content (strip tags)
                inner_ph = cond.get("placeholders", [])
                missing_inner = [p for p in inner_ph if p not in block_data]
                if missing_inner:
                    return {
                        "status": "ERROR",
                        "message": "Placeholder validation failed",
                        "missing": missing_inner,
                    }
                inner_pattern = re.compile(
                    re.escape(start_tag) + r"\n?(.*?)\n?" + re.escape(end_tag),
                    re.DOTALL,
                )
                def replace_inner(m: re.Match) -> str:
                    inner = m.group(1)
                    for p in inner_ph:
                        inner = inner.replace(f"{{{{{p}}}}}", str(block_data[p]))
                    return inner
                content = inner_pattern.sub(replace_inner, content)
            else:
                # Remove entire block including tags
                block_pattern = re.compile(
                    r"\n?" + re.escape(start_tag) + r".*?" + re.escape(end_tag) + r"\n?",
                    re.DOTALL,
                )
                content = block_pattern.sub("", content)

    # Replace all static placeholders
    for key, value in data.items():
        if key != "blocks":
            content = content.replace(f"{{{{{key}}}}}", str(value))

    # Check for any unfilled placeholders
    remaining = re.findall(r"\{\{(\w+)\}\}", content)
    if remaining:
        return {"status": "ERROR", "message": "Placeholder validation failed", "missing": remaining}

    # Save filled content
    doc["filled_content"] = content
    doc["filled_at"] = datetime.now().isoformat()
    with open(doc_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)

    # Also write as plain text
    txt_path = os.path.join(GENERATED_DIR, f"{doc_id}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {"status": "OK", "doc_id": doc_id, "message": "Document filled successfully."}


@log_mcp_call("tool", "generate_download_link")
def generate_download_link(doc_id: str) -> dict[str, Any]:
    """Generate a local download link for the filled document.

    Args:
        doc_id: The filled document ID.

    Returns:
        dict with download_link (local file path) and google_doc_link (mock).
    """
    txt_path = os.path.abspath(os.path.join(GENERATED_DIR, f"{doc_id}.txt"))
    if not os.path.exists(txt_path):
        return {"status": "ERROR", "message": f"Document '{doc_id}' not filled yet."}
    return {
        "status": "OK",
        "download_link": txt_path,
        "google_doc_link": f"ENDPOINT_PLACEHOLDER",
    }
