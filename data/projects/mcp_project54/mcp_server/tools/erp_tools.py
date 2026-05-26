"""ERP logging, database, and email notification tools — Steps 10, 11, 12."""

import csv
import json
import os
import sqlite3
import time

from .utils.log_decorator import log_mcp_call

_ERP_LOG = os.path.join("results", "outputs", "erp_log.json")
_DB_PATH = os.path.join("results", "outputs", "purchase_orders.db")
_EMAIL_LOG = os.path.join("results", "outputs", "email_log.json")


def _load_json_list(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json_list(path: str, data: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _init_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number TEXT,
            product_id TEXT,
            product_name TEXT,
            supplier_id TEXT,
            quantity INTEGER,
            unit_cost REAL,
            total_cost REAL,
            order_date TEXT,
            expected_delivery TEXT,
            status TEXT,
            created_by TEXT,
            notes TEXT,
            forecast_confidence TEXT,
            days_until_stockout INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


@log_mcp_call(operation_type="tool")
def log_to_erp(po_json: str) -> str:
    """Log a purchase order to the ERP system (mock — JSON file).

    Args:
        po_json: JSON string of the purchase order

    Returns:
        JSON string with ERP log confirmation.
    """
    po = json.loads(po_json)

    erp_record = {
        **po,
        "erp_logged_at": time.time(),
        "erp_status": "logged",
        "mock": True,
    }

    log = _load_json_list(_ERP_LOG)
    log.append(erp_record)
    _save_json_list(_ERP_LOG, log)

    return json.dumps({
        "status": "logged",
        "po_number": po["po_number"],
        "erp_record_id": f"ERP-{int(time.time())}-{po['product_id']}",
        "log_file": _ERP_LOG,
        "mock": True,
    })


@log_mcp_call(operation_type="tool")
def save_to_database(po_json: str) -> str:
    """Insert a purchase order record into the SQLite database.

    Args:
        po_json: JSON string of the purchase order

    Returns:
        JSON string with the inserted row id and confirmation.
    """
    po = json.loads(po_json)
    forecast = po.get("forecast_data", {})

    conn = _init_db()
    cursor = conn.execute(
        """INSERT INTO purchase_orders (
            po_number, product_id, product_name, supplier_id,
            quantity, unit_cost, total_cost, order_date,
            expected_delivery, status, created_by, notes,
            forecast_confidence, days_until_stockout
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            po.get("po_number"),
            po.get("product_id"),
            po.get("product_name"),
            po.get("supplier_id"),
            po.get("quantity"),
            po.get("unit_cost"),
            po.get("total_cost"),
            po.get("order_date"),
            po.get("expected_delivery"),
            po.get("status"),
            po.get("created_by"),
            po.get("notes"),
            forecast.get("confidence_level"),
            forecast.get("days_until_stockout"),
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()

    return json.dumps({
        "status": "inserted",
        "row_id": row_id,
        "po_number": po["po_number"],
        "db_path": _DB_PATH,
    })


@log_mcp_call(operation_type="tool")
def send_notification_email(po_json: str) -> str:
    """Send a notification email about a new purchase order (mock — logged to file).

    Args:
        po_json: JSON string of the purchase order

    Returns:
        JSON string with mock email delivery confirmation.
    """
    po = json.loads(po_json)
    forecast = po.get("forecast_data", {})

    subject = f"New Purchase Order Created: {po['po_number']}"
    body = (
        f"A new purchase order has been automatically generated.\n\n"
        f"PO Number:    {po['po_number']}\n"
        f"Product:      {po['product_name']} ({po['product_id']})\n"
        f"Supplier:     {po['supplier_id']}\n"
        f"Quantity:     {po['quantity']} units\n"
        f"Unit Cost:    ${po['unit_cost']:.2f}\n"
        f"Total Cost:   ${po['total_cost']:.2f} {po.get('currency', 'USD')}\n"
        f"Order Date:   {po['order_date']}\n"
        f"Delivery By:  {po['expected_delivery']}\n\n"
        f"AI Forecast:\n"
        f"  Days until stockout:    {forecast.get('days_until_stockout')}\n"
        f"  Forecasted demand (30d): {forecast.get('forecasted_demand_30days')}\n"
        f"  Confidence:             {forecast.get('confidence_level')}\n\n"
        f"Reasoning: {po.get('notes', 'N/A')}\n"
    )

    recipient = os.environ.get("NOTIFICATION_EMAIL", "EMAIL_PLACEHOLDER")

    email_record = {
        "to": recipient,
        "subject": subject,
        "body": body,
        "po_number": po["po_number"],
        "sent_at": time.time(),
        "status": "mock_sent",
        "mock": True,
    }

    log = _load_json_list(_EMAIL_LOG)
    log.append(email_record)
    _save_json_list(_EMAIL_LOG, log)

    return json.dumps({
        "status": "mock_sent",
        "to": recipient,
        "subject": subject,
        "po_number": po["po_number"],
        "log_file": _EMAIL_LOG,
        "mock": True,
    })
