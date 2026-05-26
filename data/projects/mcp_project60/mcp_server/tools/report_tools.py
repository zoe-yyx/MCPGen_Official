"""Report tools — logging, email notifications (all mocked locally)."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime

from .utils.log_decorator import log_mcp_call


def _reports_csv() -> str:
    return os.getenv("REPORTS_CSV", "data/reports.csv")


def _errors_csv() -> str:
    return os.getenv("ERRORS_CSV", "data/errors.csv")


def _output_dir() -> str:
    return os.getenv("OUTPUT_DIR", "results/outputs")


@log_mcp_call("tool")
def log_daily_report(report_json: str, total_assets: int) -> str:
    """Append parsed report to CSV (mock Google Sheets).

    Args:
        report_json: JSON with market_summary, key_movers, risk_sentiment, insight, outlook.
        total_assets: Number of assets processed.

    Returns:
        ``"logged"`` on success.
    """
    report = json.loads(report_json)
    csv_path = _reports_csv()
    os.makedirs(os.path.dirname(csv_path) or "data", exist_ok=True)

    file_exists = os.path.exists(csv_path)
    fieldnames = [
        "execution_date", "market_summary", "key_movers",
        "risk_sentiment", "insight", "outlook",
        "total_assets", "status", "workflow_version",
    ]

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "execution_date": datetime.now().isoformat(),
            "market_summary": report.get("market_summary", ""),
            "key_movers": ", ".join(report.get("key_movers", [])),
            "risk_sentiment": report.get("risk_sentiment", ""),
            "insight": report.get("insight", ""),
            "outlook": report.get("outlook", ""),
            "total_assets": total_assets,
            "status": "SUCCESS",
            "workflow_version": "v2.0-production",
        })

    return "logged"


@log_mcp_call("tool")
def send_market_email(report_json: str) -> str:
    """Mock Gmail — save market report email to local file.

    Args:
        report_json: JSON with the parsed report fields.

    Returns:
        JSON with ``status`` and ``file_path``.
    """
    report = json.loads(report_json)
    out_dir = _output_dir()
    os.makedirs(out_dir, exist_ok=True)

    movers_text = "\n".join(f"- {m}" for m in report.get("key_movers", []))

    email_body = (
        f"Subject: Today's Market Summary\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'=' * 50}\n\n"
        f"Market Summary:\n{report.get('market_summary', '')}\n\n"
        f"Key Movers:\n{movers_text}\n\n"
        f"Risk Sentiment:\n{report.get('risk_sentiment', '')}\n\n"
        f"Insight:\n{report.get('insight', '')}\n\n"
        f"Outlook:\n{report.get('outlook', '')}\n"
    )

    email_path = os.path.join(out_dir, "market_email.txt")
    with open(email_path, "w", encoding="utf-8") as f:
        f.write(email_body)

    return json.dumps({"status": "sent", "file_path": email_path})


@log_mcp_call("tool")
def log_api_error(symbol: str, status: str, message: str) -> str:
    """Log an API error to CSV (mock Google Sheets error log).

    Args:
        symbol: The failed symbol.
        status: Error status code.
        message: Error message.

    Returns:
        JSON with the error record.
    """
    csv_path = _errors_csv()
    os.makedirs(os.path.dirname(csv_path) or "data", exist_ok=True)

    file_exists = os.path.exists(csv_path)
    fieldnames = [
        "execution_date", "failed_symbol", "error_message",
        "status", "error_code", "workflow_version",
    ]

    record = {
        "execution_date": datetime.now().isoformat(),
        "failed_symbol": symbol,
        "error_message": message,
        "status": "FAILED",
        "error_code": status,
        "workflow_version": "v2.0-production",
    }

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)

    return json.dumps(record)


@log_mcp_call("tool")
def send_error_alert(symbol: str, status: str, message: str) -> str:
    """Mock Gmail — save API failure alert email to local file.

    Args:
        symbol: The failed symbol.
        status: Error status.
        message: Error message.

    Returns:
        JSON with ``status`` and ``file_path``.
    """
    out_dir = _output_dir()
    os.makedirs(out_dir, exist_ok=True)

    email_body = (
        f"Subject: API Failure Alert\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'=' * 50}\n\n"
        f"Twelve Data API failed.\n"
        f"Symbol: {symbol}\n"
        f"Status: {status}\n"
        f"Message: {message}\n"
    )

    email_path = os.path.join(out_dir, "error_alert.txt")
    with open(email_path, "a", encoding="utf-8") as f:
        f.write(email_body + "\n---\n")

    return json.dumps({"status": "alert_sent", "file_path": email_path})
