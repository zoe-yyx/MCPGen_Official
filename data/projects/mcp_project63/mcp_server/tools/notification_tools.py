"""Tools for alert message generation and multi-channel notifications (mock)."""

import json
import os
from datetime import datetime
from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "generate_alert_message")
def generate_alert_message(signal: dict) -> dict:
    """Generate formatted trading alert messages for Slack, Email, and SMS.

    Args:
        signal: Dict with action, symbol, confidence, currentPrice, recommendation, etc.

    Returns:
        Original signal dict plus alertMessages with slack, email, sms formats.
    """
    action = signal.get("action", "HOLD")
    emoji = {"BUY": "📈", "SELL": "📉"}.get(action, "⏸️")
    price = signal.get("currentPrice", 0)
    conf_pct = f"{signal.get('confidence', 0) * 100:.1f}"
    rec = signal.get("recommendation", {})

    slack_message = (
        f"{emoji} *TRADING ALERT — {action}*\n\n"
        f"*Symbol:* {signal.get('symbol')}\n"
        f"*Action:* {action}\n"
        f"*Confidence:* {conf_pct}%\n"
        f"*Current Price:* ${price:.2f}\n\n"
        f"*Recommendations:*\n"
        f"Entry: ${rec.get('entryPrice', 0):.2f}\n"
        f"Target: ${rec.get('targetPrice', 0):.2f}\n"
        f"Stop Loss: ${rec.get('stopLoss', 0):.2f}\n"
        f"Take Profit: ${rec.get('profitTarget', 0):.2f}\n\n"
        f"*Position Size:* {signal.get('positionSize', 0)}%\n"
        f"*Risk Level:* {signal.get('riskLevel')}\n"
        f"*Signal ID:* {signal.get('signalId')}\n"
        f"*AI Reasoning:* {signal.get('aiReasoning')}\n\n"
        f"*Timeframe:* {rec.get('timeframe')}"
    )

    email_subject = (
        f"{emoji} Trading Alert: {action} {signal.get('symbol')} "
        f"@ {price} - {conf_pct}% Confidence"
    )

    email_body = (
        f"<h2>{emoji} Trading Alert - {action} Signal</h2>\n"
        f"<p><strong>Symbol:</strong> {signal.get('symbol')}</p>\n"
        f"<p><strong>Action:</strong> {action}</p>\n"
        f"<p><strong>Confidence:</strong> {conf_pct}%</p>\n"
        f"<p><strong>Current Price:</strong> ${price:.2f}</p>\n\n"
        f"<h3>Recommendations</h3>\n<ul>\n"
        f"  <li>Entry Price: ${rec.get('entryPrice', 0):.2f}</li>\n"
        f"  <li>Target Price: ${rec.get('targetPrice', 0):.2f}</li>\n"
        f"  <li>Stop Loss: ${rec.get('stopLoss', 0):.2f}</li>\n"
        f"  <li>Take Profit: ${rec.get('profitTarget', 0):.2f}</li>\n"
        f"  <li>Position Size: {signal.get('positionSize', 0)}%</li>\n"
        f"  <li>Risk Level: {signal.get('riskLevel')}</li>\n"
        f"  <li>Timeframe: {rec.get('timeframe')}</li>\n</ul>\n\n"
        f"<h3>AI Analysis</h3>\n<p>{signal.get('aiReasoning')}</p>\n\n"
        f"<p><strong>Signal ID:</strong> {signal.get('signalId')}</p>\n"
        f"<p><strong>Generated:</strong> {signal.get('timestamp')}</p>"
    )

    sms_message = (
        f"{emoji} {action} {signal.get('symbol')} @ ${price:.2f} "
        f"- Confidence: {conf_pct}% - ID: {signal.get('signalId')}"
    )

    return {
        **signal,
        "alertMessages": {
            "slack": slack_message,
            "email": {"subject": email_subject, "body": email_body},
            "sms": sms_message,
        },
    }


@log_mcp_call("tool", "send_slack_notification")
def send_slack_notification(alert_data: dict) -> dict:
    """Mock sending Slack notification.

    Args:
        alert_data: Dict with alertMessages.slack content.

    Returns:
        Dict confirming notification was sent.
    """
    output_dir = "results/outputs"
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"slack_{alert_data.get('symbol', 'UNK')}_{ts}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(alert_data.get("alertMessages", {}).get("slack", ""))
    return {"status": "sent", "channel": "slack", "saved_to": filepath}


@log_mcp_call("tool", "send_email_alert")
def send_email_alert(alert_data: dict) -> dict:
    """Mock sending email alert.

    Args:
        alert_data: Dict with alertMessages.email content.

    Returns:
        Dict confirming email was sent.
    """
    output_dir = "results/outputs"
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"email_{alert_data.get('symbol', 'UNK')}_{ts}.html")
    email_info = alert_data.get("alertMessages", {}).get("email", {})
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"<!-- Subject: {email_info.get('subject', '')} -->\n")
        f.write(email_info.get("body", ""))
    return {"status": "sent", "channel": "email", "saved_to": filepath}


@log_mcp_call("tool", "send_sms_alert")
def send_sms_alert(alert_data: dict) -> dict:
    """Mock sending SMS alert via Twilio.

    Args:
        alert_data: Dict with alertMessages.sms content.

    Returns:
        Dict confirming SMS was sent.
    """
    output_dir = "results/outputs"
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"sms_{alert_data.get('symbol', 'UNK')}_{ts}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(alert_data.get("alertMessages", {}).get("sms", ""))
    return {"status": "sent", "channel": "sms", "saved_to": filepath}
