"""
Storage tools — local filesystem replacement for Airtable + Google Drive.

n8n nodes replaced:
  • Airtable - Duplicate Check          → tool_check_duplicate
  • Airtable - Find Employee Record     → tool_find_employee_record
  • Airtable - Update Existing Record   → tool_upsert_employee_record
  • Airtable - Create New Record        → tool_upsert_employee_record  (same function, create path)
  • Drive - Find Employee Folder        → tool_find_or_create_folder
  • Drive - Create Employee Folder      → (handled inside tool_find_or_create_folder)
  • Drive - Upload Document             → tool_upload_document

All data is persisted in:
  results/outputs/contracts/       ← uploaded document files
  results/outputs/airtable.json    ← employee contract records (append-only JSON list)
"""
import json
import shutil
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .utils.logging_decorator import setup_logging, log_tool_call

logger = setup_logging("logs/server.log", console_output=False)

# ── Storage paths ──────────────────────────────────────────────────────────────
_RESULTS_DIR = Path("results/outputs")
_DB_FILE = _RESULTS_DIR / "airtable.json"
_CONTRACTS_DIR = _RESULTS_DIR / "contracts"


def _load_db() -> list[dict]:
    _DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _DB_FILE.exists():
        return []
    return json.loads(_DB_FILE.read_text(encoding="utf-8"))


def _save_db(records: list[dict]) -> None:
    _DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DB_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# Duplicate Check
# ──────────────────────────────────────────────────────────────────────────────

@log_tool_call(logger)
def tool_check_duplicate(employee_id: str) -> str:
    """
    Check whether a contract is already on file for the given employee.

    Maps to: Airtable - Duplicate Check

    Args:
        employee_id: Normalised HR employee ID (e.g. "EMP-0042").

    Returns:
        JSON string: {"isDuplicate": bool, "existingRecord": dict | null}
    """
    records = _load_db()
    match = next(
        (r for r in records
         if r.get("employeeId", "").upper() == employee_id.upper()
         and r.get("contractReceived") is True),
        None,
    )
    return json.dumps({
        "isDuplicate": match is not None,
        "existingRecord": match,
    }, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Drive folder management
# ──────────────────────────────────────────────────────────────────────────────

@log_tool_call(logger)
def tool_find_or_create_folder(drive_folder_path: str) -> str:
    """
    Resolve (or create) the local folder that mirrors a Google Drive path.

    Maps to: Drive - Find Employee Folder + Drive - Create Employee Folder + Merge Folder ID

    Args:
        drive_folder_path: Logical path e.g. "HR/Contracts/2025/Engineering/Sarah Johnson".

    Returns:
        JSON string: {"folderId": str, "folderPath": str, "created": bool}
    """
    target = _CONTRACTS_DIR / drive_folder_path
    created = not target.exists()
    target.mkdir(parents=True, exist_ok=True)

    # Use a deterministic "ID" based on the path (stable across runs)
    folder_id = hashlib.md5(str(target.resolve()).encode()).hexdigest()[:16]

    return json.dumps({
        "folderId": folder_id,
        "folderPath": str(target),
        "created": created,
    }, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Document upload
# ──────────────────────────────────────────────────────────────────────────────

@log_tool_call(logger)
def tool_upload_document(
    source_path: str,
    structured_filename: str,
    folder_path: str,
    mime_type: str = "application/pdf",
) -> str:
    """
    Copy a document into the resolved local folder, simulating Drive upload.

    Maps to: Drive - Upload Document

    Args:
        source_path: Absolute or relative path to the source file.
        structured_filename: The canonical filename to store the file as.
        folder_path: Absolute path of the target folder (from tool_find_or_create_folder).
        mime_type: MIME type of the document (informational only for local storage).

    Returns:
        JSON string: {"driveFileId": str, "driveUrl": str, "storedPath": str,
                      "fileSizeBytes": int}
    """
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    dest_dir = Path(folder_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / structured_filename

    shutil.copy2(src, dest)

    file_id = hashlib.md5(str(dest.resolve()).encode()).hexdigest()[:16]
    drive_url = f"file://{dest.resolve()}"

    return json.dumps({
        "driveFileId": file_id,
        "driveUrl": drive_url,
        "storedPath": str(dest),
        "fileSizeBytes": dest.stat().st_size,
        "mimeType": mime_type,
    }, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Airtable record management
# ──────────────────────────────────────────────────────────────────────────────

@log_tool_call(logger)
def tool_find_employee_record(employee_id: str) -> str:
    """
    Look up an employee record by ID.

    Maps to: Airtable - Find Employee Record

    Args:
        employee_id: Normalised HR employee ID.

    Returns:
        JSON string: {"recordId": str | null, "recordExists": bool, "record": dict | null}
    """
    records = _load_db()
    match = next(
        (r for r in records if r.get("employeeId", "").upper() == employee_id.upper()),
        None,
    )
    return json.dumps({
        "recordId": match.get("id") if match else None,
        "recordExists": match is not None,
        "record": match,
    }, ensure_ascii=False)


@log_tool_call(logger)
def tool_upsert_employee_record(
    employee_id: str,
    employee_name: str,
    department: str,
    contract_type: str,
    effective_date: str,
    drive_url: str,
    cdn_backup_url: str,
    drive_folder_path: str,
    structured_filename: str,
    filed_by: str,
    filed_at: str,
    record_id: Optional[str] = None,
) -> str:
    """
    Insert or update an employee contract record in local storage (mirrors Airtable).

    Maps to: Airtable - Update Existing Record  /  Airtable - Create New Record

    Args:
        employee_id: Normalised HR employee ID.
        employee_name: Full name (title-cased).
        department: Department string.
        contract_type: Human-readable contract type.
        effective_date: Contract effective date (YYYY-MM-DD).
        drive_url: Shareable Drive / local file URL.
        cdn_backup_url: CDN backup URL (from upload step).
        drive_folder_path: Logical folder path string.
        structured_filename: Canonical filename.
        filed_by: Submitter identifier.
        filed_at: ISO-8601 filing timestamp.
        record_id: Existing record ID to update; None → create new.

    Returns:
        JSON string: {"id": str, "operation": "updated" | "created", "fields": dict}
    """
    records = _load_db()

    fields = {
        "employeeId": employee_id.upper(),
        "employeeName": employee_name,
        "department": department,
        "contractType": contract_type,
        "effectiveDate": effective_date,
        "contractUrl": drive_url,
        "cdnBackupUrl": cdn_backup_url,
        "driveFolderPath": drive_folder_path,
        "structuredFilename": structured_filename,
        "filedBy": filed_by,
        "filedAt": filed_at,
        "contractReceived": True,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    operation = "created"
    if record_id:
        for rec in records:
            if rec.get("id") == record_id:
                rec.update(fields)
                operation = "updated"
                break
        else:
            # record_id given but not found → create
            fields["id"] = record_id
            records.append(fields)
    else:
        # Check if same employee already exists (create-or-update by employee_id)
        existing = next(
            (r for r in records if r.get("employeeId", "").upper() == employee_id.upper()),
            None,
        )
        if existing:
            existing.update(fields)
            record_id = existing["id"]
            operation = "updated"
        else:
            new_id = hashlib.md5(f"{employee_id}{filed_at}".encode()).hexdigest()[:16]
            fields["id"] = new_id
            records.append(fields)
            record_id = new_id

    _save_db(records)

    return json.dumps({
        "id": record_id or fields.get("id"),
        "operation": operation,
        "fields": fields,
    }, ensure_ascii=False)