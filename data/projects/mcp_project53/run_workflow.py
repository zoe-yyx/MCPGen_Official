"""
run_workflow.py — Legal & Compliance Document Archiving
========================================================
Orchestrates the full n8n workflow using fastmcp Client.

Workflow steps (mirroring n8n node chain):
  1. tool_validate_and_enrich       — sanitise inputs, build structured filename
  2. tool_check_duplicate           — halt with 409 if contract already filed
  3. tool_upload_to_cdn             — stage file, obtain CDN URL
  4. tool_find_or_create_folder     — resolve/create storage folder
  5. tool_upload_document           — copy file to storage folder
  6. tool_find_employee_record      — look up existing Airtable record
  7. tool_upsert_employee_record    — create or update the record
  8. tool_send_confirmation_email   — notify HR (+ employee)
  9. tool_build_final_response      — assemble audit summary

Run with:
    uv run python run_workflow.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client

from mcp_server.tools.utils.logging_decorator import setup_logging

load_dotenv()
logger = setup_logging("logs/workflow.log", console_output=True)

# ── Demo payload (mirrors the n8n example webhook body) ───────────────────────
DEMO_PAYLOAD = {
    "employee_name": "Sarah Johnson",
    "file_url": None,                       # set to None → use local file_path below
    "filename": "contract-signed.pdf",
    "employee_id": "EMP-0042",
    "employee_email": "EMAIL_PLACEHOLDER",
    "contract_type": "Full-Time Employment",
    "department": "Engineering",
    "effective_date": "2025-03-01",
    "notify_employee": True,
    "filed_by": "HR System",
}

# For binary upload demo: place a real PDF here or the workflow will create a stub
DEMO_FILE_PATH = "results/outputs/sample_contract.pdf"


def _ensure_demo_file() -> None:
    """Create a minimal stub PDF if no real file is present."""
    p = Path(DEMO_FILE_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_bytes(
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n%%EOF\n"
        )
        logger.info("Created stub PDF at %s", DEMO_FILE_PATH)


async def run_archive_workflow(payload: dict, file_path: str) -> dict:
    """
    Execute the full contract archiving workflow via MCP tool calls.

    Args:
        payload: Webhook-style input dict.
        file_path: Local path to the document file.

    Returns:
        Final archiving summary dict.
    """
    async with Client("mcp_server/server.py") as client:

        logger.info("=" * 60)
        logger.info("STEP 0 — Available tools")
        tools = await client.list_tools()
        for t in tools:
            logger.info("  • %s", t.name)

        # ── STEP 1: Validate & Enrich ──────────────────────────────────────────
        logger.info("-" * 60)
        logger.info("STEP 1 — Validate & Enrich Payload")
        result = await client.call_tool("tool_validate_and_enrich", {
            "employee_name":   payload["employee_name"],
            "file_url":        payload.get("file_url"),
            "filename":        payload.get("filename"),
            "employee_id":     payload.get("employee_id"),
            "employee_email":  payload.get("employee_email", ""),
            "contract_type":   payload.get("contract_type", "Employment Contract"),
            "department":      payload.get("department", "General"),
            "effective_date":  payload.get("effective_date"),
            "notify_employee": payload.get("notify_employee", True),
            "filed_by":        payload.get("filed_by", "HR System"),
        })
        meta = json.loads(result.content[0].text)
        logger.info("Structured filename: %s", meta["structuredFilename"])
        logger.info("Drive folder path:   %s", meta["driveFolderPath"])

        # ── STEP 2: Duplicate Check ────────────────────────────────────────────
        logger.info("-" * 60)
        logger.info("STEP 2 — Duplicate Check")
        result = await client.call_tool("tool_check_duplicate", {
            "employee_id": meta["employeeId"],
        })
        dup_data = json.loads(result.content[0].text)
        if dup_data["isDuplicate"]:
            existing = dup_data["existingRecord"]
            logger.warning(
                "409 CONFLICT — Contract already filed for %s (%s). "
                "Existing URL: %s | Filed at: %s",
                meta["employeeName"],
                meta["employeeId"],
                existing.get("contractUrl"),
                existing.get("filedAt"),
            )
            return {
                "success": False,
                "conflict": True,
                "message": (
                    f"A contract for {meta['employeeName']} ({meta['employeeId']}) "
                    f"is already filed."
                ),
                "existingContractUrl": existing.get("contractUrl"),
                "filedAt": existing.get("filedAt"),
            }
        logger.info("No duplicate found — proceeding.")

        # ── STEP 3: Upload to CDN ──────────────────────────────────────────────
        logger.info("-" * 60)
        logger.info("STEP 3 — Upload to CDN (local staging)")
        result = await client.call_tool("tool_upload_to_cdn", {
            "file_path":           file_path,
            "file_url":            meta.get("fileUrl"),
            "structured_filename": meta["structuredFilename"],
        })
        cdn_data = json.loads(result.content[0].text)
        logger.info("CDN URL:      %s", cdn_data["cdnUrl"])
        logger.info("Upload ID:    %s", cdn_data["uploadId"])

        # ── STEP 4: Find/Create Storage Folder ────────────────────────────────
        logger.info("-" * 60)
        logger.info("STEP 4 — Resolve storage folder")
        result = await client.call_tool("tool_find_or_create_folder", {
            "drive_folder_path": meta["driveFolderPath"],
        })
        folder_data = json.loads(result.content[0].text)
        logger.info(
            "Folder: %s (created=%s)", folder_data["folderPath"], folder_data["created"]
        )

        # ── STEP 5: Upload Document to Folder ─────────────────────────────────
        logger.info("-" * 60)
        logger.info("STEP 5 — Upload document to storage folder")
        result = await client.call_tool("tool_upload_document", {
            "source_path":         file_path,
            "structured_filename": meta["structuredFilename"],
            "folder_path":         folder_data["folderPath"],
            "mime_type":           meta["mimeType"],
        })
        drive_data = json.loads(result.content[0].text)
        logger.info("Drive File ID: %s", drive_data["driveFileId"])
        logger.info("Drive URL:     %s", drive_data["driveUrl"])

        # ── STEP 6: Find Employee Record ───────────────────────────────────────
        logger.info("-" * 60)
        logger.info("STEP 6 — Look up employee record")
        result = await client.call_tool("tool_find_employee_record", {
            "employee_id": meta["employeeId"],
        })
        emp_data = json.loads(result.content[0].text)
        logger.info(
            "Record exists: %s  (ID: %s)", emp_data["recordExists"], emp_data["recordId"]
        )

        # ── STEP 7: Upsert Record ──────────────────────────────────────────────
        logger.info("-" * 60)
        logger.info("STEP 7 — Upsert employee contract record")
        result = await client.call_tool("tool_upsert_employee_record", {
            "employee_id":        meta["employeeId"],
            "employee_name":      meta["employeeName"],
            "department":         meta["department"],
            "contract_type":      meta["contractType"],
            "effective_date":     meta["effectiveDate"],
            "drive_url":          drive_data["driveUrl"],
            "cdn_backup_url":     cdn_data["cdnUrl"],
            "drive_folder_path":  meta["driveFolderPath"],
            "structured_filename": meta["structuredFilename"],
            "filed_by":           meta["filedBy"],
            "filed_at":           meta["filedAt"],
            "record_id":          emp_data.get("recordId"),
        })
        upsert_data = json.loads(result.content[0].text)
        logger.info(
            "Airtable record %s (operation: %s)",
            upsert_data["id"], upsert_data["operation"],
        )

        # ── STEP 8: Send Confirmation Email ────────────────────────────────────
        logger.info("-" * 60)
        logger.info("STEP 8 — Send confirmation email")
        result = await client.call_tool("tool_send_confirmation_email", {
            "employee_name":      meta["employeeName"],
            "employee_id":        meta["employeeId"],
            "employee_email":     meta["employeeEmail"],
            "department":         meta["department"],
            "contract_type":      meta["contractType"],
            "effective_date":     meta["effectiveDate"],
            "structured_filename": meta["structuredFilename"],
            "drive_url":          drive_data["driveUrl"],
            "cdn_backup_url":     cdn_data["cdnUrl"],
            "filed_by":           meta["filedBy"],
            "filed_at":           meta["filedAt"],
            "notify_employee":    meta["notifyEmployee"],
            "hr_email":           os.getenv("HR_EMAIL"),
            "smtp_host":          os.getenv("SMTP_HOST"),
            "smtp_port":          int(os.getenv("SMTP_PORT", "587")),
            "smtp_user":          os.getenv("SMTP_USER"),
            "smtp_password":      os.getenv("SMTP_PASSWORD"),
        })
        email_data = json.loads(result.content[0].text)
        logger.info("Email method: %s | sent to: %s", email_data["method"], email_data["emailsSent"])
        logger.info("Email file: %s", email_data["emailFile"])

        # ── STEP 9: Build Final Response ───────────────────────────────────────
        logger.info("-" * 60)
        logger.info("STEP 9 — Build final response")
        result = await client.call_tool("tool_build_final_response", {
            "employee_id":        meta["employeeId"],
            "employee_name":      meta["employeeName"],
            "department":         meta["department"],
            "structured_filename": meta["structuredFilename"],
            "contract_type":      meta["contractType"],
            "effective_date":     meta["effectiveDate"],
            "drive_file_id":      drive_data["driveFileId"],
            "drive_url":          drive_data["driveUrl"],
            "drive_folder_path":  meta["driveFolderPath"],
            "cdn_backup_url":     cdn_data["cdnUrl"],
            "airtable_record_id": upsert_data["id"],
            "filed_by":           meta["filedBy"],
            "filed_at":           meta["filedAt"],
            "upload_id":          cdn_data.get("uploadId"),
            "file_size_bytes":    cdn_data.get("fileSizeBytes"),
        })
        final = json.loads(result.content[0].text)
        logger.info("=" * 60)
        logger.info("✅ WORKFLOW COMPLETE")
        logger.info(json.dumps(final, indent=2, ensure_ascii=False))
        return final


if __name__ == "__main__":
    _ensure_demo_file()

    try:
        summary = asyncio.run(run_archive_workflow(DEMO_PAYLOAD, DEMO_FILE_PATH))
        if summary.get("success"):
            print("\n✅ Contract archived successfully!")
            print(f"   File:    {summary['structuredFilename']}")
            print(f"   Storage: {summary['driveUrl']}")
            print(f"   Record:  {summary['airtableRecordId']}")
        else:
            print("\n  Workflow halted:", summary.get("message"))
    except Exception as exc:
        logger.exception("Workflow failed: %s", exc)
        sys.exit(1)