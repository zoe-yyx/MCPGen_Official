"""Booking tools — webhook ingestion, configuration, and inventory.

Corresponds to n8n nodes:
- Ticket Booking Webhook: receive booking data
- Workflow Configuration: set config variables
- Fetch Inventory Data: fetch inventory from API (mock)
- Prepare Validation Input: combine booking + inventory + config
"""

import json
from pathlib import Path

from .utils.log_decorator import log_mcp_call

# Default workflow configuration (n8n "Workflow Configuration" Set node)
DEFAULT_CONFIG = {
    "venueCapacity": 5000,
    "maxTicketsPerCustomer": 8,
    "fraudScoreThreshold": 75,
    "highRiskThreshold": 80,
}

# Mock inventory data (replaces HTTP request to inventory API)
MOCK_INVENTORY = {
    "eventId": "EVT-2026-SUMMER",
    "eventName": "Summer Music Festival 2026",
    "tiers": {
        "GENERAL": {"price": 75.00, "total": 3000, "sold": 2100, "available": 900},
        "VIP": {"price": 225.00, "total": 1500, "sold": 1200, "available": 300},
        "PLATINUM": {"price": 500.00, "total": 500, "sold": 480, "available": 20},
    },
    "totalCapacity": 5000,
    "totalSold": 3780,
    "totalAvailable": 1220,
}


@log_mcp_call("tool", "receive_booking")
def receive_booking(booking_json: str) -> dict:
    """Receive and parse a ticket booking request (mock Webhook).

    Args:
        booking_json: JSON string of the booking request body.

    Returns:
        Parsed booking data dict.
    """
    if isinstance(booking_json, dict):
        return booking_json
    return json.loads(booking_json)


@log_mcp_call("tool", "get_workflow_config")
def get_workflow_config() -> dict:
    """Return workflow configuration settings (mock Set node).

    Returns:
        Config dict with venueCapacity, maxTicketsPerCustomer,
        fraudScoreThreshold, highRiskThreshold.
    """
    return DEFAULT_CONFIG.copy()


@log_mcp_call("tool", "fetch_inventory")
def fetch_inventory() -> dict:
    """Fetch current event inventory data (mock HTTP request).

    Returns:
        Inventory dict with tier availability and capacity info.
    """
    return MOCK_INVENTORY.copy()


@log_mcp_call("tool", "prepare_validation_input")
def prepare_validation_input(
    booking_data: str,
    inventory_data: str,
    config_data: str,
) -> dict:
    """Combine booking, inventory, and config into validation input (mock Set node).

    Args:
        booking_data: JSON string of booking data.
        inventory_data: JSON string of inventory data.
        config_data: JSON string of workflow config.

    Returns:
        Combined dict ready for the Ticket Validation Agent.
    """
    booking = json.loads(booking_data) if isinstance(booking_data, str) else booking_data
    inventory = json.loads(inventory_data) if isinstance(inventory_data, str) else inventory_data
    config = json.loads(config_data) if isinstance(config_data, str) else config_data

    return {
        "bookingData": booking,
        "inventoryData": inventory,
        "venueCapacity": config.get("venueCapacity", 5000),
        "maxTicketsPerCustomer": config.get("maxTicketsPerCustomer", 8),
        "fraudScoreThreshold": config.get("fraudScoreThreshold", 75),
        "highRiskThreshold": config.get("highRiskThreshold", 80),
    }
