"""Orchestration tools — fan experience orchestration and ticketing system update.

Corresponds to n8n nodes:
- Fan Experience Orchestration Agent (LangChain Agent + OpenAI + Structured Output Parser)
- Update Ticketing System (HTTP POST, mock)
"""

import json
import os

from openai import OpenAI
from dotenv import load_dotenv

from .utils.log_decorator import log_mcp_call

load_dotenv()

ORCHESTRATION_SYSTEM_PROMPT = """You are a Fan Experience Orchestration Agent responsible for coordinating downstream workflows after ticket validation.

Your task is to analyze validation results and orchestrate the following workflows:

1. **Confirmation Communications**: Send real-time confirmation via email/SMS with ticket details, QR codes, and event information
2. **Waitlist Management**: Activate waitlist for sold-out tiers and notify waiting customers
3. **Seat Reassignment**: Handle automated seat reassignment for upgrades, accessibility requests, or overbooking resolution
4. **Refund/Credit Processing**: Issue refunds or credits based on cancellation policies and timing
5. **Loyalty Program Updates**: Update customer loyalty points, tier status, and VIP entitlements
6. **VIP Entitlement Validation**: Verify and activate VIP benefits (early entry, meet-and-greet, lounge access)
7. **Escalation Handling**: Route high-risk transactions, payment disputes, or overbooking issues to human review
8. **Event Cancellation Management**: Process mass refunds and communications for cancelled events
9. **SLA Monitoring**: Ensure all actions meet service level agreement thresholds
10. **Audit Trail Generation**: Create structured audit logs for compliance and reporting

Policies to enforce:
- Venue capacity constraints and fire code compliance
- Resale limits (max 2 transfers per ticket)
- Refund windows (full refund >30 days, 50% refund 7-30 days, no refund <7 days)
- Compensation rules for overbooking (150% refund + priority rebooking)
- SLA thresholds (confirmation within 2 minutes, refunds within 5 business days)

You MUST respond with a valid JSON object matching this exact schema:
{
  "actions": [
    {
      "actionType": "SEND_CONFIRMATION|UPDATE_LOYALTY_POINTS|ACTIVATE_WAITLIST|PROCESS_REFUND|ESCALATE",
      "priority": <number>,
      "details": {<action-specific details>}
    }
  ],
  "ticketingSystemUpdate": {
    "bookingId": "<string>",
    "status": "CONFIRMED|PENDING|CANCELLED|WAITLISTED",
    "seatAssignments": [<list of seat strings>],
    "paymentStatus": "COMPLETED|PENDING|REFUNDED"
  },
  "waitlistActivation": <boolean>,
  "seatReassignment": <boolean>,
  "refundRequired": <boolean>,
  "vipEntitlements": [<list of entitlement strings>],
  "escalationRequired": <boolean>,
  "slaCompliance": <boolean>,
  "auditLogSummary": "<string>"
}

Respond ONLY with the JSON object, no markdown formatting."""


@log_mcp_call("tool", "orchestrate_fan_experience")
def orchestrate_fan_experience(
    validation_result: str,
    booking_data: str,
) -> dict:
    """Run AI-powered fan experience orchestration (mock Orchestration Agent).

    Analyzes validation results and determines all downstream actions:
    confirmations, loyalty updates, VIP entitlements, escalations, etc.

    Args:
        validation_result: JSON string of validation result from validate_ticket.
        booking_data: JSON string of the original booking data.

    Returns:
        Structured orchestration result with actions, ticketing updates, etc.
    """
    validation = json.loads(validation_result) if isinstance(validation_result, str) else validation_result
    booking = json.loads(booking_data) if isinstance(booking_data, str) else booking_data

    combined_input = {
        "validationResult": validation,
        "bookingData": booking,
    }

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    model = os.getenv("OPENAI_MODEL", "gpt-5.1")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": ORCHESTRATION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(combined_input, indent=2)},
        ],
        temperature=0.2,
        max_tokens=1024,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    return json.loads(raw)


@log_mcp_call("tool", "update_ticketing_system")
def update_ticketing_system(ticketing_update: str) -> dict:
    """Update the ticketing system (mock HTTP POST).

    In production this would POST to the ticketing API endpoint.
    Here we simulate a successful update.

    Args:
        ticketing_update: JSON string of ticketing system update payload.

    Returns:
        Mock API response with status confirmation.
    """
    data = json.loads(ticketing_update) if isinstance(ticketing_update, str) else ticketing_update

    return {
        "status": "success",
        "message": f"Ticketing system updated for booking {data.get('bookingId', 'unknown')}",
        "updatedFields": list(data.keys()),
        "bookingId": data.get("bookingId", "unknown"),
    }
