"""Notification tools — email, Slack alerts, and audit trail logging.

Corresponds to n8n nodes:
- Send Confirmation Email (Gmail, mock → local file)
- Alert Operations Team (Slack, mock → local file)
- Merge All Paths (logic handled in run_workflow.py)
- Log to Audit Trail (Google Sheets, mock → local CSV)
"""

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .utils.log_decorator import log_mcp_call

EMAILS_DIR = "results/outputs"
ALERTS_FILE = "results/outputs/alerts.jsonl"
AUDIT_CSV = "results/outputs/audit_trail.csv"


@log_mcp_call("tool", "send_confirmation_email")
def send_confirmation_email(
    recipient_email: str,
    subject: str,
    booking_id: str,
    status: str,
    seat_assignments: str,
) -> dict:
    """Send a ticket confirmation email (mock Gmail → local file).

    Args:
        recipient_email: Recipient email address.
        subject: Email subject line.
        booking_id: Booking ID string.
        status: Booking status (CONFIRMED, etc.).
        seat_assignments: Comma-separated seat list.

    Returns:
        Dict confirming the email was saved locally.
    """
    os.makedirs(EMAILS_DIR, exist_ok=True)

    email_content = {
        "to": recipient_email,
        "subject": subject,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "body": (
            f"Your concert tickets have been confirmed!\n\n"
            f"Booking ID: {booking_id}\n"
            f"Status: {status}\n"
            f"Seats: {seat_assignments}\n\n"
            f"Please bring this confirmation email and a valid ID to the venue."
        ),
    }

    email_path = Path(EMAILS_DIR) / f"email_{booking_id}.json"
    with open(email_path, "w", encoding="utf-8") as f:
        json.dump(email_content, f, ensure_ascii=False, indent=2)

    return {
        "status": "sent",
        "recipient": recipient_email,
        "subject": subject,
        "savedTo": str(email_path),
    }


@log_mcp_call("tool", "alert_operations_team")
def alert_operations_team(
    risk_level: str,
    risk_score: int,
    validation_status: str,
    customer_email: str,
    ticket_quantity: int,
    total_amount: float,
    fraud_indicators: str,
    escalation_reason: str,
    reasoning: str,
) -> dict:
    """Send a high-risk alert to the operations team (mock Slack → local JSONL).

    Args:
        risk_level: Risk level string (HIGH, CRITICAL).
        risk_score: Numeric risk score 0-100.
        validation_status: Validation status string.
        customer_email: Customer email.
        ticket_quantity: Number of tickets requested.
        total_amount: Total order amount.
        fraud_indicators: Comma-separated fraud indicator list.
        escalation_reason: Reason for escalation.
        reasoning: Detailed validation reasoning.

    Returns:
        Dict confirming the alert was logged.
    """
    os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)

    alert = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel": "ops-alerts",
        "riskLevel": risk_level,
        "riskScore": risk_score,
        "validationStatus": validation_status,
        "customerEmail": customer_email,
        "ticketQuantity": ticket_quantity,
        "totalAmount": total_amount,
        "fraudIndicators": fraud_indicators.split(",") if fraud_indicators else [],
        "escalationReason": escalation_reason,
        "reasoning": reasoning,
        "actionRequired": "Manual review and approval needed before processing",
    }

    with open(ALERTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(alert, ensure_ascii=False) + "\n")

    return {
        "status": "alerted",
        "channel": "ops-alerts",
        "riskLevel": risk_level,
        "savedTo": ALERTS_FILE,
    }


@log_mcp_call("tool", "log_audit_trail")
def log_audit_trail(
    booking_id: str,
    customer_email: str,
    validation_status: str,
    risk_level: str,
    risk_score: int,
    requires_human_review: bool,
    audit_summary: str,
) -> dict:
    """Log booking outcome to audit trail (mock Google Sheets → local CSV).

    Args:
        booking_id: Booking ID.
        customer_email: Customer email.
        validation_status: Validation status.
        risk_level: Risk level.
        risk_score: Numeric risk score.
        requires_human_review: Whether human review is needed.
        audit_summary: Summary string for audit log.

    Returns:
        Dict confirming the audit entry was logged.
    """
    os.makedirs(os.path.dirname(AUDIT_CSV), exist_ok=True)

    fieldnames = [
        "timestamp", "bookingId", "customerEmail", "validationStatus",
        "riskLevel", "riskScore", "requiresHumanReview", "auditSummary",
    ]

    file_exists = os.path.exists(AUDIT_CSV)

    with open(AUDIT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bookingId": booking_id,
            "customerEmail": customer_email,
            "validationStatus": validation_status,
            "riskLevel": risk_level,
            "riskScore": risk_score,
            "requiresHumanReview": requires_human_review,
            "auditSummary": audit_summary,
        })

    return {
        "status": "logged",
        "bookingId": booking_id,
        "savedTo": AUDIT_CSV,
    }
