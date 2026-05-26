"""Unit tests for AI Hotel Receptionist tools."""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.whatsapp_tools import receive_whatsapp_message, check_message, send_whatsapp_reply
from mcp_server.tools.redis_tools import check_user_model, store_user_model, _STORE
from mcp_server.tools.model_tools import decide_model
from mcp_server.tools.hotel_data_tools import get_pricing, execute_sql_query


class TestWhatsAppTools(unittest.TestCase):
    def test_receive_webhook_structure(self) -> None:
        result = json.loads(receive_whatsapp_message("Hello", "6012345", "6012345"))
        events = result["entry"][0]["changes"][0]["value"]
        self.assertEqual(events["messages"][0]["text"]["body"], "Hello")
        self.assertEqual(events["contacts"][0]["wa_id"], "6012345")

    def test_check_message_valid(self) -> None:
        webhook = receive_whatsapp_message("What rooms are free?", "601234", "601234")
        result = json.loads(check_message(webhook))
        self.assertTrue(result["valid"])
        self.assertEqual(result["message"], "What rooms are free?")
        self.assertEqual(result["wa_id"], "601234")

    def test_check_message_empty_events(self) -> None:
        bad = json.dumps({"entry": [{"changes": [{"value": {"messages": []}}]}]})
        result = json.loads(check_message(bad))
        self.assertFalse(result["valid"])

    def test_send_whatsapp_reply(self) -> None:
        result = json.loads(send_whatsapp_reply("601234567890", "Hello from hotel!"))
        self.assertEqual(result["status"], "mock_sent")
        self.assertIn("601234567890", result["to"])
        self.assertTrue(os.path.exists(result["file"]))


class TestRedisTools(unittest.TestCase):
    def setUp(self) -> None:
        _STORE.clear()

    def test_check_user_model_not_found(self) -> None:
        result = json.loads(check_user_model("unknown_user"))
        self.assertFalse(result["found"])
        self.assertIsNone(result["value"])

    def test_store_then_check(self) -> None:
        store_user_model("user001", 1)
        result = json.loads(check_user_model("user001"))
        self.assertTrue(result["found"])
        self.assertIsNotNone(result["value"])
        data = json.loads(result["value"])
        self.assertEqual(data["modelIndex"], 1)

    def test_store_returns_correct_index(self) -> None:
        result = json.loads(store_user_model("user002", 0))
        self.assertEqual(result["model_index"], 0)
        self.assertEqual(result["ttl"], 3600)
        self.assertEqual(result["status"], "mock_set")


class TestModelDecider(unittest.TestCase):
    def test_default_to_zero_when_no_data(self) -> None:
        result = json.loads(decide_model(None))
        self.assertEqual(result["model_index"], 0)

    def test_flips_from_zero_to_one(self) -> None:
        redis_val = json.dumps({"modelIndex": 0})
        result = json.loads(decide_model(redis_val))
        self.assertEqual(result["model_index"], 1)

    def test_flips_from_one_to_zero(self) -> None:
        redis_val = json.dumps({"modelIndex": 1})
        result = json.loads(decide_model(redis_val))
        self.assertEqual(result["model_index"], 0)

    def test_invalid_json_defaults_to_zero(self) -> None:
        result = json.loads(decide_model("not-json"))
        self.assertEqual(result["model_index"], 0)


class TestHotelDataTools(unittest.TestCase):
    def test_get_pricing_returns_all_room_types(self) -> None:
        result = json.loads(get_pricing())
        types = [r["room_type"] for r in result["pricing"]]
        self.assertIn("Standard", types)
        self.assertIn("Suite", types)
        self.assertIn("Deluxe", types)
        self.assertIn("Family", types)

    def test_execute_select_rooms(self) -> None:
        result = json.loads(execute_sql_query("SELECT * FROM rooms WHERE status = 'available'"))
        self.assertIn("results", result)
        self.assertGreater(result["row_count"], 0)
        for row in result["results"]:
            self.assertEqual(row["status"], "available")

    def test_execute_select_bookings(self) -> None:
        result = json.loads(execute_sql_query("SELECT * FROM bookings WHERE status = 'checked_in'"))
        self.assertGreater(result["row_count"], 0)

    def test_execute_select_join(self) -> None:
        result = json.loads(execute_sql_query(
            "SELECT b.booking_id, g.name, r.room_number FROM bookings b "
            "JOIN guests g ON b.guest_id = g.guest_id "
            "JOIN rooms r ON b.room_id = r.room_id"
        ))
        self.assertGreater(result["row_count"], 0)
        self.assertIn("name", result["columns"])

    def test_execute_blocks_insert(self) -> None:
        with self.assertRaises(ValueError):
            execute_sql_query("INSERT INTO rooms VALUES (999,'999','Standard',4,80,'available')")

    def test_execute_blocks_drop(self) -> None:
        with self.assertRaises(ValueError):
            execute_sql_query("DROP TABLE rooms")

    def test_execute_blocks_delete(self) -> None:
        with self.assertRaises(ValueError):
            execute_sql_query("DELETE FROM bookings")

    def test_execute_count_available(self) -> None:
        result = json.loads(execute_sql_query(
            "SELECT COUNT(*) as total FROM rooms WHERE status = 'available'"
        ))
        self.assertEqual(result["row_count"], 1)
        self.assertGreater(result["results"][0]["total"], 0)


class TestAITools(unittest.TestCase):
    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_ai_hotel_agent_direct_response(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.tool_calls = None
        mock_msg.content = "We have several rooms available: 101 (Standard), 103 (Deluxe), 201 (Deluxe), 203 (Suite), 301 (Family), 302 (Deluxe), 303 (Standard)."
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=mock_msg)]
        )

        from mcp_server.tools.ai_tools import ai_hotel_agent
        result = json.loads(ai_hotel_agent("What rooms are available?", "test_user", 0))
        self.assertIn("output", result)
        self.assertIn("available", result["output"].lower())
        self.assertEqual(result["wa_id"], "test_user")

    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_ai_hotel_agent_with_tool_call(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        # First call: GPT requests SQL tool
        tool_call = MagicMock()
        tool_call.id = "call_123"
        tool_call.function.name = "execute_sql_query"
        tool_call.function.arguments = json.dumps({"query": "SELECT * FROM rooms WHERE status='available'"})

        msg_with_tool = MagicMock()
        msg_with_tool.tool_calls = [tool_call]
        msg_with_tool.content = None

        # Second call: GPT gives final answer
        msg_final = MagicMock()
        msg_final.tool_calls = None
        msg_final.content = "There are 7 rooms currently available."

        mock_client.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=msg_with_tool)]),
            MagicMock(choices=[MagicMock(message=msg_final)]),
        ]

        from mcp_server.tools.ai_tools import ai_hotel_agent
        result = json.loads(ai_hotel_agent("How many rooms are free?", "tool_test_user", 1))
        self.assertIn("output", result)
        self.assertIn("available", result["output"].lower())


if __name__ == "__main__":
    unittest.main()
