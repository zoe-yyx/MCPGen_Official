"""Google Calendar Interview Scheduler Workflow.

Executes the interview scheduling workflow via MCP server using fastmcp Client.
Steps follow the same order as the n8n workflow:
1. Google Sheets Trigger - read candidate data
2. Calculate Next Interview Slot - find next Mon/Wed/Fri 3PM
3. Create Google Calendar Event - create event at the slot
4. Generate Interview Email - GPT writes personalized email (per candidate)
5. Send Interview Email via Gmail - send to candidate (per candidate)
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
    """Extract text content from MCP tool result."""
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return block.text
    if hasattr(result, "data"):
        return str(result.data)
    return str(result)


async def main() -> None:
    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info("Available tools:")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description}")
        logger.info("-" * 60)

        # ── Step 1: Google Sheets Trigger ──
        logger.info("Step 1: Polling Google Sheets for new candidates...")
        step1_result = await client.call_tool("google_sheets_trigger", {
            "sheet_id": os.getenv("GOOGLE_SHEET_ID", ""),
            "sheet_name": os.getenv("GOOGLE_SHEET_NAME", ""),
        })
        step1_data = extract_text(step1_result)
        candidates = json.loads(step1_data)
        logger.info(f"Step 1 result: Found {len(candidates)} candidate(s)")

        # ── Step 2: Calculate Next Interview Slot ──
        logger.info("Step 2: Calculating next interview slot...")
        step2_result = await client.call_tool("calculate_next_slot", {})
        step2_data = extract_text(step2_result)
        slot_info = json.loads(step2_data)
        logger.info(f"Step 2 result: nextSlot={slot_info['nextSlot']}, endSlot={slot_info['endSlot']}")

        # ── Step 3: Create Google Calendar Event ──
        logger.info("Step 3: Creating Google Calendar event...")
        step3_result = await client.call_tool("create_calendar_event", {
            "start_time": slot_info["nextSlot"],
            "end_time": slot_info["endSlot"],
            "calendar_id": os.getenv("GOOGLE_CALENDAR_ID", "EMAIL_PLACEHOLDER"),
        })
        step3_data = extract_text(step3_result)
        event_info = json.loads(step3_data)
        calendar_link = event_info["htmlLink"]
        logger.info(f"Step 3 result: Calendar event created, link={calendar_link}")

        # ── Steps 4 & 5: For each candidate, generate email and send ──
        for i, candidate in enumerate(candidates):
            name = candidate["NAME"]
            email = candidate["EMAIL"]
            education = candidate["EDUCATIONAL"]

            # Step 4: Generate Interview Email
            logger.info(f"Step 4 (candidate {i + 1}/{len(candidates)}): Generating email for {name}...")
            step4_result = await client.call_tool("generate_interview_email", {
                "candidate_name": name,
                "candidate_education": education,
                "calendar_link": calendar_link,
            })
            step4_data = extract_text(step4_result)
            email_content = json.loads(step4_data)
            logger.info(f"Step 4 result: Email generated for {name}, length={len(email_content['body'])}")

            # Step 5: Send Interview Email via Gmail
            logger.info(f"Step 5 (candidate {i + 1}/{len(candidates)}): Sending email to {email}...")
            step5_result = await client.call_tool("send_gmail", {
                "recipient_email": email,
                "subject": "Interview Details",
                "body": email_content["body"],
            })
            step5_data = extract_text(step5_result)
            logger.info(f"Step 5 result: {step5_data}")

        logger.info("=" * 60)
        logger.info("Workflow completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        raise
