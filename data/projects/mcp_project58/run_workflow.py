"""
run_workflow.py — AI-powered leads-to-sales outreach automation

Replicates the n8n workflow execution order:

  [Step 1]  Get row(s) in sheet        -> get_leads (mock: local CSV)
       |
  [Step 2]  If1 (filter unresearched)  -> filter_unresearched_leads
       |
  [Loop over each lead]
       |
  [Step 3]  Search Internet1           -> search_internet (mock Tavily)
       |
  [Step 4]  Company Research1          -> research_company (OpenAI)
       |
  [Step 5]  updateDescription          -> update_lead_research (mock Sheets)
       |
  [Step 6]  updateStatus               -> update_lead_status (mock Sheets)
       |
  [Step 7]  getTemplate                -> get_email_template (mock Sheets)
       |
  [Step 8]  getService                 -> get_services (mock Sheets)
       |
  [Step 9]  Search Internet2           -> search_internet (mock Tavily)
       |
  [Step 10] AI Sales Assistant         -> draft_sales_email (OpenAI)
       |
  [Step 11] draftEmail                 -> save_email_draft (mock Sheets)
       |
  [Step 12] Code (URL encode)          -> encode_company_url
       |
  [Step 13] inputLink                  -> save_send_link (mock Sheets)
       |
  [next lead in loop]

Run:
    uv run python run_workflow.py
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client

from mcp_server.tools.utils.log_decorator import setup_logging

load_dotenv()
logger = setup_logging("logs/workflow.log")

LEADS_CSV = os.getenv("LEADS_CSV_PATH", "data/leads.csv")
TEMPLATES_CSV = os.getenv("TEMPLATES_CSV_PATH", "data/templates.csv")
SERVICES_CSV = os.getenv("SERVICES_CSV_PATH", "data/services.csv")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(result) -> dict | list:
    """Extract dict/list from a fastmcp CallToolResult."""
    if not result.content:
        return []
    raw = result.content[0].text
    return json.loads(raw)


def _parse_text(result) -> str:
    """Extract plain text from a fastmcp CallToolResult."""
    if not result.content:
        return ""
    return result.content[0].text


# ---------------------------------------------------------------------------
# Reset leads CSV before each run
# ---------------------------------------------------------------------------

RESET_FIELDS = ["Hasil Riset", "Status", "Send Email Perkenalan", "Kirim email"]


def reset_leads_csv(csv_path: str) -> None:
    """Clear research/status/email fields so all leads are re-processed."""
    rows: list[dict] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            for field in RESET_FIELDS:
                if field in row:
                    row[field] = ""
            rows.append(row)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

async def run_workflow() -> None:
    # Reset leads CSV so every run starts fresh
    reset_leads_csv(LEADS_CSV)
    logger.info("Leads CSV reset — all leads will be re-processed.")

    logger.info(f"{'=' * 60}")
    logger.info("  AI-powered Leads-to-Sales Outreach Automation")
    logger.info(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 60}")

    async with Client("mcp_server/server.py") as client:

        # List available tools
        tools = await client.list_tools()
        logger.info(f"\nAvailable tools ({len(tools)}):")
        for tool in tools:
            logger.info(f"  - {tool.name}")

        # ==============================================================
        # Step 1 — Get leads from CSV
        # ==============================================================
        logger.info(f"\n{'=' * 60}")
        logger.info("[Step 1] Reading leads from CSV ...")
        result = await client.call_tool("get_leads", {"csv_path": LEADS_CSV})
        all_leads = _parse(result)
        logger.info(f"  -> Found {len(all_leads)} total leads")

        # ==============================================================
        # Step 2 — Filter unresearched leads
        # ==============================================================
        logger.info(f"\n{'─' * 50}")
        logger.info("[Step 2] Filtering unresearched leads ...")
        result = await client.call_tool("filter_unresearched_leads", {
            "leads_json": json.dumps(all_leads),
        })
        leads_to_process = _parse(result)
        logger.info(f"  -> {len(leads_to_process)} leads need processing")

        if not leads_to_process:
            logger.info("  No new leads to process. Workflow complete.")
            return

        # ==============================================================
        # Loop over each lead
        # ==============================================================
        processed: list[dict] = []

        for idx, lead in enumerate(leads_to_process, start=1):
            company = lead["Perusahaan"]
            name = lead.get("Nama", "")
            position = lead.get("Jabatan", "")

            logger.info(f"\n{'=' * 60}")
            logger.info(f"[Lead {idx}/{len(leads_to_process)}] {company}")
            logger.info(f"  Contact: {name} ({position})")

            try:
                # --------------------------------------------------
                # Step 3 — Search Internet for company info
                # --------------------------------------------------
                logger.info(f"\n  {'─' * 40}")
                logger.info("  [Step 3] Searching internet for company info ...")
                result = await client.call_tool("search_internet", {
                    "query": f"{company} business overview AI opportunities",
                })
                search_results = _parse_text(result)
                logger.info(f"  -> Search returned {len(search_results)} chars")

                # --------------------------------------------------
                # Step 4 — AI Company Research
                # --------------------------------------------------
                logger.info(f"\n  {'─' * 40}")
                logger.info("  [Step 4] Running AI company research ...")
                result = await client.call_tool("research_company", {
                    "company_name": company,
                    "search_results": search_results,
                })
                research_output = _parse_text(result)
                logger.info(f"  -> Research: {research_output[:150]}...")

                # --------------------------------------------------
                # Step 5 — Save research results
                # --------------------------------------------------
                logger.info(f"\n  {'─' * 40}")
                logger.info("  [Step 5] Saving research results ...")
                result = await client.call_tool("update_lead_research", {
                    "csv_path": LEADS_CSV,
                    "company_name": company,
                    "research_result": research_output,
                })
                logger.info(f"  -> {_parse(result)['status']}")

                # --------------------------------------------------
                # Step 6 — Update lead status to "Leads"
                # --------------------------------------------------
                logger.info(f"\n  {'─' * 40}")
                logger.info("  [Step 6] Updating lead status ...")
                result = await client.call_tool("update_lead_status", {
                    "csv_path": LEADS_CSV,
                    "company_name": company,
                    "status": "Leads",
                })
                logger.info(f"  -> {_parse(result)['status']}")

                # --------------------------------------------------
                # Step 7 — Get email template
                # --------------------------------------------------
                logger.info(f"\n  {'─' * 40}")
                logger.info("  [Step 7] Getting email template ...")
                result = await client.call_tool("get_email_template", {
                    "csv_path": TEMPLATES_CSV,
                    "stage": "Leads",
                })
                template = _parse(result)
                logger.info(f"  -> Theme: {template.get('Tema', 'N/A')}")

                # --------------------------------------------------
                # Step 8 — Get services list
                # --------------------------------------------------
                logger.info(f"\n  {'─' * 40}")
                logger.info("  [Step 8] Getting services list ...")
                result = await client.call_tool("get_services", {
                    "csv_path": SERVICES_CSV,
                })
                services = _parse(result)
                logger.info(f"  -> {len(services)} services available")

                # --------------------------------------------------
                # Step 9 — Search Internet for email hook
                # --------------------------------------------------
                logger.info(f"\n  {'─' * 40}")
                logger.info("  [Step 9] Searching for email hook data ...")
                hook_query = f"{position} challenges {company} industry 2025"
                result = await client.call_tool("search_internet", {
                    "query": hook_query,
                })
                additional_research = _parse_text(result)
                logger.info(f"  -> Hook search returned {len(additional_research)} chars")

                # --------------------------------------------------
                # Step 10 — AI Sales Assistant (draft email)
                # --------------------------------------------------
                logger.info(f"\n  {'─' * 40}")
                logger.info("  [Step 10] Drafting sales email with AI ...")
                result = await client.call_tool("draft_sales_email", {
                    "company": company,
                    "recipient_name": name,
                    "recipient_position": position,
                    "research_result": research_output,
                    "stage": template.get("Tahap", "Leads"),
                    "theme": template.get("Tema", ""),
                    "sample_message": template.get("Contoh message", ""),
                    "services_json": json.dumps(services),
                    "additional_research": additional_research,
                })
                email_draft = _parse(result)
                logger.info(f"  -> Subject: {email_draft.get('emailSubject', 'N/A')}")

                # --------------------------------------------------
                # Step 11 — Save email draft
                # --------------------------------------------------
                logger.info(f"\n  {'─' * 40}")
                logger.info("  [Step 11] Saving email draft ...")
                result = await client.call_tool("save_email_draft", {
                    "csv_path": LEADS_CSV,
                    "company_name": company,
                    "email_draft": json.dumps(email_draft, ensure_ascii=False),
                })
                logger.info(f"  -> {_parse(result)['status']}")

                # --------------------------------------------------
                # Step 12 — URL encode company name
                # --------------------------------------------------
                logger.info(f"\n  {'─' * 40}")
                logger.info("  [Step 12] Encoding company URL ...")
                result = await client.call_tool("encode_company_url", {
                    "company_name": company,
                })
                encoded = _parse(result)
                logger.info(f"  -> Encoded: {encoded['encoded']}")

                # --------------------------------------------------
                # Step 13 — Save send-email link
                # --------------------------------------------------
                logger.info(f"\n  {'─' * 40}")
                logger.info("  [Step 13] Saving send-email link ...")
                send_link = f"ENDPOINT_PLACEHOLDER'encoded']}"
                result = await client.call_tool("save_send_link", {
                    "csv_path": LEADS_CSV,
                    "company_name": company,
                    "send_link": send_link,
                })
                logger.info(f"  -> {_parse(result)['status']}")

                processed.append({
                    "company": company,
                    "contact": name,
                    "position": position,
                    "emailSubject": email_draft.get("emailSubject", ""),
                    "status": "success",
                })

            except Exception as exc:
                logger.error(f"  Failed for {company}: {type(exc).__name__}: {exc}")
                processed.append({"company": company, "status": "error", "error": str(exc)})

        # ==============================================================
        # Save run metrics
        # ==============================================================
        metrics_path = Path("results/metrics/run_metrics.json")
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        run_summary = {
            "run_at": datetime.now().isoformat(),
            "total_leads": len(all_leads),
            "processed": len(leads_to_process),
            "successful": sum(1 for p in processed if p["status"] == "success"),
            "details": processed,
        }
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(run_summary, f, indent=2, ensure_ascii=False)

        # Save email drafts to outputs
        outputs_dir = Path("results/outputs")
        outputs_dir.mkdir(parents=True, exist_ok=True)
        with open(outputs_dir / "email_drafts.json", "w", encoding="utf-8") as f:
            json.dump(processed, f, indent=2, ensure_ascii=False)

        logger.info(f"\n{'=' * 60}")
        logger.info("  Workflow complete.")
        logger.info(f"  Total leads: {len(all_leads)}")
        logger.info(f"  Processed: {run_summary['successful']}/{run_summary['processed']}")
        logger.info(f"  Metrics: {metrics_path}")
        logger.info(f"  Drafts: {outputs_dir / 'email_drafts.json'}")
        logger.info(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_workflow())
