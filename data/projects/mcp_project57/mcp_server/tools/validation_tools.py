"""Validation tools — AI-powered ticket validation and risk routing.

Corresponds to n8n nodes:
- Ticket Validation Agent (LangChain Agent + OpenAI + Structured Output Parser)
- Route by Risk Level (Switch node)
"""

import json
import os

from openai import OpenAI
from dotenv import load_dotenv

from .utils.log_decorator import log_mcp_call

load_dotenv()

VALIDATION_SYSTEM_PROMPT = """You are a Ticket Validation Agent responsible for comprehensive verification of concert ticket bookings.

Your task is to analyze booking signals and perform the following validations:

1. **Ticket Tier & Seat Allocation**: Verify requested tier matches availability and seat assignments are valid
2. **Payment Authorization**: Confirm payment method is authorized and amount matches pricing rules
3. **Fraud Detection**: Analyze fraud indicators including velocity checks, IP reputation, device fingerprinting, and behavioral patterns
4. **Inventory Consistency**: Cross-check available inventory against venue capacity and existing bookings
5. **Duplicate Purchase Detection**: Identify duplicate bookings by same customer (email, payment method, address)
6. **Bot Detection**: Evaluate bot detection signals and CAPTCHA results
7. **Dynamic Pricing Validation**: Verify pricing matches current tier and demand-based rules
8. **Resale Restrictions**: Check compliance with resale policies and transfer limits
9. **Customer Consent**: Validate required consent flags (terms, privacy, marketing)
10. **Refund Eligibility**: Determine refund eligibility based on timing and policy

Risk Classification:
- LOW (0-30): All checks pass, standard processing
- MEDIUM (31-60): Minor concerns, proceed with monitoring
- HIGH (61-80): Significant issues, requires additional verification
- CRITICAL (81-100): Severe fraud indicators or policy violations, requires human review

You MUST respond with a valid JSON object matching this exact schema:
{
  "validationStatus": "VALID|INVALID|PENDING",
  "riskLevel": "LOW|MEDIUM|HIGH|CRITICAL",
  "riskScore": <number 0-100>,
  "eligibilityStatus": "APPROVED|DENIED|PENDING_REVIEW",
  "fraudIndicators": [<list of string indicators>],
  "inventoryCheck": "AVAILABLE|SOLD_OUT|LIMITED",
  "duplicatePurchaseCheck": "PASS|FAIL",
  "botDetectionScore": <number 0-100>,
  "paymentAuthStatus": "AUTHORIZED|DECLINED|PENDING",
  "refundEligibility": "ELIGIBLE|PARTIAL|INELIGIBLE",
  "pricingValidation": "CORRECT|MISMATCH",
  "resaleRestrictionCheck": "COMPLIANT|NON_COMPLIANT",
  "consentFlagsCheck": "VERIFIED|INCOMPLETE",
  "seatAllocationStatus": "CONFIRMED|UNAVAILABLE|WAITLISTED",
  "reasoning": "<detailed reasoning string>",
  "requiresHumanReview": <boolean>,
  "escalationReason": "<string or null>"
}

Respond ONLY with the JSON object, no markdown formatting."""


@log_mcp_call("tool", "validate_ticket")
def validate_ticket(validation_input: str) -> dict:
    """Run AI-powered ticket validation (mock Ticket Validation Agent).

    Sends booking + inventory + config to OpenAI for comprehensive
    fraud detection, payment validation, and risk classification.

    Args:
        validation_input: JSON string with bookingData, inventoryData, and config.

    Returns:
        Structured validation result dict with risk level, fraud indicators, etc.
    """
    input_data = json.loads(validation_input) if isinstance(validation_input, str) else validation_input

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    model = os.getenv("OPENAI_MODEL", "gpt-5.1")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(input_data, indent=2)},
        ],
        temperature=0.1,
        max_tokens=1024,
    )

    raw = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    return json.loads(raw)


@log_mcp_call("tool", "route_by_risk_level")
def route_by_risk_level(validation_result: str) -> dict:
    """Route booking by risk level (mock Switch node).

    Args:
        validation_result: JSON string of the validation result.

    Returns:
        Dict with 'route' ('low_medium', 'high_critical', or 'unclassified')
        and the original validation data.
    """
    data = json.loads(validation_result) if isinstance(validation_result, str) else validation_result

    risk_level = data.get("riskLevel", "").upper()
    requires_review = data.get("requiresHumanReview", False)

    # n8n Switch: HIGH/CRITICAL branch fires on riskLevel OR requiresHumanReview
    if risk_level in ("HIGH", "CRITICAL") or requires_review:
        route = "high_critical"
    elif risk_level in ("LOW", "MEDIUM"):
        route = "low_medium"
    else:
        route = "unclassified"

    return {"route": route, "validationResult": data}
