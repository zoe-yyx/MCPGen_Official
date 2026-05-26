"""
CDN upload and notification tools.

n8n nodes replaced:
  • Upload to URL (Remote / Binary)  → tool_upload_to_cdn
  • Send Confirmation Email          → tool_send_confirmation_email
  • Build Final Response             → tool_build_final_response

Google Drive OAuth2 and Gmail are replaced with local filesystem + log-based email.
"""
import json
import hashlib
import shutil
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error
import os

from .utils.logging_decorator import setup_logging, log_tool_call

logger = setup_logging("logs/server.log", console_output=False)

_CDN_STAGING_DIR = Path("results/outputs/cdn_staging")


# ──────────────────────────────────────────────────────────────────────────────
# CDN Upload  (replaces "Upload to URL" community node)
# ──────────────────────────────────────────────────────────────────────────────

@log_tool_call(logger)
def tool_upload_to_cdn(
    file_path: Optional[str] = None,
    file_url: Optional[str] = None,
    structured_filename: str = "document.pdf",
) -> str:
    """
    Stage a file in local CDN storage and return a stable local URL.

    In production replace with real UploadToURL / S3 / Azure Blob call.
    Maps to: "Upload to URL - Remote" and "Upload to URL - Binary"

    Args:
        file_path: Local path to a binary file (binary upload path).
        file_url: Remote URL to download and re-host (remote URL path).
        structured_filename: Canonical filename to use for storage.

    Returns:
        JSON string: {"cdnUrl": str, "uploadId": str, "fileSizeBytes": int | null}
    """
    _CDN_STAGING_DIR.mkdir(parents=True, exist_ok=True)
    dest = _CDN_STAGING_DIR / structured_filename

    if file_path:
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")
        shutil.copy2(src, dest)
    elif file_url:
        try:
            with urllib.request.urlopen(file_url, timeout=30) as resp:  # noqa: S310
                dest.write_bytes(resp.read())
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Failed to download {file_url}: {exc}") from exc
    else:
        raise ValueError("Provide either file_path or file_url.")

    upload_id = hashlib.md5(str(dest.resolve()).encode()).hexdigest()[:16]
    cdn_url = f"file://{dest.resolve()}"
    size = dest.stat().st_size if dest.exists() else None

    return json.dumps({
        "cdnUrl": cdn_url,
        "uploadId": upload_id,
        "fileSizeBytes": size,
    }, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Confirmation Email  (replaces Gmail node)
# ──────────────────────────────────────────────────────────────────────────────

def _build_html_email(data: dict) -> str:
    return f"""
<html><body>
<h2>✅ Contract Filed Successfully</h2>
<table border="1" cellpadding="6" cellspacing="0">
  <tr><td><b>Employee</b></td><td>{data.get('employeeName')} ({data.get('employeeId')})</td></tr>
  <tr><td><b>Department</b></td><td>{data.get('department')}</td></tr>
  <tr><td><b>Contract Type</b></td><td>{data.get('contractType')}</td></tr>
  <tr><td><b>Effective Date</b></td><td>{data.get('effectiveDate')}</td></tr>
  <tr><td><b>Structured Filename</b></td><td>{data.get('structuredFilename')}</td></tr>
  <tr><td><b>Drive / Storage URL</b></td><td><a href="{data.get('driveUrl')}">{data.get('driveUrl')}</a></td></tr>
  <tr><td><b>CDN Backup URL</b></td><td><a href="{data.get('cdnBackupUrl')}">{data.get('cdnBackupUrl')}</a></td></tr>
  <tr><td><b>Filed By</b></td><td>{data.get('filedBy')}</td></tr>
  <tr><td><b>Filed At</b></td><td>{data.get('filedAt')}</td></tr>
</table>
</body></html>
"""


@log_tool_call(logger)
def tool_send_confirmation_email(
    employee_name: str,
    employee_id: str,
    employee_email: str,
    department: str,
    contract_type: str,
    effective_date: str,
    structured_filename: str,
    drive_url: str,
    cdn_backup_url: str,
    filed_by: str,
    filed_at: str,
    notify_employee: bool = True,
    hr_email: Optional[str] = None,
    smtp_host: Optional[str] = None,
    smtp_port: int = 587,
    smtp_user: Optional[str] = None,
    smtp_password: Optional[str] = None,
) -> str:
    """
    Send HTML confirmation email to HR (always) and optionally the employee.

    Falls back to writing email content to logs/emails/ if SMTP is not configured.
    Maps to: "Send Confirmation Email" (Gmail node).

    Args:
        employee_name: Full employee name.
        employee_id: HR employee ID.
        employee_email: Employee's email address.
        department: Department string.
        contract_type: Contract type label.
        effective_date: Contract effective date.
        structured_filename: Canonical filename.
        drive_url: Storage URL.
        cdn_backup_url: CDN backup URL.
        filed_by: Submitter.
        filed_at: Filing timestamp.
        notify_employee: Whether to CC the employee.
        hr_email: HR manager's email address (from env).
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port (default 587).
        smtp_user: SMTP authentication username.
        smtp_password: SMTP authentication password.

    Returns:
        JSON string: {"emailsSent": list[str], "method": "smtp" | "file"}
    """
    data = {
        "employeeName": employee_name,
        "employeeId": employee_id,
        "department": department,
        "contractType": contract_type,
        "effectiveDate": effective_date,
        "structuredFilename": structured_filename,
        "driveUrl": drive_url,
        "cdnBackupUrl": cdn_backup_url,
        "filedBy": filed_by,
        "filedAt": filed_at,
    }

    recipients = []
    if hr_email:
        recipients.append(hr_email)
    if notify_employee and employee_email:
        recipients.append(employee_email)

    html_body = _build_html_email(data)
    subject = f"[HR] Contract Filed: {employee_name} ({employee_id}) — {contract_type}"

    # ── Try SMTP if configured ─────────────────────────────────────────────────
    method = "file"
    if smtp_host and smtp_user and smtp_password and recipients:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = smtp_user
            msg["To"] = ", ".join(recipients)
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(smtp_host, smtp_port) as srv:
                srv.ehlo()
                srv.starttls()
                srv.login(smtp_user, smtp_password)
                srv.sendmail(smtp_user, recipients, msg.as_string())
            method = "smtp"
        except Exception as exc:
            logger.warning("SMTP send failed, falling back to file: %s", exc)

    # ── Always write email to disk (audit trail / fallback) ────────────────────
    email_dir = Path("logs/emails")
    email_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    email_file = email_dir / f"{employee_id}_{ts}.html"
    email_file.write_text(
        f"<h4>To: {', '.join(recipients) or '(no recipients)'}</h4>"
        f"<h4>Subject: {subject}</h4>"
        + html_body,
        encoding="utf-8",
    )

    return json.dumps({
        "emailsSent": recipients,
        "method": method,
        "emailFile": str(email_file),
    }, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Final Response Builder  (replaces "Build Final Response" code node)
# ──────────────────────────────────────────────────────────────────────────────

@log_tool_call(logger)
def tool_build_final_response(
    employee_id: str,
    employee_name: str,
    department: str,
    structured_filename: str,
    contract_type: str,
    effective_date: str,
    drive_file_id: str,
    drive_url: str,
    drive_folder_path: str,
    cdn_backup_url: str,
    airtable_record_id: str,
    filed_by: str,
    filed_at: str,
    upload_id: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
) -> str:
    """
    Assemble the final archiving summary returned to the caller.

    Maps to: "Build Final Response" code node.

    Returns:
        JSON string containing the complete archiving summary.
    """
    response = {
        "success": True,
        "message": f"Contract for {employee_name} successfully archived.",
        "employeeId": employee_id,
        "employeeName": employee_name,
        "department": department,
        "structuredFilename": structured_filename,
        "contractType": contract_type,
        "effectiveDate": effective_date,
        "driveFileId": drive_file_id,
        "driveUrl": drive_url,
        "driveFolderPath": drive_folder_path,
        "cdnBackupUrl": cdn_backup_url,
        "airtableRecordId": airtable_record_id,
        "auditTrail": {
            "filedBy": filed_by,
            "filedAt": filed_at,
            "uploadId": upload_id,
            "fileSizeBytes": file_size_bytes,
        },
    }

    # Persist to results/outputs/
    out_dir = Path("results/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_file = out_dir / f"archive_result_{employee_id}_{ts}.json"
    out_file.write_text(json.dumps(response, indent=2, ensure_ascii=False), encoding="utf-8")

    return json.dumps(response, ensure_ascii=False)