"""Employee Leave Alert System Workflow.

Executes the full leave management pipeline via MCP server using fastmcp Client.
Steps follow the n8n workflow order:
1. Fetch leave records (Google Sheets mock)
2. Validate & normalize leave data
3. Notify HR Slack channel - leave activated (per needsActivation record)
4. Send OOO reminder email to employee
5. Mark leave as Active in sheet
6. Notify HR Slack channel - leave completed (per needsReset record)
7. Send Welcome Back email to employee
8. Mark leave as Inactive in sheet
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
    if hasattr(result, "data"):
        return str(result.data)
    return str(result)


async def main() -> None:
    os.makedirs("logs", exist_ok=True)
    os.makedirs("results/outputs", exist_ok=True)
    os.makedirs("results/metrics", exist_ok=True)

    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info("Available tools:")
        for tool in tools:
            logger.info(f"  - {tool.name}")
        logger.info("-" * 60)

        # ── Step 1: Fetch Leave Records ──
        logger.info("Step 1: Fetching leave records from mock Google Sheets...")
        step1_result = await client.call_tool("fetch_leave_records", {})
        records_json = extract_text(step1_result)
        raw_records = json.loads(records_json)
        logger.info(f"Step 1: Fetched {len(raw_records)} records")

        # ── Step 2: Validate & Normalize Leave Data ──
        logger.info("Step 2: Validating and normalizing leave data...")
        step2_result = await client.call_tool(
            "validate_normalize_leave_data", {"records_json": records_json}
        )
        validated_json = extract_text(step2_result)
        validated = json.loads(validated_json)
        logger.info(f"Step 2: {len(validated)} valid records after normalization")

        needs_activation = [r for r in validated if r["needsActivation"]]
        needs_reset = [r for r in validated if r["needsReset"]]
        logger.info(f"Step 2: {len(needs_activation)} record(s) need activation, {len(needs_reset)} need reset")

        # ── Steps 3-5: Process Activations Sequentially ──
        logger.info(f"Steps 3-5: Processing {len(needs_activation)} activation(s)...")
        for i, record in enumerate(needs_activation, 1):
            logger.info(f"  Activation {i}/{len(needs_activation)}: {record['name']} ({record['email']})")

            # Step 3: Notify HR channel
            result = await client.call_tool("notify_hr_channel", {
                "employee_name": record["name"],
                "employee_email": record["email"],
                "start_date": record["startDate"],
                "end_date": record["endDate"],
            })
            logger.info(f"  Step 3: {extract_text(result)}")

            # Step 4: Send OOO reminder email
            result = await client.call_tool("send_ooo_reminder_email", {
                "to_email": record["email"],
                "employee_name": record["name"],
                "start_date": record["startDate"],
                "end_date": record["endDate"],
            })
            logger.info(f"  Step 4: {extract_text(result)}")

            # Step 5: Mark leave as Active
            result = await client.call_tool("mark_leave_as_active", {
                "email": record["email"],
                "today": record["today"],
            })
            logger.info(f"  Step 5: {extract_text(result)}")

        # ── Steps 6-8: Process Resets Sequentially ──
        logger.info(f"Steps 6-8: Processing {len(needs_reset)} reset(s)...")
        for i, record in enumerate(needs_reset, 1):
            logger.info(f"  Reset {i}/{len(needs_reset)}: {record['name']} ({record['email']})")

            # Step 6: Notify HR channel (leave reset)
            result = await client.call_tool("notify_hr_leave_reset", {
                "employee_name": record["name"],
                "employee_email": record["email"],
                "start_date": record["startDate"],
                "end_date": record["endDate"],
            })
            logger.info(f"  Step 6: {extract_text(result)}")

            # Step 7: Send welcome back email
            result = await client.call_tool("send_welcome_back_email", {
                "to_email": record["email"],
                "employee_name": record["name"],
                "end_date": record["endDate"],
            })
            logger.info(f"  Step 7: {extract_text(result)}")

            # Step 8: Mark leave as Inactive
            result = await client.call_tool("mark_leave_as_inactive", {
                "email": record["email"],
                "today": record["today"],
            })
            logger.info(f"  Step 8: {extract_text(result)}")

        # ── Summary ──
        metrics = {
            "total_records": len(raw_records),
            "valid_records": len(validated),
            "activations_processed": len(needs_activation),
            "resets_processed": len(needs_reset),
        }
        metrics_path = "results/metrics/workflow_metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)

        logger.info("=" * 60)
        logger.info("Workflow completed successfully!")
        logger.info(f"Metrics: {metrics}")
        logger.info(f"Metrics saved to {metrics_path}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        raise
