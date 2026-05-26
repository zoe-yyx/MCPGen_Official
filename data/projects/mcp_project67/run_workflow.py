"""AI-Powered Recruitment Pipeline Workflow.

Executes the full recruitment pipeline via MCP server using fastmcp Client.
Steps follow the n8n workflow order:
1.  Webhook - Receive CV
2.  Airtable - Store Candidate
3.  Airtable - Get Job Requirements
4.  HTTP Request - Download CV
5.  AI - Extract CV Data (GPT)
6.  AI Agent - Qualification Assessment (GPT)
7.  Airtable - Update Assessment
8.  Filter - Qualified Candidates
9.  AI Agent - Generate Email (GPT, if qualified)
10. Send Email - Candidate Outreach (if qualified)
11. Filter - Interview Candidates
12. Google Calendar - Schedule Interview (if interview)
13. Slack - Send Notification
14. Airtable - Update Interview Details (if interview)
15. Respond to Webhook
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
    # Sample candidate input
    candidate = {
        "name": "John Doe",
        "email": "EMAIL_PLACEHOLDER",
        "phone": "+1-555-0123",
        "cv_url": "ENDPOINT_PLACEHOLDER",
        "position": "Software Engineer",
    }

    async with Client("mcp_server/server.py") as client:
        tools = await client.list_tools()
        logger.info("Available tools:")
        for tool in tools:
            logger.info(f"  - {tool.name}")
        logger.info("-" * 60)

        # ── Step 1: Webhook - Receive CV ──
        logger.info("Step 1: Receiving CV submission...")
        step1_result = await client.call_tool("receive_cv", candidate)
        step1_data = json.loads(extract_text(step1_result))
        body = step1_data["body"]
        logger.info(f"Step 1: Received CV for {body['name']} applying to {body['position']}")

        # ── Step 2: Airtable - Store Candidate ──
        logger.info("Step 2: Storing candidate in Airtable...")
        step2_result = await client.call_tool("store_candidate", {
            "name": body["name"],
            "email": body["email"],
            "phone": body["phone"],
            "cv_url": body["cv_url"],
            "position": body["position"],
        })
        step2_data = json.loads(extract_text(step2_result))
        candidate_id = step2_data["id"]
        logger.info(f"Step 2: Stored candidate with ID={candidate_id}")

        # ── Step 3: Airtable - Get Job Requirements ──
        logger.info("Step 3: Fetching job requirements...")
        step3_result = await client.call_tool("get_job_requirements", {
            "position": body["position"],
        })
        step3_data = extract_text(step3_result)
        job_req = json.loads(step3_data)
        logger.info(f"Step 3: Got requirements for {job_req['Position']}")

        # ── Step 4: HTTP Request - Download CV ──
        logger.info("Step 4: Downloading CV...")
        step4_result = await client.call_tool("download_cv", {
            "cv_url": body["cv_url"],
        })
        step4_data = json.loads(extract_text(step4_result))
        logger.info(f"Step 4: Downloaded CV ({len(step4_data['text'])} chars)")

        # ── Step 5: AI - Extract CV Data ──
        logger.info("Step 5: Extracting CV data with AI...")
        step5_result = await client.call_tool("extract_cv_data", {
            "cv_text": step4_data["text"],
        })
        step5_data = extract_text(step5_result)
        cv_extracted = json.loads(step5_data)
        logger.info(f"Step 5: Extracted {len(cv_extracted.get('skills', []))} skills, "
                     f"{cv_extracted.get('years_experience', '?')} years experience")

        # ── Step 6: AI Agent - Qualification Assessment ──
        logger.info("Step 6: Running AI qualification assessment...")
        step6_result = await client.call_tool("assess_qualification", {
            "cv_data": step5_data,
            "job_requirements": step3_data,
        })
        step6_data = extract_text(step6_result)
        assessment = json.loads(step6_data)
        logger.info(f"Step 6: Score={assessment['match_score']}, "
                     f"Status={assessment['status']}, "
                     f"Recommendation={assessment['recommendation']}")

        # ── Step 7: Airtable - Update Assessment ──
        logger.info("Step 7: Updating Airtable with assessment...")
        strengths_str = ", ".join(assessment.get("strengths", []))
        gaps_str = ", ".join(assessment.get("gaps", []))
        skills_str = ", ".join(cv_extracted.get("skills", []))

        await client.call_tool("update_assessment", {
            "candidate_id": candidate_id,
            "match_score": assessment["match_score"],
            "status": assessment["status"],
            "recommendation": assessment["recommendation"],
            "strengths": strengths_str,
            "gaps": gaps_str,
            "reasoning": assessment.get("reasoning", ""),
            "skills": skills_str,
            "education": cv_extracted.get("education", ""),
            "years_experience": cv_extracted.get("years_experience", 0),
        })
        logger.info("Step 7: Assessment updated in Airtable")

        # ── Step 8: Filter - Qualified Candidates ──
        # (parallel branch A from Step 7)
        logger.info("Step 8: Filtering qualified candidates...")
        step8_result = await client.call_tool("filter_qualified", {
            "assessment_data": step6_data,
        })
        step8_data = json.loads(extract_text(step8_result))
        is_qualified = step8_data["passed"]
        is_interview = False
        logger.info(f"Step 8: Qualified={is_qualified}")

        if is_qualified:
            # ── Step 9: AI Agent - Generate Email ──
            logger.info("Step 9: Generating personalized email...")
            step9_result = await client.call_tool("generate_recruitment_email", {
                "candidate_name": body["name"],
                "position": body["position"],
                "match_score": assessment["match_score"],
                "status": assessment["status"],
                "recommendation": assessment["recommendation"],
                "strengths": strengths_str,
            })
            step9_data = json.loads(extract_text(step9_result))
            logger.info(f"Step 9: Email generated - Subject: {step9_data['subject']}")

            # ── Step 10: Send Email - Candidate Outreach ──
            logger.info("Step 10: Sending candidate email...")
            step10_result = await client.call_tool("send_candidate_email", {
                "to_email": body["email"],
                "from_email": os.getenv("EMAIL_FROM", "EMAIL_PLACEHOLDER"),
                "subject": step9_data["subject"],
                "body": step9_data["body"],
            })
            logger.info(f"Step 10: {extract_text(step10_result)}")

            # ── Step 11: Filter - Interview Candidates ──
            logger.info("Step 11: Checking if candidate qualifies for interview...")
            step11_result = await client.call_tool("filter_interview", {
                "assessment_data": step6_data,
            })
            step11_data = json.loads(extract_text(step11_result))
            is_interview = step11_data["passed"]
            logger.info(f"Step 11: Interview={is_interview}")

            if is_interview:
                # ── Step 12: Google Calendar - Schedule Interview ──
                logger.info("Step 12: Scheduling interview on Google Calendar...")
                step12_result = await client.call_tool("schedule_interview", {
                    "candidate_name": body["name"],
                    "position": body["position"],
                    "days_from_now": 3,
                })
                step12_data = json.loads(extract_text(step12_result))
                logger.info(f"Step 12: Interview scheduled - {step12_data['start']['dateTime']}")
                logger.info(f"  Meet link: {step12_data['hangoutLink']}")
        else:
            logger.info("Steps 9-12: Skipped (candidate not qualified)")

        # ── Step 13: Slack - Send Notification ──
        # (parallel branch B from Step 7, independent of Steps 8-12)
        logger.info("Step 13: Sending Slack notification...")
        step13_result = await client.call_tool("send_slack_notification", {
            "candidate_name": body["name"],
            "position": body["position"],
            "match_score": assessment["match_score"],
            "status": assessment["status"],
            "recommendation": assessment["recommendation"],
            "strengths": strengths_str,
            "candidate_id": candidate_id,
        })
        logger.info(f"Step 13: {extract_text(step13_result)}")

        # ── Step 14: Airtable - Update Interview Details ──
        # (follows Step 12, only if interview was scheduled)
        if is_qualified and is_interview:
            logger.info("Step 14: Updating interview details in Airtable...")
            await client.call_tool("update_interview_details", {
                "candidate_id": candidate_id,
                "interview_scheduled": step12_data["start"]["dateTime"],
                "interview_link": step12_data["hangoutLink"],
                "calendar_event_id": step12_data["id"],
            })
            logger.info("Step 14: Interview details updated")
        else:
            logger.info("Step 14: Skipped (no interview scheduled)")

        # ── Step 15: Respond to Webhook ──
        logger.info("Step 15: Generating webhook response...")
        step15_result = await client.call_tool("respond_webhook", {
            "candidate_id": candidate_id,
            "candidate_name": body["name"],
            "match_score": assessment["match_score"],
            "status": assessment["status"],
            "recommendation": assessment["recommendation"],
        })
        step15_data = json.loads(extract_text(step15_result))
        logger.info(f"Step 15: Final response: {json.dumps(step15_data, indent=2)}")

        logger.info("=" * 60)
        logger.info("Workflow completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        raise
