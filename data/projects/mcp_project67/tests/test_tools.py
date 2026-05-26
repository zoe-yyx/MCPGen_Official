"""Unit tests for recruitment pipeline tools.

Tests tool functions directly without MCP, simulating n8n node calls.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.data_tools import (
    receive_cv, store_candidate, get_job_requirements,
    download_cv, update_assessment, update_interview_details,
)
from mcp_server.tools.filter_tools import filter_qualified, filter_interview
from mcp_server.tools.calendar_tools import schedule_interview
from mcp_server.tools.notification_tools import (
    send_candidate_email, send_slack_notification, respond_webhook,
)


class TestDataTools(unittest.TestCase):
    """Tests for webhook, Airtable, and CV download tools."""

    def test_receive_cv(self) -> None:
        result = json.loads(receive_cv(
            name="Alice", email="EMAIL_PLACEHOLDER", phone="123",
            cv_url="ENDPOINT_PLACEHOLDER", position="Software Engineer",
        ))
        self.assertEqual(result["body"]["name"], "Alice")
        self.assertEqual(result["body"]["position"], "Software Engineer")

    def test_store_candidate(self) -> None:
        result = json.loads(store_candidate(
            name="Bob", email="EMAIL_PLACEHOLDER", phone="456",
            cv_url="ENDPOINT_PLACEHOLDER", position="Data Scientist",
        ))
        self.assertIn("id", result)
        self.assertTrue(result["id"].startswith("rec"))
        self.assertEqual(result["Name"], "Bob")
        self.assertEqual(result["Status"], "New Application")

    def test_get_job_requirements_known_position(self) -> None:
        result = json.loads(get_job_requirements("Software Engineer"))
        self.assertEqual(result["Position"], "Software Engineer")
        self.assertIn("Required_Skills", result)
        self.assertGreater(result["Required_Experience"], 0)

    def test_get_job_requirements_unknown_falls_back(self) -> None:
        result = json.loads(get_job_requirements("Unknown Role"))
        self.assertIn("Position", result)

    def test_download_cv(self) -> None:
        result = json.loads(download_cv("ENDPOINT_PLACEHOLDER"))
        self.assertIn("text", result)
        self.assertGreater(len(result["text"]), 100)

    def test_update_assessment(self) -> None:
        result = json.loads(update_assessment(
            candidate_id="rec_test_123",
            match_score=85, status="Highly Qualified",
            recommendation="Interview",
            strengths="Python, AWS", gaps="No Go experience",
            reasoning="Strong match", skills="Python, JS",
            education="MS CS", years_experience=5,
        ))
        self.assertEqual(result["AI_Recommendation"], "Interview")

    def test_update_interview_details(self) -> None:
        result = json.loads(update_interview_details(
            candidate_id="rec_test_456",
            interview_scheduled="2026-04-26T10:00:00Z",
            interview_link="ENDPOINT_PLACEHOLDER",
            calendar_event_id="evt123",
        ))
        self.assertEqual(result["Status"], "Interview Scheduled")


class TestFilterTools(unittest.TestCase):
    """Tests for candidate filtering tools."""

    def test_filter_qualified_passes_interview(self) -> None:
        data = json.dumps({"recommendation": "Interview", "match_score": 90})
        result = json.loads(filter_qualified(data))
        self.assertTrue(result["passed"])

    def test_filter_qualified_passes_phone_screen(self) -> None:
        data = json.dumps({"recommendation": "Phone Screen", "match_score": 60})
        result = json.loads(filter_qualified(data))
        self.assertTrue(result["passed"])

    def test_filter_qualified_rejects(self) -> None:
        data = json.dumps({"recommendation": "Reject", "match_score": 20})
        result = json.loads(filter_qualified(data))
        self.assertFalse(result["passed"])

    def test_filter_interview_passes(self) -> None:
        data = json.dumps({"recommendation": "Interview"})
        result = json.loads(filter_interview(data))
        self.assertTrue(result["passed"])

    def test_filter_interview_blocks_phone_screen(self) -> None:
        data = json.dumps({"recommendation": "Phone Screen"})
        result = json.loads(filter_interview(data))
        self.assertFalse(result["passed"])


class TestCalendarTools(unittest.TestCase):
    """Tests for calendar scheduling tool."""

    def test_schedule_interview(self) -> None:
        result = json.loads(schedule_interview("Alice", "Software Engineer", 3))
        self.assertEqual(result["status"], "confirmed")
        self.assertIn("hangoutLink", result)
        self.assertIn("Alice", result["summary"])
        self.assertIn("Software Engineer", result["summary"])
        self.assertIn("start", result)
        self.assertIn("end", result)


class TestNotificationTools(unittest.TestCase):
    """Tests for notification tools (mocked file output)."""

    def test_send_candidate_email(self) -> None:
        result = json.loads(send_candidate_email(
            to_email="EMAIL_PLACEHOLDER", from_email="EMAIL_PLACEHOLDER",
            subject="Interview Invite", body="Dear candidate...",
        ))
        self.assertEqual(result["status"], "sent_mock")
        self.assertTrue(os.path.exists(result["file"]))

    def test_send_slack_notification(self) -> None:
        result = json.loads(send_slack_notification(
            candidate_name="Alice", position="Engineer",
            match_score=85, status="Qualified",
            recommendation="Interview", strengths="Python, AWS",
        ))
        self.assertEqual(result["status"], "sent_mock")
        self.assertTrue(os.path.exists(result["file"]))

    def test_respond_webhook(self) -> None:
        result = json.loads(respond_webhook(
            candidate_id="rec123", candidate_name="Bob",
            match_score=70, status="Qualified",
            recommendation="Phone Screen",
        ))
        self.assertTrue(result["success"])
        self.assertEqual(result["name"], "Bob")
        self.assertEqual(result["recommendation"], "Phone Screen")


class TestAITools(unittest.TestCase):
    """Tests for AI tools (mocked OpenAI calls)."""

    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_extract_cv_data(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "skills": ["Python", "JavaScript"],
            "education": "MS CS Stanford",
            "years_experience": 4,
            "summary": "Experienced engineer.",
        })
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        from mcp_server.tools.ai_tools import extract_cv_data
        result = json.loads(extract_cv_data("Some CV text"))
        self.assertIn("skills", result)
        self.assertEqual(result["years_experience"], 4)

    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_assess_qualification(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "match_score": 88,
            "status": "Highly Qualified",
            "strengths": ["Python expert", "AWS certified"],
            "gaps": ["No Go experience"],
            "recommendation": "Interview",
            "reasoning": "Strong match overall.",
        })
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        from mcp_server.tools.ai_tools import assess_qualification
        cv = json.dumps({"skills": ["Python"], "education": "MS", "years_experience": 4})
        job = json.dumps({"Position": "Engineer", "Required_Experience": 3, "Required_Skills": "Python"})
        result = json.loads(assess_qualification(cv, job))
        self.assertEqual(result["match_score"], 88)
        self.assertEqual(result["recommendation"], "Interview")

    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_generate_recruitment_email(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "subject": "Interview Invitation - Software Engineer",
            "body": "Dear Alice, we are pleased to invite you...",
        })
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        from mcp_server.tools.ai_tools import generate_recruitment_email
        result = json.loads(generate_recruitment_email(
            candidate_name="Alice", position="Software Engineer",
            match_score=90, status="Highly Qualified",
            recommendation="Interview", strengths="Python, AWS",
        ))
        self.assertIn("subject", result)
        self.assertIn("body", result)


if __name__ == "__main__":
    unittest.main()
