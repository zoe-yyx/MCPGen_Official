"""Unit tests for Google Tasks → n8n Plans tools."""

import csv
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.tasks_tools import get_new_ideas, filter_processed, mark_as_notified
from mcp_server.tools.slack_tools import slack_review_approve, check_approval
from mcp_server.tools.sheets_tools import archive_to_sheets


class TestGetNewIdeas(unittest.TestCase):
    def test_returns_up_to_limit(self) -> None:
        result = json.loads(get_new_ideas(limit=3))
        self.assertLessEqual(result["count"], 3)
        self.assertEqual(len(result["tasks"]), result["count"])

    def test_task_structure(self) -> None:
        result = json.loads(get_new_ideas(limit=5))
        for task in result["tasks"]:
            self.assertIn("id", task)
            self.assertIn("title", task)
            self.assertIn("notes", task)

    def test_default_limit(self) -> None:
        result = json.loads(get_new_ideas())
        self.assertLessEqual(result["count"], 5)


class TestFilterProcessed(unittest.TestCase):
    def _make_tasks_json(self, tasks: list) -> str:
        return json.dumps({"tasks": tasks, "count": len(tasks), "fetched_at": "2026-05-18T09:00:00Z"})

    def test_filters_processed_tasks(self) -> None:
        tasks = [
            {"id": "t1", "title": "Idea A", "notes": ""},
            {"id": "t2", "title": "Idea B", "notes": "✅ Processed"},
            {"id": "t3", "title": "Idea C", "notes": "some note"},
        ]
        result = json.loads(filter_processed(self._make_tasks_json(tasks)))
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["skipped"], 1)
        ids = [t["id"] for t in result["tasks"]]
        self.assertIn("t1", ids)
        self.assertNotIn("t2", ids)

    def test_all_processed(self) -> None:
        tasks = [{"id": "t1", "title": "A", "notes": "✅ Processed"}]
        result = json.loads(filter_processed(self._make_tasks_json(tasks)))
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["skipped"], 1)

    def test_none_processed(self) -> None:
        tasks = [
            {"id": "t1", "title": "A", "notes": ""},
            {"id": "t2", "title": "B", "notes": "draft"},
        ]
        result = json.loads(filter_processed(self._make_tasks_json(tasks)))
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["skipped"], 0)


class TestMarkAsNotified(unittest.TestCase):
    def test_marks_task(self) -> None:
        result = json.loads(mark_as_notified("task_001"))
        self.assertEqual(result["task_id"], "task_001")
        self.assertEqual(result["notes"], "✅ Processed")
        self.assertEqual(result["status"], "mock_updated")
        self.assertTrue(os.path.exists(result["file"] if "file" in result else "results/outputs/task_notified_task_001.json"))

    def test_unknown_task(self) -> None:
        result = json.loads(mark_as_notified("nonexistent_task"))
        self.assertEqual(result["notes"], "✅ Processed")
        self.assertEqual(result["status"], "mock_updated")


class TestSlackTools(unittest.TestCase):
    def test_slack_review_approve_auto_approve(self) -> None:
        with patch.dict(os.environ, {"SLACK_AUTO_APPROVE": "true"}):
            result = json.loads(slack_review_approve("Hello from Slack", "Test Idea"))
        self.assertTrue(result["data"]["approved"])
        self.assertEqual(result["data"]["response"], "Approve")
        self.assertEqual(result["data"]["status"], "mock_sent")

    def test_slack_review_approve_auto_reject(self) -> None:
        with patch.dict(os.environ, {"SLACK_AUTO_APPROVE": "false"}):
            result = json.loads(slack_review_approve("Hello from Slack", "Test Idea"))
        self.assertFalse(result["data"]["approved"])
        self.assertEqual(result["data"]["response"], "Regenerate")

    def test_check_approval_true(self) -> None:
        slack_resp = json.dumps({"data": {"approved": True}})
        result = json.loads(check_approval(slack_resp))
        self.assertTrue(result["approved"])
        self.assertEqual(result["route"], "approved")

    def test_check_approval_false(self) -> None:
        slack_resp = json.dumps({"data": {"approved": False}})
        result = json.loads(check_approval(slack_resp))
        self.assertFalse(result["approved"])
        self.assertEqual(result["route"], "regenerate")


class TestArchiveToSheets(unittest.TestCase):
    def test_appends_row(self) -> None:
        result = json.loads(archive_to_sheets(
            idea_title="Test Idea Title",
            nodes="Schedule Trigger → HTTP Request → Slack",
            challenges="OAuth token expiry",
            improvements="Add error handler",
            alternatives="Use webhook instead of schedule",
            source_task_id="task_001",
        ))
        self.assertEqual(result["status"], "mock_appended")
        self.assertTrue(os.path.exists(result["file"]))
        row = result["row"]
        self.assertEqual(row["Idea Title"], "Test Idea Title")
        self.assertEqual(row["Status"], "Approved")
        self.assertEqual(row["Source Task ID"], "task_001")

    def test_csv_file_has_header(self) -> None:
        archive_to_sheets(
            idea_title="Another Idea",
            nodes="Gmail → Sheets",
            challenges="Rate limits",
            improvements="Batch writes",
            alternatives="Use Zapier",
            source_task_id="task_002",
        )
        with open("results/outputs/archived_ideas.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.assertIn("Idea Title", reader.fieldnames or [])
            self.assertIn("Status", reader.fieldnames or [])


class TestAITools(unittest.TestCase):
    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_ai_solution_architect(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "title": "Automated Email Digest from Gmail",
            "nodes": "Schedule Trigger → Gmail → Code → Slack",
            "challenges": "Gmail API rate limits",
            "improvements": "Add HTML formatting",
            "alternatives": "Use Zapier instead",
            "slack_message": "*Automated Email Digest*\n\n*Nodes:* Schedule Trigger → Gmail → Slack",
        })
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        from mcp_server.tools.ai_tools import ai_solution_architect
        result = json.loads(ai_solution_architect("Build an automated email digest from Gmail"))
        self.assertIn("output", result)
        self.assertEqual(result["output"]["title"], "Automated Email Digest from Gmail")
        self.assertIn("slack_message", result["output"])
        self.assertIn("nodes", result["output"])

    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_ai_solution_architect_json_fallback(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = "invalid json {{{"
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        from mcp_server.tools.ai_tools import ai_solution_architect
        result = json.loads(ai_solution_architect("Some idea"))
        self.assertIn("output", result)
        self.assertEqual(result["output"]["title"], "Some idea")


if __name__ == "__main__":
    unittest.main()
