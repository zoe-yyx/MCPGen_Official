"""Unit tests for tool functions — direct Python calls, no MCP."""

import json
import os
import tempfile
import unittest

from mcp_server.tools.booking_tools import (
    receive_booking,
    get_workflow_config,
    fetch_inventory,
    prepare_validation_input,
)
from mcp_server.tools.validation_tools import route_by_risk_level
from mcp_server.tools.orchestration_tools import update_ticketing_system
from mcp_server.tools.notification_tools import (
    send_confirmation_email,
    alert_operations_team,
    log_audit_trail,
)


SAMPLE_BOOKING = {
    "bookingId": "BK-TEST-001",
    "customerEmail": "EMAIL_PLACEHOLDER",
    "customerName": "Test User",
    "eventName": "Test Concert",
    "ticketTier": "VIP",
    "ticketQuantity": 2,
    "totalAmount": 450.00,
    "paymentMethod": "CREDIT_CARD",
    "consentFlags": {"termsAccepted": True, "privacyPolicyAccepted": True},
}


class TestBookingTools(unittest.TestCase):

    def test_receive_booking_from_dict(self):
        result = receive_booking(SAMPLE_BOOKING)
        self.assertEqual(result["bookingId"], "BK-TEST-001")

    def test_receive_booking_from_json_string(self):
        result = receive_booking(json.dumps(SAMPLE_BOOKING))
        self.assertEqual(result["customerEmail"], "EMAIL_PLACEHOLDER")

    def test_get_workflow_config(self):
        config = get_workflow_config()
        self.assertEqual(config["venueCapacity"], 5000)
        self.assertEqual(config["maxTicketsPerCustomer"], 8)
        self.assertEqual(config["fraudScoreThreshold"], 75)

    def test_fetch_inventory(self):
        inv = fetch_inventory()
        self.assertEqual(inv["totalCapacity"], 5000)
        self.assertIn("VIP", inv["tiers"])
        self.assertGreater(inv["tiers"]["VIP"]["available"], 0)

    def test_prepare_validation_input(self):
        config = get_workflow_config()
        inv = fetch_inventory()
        result = prepare_validation_input(
            json.dumps(SAMPLE_BOOKING),
            json.dumps(inv),
            json.dumps(config),
        )
        self.assertIn("bookingData", result)
        self.assertIn("inventoryData", result)
        self.assertEqual(result["venueCapacity"], 5000)


class TestValidationTools(unittest.TestCase):

    def test_route_low_risk(self):
        result = route_by_risk_level(json.dumps({
            "riskLevel": "LOW",
            "requiresHumanReview": False,
        }))
        self.assertEqual(result["route"], "low_medium")

    def test_route_medium_risk(self):
        result = route_by_risk_level(json.dumps({
            "riskLevel": "MEDIUM",
            "requiresHumanReview": False,
        }))
        self.assertEqual(result["route"], "low_medium")

    def test_route_high_risk(self):
        result = route_by_risk_level(json.dumps({
            "riskLevel": "HIGH",
            "requiresHumanReview": True,
        }))
        self.assertEqual(result["route"], "high_critical")

    def test_route_critical_risk(self):
        result = route_by_risk_level(json.dumps({
            "riskLevel": "CRITICAL",
            "requiresHumanReview": True,
        }))
        self.assertEqual(result["route"], "high_critical")

    def test_route_requires_review_overrides(self):
        result = route_by_risk_level(json.dumps({
            "riskLevel": "MEDIUM",
            "requiresHumanReview": True,
        }))
        # requiresHumanReview=True with MEDIUM still goes low_medium
        # because the switch checks riskLevel first
        # but in n8n the HIGH/CRITICAL branch also triggers on requiresHumanReview=True
        # Let's verify what route_by_risk_level actually does
        # It checks: if HIGH/CRITICAL OR requiresHumanReview → high_critical
        self.assertEqual(result["route"], "high_critical")


class TestOrchestrationTools(unittest.TestCase):

    def test_update_ticketing_system(self):
        update = {
            "bookingId": "BK-TEST-001",
            "status": "CONFIRMED",
            "seatAssignments": ["A12", "A13"],
            "paymentStatus": "COMPLETED",
        }
        result = update_ticketing_system(json.dumps(update))
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["bookingId"], "BK-TEST-001")


class TestNotificationTools(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def test_send_confirmation_email(self):
        import mcp_server.tools.notification_tools as nt
        original = nt.EMAILS_DIR
        nt.EMAILS_DIR = self.test_dir
        try:
            result = send_confirmation_email(
                recipient_email="EMAIL_PLACEHOLDER",
                subject="Ticket Confirmation",
                booking_id="BK-TEST-001",
                status="CONFIRMED",
                seat_assignments="A12, A13",
            )
            self.assertEqual(result["status"], "sent")
            self.assertEqual(result["recipient"], "EMAIL_PLACEHOLDER")
        finally:
            nt.EMAILS_DIR = original

    def test_alert_operations_team(self):
        import mcp_server.tools.notification_tools as nt
        original = nt.ALERTS_FILE
        nt.ALERTS_FILE = os.path.join(self.test_dir, "alerts.jsonl")
        try:
            result = alert_operations_team(
                risk_level="HIGH",
                risk_score=85,
                validation_status="INVALID",
                customer_email="EMAIL_PLACEHOLDER",
                ticket_quantity=8,
                total_amount=4000.0,
                fraud_indicators="velocity_check_failed,ip_mismatch",
                escalation_reason="Multiple fraud indicators",
                reasoning="High risk detected",
            )
            self.assertEqual(result["status"], "alerted")
        finally:
            nt.ALERTS_FILE = original

    def test_log_audit_trail(self):
        import mcp_server.tools.notification_tools as nt
        original = nt.AUDIT_CSV
        nt.AUDIT_CSV = os.path.join(self.test_dir, "audit.csv")
        try:
            result = log_audit_trail(
                booking_id="BK-TEST-001",
                customer_email="EMAIL_PLACEHOLDER",
                validation_status="VALID",
                risk_level="LOW",
                risk_score=15,
                requires_human_review=False,
                audit_summary="Standard booking processed",
            )
            self.assertEqual(result["status"], "logged")
            self.assertTrue(os.path.exists(nt.AUDIT_CSV))
        finally:
            nt.AUDIT_CSV = original


if __name__ == "__main__":
    unittest.main()
