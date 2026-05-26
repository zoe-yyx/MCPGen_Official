"""Unit tests for interview scheduler tools.

Tests tool functions directly without MCP, simulating n8n node calls.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.sheets_tools import google_sheets_trigger
from mcp_server.tools.scheduling_tools import calculate_next_slot, create_calendar_event
from mcp_server.tools.email_tools import send_gmail


class TestSheetsTools(unittest.TestCase):
    """Tests for Google Sheets trigger tool."""

    def test_google_sheets_trigger_returns_candidates(self) -> None:
        result = json.loads(google_sheets_trigger())
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_candidate_has_required_fields(self) -> None:
        result = json.loads(google_sheets_trigger())
        for candidate in result:
            self.assertIn("NAME", candidate)
            self.assertIn("EMAIL", candidate)
            self.assertIn("EDUCATIONAL", candidate)

    def test_candidate_email_format(self) -> None:
        result = json.loads(google_sheets_trigger())
        for candidate in result:
            self.assertIn("@", candidate["EMAIL"])


class TestSchedulingTools(unittest.TestCase):
    """Tests for scheduling tools."""

    def test_calculate_next_slot_returns_valid_times(self) -> None:
        result = json.loads(calculate_next_slot())
        self.assertIn("nextSlot", result)
        self.assertIn("endSlot", result)
        # Verify format
        next_dt = datetime.strptime(result["nextSlot"], "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(result["endSlot"], "%Y-%m-%d %H:%M:%S")
        # End should be 1 hour after start
        diff = (end_dt - next_dt).total_seconds()
        self.assertEqual(diff, 3600)

    def test_next_slot_is_in_future(self) -> None:
        result = json.loads(calculate_next_slot())
        next_dt = datetime.strptime(result["nextSlot"], "%Y-%m-%d %H:%M:%S")
        self.assertGreater(next_dt, datetime.now())

    def test_next_slot_is_mon_wed_or_fri(self) -> None:
        result = json.loads(calculate_next_slot())
        next_dt = datetime.strptime(result["nextSlot"], "%Y-%m-%d %H:%M:%S")
        # weekday(): 0=Mon, 2=Wed, 4=Fri
        self.assertIn(next_dt.weekday(), [0, 2, 4])

    def test_next_slot_is_at_3pm(self) -> None:
        result = json.loads(calculate_next_slot())
        next_dt = datetime.strptime(result["nextSlot"], "%Y-%m-%d %H:%M:%S")
        self.assertEqual(next_dt.hour, 15)
        self.assertEqual(next_dt.minute, 0)

    def test_create_calendar_event(self) -> None:
        result = json.loads(create_calendar_event(
            start_time="2026-04-27 15:00:00",
            end_time="2026-04-27 16:00:00",
        ))
        self.assertEqual(result["status"], "confirmed")
        self.assertIn("htmlLink", result)
        self.assertTrue(result["htmlLink"].startswith("ENDPOINT_PLACEHOLDER"))
        self.assertEqual(result["start"]["dateTime"], "2026-04-27 15:00:00")
        self.assertEqual(result["end"]["dateTime"], "2026-04-27 16:00:00")


class TestEmailTools(unittest.TestCase):
    """Tests for email tools (mocked file output)."""

    def test_send_gmail(self) -> None:
        result = json.loads(send_gmail(
            recipient_email="EMAIL_PLACEHOLDER",
            subject="Interview Details",
            body="Dear candidate, you are invited for an interview.",
        ))
        self.assertEqual(result["status"], "sent_mock")
        self.assertEqual(result["channel"], "gmail")
        self.assertEqual(result["recipient"], "EMAIL_PLACEHOLDER")
        self.assertTrue(os.path.exists(result["file"]))

        # Verify file content
        with open(result["file"], "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("EMAIL_PLACEHOLDER", content)
        self.assertIn("Interview Details", content)


class TestAITools(unittest.TestCase):
    """Tests for AI email generation tool (mocked OpenAI call)."""

    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_generate_interview_email(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = (
            "Dear Alice,\n\nWe are excited to invite you for an interview. "
            "Please find the calendar link below.\n\nBest regards,\nSurya\nTechdome"
        )
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        from mcp_server.tools.ai_tools import generate_interview_email

        result = json.loads(generate_interview_email(
            candidate_name="Alice Johnson",
            candidate_education="M.Sc. Computer Science",
            calendar_link="ENDPOINT_PLACEHOLDER",
        ))
        self.assertIn("body", result)
        self.assertIn("Alice", result["body"])
        self.assertIn("interview", result["body"].lower())


if __name__ == "__main__":
    unittest.main()
