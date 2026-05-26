"""Tools for performance gap checking, email sending (mock), and report history storage (mock)."""

import json
import os
from datetime import datetime
from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "check_performance_gap")
def check_performance_gap(difference: str, threshold: float) -> dict:
    """Check if the performance gap exceeds the threshold.

    Args:
        difference: Absolute performance difference string (e.g. "2.11").
        threshold: Threshold percentage for triggering an alert.

    Returns:
        Dict with gap_exceeds_threshold (bool), abs_difference, threshold.
    """
    abs_diff = abs(float(difference))
    exceeds = abs_diff > threshold
    return {
        "gap_exceeds_threshold": exceeds,
        "abs_difference": abs_diff,
        "threshold": threshold,
    }


@log_mcp_call("tool", "send_report_email")
def send_report_email(html_content: str, subject: str) -> dict:
    """Mock sending a standard report email via Gmail.

    Args:
        html_content: HTML body of the email.
        subject: Email subject line.

    Returns:
        Dict confirming the email was sent (mock).
    """
    output_dir = "results/outputs"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"report_email_{timestamp}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {
        "status": "sent",
        "type": "report",
        "subject": subject,
        "saved_to": filepath,
        "message": f"Mock email saved to {filepath}",
    }


@log_mcp_call("tool", "send_alert_email")
def send_alert_email(html_content: str, subject: str) -> dict:
    """Mock sending an alert email via Gmail when performance gap is significant.

    Args:
        html_content: HTML body with alert prefix.
        subject: Email subject line.

    Returns:
        Dict confirming the alert email was sent (mock).
    """
    alert_body = f"Alert Triggered!\n\nA significant difference in asset performance detected.\n{html_content}"

    output_dir = "results/outputs"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"alert_email_{timestamp}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(alert_body)

    return {
        "status": "sent",
        "type": "alert",
        "subject": subject,
        "saved_to": filepath,
        "message": f"Mock alert email saved to {filepath}",
    }


@log_mcp_call("tool", "store_report_history")
def store_report_history(
    date: str,
    winner: str,
    summary: str,
    report: str,
) -> dict:
    """Mock storing report history to Google Sheets (saves locally as JSON).

    Args:
        date: Report generation date.
        winner: Winning asset (Gold/Equity).
        summary: AI-generated summary.
        report: AI-generated reason/report.

    Returns:
        Dict confirming the record was stored.
    """
    output_dir = "results/metrics"
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, "report_history.json")

    history: list[dict] = []
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                history = []

    record = {
        "Date": date,
        "Winner": winner,
        "Summary": summary,
        "Report": report,
    }
    history.append(record)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    return {
        "status": "stored",
        "saved_to": filepath,
        "record": record,
    }
