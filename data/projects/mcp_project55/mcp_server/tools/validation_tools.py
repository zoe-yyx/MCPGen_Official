"""Ticket validation - route by conditional rules.

Replaces: Route by Conditional Rules (Switch node).
"""

from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "validate_ticket")
def validate_ticket(scanned_code: str, matched_rows: list[dict]) -> dict:
    """Validate a scanned ticket against the ticket database.

    Simulates: Route by Conditional Rules (n8n Switch node).
    - VALID: scanned ticket code matches a TIKET field in the database rows.
    - TIDAK VALID: no match found.

    Args:
        scanned_code: The ticket code extracted from the QR scan.
        matched_rows: Rows returned from the ticket database lookup.

    Returns:
        Dict with 'status' ("VALID"/"TIDAK VALID") and 'matched_record' (if valid).
    """
    for row in matched_rows:
        if row.get("TIKET") == scanned_code:
            return {
                "status": "VALID",
                "matched_record": row,
            }
    return {
        "status": "TIDAK VALID",
        "matched_record": None,
    }
