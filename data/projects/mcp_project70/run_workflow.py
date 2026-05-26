"""Google Tasks → n8n Plans Workflow.

Converts Google Tasks ideas into n8n workflow plans using GPT,
routes each plan through Slack approval, archives approved plans,
and marks processed tasks.

Step order (matches workflow.json step_id):
  1 schedule_trigger (inline)
  2 get_new_ideas
  3 filter_processed
  4 iterate_ideas (inline loop per idea)
  5 ai_solution_architect
  6 slack_review_approve
  7 check_approval
  8 archive_to_sheets (if approved)
  9 mark_as_notified (if approved)
  [loop back to next idea]
"""

import asyncio
import json
import os
import sys
from datetime import datetime

from fastmcp import Client

sys.path.insert(0, os.path.dirname(__file__))
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/workflow.log")

MAX_REGENERATE_ATTEMPTS = 2


def extract_text(result) -> str:
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return block.text
    return str(result)


async def process_idea(client: Client, idea: dict, idea_index: int, total: int) -> None:
    """Process a single idea through steps 5→6→7→8→9 with regeneration loop."""
    logger.info("Step 4: Iterate Ideas — [%d/%d] '%s'", idea_index + 1, total, idea["title"])

    for attempt in range(1, MAX_REGENERATE_ATTEMPTS + 2):
        # Step 5: AI Solution Architect
        logger.info("Step 5: AI Solution Architect (attempt %d) — '%s'", attempt, idea["title"])
        step5_result = await client.call_tool("ai_solution_architect", {
            "idea_title": idea["title"],
        })
        step5_data = json.loads(extract_text(step5_result))
        output = step5_data.get("output", {})
        logger.info("Step 5: Plan title='%s'", output.get("title", ""))

        # Step 6: Slack Review & Approve
        logger.info("Step 6: Sending plan to Slack for review...")
        step6_result = await client.call_tool("slack_review_approve", {
            "slack_message": output.get("slack_message", ""),
            "idea_title": output.get("title", idea["title"]),
        })
        step6_text = extract_text(step6_result)

        # Step 7: Check Approval
        logger.info("Step 7: Checking Slack approval response...")
        step7_result = await client.call_tool("check_approval", {
            "slack_response_json": step6_text,
        })
        step7_data = json.loads(extract_text(step7_result))
        approved = step7_data.get("approved", False)
        logger.info("Step 7: approved=%s route='%s'", approved, step7_data.get("route"))

        if approved:
            # Step 8: Archive to Sheets
            logger.info("Step 8: Archiving approved plan to Google Sheets...")
            step8_result = await client.call_tool("archive_to_sheets", {
                "idea_title": output.get("title", idea["title"]),
                "nodes": output.get("nodes", ""),
                "challenges": output.get("challenges", ""),
                "improvements": output.get("improvements", ""),
                "alternatives": output.get("alternatives", ""),
                "source_task_id": idea["id"],
            })
            step8_data = json.loads(extract_text(step8_result))
            logger.info("Step 8: Archived to '%s'", step8_data.get("file", ""))

            # Step 9: Mark as Notified
            logger.info("Step 9: Marking task '%s' as '✅ Processed'...", idea["id"])
            step9_result = await client.call_tool("mark_as_notified", {
                "task_id": idea["id"],
            })
            step9_data = json.loads(extract_text(step9_result))
            logger.info("Step 9: Task marked — status='%s'", step9_data.get("status"))
            return
        else:
            if attempt <= MAX_REGENERATE_ATTEMPTS:
                logger.info("Step 7: Not approved — regenerating plan (attempt %d of %d)...",
                            attempt, MAX_REGENERATE_ATTEMPTS)
            else:
                logger.warning("Step 7: Max regeneration attempts reached for '%s'. Skipping.", idea["title"])
                return


async def main() -> None:
    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info("Server started with %d tools registered", len(tools))
        logger.info("-" * 60)

        # Step 1: Schedule Trigger (inline)
        logger.info("=" * 60)
        logger.info("Step 1: Schedule Trigger — %s", datetime.utcnow().strftime("%Y-%m-%dT09:00:00Z"))
        logger.info("=" * 60)

        # Step 2: Get New Ideas
        logger.info("Step 2: Fetching new ideas from Google Tasks...")
        step2_result = await client.call_tool("get_new_ideas", {"limit": 5})
        step2_data = json.loads(extract_text(step2_result))
        logger.info("Step 2: Fetched %d tasks", step2_data.get("count", 0))

        # Step 3: Filter Processed
        logger.info("Step 3: Filtering already-processed tasks...")
        step3_result = await client.call_tool("filter_processed", {
            "tasks_json": extract_text(step2_result),
        })
        step3_data = json.loads(extract_text(step3_result))
        logger.info("Step 3: %d tasks remaining (skipped %d)",
                    step3_data.get("count", 0), step3_data.get("skipped", 0))

        ideas = step3_data.get("tasks", [])
        if not ideas:
            logger.info("No unprocessed ideas found. Workflow complete.")
            return

        # Steps 4–9: Iterate over each idea
        logger.info("=" * 60)
        logger.info("Starting idea processing loop (%d ideas)...", len(ideas))
        logger.info("=" * 60)

        for idx, idea in enumerate(ideas):
            await process_idea(client, idea, idx, len(ideas))
            logger.info("-" * 40)

        logger.info("=" * 60)
        logger.info("All ideas processed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Workflow failed: %s", e, exc_info=True)
        raise
