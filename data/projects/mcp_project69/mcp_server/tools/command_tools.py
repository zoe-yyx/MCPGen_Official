"""Command tools: parse Telegram messages, route commands, parse update output.

Converted from n8n Extract the Service Name (Code), Switch, and Code in Python nodes.
"""

import json
import re

from .utils.log_decorator import log_mcp_call

# Command routing constants
CMD_LOGS = "logs"
CMD_RESTART = "restart"
CMD_STATUS = "status"
CMD_UPDATE = "update"
CMD_UNKNOWN = "unknown"


@log_mcp_call("tool", "extract_service_name")
def extract_service_name(message_text: str) -> str:
    """Extract the Docker service name from a Telegram message.

    Takes the first word of the message as the service name.
    E.g. "nginx logs" → "nginx", "restart nginx" → "restart"

    Args:
        message_text: Raw text from Telegram message.

    Returns:
        JSON string with 'service_name' field.
    """
    parts = message_text.strip().split()
    service_name = parts[0] if parts else ""
    return json.dumps({"service_name": service_name, "full_text": message_text})


@log_mcp_call("tool", "route_command")
def route_command(message_text: str) -> str:
    """Route Telegram message to a command branch.

    Switch node logic:
    - contains "logs"    → CMD_LOGS
    - contains "restart" → CMD_RESTART
    - equals "status"    → CMD_STATUS
    - equals "update"    → CMD_UPDATE

    Args:
        message_text: Raw text from Telegram message (lowercased internally).

    Returns:
        JSON string with 'command' (CMD_LOGS/CMD_RESTART/CMD_STATUS/CMD_UPDATE/unknown)
        and 'service_name' extracted from the message.
    """
    text = message_text.lower().strip()
    parts = text.split()

    if "logs" in text:
        command = CMD_LOGS
        # service name is the word before "logs", e.g. "nginx logs"
        service_name = parts[0] if len(parts) >= 2 else ""
    elif "restart" in text:
        command = CMD_RESTART
        # service name is after "restart", e.g. "restart nginx" or "nginx restart"
        service_name = parts[-1] if "restart" not in parts[-1] else (parts[0] if parts[0] != "restart" else "")
    elif text == CMD_STATUS:
        command = CMD_STATUS
        service_name = ""
    elif text == CMD_UPDATE:
        command = CMD_UPDATE
        service_name = ""
    else:
        command = CMD_UNKNOWN
        service_name = parts[0] if parts else ""

    return json.dumps({"command": command, "service_name": service_name, "raw_text": message_text})


@log_mcp_call("tool", "parse_update_summary")
def parse_update_summary(stdout: str) -> str:
    """Parse update summary from docker update script output.

    Converted from the Python code node in n8n.

    Args:
        stdout: Raw stdout from the update-all-docker-compose.sh script.

    Returns:
        JSON string with 'message' summarizing what was updated.
    """
    match = re.search(r"Update Summary:\n(\{.*?\})", stdout, re.DOTALL)
    if not match:
        return json.dumps({"message": "Update completed. No summary found."})

    update_json_str = match.group(1)
    # Remove trailing commas before ] or }
    update_json_clean = re.sub(r",\s*([\]\}])", r"\1", update_json_str)

    try:
        update_summary = json.loads(update_json_clean)
    except json.JSONDecodeError:
        return json.dumps({"message": f"Update completed. (parse error)\n{stdout[:200]}"})

    status_parts = []
    for compose_file, updates in update_summary.items():
        service = compose_file.replace("-compose.yaml", "")
        if updates == ["none"] or not updates:
            status_parts.append(f"{service}: No updates")
        else:
            status_parts.append(f"{service}: Updated ({', '.join(updates)})")

    message = "; ".join(status_parts) if status_parts else "All services up to date."
    return json.dumps({"message": message})
