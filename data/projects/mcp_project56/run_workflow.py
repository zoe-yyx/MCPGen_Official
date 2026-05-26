"""
run_workflow.py — Chat with PDF/MD/Text Files using GraphRAG

Replicates the n8n workflow execution order:

  Flow 1 — Document Ingestion:
    Manual Trigger
         |
    [Step 1] Search Google Drive     -> search_local_files (mock: local folder)
         |
    [Loop over each file]
         |
    [Step 2] Retrieve File           -> retrieve_file
         |
    [Step 3] Switch (MIME type)      -> detect_file_type
         |
    [Step 4] Extract Text            -> extract_pdf_text / extract_text_file / extract_markdown_file
         |
    [Step 5] Map to Text             -> map_to_text
         |
    [Step 6] Save to Graph           -> save_to_graph (mock InfraNodus)
         |
    [next file in loop]

  Flow 2 — Chat with Documents:
    [Step 7] Clear Memory            -> clear_memory
         |
    [Step 8] Chat with KB            -> chat_with_knowledge_base (OpenAI + GraphRAG)

Run:
    uv run python run_workflow.py
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client

from mcp_server.tools.utils.log_decorator import setup_logging

load_dotenv()
logger = setup_logging("logs/workflow.log")

GRAPH_NAME = "graphrag_from_google_drive"
DATA_FOLDER = os.getenv("DATA_FOLDER", "data")
GRAPH_STORE_PATH = os.getenv("GRAPH_STORE_PATH", "results/outputs/graph_store.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(result) -> dict:
    """Extract dict from a fastmcp CallToolResult."""
    raw = result.content[0].text
    return json.loads(raw)


def _parse_text(result) -> str:
    """Extract plain text from a fastmcp CallToolResult."""
    return result.content[0].text


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

async def run_workflow() -> None:
    logger.info(f"{'=' * 60}")
    logger.info(f"  Chat with PDF/MD/Text Files using GraphRAG")
    logger.info(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Data folder: {DATA_FOLDER}")
    logger.info(f"  Graph store: {GRAPH_STORE_PATH}")
    logger.info(f"{'=' * 60}")

    async with Client("mcp_server/server.py") as client:

        # List available tools
        tools = await client.list_tools()
        logger.info(f"\nAvailable tools ({len(tools)}):")
        for tool in tools:
            logger.info(f"  - {tool.name}")

        # ==============================================================
        # FLOW 1: Document Ingestion
        # ==============================================================
        logger.info(f"\n{'=' * 60}")
        logger.info("FLOW 1: Document Ingestion")
        logger.info(f"{'=' * 60}")

        # ----------------------------------------------------------
        # Step 1 — Search local files (mock Google Drive Search)
        # ----------------------------------------------------------
        logger.info("\n[Step 1] Searching for files ...")
        result = await client.call_tool("search_local_files", {"folder_path": DATA_FOLDER})
        files = _parse(result)
        logger.info(f"  -> Found {len(files)} file(s)")

        if not files:
            logger.warning("  No files found — ingestion skipped.")
        else:
            # ----------------------------------------------------------
            # Loop over items (n8n: splitInBatches)
            # ----------------------------------------------------------
            ingestion_metrics: list[dict] = []

            for idx, file_info in enumerate(files, start=1):
                logger.info(f"\n{'─' * 50}")
                logger.info(f"[File {idx}/{len(files)}] {file_info['name']}")

                try:
                    # --------------------------------------------------
                    # Step 2 — Retrieve File (mock Google Drive Download)
                    # --------------------------------------------------
                    logger.info("  [Step 2] Retrieving file ...")
                    result = await client.call_tool("retrieve_file", {"file_path": file_info["id"]})
                    file_meta = _parse(result)
                    mime_type = file_meta["mimeType"]
                    file_path = file_meta["path"]
                    logger.info(f"  -> {file_meta['name']} (MIME: {mime_type})")

                    # --------------------------------------------------
                    # Step 3 — Switch by MIME type
                    # --------------------------------------------------
                    logger.info("  [Step 3] Detecting file type ...")
                    result = await client.call_tool("detect_file_type", {"mime_type": mime_type})
                    file_type = _parse_text(result).strip().strip('"')
                    logger.info(f"  -> Type: {file_type}")

                    # --------------------------------------------------
                    # Step 4 — Extract text (PDF / Text / Markdown)
                    # --------------------------------------------------
                    logger.info("  [Step 4] Extracting text ...")
                    if file_type == "pdf":
                        result = await client.call_tool("extract_pdf_text", {"file_path": file_path})
                    elif file_type == "text":
                        result = await client.call_tool("extract_text_file", {"file_path": file_path})
                    elif file_type == "markdown":
                        result = await client.call_tool("extract_markdown_file", {"file_path": file_path})
                    else:
                        logger.warning(f"  -> Unsupported type '{file_type}', skipping.")
                        ingestion_metrics.append({"file": file_info["name"], "status": "skipped", "reason": f"unsupported type: {file_type}"})
                        continue
                    raw_text = _parse_text(result)
                    logger.info(f"  -> Extracted {len(raw_text)} chars")

                    # --------------------------------------------------
                    # Step 5 — Map to text (normalize)
                    # --------------------------------------------------
                    logger.info("  [Step 5] Normalizing text ...")
                    result = await client.call_tool("map_to_text", {"raw_text": raw_text})
                    cleaned_text = _parse_text(result)
                    logger.info(f"  -> Cleaned to {len(cleaned_text)} chars")

                    # --------------------------------------------------
                    # Step 6 — Save to graph (mock InfraNodus)
                    # --------------------------------------------------
                    logger.info("  [Step 6] Saving to graph ...")
                    result = await client.call_tool("save_to_graph", {
                        "graph_name": GRAPH_NAME,
                        "text": cleaned_text,
                        "category": f"filename: {file_info['name']}",
                        "store_path": GRAPH_STORE_PATH,
                    })
                    save_result = _parse(result)
                    logger.info(f"  -> Saved ({save_result['text_length']} chars) to graph '{save_result['graph_name']}'")

                    ingestion_metrics.append({
                        "file": file_info["name"],
                        "type": file_type,
                        "text_length": int(save_result["text_length"]),
                        "status": "success",
                    })

                except Exception as exc:
                    logger.error(f"  Failed for {file_info['name']}: {type(exc).__name__}: {exc}")
                    ingestion_metrics.append({"file": file_info["name"], "status": "error", "error": str(exc)})

            logger.info(f"\n{'─' * 50}")
            logger.info(f"Ingestion complete: {sum(1 for m in ingestion_metrics if m['status'] == 'success')}/{len(files)} files processed.")

        # ==============================================================
        # FLOW 2: Chat with Documents
        # ==============================================================
        logger.info(f"\n{'=' * 60}")
        logger.info("FLOW 2: Chat with Documents")
        logger.info(f"{'=' * 60}")

        # ----------------------------------------------------------
        # Step 7 — Clear memory
        # ----------------------------------------------------------
        logger.info("\n[Step 7] Clearing conversation memory ...")
        await client.call_tool("clear_memory", {})
        logger.info("  -> Memory cleared.")

        # ----------------------------------------------------------
        # Step 8 — Chat with knowledge base
        # ----------------------------------------------------------
        questions = [
            "What is GraphRAG and how does it work?",
            "What are the key concepts of knowledge graphs?",
        ]

        chat_results: list[dict] = []
        for q_idx, question in enumerate(questions, start=1):
            logger.info(f"\n[Step 8-{q_idx}] Chat query ...")
            logger.info(f"  User: {question}")
            result = await client.call_tool("chat_with_knowledge_base", {
                "user_message": question,
                "graph_name": GRAPH_NAME,
                "store_path": GRAPH_STORE_PATH,
            })
            answer = _parse_text(result)
            logger.info(f"  Assistant: {answer[:200]}...")
            chat_results.append({"question": question, "answer": answer})

        # ----------------------------------------------------------
        # Save results and metrics
        # ----------------------------------------------------------
        outputs_dir = Path("results/outputs")
        outputs_dir.mkdir(parents=True, exist_ok=True)

        with open(outputs_dir / "chat_results.json", "w", encoding="utf-8") as f:
            json.dump(chat_results, f, ensure_ascii=False, indent=2)

        metrics_path = Path("results/metrics/run_metrics.json")
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        run_summary = {
            "run_at": datetime.now().isoformat(),
            "total_files": len(files) if files else 0,
            "ingested": sum(1 for m in ingestion_metrics if m["status"] == "success") if files else 0,
            "chat_queries": len(chat_results),
            "ingestion_details": ingestion_metrics if files else [],
        }
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(run_summary, f, indent=2, ensure_ascii=False)

        logger.info(f"\n{'=' * 60}")
        logger.info(f"  Workflow complete.")
        logger.info(f"  Ingested: {run_summary['ingested']}/{run_summary['total_files']} files")
        logger.info(f"  Chat queries: {run_summary['chat_queries']}")
        logger.info(f"  Metrics: {metrics_path}")
        logger.info(f"  Chat results: {outputs_dir / 'chat_results.json'}")
        logger.info(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_workflow())
