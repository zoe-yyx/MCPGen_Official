"""Unit tests for Smart Inventory Replenishment tools."""

import json
import os
import sqlite3
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.inventory_tools import (
    fetch_inventory,
    fetch_sales_velocity,
    schedule_trigger,
)
from mcp_server.tools.data_tools import (
    create_purchase_order,
    filter_reorder_needed,
    merge_inventory_and_sales,
    parse_ai_response,
)
from mcp_server.tools.supplier_tools import send_po_to_supplier
from mcp_server.tools.erp_tools import (
    log_to_erp,
    save_to_database,
    send_notification_email,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_inventory_json() -> str:
    return fetch_inventory()


def _make_sales_json() -> str:
    return fetch_sales_velocity(30)


def _make_merged_json() -> str:
    return merge_inventory_and_sales(_make_inventory_json(), _make_sales_json())


def _make_single_item_json(product_id: str = "SKU002") -> str:
    merged = json.loads(_make_merged_json())
    item = next(i for i in merged["merged"] if i["product_id"] == product_id)
    return json.dumps(item)


def _make_ai_response_json(should_reorder: bool = True) -> str:
    forecast = {
        "should_reorder": should_reorder,
        "recommended_quantity": 100,
        "days_until_stockout": 2,
        "forecasted_demand_30days": 201,
        "confidence_level": "high",
        "reasoning": "Stock critically low with increasing trend.",
    }
    return json.dumps({"product_id": "SKU002", "forecast": forecast, "model": "gpt-5.1", "raw_response": json.dumps(forecast)})


def _make_parsed_json(should_reorder: bool = True) -> str:
    item_json = _make_single_item_json("SKU002")
    ai_json = _make_ai_response_json(should_reorder)
    return parse_ai_response(ai_json, item_json)


def _make_po_json() -> str:
    parsed = _make_parsed_json(should_reorder=True)
    return create_purchase_order(parsed, index=0)


# ---------------------------------------------------------------------------
# TestInventoryTools
# ---------------------------------------------------------------------------

class TestInventoryTools(unittest.TestCase):
    def test_schedule_trigger_returns_dict(self) -> None:
        result = json.loads(schedule_trigger())
        self.assertIn("triggered_at", result)
        self.assertIn("interval_hours", result)

    def test_schedule_trigger_interval(self) -> None:
        result = json.loads(schedule_trigger())
        self.assertEqual(result["interval_hours"], 6)

    def test_schedule_trigger_is_mock(self) -> None:
        result = json.loads(schedule_trigger())
        self.assertTrue(result["mock"])

    def test_fetch_inventory_returns_5_products(self) -> None:
        result = json.loads(fetch_inventory())
        self.assertEqual(result["total_products"], 5)

    def test_fetch_inventory_has_required_fields(self) -> None:
        result = json.loads(fetch_inventory())
        for item in result["inventory"]:
            self.assertIn("product_id", item)
            self.assertIn("current_stock", item)
            self.assertIn("reorder_point", item)
            self.assertIn("supplier_id", item)

    def test_fetch_inventory_is_mock(self) -> None:
        result = json.loads(fetch_inventory())
        self.assertTrue(result["mock"])

    def test_fetch_sales_velocity_default_days(self) -> None:
        result = json.loads(fetch_sales_velocity())
        self.assertEqual(result["days"], 30)

    def test_fetch_sales_velocity_custom_days(self) -> None:
        result = json.loads(fetch_sales_velocity(60))
        self.assertEqual(result["days"], 60)

    def test_fetch_sales_velocity_returns_5_items(self) -> None:
        result = json.loads(fetch_sales_velocity(30))
        self.assertEqual(result["total_products"], 5)

    def test_fetch_sales_velocity_trend_field(self) -> None:
        result = json.loads(fetch_sales_velocity(30))
        for item in result["sales"]:
            self.assertIn(item["trend"], ("stable", "increasing", "decreasing"))


# ---------------------------------------------------------------------------
# TestDataTools
# ---------------------------------------------------------------------------

class TestDataTools(unittest.TestCase):
    def test_merge_returns_correct_count(self) -> None:
        merged = json.loads(_make_merged_json())
        self.assertEqual(merged["count"], 5)

    def test_merge_joins_by_product_id(self) -> None:
        merged = json.loads(_make_merged_json())
        for item in merged["merged"]:
            self.assertIn("avg_daily_sales", item)
            self.assertIn("units_sold_30days", item)
            self.assertIn("trend", item)

    def test_merge_preserves_inventory_fields(self) -> None:
        merged = json.loads(_make_merged_json())
        for item in merged["merged"]:
            self.assertIn("current_stock", item)
            self.assertIn("reorder_point", item)
            self.assertIn("unit_cost", item)

    def test_parse_ai_response_has_reorder_flag(self) -> None:
        parsed = json.loads(_make_parsed_json(should_reorder=True))
        self.assertIn("should_reorder", parsed)
        self.assertTrue(parsed["should_reorder"])

    def test_parse_ai_response_false(self) -> None:
        parsed = json.loads(_make_parsed_json(should_reorder=False))
        self.assertFalse(parsed["should_reorder"])

    def test_parse_ai_response_invalid_json_defaults(self) -> None:
        item_json = _make_single_item_json("SKU001")
        bad_ai = json.dumps({"product_id": "SKU001", "forecast": "not_json_object", "model": "gpt"})
        # forecast is a string "not_json_object" that is not parseable as JSON
        result = json.loads(parse_ai_response(bad_ai, item_json))
        # Should still have should_reorder from the forecast dict — but since
        # it can't be parsed as dict, fallback kicks in
        self.assertIn("should_reorder", result)

    def test_filter_reorder_passes_true(self) -> None:
        parsed = _make_parsed_json(should_reorder=True)
        result = json.loads(filter_reorder_needed(parsed))
        self.assertTrue(result["passes"])

    def test_filter_reorder_blocks_false(self) -> None:
        parsed = _make_parsed_json(should_reorder=False)
        result = json.loads(filter_reorder_needed(parsed))
        self.assertFalse(result["passes"])

    def test_create_po_has_po_number(self) -> None:
        po = json.loads(_make_po_json())
        self.assertIn("po_number", po)
        self.assertTrue(po["po_number"].startswith("PO-"))

    def test_create_po_calculates_total_cost(self) -> None:
        po = json.loads(_make_po_json())
        expected = round(po["quantity"] * po["unit_cost"], 2)
        self.assertAlmostEqual(po["total_cost"], expected, places=2)

    def test_create_po_has_forecast_data(self) -> None:
        po = json.loads(_make_po_json())
        self.assertIn("forecast_data", po)
        self.assertIn("confidence_level", po["forecast_data"])

    def test_create_po_status_pending(self) -> None:
        po = json.loads(_make_po_json())
        self.assertEqual(po["status"], "pending")


# ---------------------------------------------------------------------------
# TestAITools — mocked
# ---------------------------------------------------------------------------

class TestAITools(unittest.TestCase):
    def _mock_response(self, content: str):
        msg = MagicMock()
        msg.content = content
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    @patch("mcp_server.tools.ai_tools._get_client")
    def test_ai_forecasting_returns_forecast(self, mock_get_client) -> None:
        from mcp_server.tools.ai_tools import ai_demand_forecasting
        forecast_content = json.dumps({
            "should_reorder": True,
            "recommended_quantity": 150,
            "days_until_stockout": 1,
            "forecasted_demand_30days": 200,
            "confidence_level": "high",
            "reasoning": "Stock critically low.",
        })
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._mock_response(forecast_content)
        mock_get_client.return_value = mock_client

        item_json = _make_single_item_json("SKU002")
        result = json.loads(ai_demand_forecasting(item_json))
        self.assertIn("forecast", result)
        self.assertTrue(result["forecast"]["should_reorder"])

    @patch("mcp_server.tools.ai_tools._get_client")
    def test_ai_forecasting_handles_bad_json(self, mock_get_client) -> None:
        from mcp_server.tools.ai_tools import ai_demand_forecasting
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._mock_response("NOT JSON")
        mock_get_client.return_value = mock_client

        item_json = _make_single_item_json("SKU001")
        result = json.loads(ai_demand_forecasting(item_json))
        self.assertIn("forecast", result)
        self.assertFalse(result["forecast"]["should_reorder"])


# ---------------------------------------------------------------------------
# TestSupplierTools
# ---------------------------------------------------------------------------

class TestSupplierTools(unittest.TestCase):
    def test_send_po_returns_success(self) -> None:
        po_json = _make_po_json()
        result = json.loads(send_po_to_supplier(po_json))
        self.assertEqual(result["status"], "success")

    def test_send_po_has_supplier_po_id(self) -> None:
        po_json = _make_po_json()
        result = json.loads(send_po_to_supplier(po_json))
        self.assertIn("po_id", result)
        self.assertTrue(result["po_id"].startswith("SUP-PO-"))

    def test_send_po_is_mock(self) -> None:
        po_json = _make_po_json()
        result = json.loads(send_po_to_supplier(po_json))
        self.assertTrue(result["mock"])


# ---------------------------------------------------------------------------
# TestERPTools
# ---------------------------------------------------------------------------

class TestERPTools(unittest.TestCase):
    def test_log_to_erp_status(self) -> None:
        po_json = _make_po_json()
        result = json.loads(log_to_erp(po_json))
        self.assertEqual(result["status"], "logged")

    def test_log_to_erp_creates_file(self) -> None:
        log_to_erp(_make_po_json())
        self.assertTrue(os.path.exists("results/outputs/erp_log.json"))

    def test_log_to_erp_has_erp_record_id(self) -> None:
        po_json = _make_po_json()
        result = json.loads(log_to_erp(po_json))
        self.assertIn("erp_record_id", result)

    def test_save_to_database_inserts_row(self) -> None:
        po_json = _make_po_json()
        result = json.loads(save_to_database(po_json))
        self.assertEqual(result["status"], "inserted")
        self.assertIsNotNone(result["row_id"])
        self.assertGreater(result["row_id"], 0)

    def test_save_to_database_row_in_db(self) -> None:
        po = json.loads(_make_po_json())
        save_to_database(json.dumps(po))
        conn = sqlite3.connect("results/outputs/purchase_orders.db")
        rows = conn.execute(
            "SELECT * FROM purchase_orders WHERE po_number=?", (po["po_number"],)
        ).fetchall()
        conn.close()
        self.assertGreater(len(rows), 0)

    def test_send_email_is_mock_sent(self) -> None:
        po_json = _make_po_json()
        result = json.loads(send_notification_email(po_json))
        self.assertEqual(result["status"], "mock_sent")

    def test_send_email_creates_log(self) -> None:
        send_notification_email(_make_po_json())
        self.assertTrue(os.path.exists("results/outputs/email_log.json"))

    def test_send_email_has_subject(self) -> None:
        po = json.loads(_make_po_json())
        result = json.loads(send_notification_email(json.dumps(po)))
        self.assertIn(po["po_number"], result["subject"])


if __name__ == "__main__":
    unittest.main()
