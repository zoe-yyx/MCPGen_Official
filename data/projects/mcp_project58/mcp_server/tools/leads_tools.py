"""Leads tools — read, filter, and update leads data.

Corresponds to n8n nodes:
- Get row(s) in sheet: read leads from Google Sheets (mock → local CSV)
- If1: filter leads where "Hasil Riset" is empty
- updateDescription: save research results to sheet
- updateStatus: update lead status
- draftEmail: save email draft to sheet
- inputLink: save send-email link to sheet
- Code: URL-encode company name
"""

import csv
import json
import os
from urllib.parse import quote

from .utils.log_decorator import log_mcp_call

LEADS_CSV = os.getenv("LEADS_CSV_PATH", "data/leads.csv")
TEMPLATES_CSV = os.getenv("TEMPLATES_CSV_PATH", "data/templates.csv")
SERVICES_CSV = os.getenv("SERVICES_CSV_PATH", "data/services.csv")


def _read_csv(path: str) -> list[dict[str, str]]:
    """Read a CSV file and return list of row dicts."""
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _write_csv(path: str, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    """Write list of row dicts to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


@log_mcp_call("tool", "get_leads")
def get_leads(csv_path: str) -> list[dict[str, str]]:
    """Read all leads from CSV (mock Google Sheets Get row(s)).

    Args:
        csv_path: Path to the leads CSV file.

    Returns:
        List of lead dicts.
    """
    return _read_csv(csv_path)


@log_mcp_call("tool", "filter_unresearched_leads")
def filter_unresearched_leads(leads_json: str) -> list[dict[str, str]]:
    """Filter leads where 'Hasil Riset' is empty (mock If1 node).

    Args:
        leads_json: JSON string of leads list.

    Returns:
        List of leads that need research.
    """
    leads = json.loads(leads_json) if isinstance(leads_json, str) else leads_json
    return [lead for lead in leads if not lead.get("Hasil Riset", "").strip()]


@log_mcp_call("tool", "update_lead_research")
def update_lead_research(csv_path: str, company_name: str, research_result: str) -> dict[str, str]:
    """Save research result to lead row (mock updateDescription Google Sheets).

    Args:
        csv_path: Path to the leads CSV file.
        company_name: Company name to match (Perusahaan column).
        research_result: Research text to save.

    Returns:
        Status dict.
    """
    rows = _read_csv(csv_path)
    fieldnames = list(rows[0].keys()) if rows else []
    updated = False
    for row in rows:
        if row.get("Perusahaan") == company_name:
            row["Hasil Riset"] = research_result
            updated = True
            break
    if updated:
        _write_csv(csv_path, rows, fieldnames)
    return {"status": "updated" if updated else "not_found", "company": company_name}


@log_mcp_call("tool", "update_lead_status")
def update_lead_status(csv_path: str, company_name: str, status: str) -> dict[str, str]:
    """Update lead status (mock updateStatus Google Sheets).

    Args:
        csv_path: Path to the leads CSV file.
        company_name: Company name to match.
        status: New status value (e.g., 'Leads').

    Returns:
        Status dict.
    """
    rows = _read_csv(csv_path)
    fieldnames = list(rows[0].keys()) if rows else []
    updated = False
    for row in rows:
        if row.get("Perusahaan") == company_name:
            row["Status"] = status
            updated = True
            break
    if updated:
        _write_csv(csv_path, rows, fieldnames)
    return {"status": "updated" if updated else "not_found", "company": company_name}


@log_mcp_call("tool", "get_email_template")
def get_email_template(csv_path: str, stage: str) -> dict[str, str]:
    """Get email template by stage (mock getTemplate Google Sheets).

    Args:
        csv_path: Path to the templates CSV file.
        stage: Stage name to match (Tahap column), e.g. 'Leads'.

    Returns:
        Template dict with Tahap, Tema, Contoh message.
    """
    rows = _read_csv(csv_path)
    for row in rows:
        if row.get("Tahap", "").strip() == stage.strip():
            return row
    return {"Tahap": stage, "Tema": "General introduction", "Contoh message": ""}


@log_mcp_call("tool", "get_services")
def get_services(csv_path: str) -> list[dict[str, str]]:
    """Get list of products/services (mock getService Google Sheets).

    Args:
        csv_path: Path to the services CSV file.

    Returns:
        List of service dicts with Product and Description.
    """
    return _read_csv(csv_path)


@log_mcp_call("tool", "save_email_draft")
def save_email_draft(csv_path: str, company_name: str, email_draft: str) -> dict[str, str]:
    """Save email draft to lead row (mock draftEmail Google Sheets).

    Args:
        csv_path: Path to the leads CSV file.
        company_name: Company name to match.
        email_draft: Email draft JSON string to save.

    Returns:
        Status dict.
    """
    rows = _read_csv(csv_path)
    fieldnames = list(rows[0].keys()) if rows else []
    updated = False
    for row in rows:
        if row.get("Perusahaan") == company_name:
            row["Send Email Perkenalan"] = email_draft
            updated = True
            break
    if updated:
        _write_csv(csv_path, rows, fieldnames)
    return {"status": "updated" if updated else "not_found", "company": company_name}


@log_mcp_call("tool", "encode_company_url")
def encode_company_url(company_name: str) -> dict[str, str]:
    """URL-encode company name (mock Code node).

    Args:
        company_name: Raw company name string.

    Returns:
        Dict with original and encoded company name.
    """
    return {
        "company": company_name,
        "encoded": quote(company_name),
    }


@log_mcp_call("tool", "save_send_link")
def save_send_link(csv_path: str, company_name: str, send_link: str) -> dict[str, str]:
    """Save send-email trigger link to lead row (mock inputLink Google Sheets).

    Args:
        csv_path: Path to the leads CSV file.
        company_name: Company name to match.
        send_link: The webhook URL to trigger email sending.

    Returns:
        Status dict.
    """
    rows = _read_csv(csv_path)
    fieldnames = list(rows[0].keys()) if rows else []
    updated = False
    for row in rows:
        if row.get("Perusahaan") == company_name:
            row["Kirim email"] = send_link
            updated = True
            break
    if updated:
        _write_csv(csv_path, rows, fieldnames)
    return {"status": "updated" if updated else "not_found", "company": company_name}
