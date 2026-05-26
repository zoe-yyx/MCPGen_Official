"""Data processing tools — Steps 4, 6, 7, 8."""

import json
import time

from .utils.log_decorator import log_mcp_call


@log_mcp_call(operation_type="tool")
def merge_inventory_and_sales(inventory_json: str, sales_json: str) -> str:
    """Merge inventory and sales data by product_id.

    Args:
        inventory_json: JSON string from fetch_inventory (contains 'inventory' list)
        sales_json: JSON string from fetch_sales_velocity (contains 'sales' list)

    Returns:
        JSON string with list of merged product dicts.
    """
    inv_data = json.loads(inventory_json)
    sales_data = json.loads(sales_json)

    inventory = inv_data.get("inventory", inv_data) if isinstance(inv_data, dict) else inv_data
    sales = sales_data.get("sales", sales_data) if isinstance(sales_data, dict) else sales_data

    sales_map: dict[str, dict] = {}
    for sale in (sales if isinstance(sales, list) else [sales]):
        sales_map[sale["product_id"]] = sale

    merged = []
    for item in (inventory if isinstance(inventory, list) else [inventory]):
        sale_info = sales_map.get(item["product_id"], {
            "units_sold_30days": 0,
            "avg_daily_sales": 0.0,
            "trend": "stable",
        })
        merged.append({
            "product_id": item["product_id"],
            "product_name": item["product_name"],
            "current_stock": item["current_stock"],
            "reorder_point": item["reorder_point"],
            "supplier_id": item["supplier_id"],
            "unit_cost": item.get("unit_cost", 0.0),
            "lead_time_days": item.get("lead_time_days", 7),
            "units_sold_30days": sale_info["units_sold_30days"],
            "avg_daily_sales": sale_info["avg_daily_sales"],
            "trend": sale_info["trend"],
        })

    return json.dumps({"merged": merged, "count": len(merged)})


@log_mcp_call(operation_type="tool")
def parse_ai_response(ai_response_json: str, original_item_json: str) -> str:
    """Parse the AI demand forecast response and merge with the original product data.

    Args:
        ai_response_json: JSON string returned by ai_demand_forecasting
        original_item_json: JSON string of the original merged product item

    Returns:
        JSON string with original item + ai_forecast fields flattened.
    """
    try:
        ai_data = json.loads(ai_response_json)
        forecast_str = ai_data.get("forecast", ai_data.get("content", "{}"))
        if isinstance(forecast_str, str):
            forecast = json.loads(forecast_str)
        else:
            forecast = forecast_str
    except (json.JSONDecodeError, KeyError):
        forecast = {
            "should_reorder": False,
            "recommended_quantity": 0,
            "days_until_stockout": 999,
            "forecasted_demand_30days": 0,
            "confidence_level": "low",
            "reasoning": "Failed to parse AI response",
        }

    original = json.loads(original_item_json)

    result = {
        **original,
        "ai_forecast": forecast,
        "should_reorder": forecast.get("should_reorder", False),
        "recommended_quantity": forecast.get("recommended_quantity", 0),
        "days_until_stockout": forecast.get("days_until_stockout", 999),
        "forecasted_demand_30days": forecast.get("forecasted_demand_30days", 0),
        "confidence_level": forecast.get("confidence_level", "low"),
        "reasoning": forecast.get("reasoning", ""),
    }
    return json.dumps(result)


@log_mcp_call(operation_type="tool")
def filter_reorder_needed(parsed_item_json: str) -> str:
    """Filter: pass only items where should_reorder is True.

    Returns:
        JSON string with 'passes' bool and the item data.
    """
    item = json.loads(parsed_item_json)
    passes = bool(item.get("should_reorder", False))
    return json.dumps({"passes": passes, "item": item})


@log_mcp_call(operation_type="tool")
def create_purchase_order(item_json: str, index: int = 0) -> str:
    """Generate a purchase order document from a filtered reorder item.

    Args:
        item_json: JSON string of the parsed item that passed the filter
        index: Sequence index for unique PO numbering

    Returns:
        JSON string with complete PO document.
    """
    item = json.loads(item_json)

    ts = int(time.time() * 1000)
    po_number = f"PO-{ts}-{str(index + 1).zfill(3)}"

    quantity = item.get("recommended_quantity", 0)
    unit_cost = item.get("unit_cost", 0.0)
    total_cost = round(quantity * unit_cost, 2)
    lead_days = item.get("lead_time_days", 7)
    delivery_ts = time.time() + lead_days * 86400

    import datetime
    order_date = datetime.datetime.utcnow().isoformat() + "Z"
    delivery_date = (datetime.datetime.utcnow() + datetime.timedelta(days=lead_days)).isoformat() + "Z"

    po = {
        "po_number": po_number,
        "product_id": item["product_id"],
        "product_name": item["product_name"],
        "supplier_id": item["supplier_id"],
        "quantity": quantity,
        "unit_cost": unit_cost,
        "total_cost": total_cost,
        "currency": "USD",
        "order_date": order_date,
        "expected_delivery": delivery_date,
        "status": "pending",
        "created_by": "AI_System",
        "notes": item.get("reasoning", ""),
        "forecast_data": {
            "current_stock": item.get("current_stock"),
            "days_until_stockout": item.get("days_until_stockout"),
            "forecasted_demand_30days": item.get("forecasted_demand_30days"),
            "confidence_level": item.get("confidence_level"),
        },
    }
    return json.dumps(po)
