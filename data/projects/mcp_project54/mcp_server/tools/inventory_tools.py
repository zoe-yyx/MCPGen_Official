"""Inventory and sales data tools — Steps 1, 2, 3."""

import json
import time

from .utils.log_decorator import log_mcp_call

# Mock inventory data: 5 products
_MOCK_INVENTORY = [
    {
        "product_id": "SKU001",
        "product_name": "Widget Pro",
        "current_stock": 50,
        "reorder_point": 20,
        "supplier_id": "SUP001",
        "unit_cost": 25.00,
        "lead_time_days": 7,
    },
    {
        "product_id": "SKU002",
        "product_name": "Gadget Ultra",
        "current_stock": 5,
        "reorder_point": 25,
        "supplier_id": "SUP002",
        "unit_cost": 89.99,
        "lead_time_days": 14,
    },
    {
        "product_id": "SKU003",
        "product_name": "Component Basic",
        "current_stock": 100,
        "reorder_point": 30,
        "supplier_id": "SUP001",
        "unit_cost": 5.50,
        "lead_time_days": 3,
    },
    {
        "product_id": "SKU004",
        "product_name": "Device Elite",
        "current_stock": 3,
        "reorder_point": 10,
        "supplier_id": "SUP003",
        "unit_cost": 199.99,
        "lead_time_days": 21,
    },
    {
        "product_id": "SKU005",
        "product_name": "Part Standard",
        "current_stock": 80,
        "reorder_point": 40,
        "supplier_id": "SUP002",
        "unit_cost": 12.75,
        "lead_time_days": 7,
    },
]

# Mock sales velocity data (30 days)
_MOCK_SALES = [
    {"product_id": "SKU001", "units_sold_30days": 45, "avg_daily_sales": 1.5, "trend": "stable"},
    {"product_id": "SKU002", "units_sold_30days": 201, "avg_daily_sales": 6.7, "trend": "increasing"},
    {"product_id": "SKU003", "units_sold_30days": 21, "avg_daily_sales": 0.7, "trend": "decreasing"},
    {"product_id": "SKU004", "units_sold_30days": 75, "avg_daily_sales": 2.5, "trend": "increasing"},
    {"product_id": "SKU005", "units_sold_30days": 90, "avg_daily_sales": 3.0, "trend": "stable"},
]


@log_mcp_call(operation_type="trigger")
def schedule_trigger() -> str:
    """Simulates the schedule trigger that fires every 6 hours."""
    return json.dumps({
        "triggered_at": time.time(),
        "interval_hours": 6,
        "trigger_type": "schedule",
        "mock": True,
    })


@log_mcp_call(operation_type="tool")
def fetch_inventory() -> str:
    """Fetch current stock levels from warehouse system (mock)."""
    return json.dumps({
        "status": "ok",
        "inventory": _MOCK_INVENTORY,
        "total_products": len(_MOCK_INVENTORY),
        "mock": True,
    })


@log_mcp_call(operation_type="tool")
def fetch_sales_velocity(days: int = 30) -> str:
    """Fetch sales velocity data for the past N days (mock)."""
    return json.dumps({
        "status": "ok",
        "days": days,
        "sales": _MOCK_SALES,
        "total_products": len(_MOCK_SALES),
        "mock": True,
    })
