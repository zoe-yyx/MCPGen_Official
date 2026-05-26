"""Threads Video Downloader Workflow.

Simulates the full download pipeline for Threads video URLs.
Steps match workflow.json step_id order:
  1  submit_form                  — user submits Threads URL via form
  2  fetch_threads_video_data     — call Threads Downloader RapidAPI
  3  check_video_exists           — verify download URL present
  4  download_video_file          — (success) download video binary
  5  upload_video_to_drive        — upload to Google Drive
  6  set_sharing_permissions      — make Drive file publicly accessible
  7  log_success_to_sheets        — log URL + Drive link to Google Sheets
  8  wait_before_logging_failure  — (failure) brief pause
  9  log_failure_to_sheets        — log URL + N/A to Google Sheets
"""

import asyncio
import json
import os
import sys

from fastmcp import Client

sys.path.insert(0, os.path.dirname(__file__))
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/workflow.log")

# Demo sessions: mix of valid Threads URLs and invalid ones
DEMO_URLS = [
    "ENDPOINT_PLACEHOLDER",
    "ENDPOINT_PLACEHOLDER",
    "ENDPOINT_PLACEHOLDER",   # no video found
    "ENDPOINT_PLACEHOLDER",  # valid Threads URL
]


def extract_text(result) -> str:
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                return block.text
    return str(result)


async def handle_url(client: Client, url: str) -> None:
    """Run steps 1-7 (success) or 1-3, 8-9 (failure) for one URL submission."""
    logger.info("-" * 55)
    logger.info("Processing URL: %s", url)

    # Step 1: Submit Form
    step1 = extract_text(await client.call_tool("submit_form", {"url": url}))
    step1_data = json.loads(step1)
    logger.info("Step 1: form submitted with URL='%s'", step1_data["URL"])

    # Step 2: Fetch Threads Video Data
    step2 = extract_text(await client.call_tool("fetch_threads_video_data", {
        "url": step1_data["URL"],
    }))
    step2_data = json.loads(step2)
    logger.info("Step 2: API status='%s' video_count=%d", step2_data["status"], len(step2_data.get("video_urls", [])))

    # Step 3: Check If Video Exists
    step3 = extract_text(await client.call_tool("check_video_exists", {
        "api_response_json": step2,
    }))
    step3_data = json.loads(step3)
    logger.info("Step 3: has_video=%s download_url=%s", step3_data["has_video"], step3_data["download_url"])

    if step3_data["has_video"]:
        # SUCCESS PATH: Steps 4 → 5 → 6 → 7

        # Step 4: Download Video File
        step4 = extract_text(await client.call_tool("download_video_file", {
            "download_url": step3_data["download_url"],
        }))
        step4_data = json.loads(step4)
        logger.info("Step 4: downloaded → %s (%d bytes)", step4_data["filename"], step4_data["size_bytes"])

        # Step 5: Upload to Google Drive
        step5 = extract_text(await client.call_tool("upload_video_to_drive", {
            "local_video_path": step4_data["local_path"],
            "filename": step4_data["filename"],
        }))
        step5_data = json.loads(step5)
        logger.info("Step 5: uploaded → Drive id=%s", step5_data["id"])

        # Step 6: Set Sharing Permissions
        step6 = extract_text(await client.call_tool("set_sharing_permissions", {
            "file_id": step5_data["id"],
        }))
        step6_data = json.loads(step6)
        logger.info("Step 6: sharing set → %s", step6_data["sharing_url"])

        # Step 7: Log Success to Sheets
        step7 = extract_text(await client.call_tool("log_success_to_sheets", {
            "url": step1_data["URL"],
            "drive_url": step5_data["webViewLink"],
        }))
        step7_data = json.loads(step7)
        logger.info("Step 7: logged success → %s", step7_data["csv_file"])
        logger.info("Result: SUCCESS | Drive → %s", step5_data["webViewLink"])

    else:
        # FAILURE PATH: Steps 8 → 9

        # Step 8: Wait Before Logging Failure
        step8 = extract_text(await client.call_tool("wait_before_logging_failure", {
            "seconds": 1,
        }))
        step8_data = json.loads(step8)
        logger.info("Step 8: waited %ds — %s", step8_data["waited_seconds"], step8_data["note"])

        # Step 9: Log Failure to Sheets
        step9 = extract_text(await client.call_tool("log_failure_to_sheets", {
            "url": step1_data["URL"],
        }))
        step9_data = json.loads(step9)
        logger.info("Step 9: logged failure → %s", step9_data["csv_file"])
        logger.info("Result: FAILED | logged N/A for URL")


async def main() -> None:
    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info("Server started with %d tools registered", len(tools))
        logger.info("=" * 55)
        logger.info("ThreadsDownloader — Video Download Pipeline")
        logger.info("=" * 55)

        for url in DEMO_URLS:
            await handle_url(client, url)

        logger.info("=" * 55)
        logger.info("All demo URLs processed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Workflow failed: %s", e, exc_info=True)
        raise
