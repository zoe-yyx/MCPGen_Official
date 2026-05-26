"""Notification tools: Telegram message sending (mocked to local files).

All Telegram send nodes from the n8n workflow are represented here.
"""

import json
import os
from datetime import datetime, timezone

from .utils.log_decorator import log_mcp_call

MOCK_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "results", "outputs")


def _save_message(label: str, text: str) -> str:
    """Save a Telegram message to a local file and return file path."""
    os.makedirs(MOCK_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    filename = f"telegram_{label}_{ts}.txt"
    filepath = os.path.join(MOCK_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    return filepath


@log_mcp_call("tool", "send_ok_notification")
def send_ok_notification(message: str, chat_id: str = "123456789") -> str:
    """Send an OK / running status message to Telegram (mocked).

    Corresponds to the 'OK Message' Telegram node.

    Args:
        message: Status message text to send.
        chat_id: Telegram chat ID (ignored in mock).

    Returns:
        JSON string confirming the message was saved.
    """
    filepath = _save_message("ok", message)
    return json.dumps({"status": "sent_mock", "type": "ok", "message": message, "file": filepath})


@log_mcp_call("tool", "send_error_notification")
def send_error_notification(
    docker_container: str, issue: str, timestamp: str, chat_id: str = "123456789"
) -> str:
    """Send an error alert to Telegram with quick-action keyboard (mocked).

    Corresponds to the 'ERROR Message' Telegram node.

    Args:
        docker_container: Name of the container reporting an issue.
        issue: Issue description from heartbeat.
        timestamp: Time of the issue.
        chat_id: Telegram chat ID (ignored in mock).

    Returns:
        JSON string with the message text, keyboard buttons, and file path.
    """
    text = f"{docker_container} reported an issue: {issue} at {timestamp}"
    keyboard = [f"{docker_container} Logs", f"{docker_container} Restart"]
    filepath = _save_message("error", text)
    return json.dumps({
        "status": "sent_mock", "type": "error",
        "message": text, "keyboard": keyboard, "file": filepath,
    })


@log_mcp_call("tool", "send_analyzing_status")
def send_analyzing_status(chat_id: str = "123456789") -> str:
    """Send 'Analyzing Log File...' status message to Telegram (mocked).

    Corresponds to the 'Status Update' Telegram node.

    Args:
        chat_id: Telegram chat ID (ignored in mock).

    Returns:
        JSON string confirming the message was saved.
    """
    text = "Analyzing Log File..."
    filepath = _save_message("status_update", text)
    return json.dumps({"status": "sent_mock", "type": "status_update", "message": text, "file": filepath})


@log_mcp_call("tool", "send_log_analysis")
def send_log_analysis(analysis_text: str, chat_id: str = "123456789") -> str:
    """Send AI log analysis result to Telegram (mocked).

    Corresponds to the 'Log Analysis' Telegram node.

    Args:
        analysis_text: AI-generated analysis text.
        chat_id: Telegram chat ID (ignored in mock).

    Returns:
        JSON string confirming the message was saved.
    """
    filepath = _save_message("log_analysis", analysis_text)
    return json.dumps({"status": "sent_mock", "type": "log_analysis", "file": filepath})


@log_mcp_call("tool", "send_restart_message")
def send_restart_message(chat_id: str = "123456789") -> str:
    """Send 'Attempting to restart...' message to Telegram (mocked).

    Corresponds to the 'Restart Message' Telegram node.

    Args:
        chat_id: Telegram chat ID (ignored in mock).

    Returns:
        JSON string confirming the message was saved.
    """
    text = "Attempting to restart..."
    filepath = _save_message("restart_msg", text)
    return json.dumps({"status": "sent_mock", "type": "restart_message", "message": text, "file": filepath})


@log_mcp_call("tool", "send_restart_success")
def send_restart_success(service_name: str, chat_id: str = "123456789") -> str:
    """Send successful restart confirmation to Telegram (mocked).

    Corresponds to the 'Success restart' Telegram node.

    Args:
        service_name: Name of the successfully restarted container.
        chat_id: Telegram chat ID (ignored in mock).

    Returns:
        JSON string confirming the message was saved.
    """
    text = f"Successfully restarting {service_name}"
    filepath = _save_message("restart_success", text)
    return json.dumps({"status": "sent_mock", "type": "restart_success", "message": text, "file": filepath})


@log_mcp_call("tool", "send_restart_failed")
def send_restart_failed(stderr: str, chat_id: str = "123456789") -> str:
    """Send restart failure message to Telegram (mocked).

    Corresponds to the 'Restart Failed' Telegram node.

    Args:
        stderr: Error output from the failed restart command.
        chat_id: Telegram chat ID (ignored in mock).

    Returns:
        JSON string confirming the message was saved.
    """
    text = f"Restart failed\n{stderr}"
    filepath = _save_message("restart_failed", text)
    return json.dumps({"status": "sent_mock", "type": "restart_failed", "message": text, "file": filepath})


@log_mcp_call("tool", "send_docker_status")
def send_docker_status(stdout: str, chat_id: str = "123456789") -> str:
    """Send docker ps output to Telegram (mocked).

    Corresponds to the 'Docker Status' Telegram node.

    Args:
        stdout: Output from 'docker ps' command.
        chat_id: Telegram chat ID (ignored in mock).

    Returns:
        JSON string confirming the message was saved.
    """
    filepath = _save_message("docker_status", stdout)
    return json.dumps({"status": "sent_mock", "type": "docker_status", "message": stdout, "file": filepath})


@log_mcp_call("tool", "send_update_started")
def send_update_started(chat_id: str = "123456789") -> str:
    """Send 'Running Update...' message to Telegram (mocked).

    Corresponds to the 'Update Msg' Telegram node.

    Args:
        chat_id: Telegram chat ID (ignored in mock).

    Returns:
        JSON string confirming the message was saved.
    """
    text = "Running Update..."
    filepath = _save_message("update_started", text)
    return json.dumps({"status": "sent_mock", "type": "update_started", "message": text, "file": filepath})


@log_mcp_call("tool", "send_update_result")
def send_update_result(message: str, chat_id: str = "123456789") -> str:
    """Send update results summary to Telegram (mocked).

    Corresponds to the 'Update Msg1' Telegram node.

    Args:
        message: Formatted update summary string.
        chat_id: Telegram chat ID (ignored in mock).

    Returns:
        JSON string confirming the message was saved.
    """
    filepath = _save_message("update_result", message)
    return json.dumps({"status": "sent_mock", "type": "update_result", "message": message, "file": filepath})
