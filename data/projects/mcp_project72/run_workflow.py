"""AI Hotel Receptionist Workflow.

Simulates hotel guest WhatsApp interactions with an AI receptionist powered by GPT.
Steps match workflow.json step_id order:
  1 receive_whatsapp_message  — simulate WhatsApp guest message
  2 check_message             — validate text message
  3 check_user_model          — Redis GET: retrieve model assignment
  4 decide_model              — alternate model index
  5 store_user_model          — Redis SET: persist new model assignment
  6 ai_hotel_agent            — GPT agent with SQL + pricing tools
  7 send_whatsapp_reply       — mock WhatsApp reply
"""

import asyncio
import json
import os
import sys

from fastmcp import Client

sys.path.insert(0, os.path.dirname(__file__))
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/workflow.log")

# Demo guest conversations
DEMO_SESSIONS = [
    {"wa_id": "601234567890", "phone": "601234567890", "messages": [
        "What rooms are currently available?",
        "What is the price for a Suite room?",
    ]},
    {"wa_id": "601987654321", "phone": "601987654321", "messages": [
        "Show me all bookings checking in today or tomorrow",
    ]},
    {"wa_id": "601234567890", "phone": "601234567890", "messages": [
        "I want to book room 203 — can you do that for me?",
    ]},
]


def extract_text(result) -> str:
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return block.text
    return str(result)


async def handle_message(client: Client, wa_id: str, phone: str, message: str) -> None:
    """Run steps 1-7 for a single guest message."""
    logger.info("-" * 50)
    logger.info("Guest [%s]: %s", wa_id, message)

    # Step 1: Receive WhatsApp Message
    step1_result = await client.call_tool("receive_whatsapp_message", {
        "message": message,
        "wa_id": wa_id,
        "phone_number": phone,
    })

    # Step 2: Check Message
    step2_result = await client.call_tool("check_message", {
        "webhook_json": extract_text(step1_result),
    })
    step2_data = json.loads(extract_text(step2_result))
    if not step2_data.get("valid"):
        logger.info("Step 2: Not a valid text message — skipping")
        return
    logger.info("Step 2: Valid message from wa_id='%s'", step2_data["wa_id"])

    # Step 3: Check User Number (Redis GET)
    step3_result = await client.call_tool("check_user_model", {
        "wa_id": step2_data["wa_id"],
    })
    step3_data = json.loads(extract_text(step3_result))
    logger.info("Step 3: Redis value='%s' found=%s", step3_data["value"], step3_data["found"])

    # Step 4: Model Decider
    step4_result = await client.call_tool("decide_model", {
        "redis_value": step3_data["value"],
    })
    step4_data = json.loads(extract_text(step4_result))
    logger.info("Step 4: model_index=%d (%s)", step4_data["model_index"], step4_data["model_name"])

    # Step 5: Store User Number (Redis SET)
    step5_result = await client.call_tool("store_user_model", {
        "wa_id": step2_data["wa_id"],
        "model_index": step4_data["model_index"],
    })
    step5_data = json.loads(extract_text(step5_result))
    logger.info("Step 5: Redis SET key='%s' TTL=%ds", step5_data["key"], step5_data["ttl"])

    # Step 6: AI Hotel Agent
    logger.info("Step 6: AI agent processing...")
    step6_result = await client.call_tool("ai_hotel_agent", {
        "user_message": step2_data["message"],
        "wa_id": step2_data["wa_id"],
        "model_index": step4_data["model_index"],
    })
    step6_data = json.loads(extract_text(step6_result))
    logger.info("Step 6: AI response (%d chars)", len(step6_data["output"]))

    # Step 7: Send WhatsApp Reply
    step7_result = await client.call_tool("send_whatsapp_reply", {
        "recipient_phone": step2_data["from_phone"],
        "message_text": step6_data["output"],
    })
    step7_data = json.loads(extract_text(step7_result))
    logger.info("Step 7: Reply sent → '%s'", step7_data["message_preview"])
    logger.info("Bot: %s", step6_data["output"])


async def main() -> None:
    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info("Server started with %d tools registered", len(tools))
        logger.info("=" * 60)
        logger.info("AI Hotel Receptionist — Grand Palace Hotel")
        logger.info("=" * 60)

        for session in DEMO_SESSIONS:
            for msg in session["messages"]:
                await handle_message(client, session["wa_id"], session["phone"], msg)

        logger.info("=" * 60)
        logger.info("All demo conversations completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Workflow failed: %s", e, exc_info=True)
        raise
