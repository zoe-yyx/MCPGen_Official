"""Unit tests for DocAgent tool functions (no MCP dependency)."""

import json
import os
import sys
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Point to the actual data dir for template tests
os.environ.setdefault("TEMPLATE_DIR", "data/templates")
os.environ.setdefault("GENERATED_DIR", "data/generated")

from mcp_server.tools.template_tools import (
    list_templates,
    get_template_metadata,
    copy_template,
    fill_document,
    generate_download_link,
)
from mcp_server.tools.doc_process_tools import formatting_correction


# ── Template tool tests ──────────────────────────────────────────


def test_list_templates():
    templates = list_templates()
    assert isinstance(templates, list)
    assert len(templates) >= 2
    ids = [t["id"] for t in templates]
    assert "tpl_001" in ids
    assert "tpl_002" in ids


def test_get_template_metadata_valid():
    result = get_template_metadata("tpl_001")
    assert result["status"] == "OK"
    meta = result["metadata"]
    assert "SELLER_NAME" in meta["placeholders"]
    assert any(c["flag"] == "MANDATE_INSTALLMENT" for c in meta["conditionals"])


def test_get_template_metadata_invalid():
    result = get_template_metadata("tpl_999")
    assert result["status"] == "ERROR"


def test_copy_template(tmp_path, monkeypatch):
    import mcp_server.tools.template_tools as tt
    monkeypatch.setattr(tt, "GENERATED_DIR", str(tmp_path))
    result = copy_template("tpl_001", "Test Document")
    assert result["status"] == "OK"
    assert result["id"].startswith("doc_")
    assert os.path.exists(os.path.join(str(tmp_path), f"{result['id']}.json"))


def test_fill_document_success(tmp_path, monkeypatch):
    import mcp_server.tools.template_tools as tt
    monkeypatch.setattr(tt, "GENERATED_DIR", str(tmp_path))

    copy_result = copy_template("tpl_001", "Test Fill")
    doc_id = copy_result["id"]

    data = {
        "SELLER_NAME": "Alice",
        "BUYER_NAME": "Bob",
        "PRODUCT_NAME": "Laptop",
        "PRICE": "10000",
        "DELIVER_DATE": "01.06.2026",
        "TODAY_DATE": "18.05.2026",
        "blocks": {
            "MANDATE_INSTALLMENT": {"include": False},
            "GUARANTEE": {"include": True, "GUARANTEE_PERIOD": "12"},
        },
    }
    result = fill_document(doc_id, data)
    assert result["status"] == "OK"

    txt_path = os.path.join(str(tmp_path), f"{doc_id}.txt")
    assert os.path.exists(txt_path)
    content = open(txt_path, encoding="utf-8").read()
    assert "Alice" in content
    assert "Laptop" in content
    assert "12 aylık garanti" in content
    assert "TAKSİT" not in content  # block excluded


def test_fill_document_missing_placeholder(tmp_path, monkeypatch):
    import mcp_server.tools.template_tools as tt
    monkeypatch.setattr(tt, "GENERATED_DIR", str(tmp_path))

    copy_result = copy_template("tpl_001", "Test Missing")
    doc_id = copy_result["id"]

    data = {
        "SELLER_NAME": "Alice",
        # Missing all others
    }
    result = fill_document(doc_id, data)
    assert result["status"] == "ERROR"
    assert "missing" in result


def test_fill_document_conditional_include(tmp_path, monkeypatch):
    import mcp_server.tools.template_tools as tt
    monkeypatch.setattr(tt, "GENERATED_DIR", str(tmp_path))

    copy_result = copy_template("tpl_001", "Test Conditional")
    doc_id = copy_result["id"]

    data = {
        "SELLER_NAME": "X",
        "BUYER_NAME": "Y",
        "PRODUCT_NAME": "Car",
        "PRICE": "500000",
        "DELIVER_DATE": "01.01.2027",
        "TODAY_DATE": "18.05.2026",
        "blocks": {
            "MANDATE_INSTALLMENT": {
                "include": True,
                "INSTALLMENT_PLAN": "10 x 50000 TL",
            },
            "GUARANTEE": {"include": False},
        },
    }
    result = fill_document(doc_id, data)
    assert result["status"] == "OK"
    txt = open(os.path.join(str(tmp_path), f"{doc_id}.txt"), encoding="utf-8").read()
    assert "10 x 50000 TL" in txt
    assert "GARANTİ" not in txt


def test_generate_download_link_not_filled(tmp_path, monkeypatch):
    import mcp_server.tools.template_tools as tt
    monkeypatch.setattr(tt, "GENERATED_DIR", str(tmp_path))
    result = generate_download_link("nonexistent_doc")
    assert result["status"] == "ERROR"


# ── doc_process_tools tests ──────────────────────────────────────


def test_formatting_correction_plain_json():
    raw = '{"docId": "doc_abc", "data": {"NAME": "Alice"}}'
    result = formatting_correction(raw)
    assert result["docId"] == "doc_abc"
    assert result["data"]["NAME"] == "Alice"


def test_formatting_correction_markdown_json():
    raw = '```json\n{"docId": "doc_xyz", "data": {"KEY": "val"}}\n```'
    result = formatting_correction(raw)
    assert result["docId"] == "doc_xyz"


def test_formatting_correction_invalid():
    with pytest.raises(json.JSONDecodeError):
        formatting_correction("not valid json")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
