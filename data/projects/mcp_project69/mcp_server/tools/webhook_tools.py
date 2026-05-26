"""Webhook tools: Uptime Kuma heartbeat monitoring.

Simulates the Webhook + Switch1 nodes that receive Uptime Kuma monitor alerts
and route them based on heartbeat status.
"""

import json

from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "receive_uptime_webhook")
def receive_uptime_webhook(
    heartbeat_msg: str,
    heartbeat_time: str,
    monitor_name: str,
    monitor_docker_container: str,
) -> str:
    """Receive and parse an Uptime Kuma heartbeat webhook payload (mocked).

    Args:
        heartbeat_msg: Status message, e.g. 'running' or error description.
        heartbeat_time: ISO timestamp of the heartbeat.
        monitor_name: Name of the Uptime Kuma monitor.
        monitor_docker_container: Docker container name being monitored.

    Returns:
        JSON string with parsed webhook body.
    """
    return json.dumps({
        "body": {
            "heartbeat": {
                "msg": heartbeat_msg,
                "time": heartbeat_time,
            },
            "monitor": {
                "name": monitor_name,
                "docker_container": monitor_docker_container,
            },
            "msg": f"Monitor '{monitor_name}' is {heartbeat_msg}",
        }
    })


@log_mcp_call("tool", "check_heartbeat_status")
def check_heartbeat_status(webhook_data: str) -> str:
    """Route webhook based on heartbeat status: 'running' vs other.

    Corresponds to Switch1 node in n8n.

    Args:
        webhook_data: JSON string from receive_uptime_webhook.

    Returns:
        JSON string with 'route' ('ok' | 'error') and original body fields.
    """
    data = json.loads(webhook_data)
    body = data.get("body", {})
    msg = body.get("heartbeat", {}).get("msg", "")
    route = "ok" if msg == "running" else "error"
    return json.dumps({
        "route": route,
        "ok_message": body.get("msg", ""),
        "error_message": (
            f"{body.get('monitor', {}).get('docker_container', 'unknown')} "
            f"reported an issue: {msg} at "
            f"{body.get('heartbeat', {}).get('time', '')}"
        ),
        "docker_container": body.get("monitor", {}).get("docker_container", ""),
    })
