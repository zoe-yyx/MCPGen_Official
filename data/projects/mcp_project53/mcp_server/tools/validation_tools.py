"""
Validation & enrichment tools.

Maps to n8n node: "Validate & Enrich Payload"
Normalises employee data, generates structured filename, builds Drive folder path.
"""
import re
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .utils.logging_decorator import setup_logging, log_tool_call

logger = setup_logging("logs/server.log", console_output=False)

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "docx", "tiff"}
MIME_MAP = {
    "pdf":  "application/pdf",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "png":  "image/png",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "tiff": "image/tiff",
}


def _normalise_name(raw: str) -> str:
    """Title-case, strip special chars, collapse whitespace."""
    cleaned = re.sub(r"[^a-zA-Z\s\-']", "", raw).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return " ".join(w.capitalize() for w in cleaned.split())


@log_tool_call(logger)
def tool_validate_and_enrich(
    employee_name: str,
    file_url: Optional[str] = None,
    filename: Optional[str] = None,
    employee_id: Optional[str] = None,
    employee_email: str = "",
    contract_type: str = "Employment Contract",
    department: str = "General",
    effective_date: Optional[str] = None,
    notify_employee: bool = True,
    filed_by: str = "HR System",
) -> str:
    """
    Validate incoming contract submission and enrich with derived metadata.

    Replicates n8n "Validate & Enrich Payload" code node.

    Args:
        employee_name: Full name of the employee (required).
        file_url: Remote URL of the document (mutually exclusive with filename).
        filename: Original filename for binary uploads.
        employee_id: HR employee identifier. Auto-generated if absent.
        employee_email: Employee's email address.
        contract_type: Type of contract (e.g. "Full-Time Employment").
        department: Department name (e.g. "Engineering").
        effective_date: Contract effective date (YYYY-MM-DD). Defaults to today.
        notify_employee: Whether to send confirmation email to the employee.
        filed_by: Name / system that triggered the filing.

    Returns:
        JSON string with enriched payload dict.

    Raises:
        ValueError: On missing required fields or unsupported file type.
    """
    # ── Required guards ────────────────────────────────────────────────────────
    if not employee_name or not employee_name.strip():
        raise ValueError("Missing required field: employeeName")
    if not file_url and not filename:
        raise ValueError(
            "Provide either file_url (remote document) or filename (binary upload)."
        )

    # ── Name normalisation ─────────────────────────────────────────────────────
    employee_name_norm = _normalise_name(employee_name)
    name_parts = employee_name_norm.split()
    last_name = name_parts[-1] if name_parts else employee_name_norm
    first_name = name_parts[0] if name_parts else ""

    # ── Employee ID ────────────────────────────────────────────────────────────
    emp_id_raw = (employee_id or "").upper()
    emp_id = re.sub(r"[^A-Z0-9\-]", "", emp_id_raw) or f"EMP-{int(datetime.now().timestamp())}"

    # ── Contract type slug ─────────────────────────────────────────────────────
    contract_type_slug = re.sub(r"[^a-zA-Z0-9\-]", "", contract_type.replace(" ", "-")).upper()

    # ── Date handling ──────────────────────────────────────────────────────────
    eff_date = effective_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filed_at = datetime.now(timezone.utc).isoformat()
    year_folder = eff_date.split("-")[0]

    # ── Filename & extension ───────────────────────────────────────────────────
    raw_filename = (
        filename
        or (file_url.split("?")[0].split("/")[-1] if file_url else None)
        or "document.pdf"
    )
    ext = (Path(raw_filename).suffix.lstrip(".") or "pdf").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"File type .{ext} not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    mime_type = MIME_MAP.get(ext, "application/octet-stream")

    structured_filename = (
        f"{emp_id}_{last_name.upper()}_{contract_type_slug}_{eff_date}.{ext}"
    )

    # ── Drive folder path ──────────────────────────────────────────────────────
    drive_folder_path = f"HR/Contracts/{year_folder}/{department}/{employee_name_norm}"

    payload = {
        "fileUrl": file_url,
        "originalFilename": raw_filename,
        "structuredFilename": structured_filename,
        "mimeType": mime_type,
        "ext": ext,
        "employeeName": employee_name_norm,
        "firstName": first_name,
        "lastName": last_name,
        "employeeId": emp_id,
        "employeeEmail": employee_email,
        "department": department,
        "contractType": contract_type,
        "contractTypeSlug": contract_type_slug,
        "effectiveDate": eff_date,
        "driveFolderPath": drive_folder_path,
        "yearFolder": year_folder,
        "notifyEmployee": notify_employee,
        "filedBy": filed_by,
        "filedAt": filed_at,
    }
    return json.dumps(payload, ensure_ascii=False)