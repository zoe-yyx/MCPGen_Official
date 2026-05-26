"""Unit tests for leave management tools - direct Python function calls (no MCP)."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mcp_server.tools.leave_tools import (
    fetch_leave_records,
    validate_normalize_leave_data,
    mark_leave_as_active,
    mark_leave_as_inactive,
)
from mcp_server.tools.notification_tools import notify_hr_channel, notify_hr_leave_reset
from mcp_server.tools.email_tools import send_ooo_reminder_email, send_welcome_back_email


class TestLeaveTools(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.data_file = os.path.join(self.tmp_dir, "leave_records.json")
        self.test_records = [
            {
                "Employee Email": "EMAIL_PLACEHOLDER",
                "Name": "Test User",
                "Start Date": "2026-05-17",
                "End Date": "2026-05-22",
                "Status": "Inactive",
                "Last Updated": "",
            },
            {
                "Employee Email": "EMAIL_PLACEHOLDER",
                "Name": "Past User",
                "Start Date": "2026-05-10",
                "End Date": "2026-05-15",
                "Status": "Active",
                "Last Updated": "2026-05-10",
            },
        ]
        with open(self.data_file, "w") as f:
            json.dump(self.test_records, f)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_fetch_leave_records(self):
        import mcp_server.tools.leave_tools as lt
        original = lt.DATA_FILE
        lt.DATA_FILE = self.data_file
        try:
            result = fetch_leave_records()
            records = json.loads(result)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["Employee Email"], "EMAIL_PLACEHOLDER")
        finally:
            lt.DATA_FILE = original

    def test_validate_normalize_valid_records(self):
        records = json.dumps(self.test_records)
        with patch("mcp_server.tools.leave_tools.date") as mock_date:
            mock_date.today.return_value = date(2026, 5, 18)
            result = validate_normalize_leave_data(records)
        normalized = json.loads(result)
        self.assertEqual(len(normalized), 2)
        test_record = next(r for r in normalized if r["email"] == "EMAIL_PLACEHOLDER")
        self.assertTrue(test_record["needsActivation"])
        self.assertFalse(test_record["needsReset"])
        past_record = next(r for r in normalized if r["email"] == "EMAIL_PLACEHOLDER")
        self.assertFalse(past_record["needsActivation"])
        self.assertTrue(past_record["needsReset"])

    def test_validate_normalize_skips_invalid(self):
        bad_records = [
            {"Employee Email": "", "Name": "No Email", "Start Date": "2026-05-17", "End Date": "2026-05-22", "Status": "Inactive"},
            {"Employee Email": "EMAIL_PLACEHOLDER", "Name": "Valid", "Start Date": "bad-date", "End Date": "2026-05-22", "Status": "Inactive"},
        ]
        result = validate_normalize_leave_data(json.dumps(bad_records))
        normalized = json.loads(result)
        self.assertEqual(len(normalized), 0)

    def test_mark_leave_as_active(self):
        import mcp_server.tools.leave_tools as lt
        original = lt.DATA_FILE
        lt.DATA_FILE = self.data_file
        try:
            result = mark_leave_as_active("EMAIL_PLACEHOLDER", "2026-05-18")
            self.assertIn("Active", result)
            records = json.loads(open(self.data_file, encoding="utf-8").read())
            target = next(r for r in records if r["Employee Email"] == "EMAIL_PLACEHOLDER")
            self.assertEqual(target["Status"], "Active")
            self.assertEqual(target["Last Updated"], "2026-05-18")
        finally:
            lt.DATA_FILE = original

    def test_mark_leave_as_inactive(self):
        import mcp_server.tools.leave_tools as lt
        original = lt.DATA_FILE
        lt.DATA_FILE = self.data_file
        try:
            result = mark_leave_as_inactive("EMAIL_PLACEHOLDER", "2026-05-18")
            self.assertIn("Inactive", result)
            records = json.loads(open(self.data_file, encoding="utf-8").read())
            target = next(r for r in records if r["Employee Email"] == "EMAIL_PLACEHOLDER")
            self.assertEqual(target["Status"], "Inactive")
        finally:
            lt.DATA_FILE = original

    def test_mark_not_found(self):
        import mcp_server.tools.leave_tools as lt
        original = lt.DATA_FILE
        lt.DATA_FILE = self.data_file
        try:
            result = mark_leave_as_active("EMAIL_PLACEHOLDER", "2026-05-18")
            self.assertIn("No matching record", result)
        finally:
            lt.DATA_FILE = original


class TestNotificationTools(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.slack_log = os.path.join(self.tmp_dir, "slack_notifications.json")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_notify_hr_channel(self):
        import mcp_server.tools.notification_tools as nt
        original = nt.SLACK_LOG_FILE
        nt.SLACK_LOG_FILE = self.slack_log
        try:
            result = notify_hr_channel("Alice Smith", "EMAIL_PLACEHOLDER", "2026-05-17", "2026-05-22")
            self.assertIn("Alice Smith", result)
            self.assertTrue(os.path.exists(self.slack_log))
            messages = json.loads(open(self.slack_log, encoding="utf-8").read())
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]["type"], "leave_activated")
            self.assertEqual(messages[0]["employee_email"], "EMAIL_PLACEHOLDER")
        finally:
            nt.SLACK_LOG_FILE = original

    def test_notify_hr_leave_reset(self):
        import mcp_server.tools.notification_tools as nt
        original = nt.SLACK_LOG_FILE
        nt.SLACK_LOG_FILE = self.slack_log
        try:
            result = notify_hr_leave_reset("Bob Johnson", "EMAIL_PLACEHOLDER", "2026-05-10", "2026-05-15")
            self.assertIn("Bob Johnson", result)
            messages = json.loads(open(self.slack_log, encoding="utf-8").read())
            self.assertEqual(messages[0]["type"], "leave_completed")
            self.assertEqual(messages[0]["employee_email"], "EMAIL_PLACEHOLDER")
        finally:
            nt.SLACK_LOG_FILE = original


class TestEmailTools(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.email_log = os.path.join(self.tmp_dir, "emails.json")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_send_ooo_reminder_email(self):
        import mcp_server.tools.email_tools as et
        original = et.EMAIL_LOG_FILE
        et.EMAIL_LOG_FILE = self.email_log
        try:
            result = send_ooo_reminder_email("EMAIL_PLACEHOLDER", "Alice Smith", "2026-05-17", "2026-05-22")
            self.assertIn("EMAIL_PLACEHOLDER", result)
            emails = json.loads(open(self.email_log, encoding="utf-8").read())
            self.assertEqual(emails[0]["type"], "ooo_reminder")
            self.assertIn("Alice Smith", emails[0]["body"])
        finally:
            et.EMAIL_LOG_FILE = original

    def test_send_welcome_back_email(self):
        import mcp_server.tools.email_tools as et
        original = et.EMAIL_LOG_FILE
        et.EMAIL_LOG_FILE = self.email_log
        try:
            result = send_welcome_back_email("EMAIL_PLACEHOLDER", "Bob Johnson", "2026-05-15")
            self.assertIn("EMAIL_PLACEHOLDER", result)
            emails = json.loads(open(self.email_log, encoding="utf-8").read())
            self.assertEqual(emails[0]["type"], "welcome_back")
            self.assertIn("Bob Johnson", emails[0]["body"])
        finally:
            et.EMAIL_LOG_FILE = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
