"""
run_workflow.py -- Automated QR Ticket Scanner & Validator

Replicates the n8n workflow execution order:

  Sheets Update Trigger
       |
  Step 1: get_form_responses     (Trigger - read QR scan submissions)
       |
  [Loop over each scan]
       |
  Step 2: select_latest_item     (Get last row from triggered data)
       |
  Step 3: set_ticket_code        (Extract QR code -> kode_tiket)
       |
  Step 4: read_ticket_rows       (Lookup ticket in database)
       |
  Step 5: validate_ticket        (Route: VALID vs TIDAK VALID)
       |
    VALID path:
  Step 6a: append_scan_result    (Append with participant info, STATUS=VALID)
       |
    TIDAK VALID path:
  Step 6b: get_form_responses    (Read form responses sheet)
       |
  Step 7: select_latest_item     (Get latest form response)
       |
  Step 8: append_scan_result     (Append with placeholder data, STATUS=TIDAK VALID)

Run:
    uv run python run_workflow.py
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from fastmcp import Client
from mcp_server.tools.utils.log_decorator import setup_logging

logger = setup_logging("logs/workflow.log")

RESULTS_DIR = "results/outputs"


def save_result(name: str, data: dict | list) -> None:
    """Save a result to the results/outputs directory."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    filepath = os.path.join(RESULTS_DIR, f"{name}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"  Result saved to {filepath}")


def _parse(result) -> dict | list | str:
    """Extract data from a fastmcp CallToolResult."""
    if hasattr(result, "data"):
        return result.data
    if hasattr(result, "content") and result.content:
        raw = result.content[0].text
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
    return str(result)


async def process_single_scan(client, qr_code: str, scan_index: int) -> dict:
    """Process a single QR code scan through the full validation pipeline."""
    logger.info(f"\n{'─' * 50}")
    logger.info(f"[Scan {scan_index}] QR code = '{qr_code}'")

    # ------------------------------------------------------------------
    # Step 3 — Set Ticket Code Field
    # ------------------------------------------------------------------
    logger.info("  [Step 3] Set ticket code - extract kode_tiket from QR code")
    result = await client.call_tool("set_ticket_code", {"qr_code": qr_code})
    ticket_data = _parse(result)
    logger.info(f"  -> {ticket_data}")

    # ------------------------------------------------------------------
    # Step 4 — Read Trigger Sheet Rows (lookup by ticket code)
    # ------------------------------------------------------------------
    logger.info("  [Step 4] Read ticket rows - lookup in database")
    result = await client.call_tool("read_ticket_rows", {"ticket_code": qr_code})
    matched_rows = _parse(result)
    logger.info(f"  -> {len(matched_rows) if isinstance(matched_rows, list) else 0} row(s) matched")

    # ------------------------------------------------------------------
    # Step 5 — Route by Conditional Rules (validate ticket)
    # ------------------------------------------------------------------
    logger.info("  [Step 5] Validate ticket - route VALID / TIDAK VALID")
    result = await client.call_tool("validate_ticket", {
        "scanned_code": qr_code,
        "matched_rows": matched_rows if isinstance(matched_rows, list) else [],
    })
    validation = _parse(result)
    status = validation.get("status", "TIDAK VALID") if isinstance(validation, dict) else "TIDAK VALID"
    logger.info(f"  -> Status: {status}")

    if status == "VALID":
        # ------------------------------------------------------------------
        # Step 6a — Append Scan Results (VALID path)
        # ------------------------------------------------------------------
        record = validation["matched_record"]
        logger.info("  [Step 6a] Append scan result - VALID with participant info")
        result = await client.call_tool("append_scan_result", {
            "ticket_id": record["ID"],
            "nama": record["NAMA"],
            "email": record["EMAIL"],
            "no_hp": record["NO HP"],
            "tiket": record["TIKET"],
            "status": "VALID",
            "ukuran_jersey": record["UKURAN JERSEY"],
            "golongan_darah": record["GOLONGAN DARAH"],
        })
        appended = _parse(result)
        logger.info(f"  -> Appended: {appended}")
        return {"scan": qr_code, "status": "VALID", "record": appended}
    else:
        # ------------------------------------------------------------------
        # Step 6b — Read Form Responses Sheet (TIDAK VALID path)
        # ------------------------------------------------------------------
        logger.info("  [Step 6b] Read form responses - TIDAK VALID path")
        result = await client.call_tool("get_form_responses", {})
        form_responses = _parse(result)

        # ------------------------------------------------------------------
        # Step 7 — Select Latest Form Response
        # ------------------------------------------------------------------
        logger.info("  [Step 7] Select latest form response")
        if isinstance(form_responses, list) and form_responses:
            result = await client.call_tool("select_latest_item", {"items": form_responses})
            latest = _parse(result)
            logger.info(f"  -> Latest: {latest}")

        # ------------------------------------------------------------------
        # Step 8 — Append to Scan Results Sheet (TIDAK VALID)
        # ------------------------------------------------------------------
        logger.info("  [Step 8] Append scan result - TIDAK VALID with placeholder data")
        result = await client.call_tool("append_scan_result", {
            "ticket_id": "-",
            "nama": "-",
            "email": "-",
            "no_hp": "-",
            "tiket": qr_code,
            "status": "TIDAK VALID",
            "ukuran_jersey": "-",
            "golongan_darah": "-",
        })
        appended = _parse(result)
        logger.info(f"  -> Appended: {appended}")
        return {"scan": qr_code, "status": "TIDAK VALID", "record": appended}


async def main() -> None:
    logger.info("=" * 60)
    logger.info("  Automated QR Ticket Scanner & Validator Workflow")
    logger.info(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Reset scan results before running
    os.makedirs("data", exist_ok=True)
    with open("data/scan_results.json", "w", encoding="utf-8") as f:
        json.dump([], f)

    async with Client("mcp_server/server.py") as client:
        # List available tools
        tools = await client.list_tools()
        logger.info("Available tools:")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description}")
        logger.info("-" * 60)

        # ------------------------------------------------------------------
        # Step 1 — Sheets Update Trigger (get form responses)
        # ------------------------------------------------------------------
        logger.info("\n[Step 1] Get form responses - simulate Google Sheets trigger")
        result = await client.call_tool("get_form_responses", {})
        form_responses = _parse(result)
        logger.info(f"  -> {len(form_responses) if isinstance(form_responses, list) else 0} response(s) loaded")

        if not isinstance(form_responses, list) or not form_responses:
            logger.info("No form responses to process.")
            return

        # ------------------------------------------------------------------
        # Step 2 — Select Latest Item (process each scan)
        # ------------------------------------------------------------------
        all_results = []
        for i, response in enumerate(form_responses, 1):
            logger.info(f"\n[Step 2] Select latest item - processing scan {i}/{len(form_responses)}")
            result = await client.call_tool("select_latest_item", {"items": [response]})
            latest = _parse(result)
            qr_code = latest.get("QR code", "") if isinstance(latest, dict) else ""
            logger.info(f"  -> Selected: {latest}")

            # Steps 3-8 per scan
            scan_result = await process_single_scan(client, qr_code, i)
            all_results.append(scan_result)

        # ------------------------------------------------------------------
        # Save results & metrics
        # ------------------------------------------------------------------
        save_result("all_scan_results", all_results)

        valid_count = sum(1 for r in all_results if r["status"] == "VALID")
        invalid_count = sum(1 for r in all_results if r["status"] == "TIDAK VALID")
        metrics_path = Path("results/metrics/run_metrics.json")
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        run_summary = {
            "run_at": datetime.now().isoformat(),
            "total_scans": len(all_results),
            "valid": valid_count,
            "invalid": invalid_count,
            "details": all_results,
        }
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(run_summary, f, indent=2, ensure_ascii=False)

        logger.info(f"\n{'=' * 60}")
        logger.info("  Workflow complete.")
        logger.info(f"  Valid: {valid_count} / {len(all_results)}")
        logger.info(f"  Invalid: {invalid_count} / {len(all_results)}")
        logger.info(f"  Metrics: {metrics_path}")
        logger.info(f"  Results: {RESULTS_DIR}/")
        logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
