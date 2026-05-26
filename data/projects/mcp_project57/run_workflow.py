"""
run_workflow.py — AI-powered concert ticket validation and fan experience orchestration

Replicates the n8n workflow execution order:

  [Step 1]  Ticket Booking Webhook     -> receive_booking (mock: local JSON)
       |
  [Step 2]  Workflow Configuration     -> get_workflow_config
       |
  [Step 3]  Fetch Inventory Data       -> fetch_inventory (mock)
       |
  [Step 4]  Prepare Validation Input   -> prepare_validation_input
       |
  [Step 5]  Ticket Validation Agent    -> validate_ticket (OpenAI)
       |
  [Step 6]  Route by Risk Level        -> route_by_risk_level
       |
       +--[Low/Medium]--+                      +--[High/Critical]--+
       |                |                      |                   |
  [Step 7] Orchestrate  |                 [Step 9] Alert Ops Team  |
       |                |                      |                   |
  [Step 8] Update       |                      +-------------------+
    Ticketing System    |                              |
       |                |                              |
  [Step 8b] Send Email  |                              |
       |                |                              |
       +---[Merge All Paths]---------------------------+
                        |
                  [Step 10] Log to Audit Trail

Run:
    uv run python run_workflow.py
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client

from mcp_server.tools.utils.log_decorator import setup_logging

load_dotenv()
logger = setup_logging("logs/workflow.log")

SAMPLE_BOOKING_PATH = os.getenv("SAMPLE_BOOKING_PATH", "data/sample_booking.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(result) -> dict:
    """Extract dict from a fastmcp CallToolResult."""
    raw = result.content[0].text
    return json.loads(raw)


def _parse_text(result) -> str:
    """Extract plain text from a fastmcp CallToolResult."""
    return result.content[0].text


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

async def run_workflow() -> None:
    logger.info(f"{'=' * 60}")
    logger.info("  AI-powered Concert Ticket Validation & Fan Experience")
    logger.info(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 60}")

    async with Client("mcp_server/server.py") as client:

        # List available tools
        tools = await client.list_tools()
        logger.info(f"\nAvailable tools ({len(tools)}):")
        for tool in tools:
            logger.info(f"  - {tool.name}")

        # ==============================================================
        # Step 1 — Ticket Booking Webhook (receive booking)
        # ==============================================================
        logger.info(f"\n{'=' * 60}")
        logger.info("[Step 1] Receiving ticket booking ...")
        with open(SAMPLE_BOOKING_PATH, "r", encoding="utf-8") as f:
            booking_json = f.read()
        result = await client.call_tool("receive_booking", {"booking_json": booking_json})
        booking_data = _parse(result)
        logger.info(f"  -> Booking ID: {booking_data.get('bookingId')}")
        logger.info(f"  -> Customer: {booking_data.get('customerEmail')}")
        logger.info(f"  -> Tier: {booking_data.get('ticketTier')}, Qty: {booking_data.get('ticketQuantity')}")

        # ==============================================================
        # Step 2 — Workflow Configuration
        # ==============================================================
        logger.info(f"\n{'─' * 50}")
        logger.info("[Step 2] Loading workflow configuration ...")
        result = await client.call_tool("get_workflow_config", {})
        config_data = _parse(result)
        logger.info(f"  -> Venue capacity: {config_data['venueCapacity']}")
        logger.info(f"  -> Max tickets/customer: {config_data['maxTicketsPerCustomer']}")
        logger.info(f"  -> Fraud threshold: {config_data['fraudScoreThreshold']}")

        # ==============================================================
        # Step 3 — Fetch Inventory Data
        # ==============================================================
        logger.info(f"\n{'─' * 50}")
        logger.info("[Step 3] Fetching inventory data ...")
        result = await client.call_tool("fetch_inventory", {})
        inventory_data = _parse(result)
        logger.info(f"  -> Total capacity: {inventory_data['totalCapacity']}")
        logger.info(f"  -> Total sold: {inventory_data['totalSold']}")
        logger.info(f"  -> Total available: {inventory_data['totalAvailable']}")

        # ==============================================================
        # Step 4 — Prepare Validation Input
        # ==============================================================
        logger.info(f"\n{'─' * 50}")
        logger.info("[Step 4] Preparing validation input ...")
        result = await client.call_tool("prepare_validation_input", {
            "booking_data": json.dumps(booking_data),
            "inventory_data": json.dumps(inventory_data),
            "config_data": json.dumps(config_data),
        })
        validation_input = _parse(result)
        logger.info("  -> Validation input prepared")

        # ==============================================================
        # Step 5 — Ticket Validation Agent (AI)
        # ==============================================================
        logger.info(f"\n{'─' * 50}")
        logger.info("[Step 5] Running Ticket Validation Agent (AI) ...")
        result = await client.call_tool("validate_ticket", {
            "validation_input": json.dumps(validation_input),
        })
        validation_result = _parse(result)
        logger.info(f"  -> Status: {validation_result.get('validationStatus')}")
        logger.info(f"  -> Risk Level: {validation_result.get('riskLevel')}")
        logger.info(f"  -> Risk Score: {validation_result.get('riskScore')}")
        logger.info(f"  -> Eligibility: {validation_result.get('eligibilityStatus')}")
        logger.info(f"  -> Fraud Indicators: {validation_result.get('fraudIndicators')}")
        logger.info(f"  -> Requires Human Review: {validation_result.get('requiresHumanReview')}")

        # ==============================================================
        # Step 6 — Route by Risk Level
        # ==============================================================
        logger.info(f"\n{'─' * 50}")
        logger.info("[Step 6] Routing by risk level ...")
        result = await client.call_tool("route_by_risk_level", {
            "validation_result": json.dumps(validation_result),
        })
        routing = _parse(result)
        route = routing["route"]
        logger.info(f"  -> Route: {route}")

        orchestration_result = None

        if route == "low_medium":
            # ==============================================================
            # Step 7 — Fan Experience Orchestration Agent (AI)
            # ==============================================================
            logger.info(f"\n{'─' * 50}")
            logger.info("[Step 7] Running Fan Experience Orchestration Agent (AI) ...")
            result = await client.call_tool("orchestrate_fan_experience", {
                "validation_result": json.dumps(validation_result),
                "booking_data": json.dumps(booking_data),
            })
            orchestration_result = _parse(result)
            logger.info(f"  -> Actions: {[a['actionType'] for a in orchestration_result.get('actions', [])]}")
            logger.info(f"  -> Ticketing status: {orchestration_result.get('ticketingSystemUpdate', {}).get('status')}")
            logger.info(f"  -> SLA compliance: {orchestration_result.get('slaCompliance')}")

            # ==============================================================
            # Step 8 — Update Ticketing System
            # ==============================================================
            logger.info(f"\n{'─' * 50}")
            logger.info("[Step 8] Updating ticketing system ...")
            ticketing_update = orchestration_result.get("ticketingSystemUpdate", {})
            result = await client.call_tool("update_ticketing_system", {
                "ticketing_update": json.dumps(ticketing_update),
            })
            update_result = _parse(result)
            logger.info(f"  -> {update_result.get('message')}")

            # ==============================================================
            # Step 8b — Send Confirmation Email
            # ==============================================================
            logger.info(f"\n{'─' * 50}")
            logger.info("[Step 8b] Sending confirmation email ...")
            seat_assignments = ticketing_update.get("seatAssignments", [])
            confirmation_action = next(
                (a for a in orchestration_result.get("actions", [])
                 if a.get("actionType") == "SEND_CONFIRMATION"),
                None,
            )
            recipient = (
                confirmation_action.get("details", {}).get("recipientEmail", booking_data["customerEmail"])
                if confirmation_action else booking_data["customerEmail"]
            )
            subject = (
                confirmation_action.get("details", {}).get("subject", "Concert Ticket Confirmation")
                if confirmation_action else "Concert Ticket Confirmation"
            )
            result = await client.call_tool("send_confirmation_email", {
                "recipient_email": recipient,
                "subject": subject,
                "booking_id": ticketing_update.get("bookingId", booking_data.get("bookingId", "")),
                "status": ticketing_update.get("status", "CONFIRMED"),
                "seat_assignments": ", ".join(seat_assignments) if isinstance(seat_assignments, list) else str(seat_assignments),
            })
            email_result = _parse(result)
            logger.info(f"  -> Email sent to {email_result.get('recipient')}")

        elif route == "high_critical":
            # ==============================================================
            # Step 9 — Alert Operations Team
            # ==============================================================
            logger.info(f"\n{'─' * 50}")
            logger.info("[Step 9] Alerting operations team (HIGH RISK) ...")
            fraud_indicators = validation_result.get("fraudIndicators", [])
            result = await client.call_tool("alert_operations_team", {
                "risk_level": validation_result.get("riskLevel", "HIGH"),
                "risk_score": validation_result.get("riskScore", 0),
                "validation_status": validation_result.get("validationStatus", ""),
                "customer_email": booking_data.get("customerEmail", ""),
                "ticket_quantity": booking_data.get("ticketQuantity", 0),
                "total_amount": booking_data.get("totalAmount", 0.0),
                "fraud_indicators": ",".join(fraud_indicators) if isinstance(fraud_indicators, list) else str(fraud_indicators),
                "escalation_reason": validation_result.get("escalationReason", "High risk score threshold exceeded"),
                "reasoning": validation_result.get("reasoning", ""),
            })
            alert_result = _parse(result)
            logger.info(f"  -> Alert sent to channel: {alert_result.get('channel')}")
        else:
            logger.warning(f"  -> Unclassified route, logging for review.")

        # ==============================================================
        # Step 10 — Log to Audit Trail (Merge All Paths)
        # ==============================================================
        logger.info(f"\n{'─' * 50}")
        logger.info("[Step 10] Logging to audit trail ...")
        audit_summary = (
            orchestration_result.get("auditLogSummary", "Processed")
            if orchestration_result else f"Escalated — risk level {validation_result.get('riskLevel')}"
        )
        result = await client.call_tool("log_audit_trail", {
            "booking_id": booking_data.get("bookingId", ""),
            "customer_email": booking_data.get("customerEmail", ""),
            "validation_status": validation_result.get("validationStatus", ""),
            "risk_level": validation_result.get("riskLevel", ""),
            "risk_score": validation_result.get("riskScore", 0),
            "requires_human_review": validation_result.get("requiresHumanReview", False),
            "audit_summary": audit_summary,
        })
        audit_result = _parse(result)
        logger.info(f"  -> Audit logged for booking {audit_result.get('bookingId')}")

        # ==============================================================
        # Save run metrics
        # ==============================================================
        metrics_path = Path("results/metrics/run_metrics.json")
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        run_summary = {
            "run_at": datetime.now().isoformat(),
            "bookingId": booking_data.get("bookingId"),
            "customerEmail": booking_data.get("customerEmail"),
            "riskLevel": validation_result.get("riskLevel"),
            "riskScore": validation_result.get("riskScore"),
            "route": route,
            "validationStatus": validation_result.get("validationStatus"),
            "eligibilityStatus": validation_result.get("eligibilityStatus"),
            "requiresHumanReview": validation_result.get("requiresHumanReview"),
            "orchestrationActions": (
                [a["actionType"] for a in orchestration_result.get("actions", [])]
                if orchestration_result else []
            ),
        }
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(run_summary, f, indent=2, ensure_ascii=False)

        logger.info(f"\n{'=' * 60}")
        logger.info("  Workflow complete.")
        logger.info(f"  Booking: {run_summary['bookingId']}")
        logger.info(f"  Risk: {run_summary['riskLevel']} ({run_summary['riskScore']})")
        logger.info(f"  Route: {run_summary['route']}")
        logger.info(f"  Metrics: {metrics_path}")
        logger.info(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_workflow())
