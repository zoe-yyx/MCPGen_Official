"""Docker Management Bot Workflow.

Demonstrates all four Telegram command paths and the Uptime Kuma webhook path,
following the step order in workflow.json.

Path A - Uptime Kuma Webhook (Steps 1-4):
  1 receive_uptime_webhook → 2 check_heartbeat_status
  → 3 send_ok_notification (if running)
  → 4 send_error_notification (if error)

Path B - Telegram 'logs' (Steps 5-10):
  5 extract_service_name → 6 route_command
  → 7 get_docker_logs → 8 send_analyzing_status
  → 9 analyze_logs_with_ai → 10 send_log_analysis

Path C - Telegram 'restart' (Steps 11-15):
  11 send_restart_message → 12 restart_docker_container
  → 13 check_restart_success → 14 send_restart_success / 15 send_restart_failed

Path D - Telegram 'status' (Steps 16-17):
  16 get_docker_status → 17 send_docker_status

Path E - Telegram 'update' (Steps 18-21):
  18 send_update_started → 19 run_docker_update
  → 20 parse_update_summary → 21 send_update_result
"""

import asyncio
import json
import os
import sys

from fastmcp import Client

sys.path.insert(0, os.path.dirname(__file__))
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/workflow.log")


def extract_text(result) -> str:
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return block.text
    return str(result)


async def run_webhook_path(client: Client) -> None:
    """Path A: Uptime Kuma heartbeat webhook - Steps 1-4."""
    logger.info("=" * 60)
    logger.info("PATH A: Uptime Kuma Webhook Monitor")
    logger.info("=" * 60)

    # Step 1: Receive webhook (error scenario)
    logger.info("Step 1: Receiving Uptime Kuma webhook (error)...")
    step1_result = await client.call_tool("receive_uptime_webhook", {
        "heartbeat_msg": "Service unavailable",
        "heartbeat_time": "2026-04-23T05:15:00Z",
        "monitor_name": "nginx-monitor",
        "monitor_docker_container": "nginx",
    })
    step1_data = json.loads(extract_text(step1_result))
    logger.info(f"Step 1: Webhook received for container '{step1_data['body']['monitor']['docker_container']}'")

    # Step 2: Check heartbeat
    logger.info("Step 2: Checking heartbeat status...")
    step2_result = await client.call_tool("check_heartbeat_status", {
        "webhook_data": extract_text(step1_result),
    })
    step2_data = json.loads(extract_text(step2_result))
    logger.info(f"Step 2: Route={step2_data['route']}")

    if step2_data["route"] == "ok":
        # Step 3: OK notification
        logger.info("Step 3: Sending OK notification...")
        r = await client.call_tool("send_ok_notification", {"message": step2_data["ok_message"]})
        logger.info(f"Step 3: {extract_text(r)}")
    else:
        # Step 4: Error notification
        logger.info("Step 4: Sending ERROR notification with action keyboard...")
        r = await client.call_tool("send_error_notification", {
            "docker_container": step2_data["docker_container"],
            "issue": step1_data["body"]["heartbeat"]["msg"],
            "timestamp": step1_data["body"]["heartbeat"]["time"],
        })
        step4_data = json.loads(extract_text(r))
        logger.info(f"Step 4: Error sent - keyboard={step4_data['keyboard']}")


async def run_logs_path(client: Client, message: str = "nginx logs") -> None:
    """Path B: Telegram 'logs' command - Steps 5-10."""
    logger.info("=" * 60)
    logger.info(f"PATH B: Telegram 'logs' command — '{message}'")
    logger.info("=" * 60)

    # Step 5: Extract service name
    logger.info("Step 5: Extracting service name from Telegram message...")
    step5_result = await client.call_tool("extract_service_name", {"message_text": message})
    step5_data = json.loads(extract_text(step5_result))
    logger.info(f"Step 5: service_name='{step5_data['service_name']}'")

    # Step 6: Route command
    logger.info("Step 6: Routing command...")
    step6_result = await client.call_tool("route_command", {"message_text": message})
    step6_data = json.loads(extract_text(step6_result))
    logger.info(f"Step 6: command='{step6_data['command']}', service='{step6_data['service_name']}'")

    # Step 7: Get logs
    logger.info(f"Step 7: Fetching Docker logs for '{step5_data['service_name']}'...")
    step7_result = await client.call_tool("get_docker_logs", {
        "service_name": step5_data["service_name"],
        "tail": 100,
    })
    step7_data = json.loads(extract_text(step7_result))
    logger.info(f"Step 7: Fetched {len(step7_data['stdout'])} chars of logs")

    # Step 8: Send "analyzing" status
    logger.info("Step 8: Notifying user 'Analyzing Log File...'")
    await client.call_tool("send_analyzing_status", {})

    # Step 9: AI analysis
    logger.info("Step 9: Running AI log analysis...")
    step9_result = await client.call_tool("analyze_logs_with_ai", {
        "log_stdout": step7_data["stdout"],
    })
    step9_data = json.loads(extract_text(step9_result))
    logger.info(f"Step 9: AI analysis complete ({len(step9_data['analysis'])} chars)")

    # Step 10: Send analysis
    logger.info("Step 10: Sending log analysis to Telegram...")
    step10_result = await client.call_tool("send_log_analysis", {
        "analysis_text": step9_data["analysis"],
    })
    logger.info(f"Step 10: {extract_text(step10_result)}")
    logger.info(f"\nAI Analysis Preview:\n{step9_data['analysis'][:500]}...\n")


async def run_restart_path(client: Client, message: str = "nginx restart") -> None:
    """Path C: Telegram 'restart' command - Steps 11-15."""
    logger.info("=" * 60)
    logger.info(f"PATH C: Telegram 'restart' command — '{message}'")
    logger.info("=" * 60)

    # Step 5 (reused): extract service name
    step5_result = await client.call_tool("extract_service_name", {"message_text": message})
    step5_data = json.loads(extract_text(step5_result))

    # Step 11: Restart message
    logger.info("Step 11: Sending 'Attempting to restart...'")
    await client.call_tool("send_restart_message", {})

    # Step 12: Restart container
    logger.info(f"Step 12: Restarting container '{step5_data['service_name']}'...")
    step12_result = await client.call_tool("restart_docker_container", {
        "service_name": step5_data["service_name"],
    })

    # Step 13: Check restart success
    logger.info("Step 13: Checking restart result...")
    step13_result = await client.call_tool("check_restart_success", {
        "restart_result": extract_text(step12_result),
    })
    step13_data = json.loads(extract_text(step13_result))
    logger.info(f"Step 13: success={step13_data['success']}")

    if step13_data["success"]:
        # Step 14: Success
        logger.info("Step 14: Sending restart success notification...")
        r = await client.call_tool("send_restart_success", {"service_name": step13_data["stdout"]})
        logger.info(f"Step 14: {extract_text(r)}")
    else:
        # Step 15: Failed
        logger.info("Step 15: Sending restart failed notification...")
        r = await client.call_tool("send_restart_failed", {"stderr": step13_data["stderr"]})
        logger.info(f"Step 15: {extract_text(r)}")


async def run_status_path(client: Client) -> None:
    """Path D: Telegram 'status' command - Steps 16-17."""
    logger.info("=" * 60)
    logger.info("PATH D: Telegram 'status' command")
    logger.info("=" * 60)

    # Step 16: docker ps
    logger.info("Step 16: Running 'docker ps'...")
    step16_result = await client.call_tool("docker_ps", {})
    step16_data = json.loads(extract_text(step16_result))
    logger.info(f"Step 16: Got docker ps output ({len(step16_data['stdout'])} chars)")

    # Step 17: Send status
    logger.info("Step 17: Sending Docker status to Telegram...")
    step17_result = await client.call_tool("send_docker_status", {"stdout": step16_data["stdout"]})
    logger.info(f"Step 17: {extract_text(step17_result)}")


async def run_update_path(client: Client) -> None:
    """Path E: Telegram 'update' command - Steps 18-21."""
    logger.info("=" * 60)
    logger.info("PATH E: Telegram 'update' command")
    logger.info("=" * 60)

    # Step 18: Update started
    logger.info("Step 18: Sending 'Running Update...'")
    await client.call_tool("send_update_started", {})

    # Step 19: Run update script
    logger.info("Step 19: Running docker update script...")
    step19_result = await client.call_tool("run_docker_update", {})
    step19_data = json.loads(extract_text(step19_result))
    logger.info(f"Step 19: Update script completed ({len(step19_data['stdout'])} chars)")

    # Step 20: Parse summary
    logger.info("Step 20: Parsing update summary...")
    step20_result = await client.call_tool("parse_update_summary", {
        "stdout": step19_data["stdout"],
    })
    step20_data = json.loads(extract_text(step20_result))
    logger.info(f"Step 20: Summary='{step20_data['message']}'")

    # Step 21: Send result
    logger.info("Step 21: Sending update result to Telegram...")
    step21_result = await client.call_tool("send_update_result", {"message": step20_data["message"]})
    logger.info(f"Step 21: {extract_text(step21_result)}")


async def main() -> None:
    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info(f"Server started with {len(tools)} tools registered")
        logger.info("-" * 60)

        # Run all five workflow paths in step-id order
        await run_webhook_path(client)
        await run_logs_path(client, "nginx logs")
        await run_restart_path(client, "nginx restart")
        await run_status_path(client)
        await run_update_path(client)

        logger.info("=" * 60)
        logger.info("All workflow paths completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        raise
