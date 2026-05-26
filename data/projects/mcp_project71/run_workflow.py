"""Instant Ad Banner Generator Workflow.

Converts a LINE user message into a generated marketing banner using:
  GPT prompt optimization → AI image generation → S3 hosting → LINE reply

Step order (matches workflow.json step_id):
  1  receive_line_webhook   — simulate LINE user message
  2  extract_line_data      — parse replyToken, userId, message
  3  optimize_prompt        — GPT writes English image generation prompt
  4  extract_prompt_text    — clean prompt text from GPT response
  5  submit_image_generation — submit job to mock kie.ai API
  6  wait_for_processing    — pause 10s (mock)
  7  check_job_status       — poll job status
  8  wait_for_generation    — pause 10s (mock)
  9  parse_result           — extract imageUrl (loop if still processing)
  10 download_image         — download image or create placeholder
  11 upload_to_s3           — mock S3 upload → return public URL
  12 send_line_reply        — mock LINE image reply
"""

import asyncio
import json
import os
import sys

from fastmcp import Client

sys.path.insert(0, os.path.dirname(__file__))
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/workflow.log")

MAX_POLL_ATTEMPTS = 5

# Sample LINE messages to demo the workflow
DEMO_MESSAGES = [
    "商品名: プレミアムコーヒー / ターゲット: 30代ビジネスマン / キャッチコピー: 朝の一杯が、仕事を変える。",
    "商品名: スマートウォッチ / ターゲット: フィットネス愛好家 / キャッチコピー: あなたの健康を、腕に巻く。",
]


def extract_text(result) -> str:
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return block.text
    return str(result)


async def run_banner_generation(client: Client, message: str) -> None:
    """Run all 12 workflow steps for one banner generation request."""
    logger.info("=" * 60)
    logger.info("Banner Generation — message: '%s'", message[:60])
    logger.info("=" * 60)

    # Step 1: Receive LINE Webhook
    logger.info("Step 1: Receiving LINE webhook...")
    step1_result = await client.call_tool("receive_line_webhook", {
        "message": message,
        "user_id": "U1234567890abcdef",
    })
    logger.info("Step 1: Webhook received")

    # Step 2: Extract LINE Data
    logger.info("Step 2: Extracting LINE event data...")
    step2_result = await client.call_tool("extract_line_data", {
        "webhook_json": extract_text(step1_result),
    })
    step2_data = json.loads(extract_text(step2_result))
    logger.info("Step 2: user_id='%s' reply_token='%s'",
                step2_data["user_id"], step2_data["reply_token"][:20] + "...")

    # Step 3: Optimize Prompt (Marketing)
    logger.info("Step 3: Optimizing marketing prompt with GPT...")
    step3_result = await client.call_tool("optimize_prompt", {
        "message": step2_data["message"],
    })
    logger.info("Step 3: GPT prompt response received")

    # Step 4: Extract Prompt Text
    logger.info("Step 4: Extracting clean prompt text...")
    step4_result = await client.call_tool("extract_prompt_text", {
        "response_json": extract_text(step3_result),
        "user_id": step2_data["user_id"],
    })
    step4_data = json.loads(extract_text(step4_result))
    logger.info("Step 4: prompt='%s'", step4_data["prompt"][:100] + "...")

    # Step 5: Submit Image Generation
    logger.info("Step 5: Submitting image generation job to Nano Banana Pro...")
    step5_result = await client.call_tool("submit_image_generation", {
        "prompt": step4_data["prompt"],
    })
    step5_data = json.loads(extract_text(step5_result))
    task_id = step5_data["data"]["taskId"]
    record_id = step5_data["data"]["recordId"]
    logger.info("Step 5: task_id='%s'", task_id)

    # Steps 6-9: Poll until image is ready
    image_url = None
    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        # Step 6: Wait for Processing
        logger.info("Step 6: Waiting for processing (attempt %d)...", attempt)
        await client.call_tool("wait_for_processing", {"seconds": 10})

        # Step 7: Check Job Status
        logger.info("Step 7: Checking job status...")
        step7_result = await client.call_tool("check_job_status", {
            "task_id": task_id,
            "record_id": record_id,
        })

        # Step 8: Wait for Generation
        logger.info("Step 8: Waiting for generation...")
        await client.call_tool("wait_for_generation", {"seconds": 10})

        # Step 9: Parse Result
        logger.info("Step 9: Parsing generation result...")
        step9_result = await client.call_tool("parse_result", {
            "status_response_json": extract_text(step7_result),
        })
        step9_data = json.loads(extract_text(step9_result))
        logger.info("Step 9: status='%s'", step9_data.get("status"))

        if step9_data.get("status") == "completed":
            image_url = step9_data["imageUrl"]
            logger.info("Step 9: Image URL='%s'", image_url)
            break
        elif step9_data.get("status") == "error":
            raise RuntimeError(f"Image generation error: {step9_data.get('message')}")
        else:
            logger.info("Step 9: Still processing, retrying...")

    if not image_url:
        raise RuntimeError("Image generation did not complete within max poll attempts")

    # Step 10: Download Image
    logger.info("Step 10: Downloading generated image...")
    step10_result = await client.call_tool("download_image", {"image_url": image_url})
    step10_data = json.loads(extract_text(step10_result))
    logger.info("Step 10: Downloaded to '%s' (%d bytes, downloaded=%s)",
                step10_data["file_path"], step10_data["file_size"], step10_data["downloaded"])

    # Step 11: Upload to S3
    logger.info("Step 11: Uploading to S3...")
    step11_result = await client.call_tool("upload_to_s3", {
        "file_path": step10_data["file_path"],
    })
    step11_data = json.loads(extract_text(step11_result))
    logger.info("Step 11: S3 URL='%s'", step11_data["Location"])

    # Step 12: Send LINE Reply
    logger.info("Step 12: Sending LINE image reply...")
    step12_result = await client.call_tool("send_line_reply", {
        "reply_token": step2_data["reply_token"],
        "image_url": step11_data["Location"],
    })
    step12_data = json.loads(extract_text(step12_result))
    logger.info("Step 12: LINE reply sent — status='%s' file='%s'",
                step12_data["status"], step12_data["file"])


async def main() -> None:
    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info("Server started with %d tools registered", len(tools))
        logger.info("-" * 60)

        for message in DEMO_MESSAGES:
            await run_banner_generation(client, message)
            logger.info("-" * 60)

        logger.info("All banner generation workflows completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Workflow failed: %s", e, exc_info=True)
        raise
