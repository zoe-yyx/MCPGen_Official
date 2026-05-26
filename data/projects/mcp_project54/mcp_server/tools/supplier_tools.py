"""Supplier API tool — Step 9."""

import json
import os
import time

from .utils.log_decorator import log_mcp_call

_SUPPLIER_DB = os.path.join("results", "outputs", "supplier_orders.json")


def _load_orders() -> list[dict]:
    if not os.path.exists(_SUPPLIER_DB):
        return []
    with open(_SUPPLIER_DB, encoding="utf-8") as f:
        return json.load(f)


def _save_orders(orders: list[dict]) -> None:
    os.makedirs(os.path.dirname(_SUPPLIER_DB), exist_ok=True)
    with open(_SUPPLIER_DB, "w", encoding="utf-8") as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)


@log_mcp_call(operation_type="tool")
def send_po_to_supplier(po_json: str) -> str:
    """Send a purchase order to the supplier system (mock — persisted locally).

    Args:
        po_json: JSON string of the purchase order from create_purchase_order

    Returns:
        JSON string with supplier confirmation details.
    """
    po = json.loads(po_json)

    sup_po_id = f"SUP-PO-{int(time.time())}-{po['product_id']}"
    confirmation = {
        "status": "success",
        "po_id": sup_po_id,
        "our_po_number": po["po_number"],
        "supplier_id": po["supplier_id"],
        "confirmation": "Order received and queued for processing",
        "estimated_ship_date": po.get("expected_delivery", ""),
        "received_at": time.time(),
        "mock": True,
    }

    orders = _load_orders()
    orders.append({**po, "supplier_confirmation": confirmation})
    _save_orders(orders)

    return json.dumps(confirmation)
