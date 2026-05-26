"""Data processing tools - select latest item and extract ticket code.

Replaces: Select Latest Item (Code node), Set Ticket Code Field (Set node),
          Select Latest Form Response (Code node).
"""

from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "select_latest_item")
def select_latest_item(items: list[dict]) -> dict:
    """Select the latest (last) item from a list of records.

    Simulates: Select Latest Item (n8n Code node - returns last row).

    Args:
        items: List of records from the trigger sheet.

    Returns:
        The last record in the list. Empty dict if list is empty.
    """
    if not items:
        return {}
    return items[-1]


@log_mcp_call("tool", "set_ticket_code")
def set_ticket_code(qr_code: str) -> dict:
    """Extract ticket code from QR code scan data.

    Simulates: Set Ticket Code Field (n8n Set node - maps QR code to kode_tiket).

    Args:
        qr_code: The raw QR code string scanned from the ticket.

    Returns:
        Dict with kode_tiket field extracted from the QR code.
    """
    return {"kode_tiket": qr_code}
