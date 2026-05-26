"""Tools for saving to Google Sheets (mock) and sending email (mock Gmail)."""

import json
import os
from datetime import datetime
from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "save_to_sheets")
def save_to_sheets(stock_data: list[dict]) -> dict:
    """Mock saving scraped stock data to Google Sheets (saves locally as JSON).

    Args:
        stock_data: List of scraped stock data dicts.

    Returns:
        Dict confirming data was saved.
    """
    output_dir = "results/outputs"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"sheets_data_{timestamp}.json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(stock_data, f, indent=2, ensure_ascii=False)

    return {
        "status": "saved",
        "rows": len(stock_data),
        "saved_to": filepath,
        "message": f"Mock Google Sheets: saved {len(stock_data)} rows to {filepath}",
    }


@log_mcp_call("tool", "send_email")
def send_email(subject: str, html_content: str, send_to: str = "EMAIL_PLACEHOLDER") -> dict:
    """Mock sending email via Gmail (saves HTML locally).

    Args:
        subject: Email subject line.
        html_content: HTML body of the email.
        send_to: Recipient email address.

    Returns:
        Dict confirming the email was sent (mock).
    """
    output_dir = "results/outputs"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"email_{timestamp}.html")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"<!-- Subject: {subject} -->\n")
        f.write(f"<!-- To: {send_to} -->\n")
        f.write(html_content)

    return {
        "status": "sent",
        "to": send_to,
        "subject": subject,
        "saved_to": filepath,
        "message": f"Mock Gmail: email saved to {filepath}",
    }
