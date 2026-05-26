"""
Run the DocAgent document generation workflow via MCP client.

Simulates a full user interaction:
  - User selects SATIŞ SÖZLEŞMESİ (Sales Contract)
  - Provides all placeholder values
  - Confirms conditional blocks
  - Gets a generated document download link
"""

import asyncio
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from fastmcp import Client

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_server.tools.utils.log_decorator import setup_logging

load_dotenv()
logger = setup_logging("logs/workflow.log")


def _parse(result) -> dict | list | str:
    """Extract and parse MCP tool result."""
    text = ""
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                text = block.text
                break
    elif hasattr(result, "data"):
        text = str(result.data)
    else:
        text = str(result)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


async def main() -> None:
    logger.info("=" * 60)
    logger.info("DocAgent Workflow Start")
    logger.info("=" * 60)

    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info(f"Available tools: {[t.name for t in tools]}")

        # ── Step 1: List templates ───────────────────────────────
        logger.info("\n--- Step 1: List templates ---")
        result = await client.call_tool("list_templates", {})
        catalog = _parse(result)
        logger.info(f"Templates: {json.dumps(catalog, ensure_ascii=False)}")

        # ── Step 2: Get metadata for SATIŞ SÖZLEŞMESİ ──────────
        logger.info("\n--- Step 2: Get template metadata ---")
        result = await client.call_tool("get_template_metadata", {"template_id": "tpl_001"})
        meta_result = _parse(result)
        metadata = meta_result.get("metadata", {})
        logger.info(f"Metadata: {json.dumps(metadata, ensure_ascii=False)}")

        # ── Step 3: Verify user choice via LLM ──────────────────
        logger.info("\n--- Step 3: Verify user choice ---")
        result = await client.call_tool(
            "verify_user_choice",
            {
                "user_choice_name": "SATIŞ SÖZLEŞMESİ",
                "user_choice_id": "tpl_001",
                "template_catalog": catalog,
            },
        )
        verify = _parse(result)
        logger.info(f"Verification result: {verify}")

        if not verify.get("eslesme", False):
            logger.error(f"Template name-ID mismatch! correct_id={verify.get('correct_id')}")
            return

        # ── Step 4: Format user data via LLM ────────────────────
        logger.info("\n--- Step 4: Format user data ---")
        today = datetime.now().strftime("%d.%m.%Y")
        user_answers = {
            "seller": "Ahmet Yılmaz",
            "buyer": "Mehmet Kaya",
            "product": "Dizüstü Bilgisayar",
            "price": "25000",
            "delivery_date": "30.05.2026",
            "today": today,
            "installment": "yes, 5 equal monthly installments of 5000 TL",
            "warranty": "yes, 24 months",
        }

        # Copy template first (needed for doc_id in format_user_data)
        logger.info("\n--- Step 5: Copy template ---")
        copy_title = f"{today} tarihli SATIŞ SÖZLEŞMESİ belgesi"
        result = await client.call_tool(
            "copy_template",
            {"template_id": "tpl_001", "title": copy_title},
        )
        copy_result = _parse(result)
        doc_id = copy_result.get("id", "")
        logger.info(f"Copied document ID: {doc_id}")

        # Now format data with the real doc_id
        result = await client.call_tool(
            "format_user_data",
            {
                "doc_id": doc_id,
                "metadata": metadata,
                "user_answers": user_answers,
            },
        )
        formatted = _parse(result)
        logger.info(f"Formatted data: {json.dumps(formatted, ensure_ascii=False, indent=2)}")

        # ── Step 6: Fill document ────────────────────────────────
        logger.info("\n--- Step 6: Fill document ---")
        fill_data = formatted.get("data", formatted)
        result = await client.call_tool(
            "fill_document",
            {"doc_id": doc_id, "data": fill_data},
        )
        fill_result = _parse(result)
        logger.info(f"Fill result: {fill_result}")

        if fill_result.get("status") != "OK":
            logger.error(f"Fill failed: {fill_result}")
            return

        # ── Step 7: Generate download link ───────────────────────
        logger.info("\n--- Step 7: Generate download link ---")
        result = await client.call_tool("generate_download_link", {"doc_id": doc_id})
        link_result = _parse(result)
        logger.info(f"Download link: {link_result}")

        # ── Save summary ─────────────────────────────────────────
        os.makedirs("results/outputs", exist_ok=True)
        summary = {
            "status": "completed",
            "template": "SATIŞ SÖZLEŞMESİ",
            "doc_id": doc_id,
            "download_link": link_result.get("download_link", ""),
            "google_doc_link": link_result.get("google_doc_link", ""),
        }
        with open("results/outputs/workflow_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logger.info("\n" + "=" * 60)
        logger.info("DocAgent Workflow Complete!")
        logger.info(f"  Document: {summary['template']}")
        logger.info(f"  Doc ID  : {doc_id}")
        logger.info(f"  Download: {link_result.get('download_link','')}")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
