"""Unit tests for Docker Management Bot tools."""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.webhook_tools import receive_uptime_webhook, check_heartbeat_status
from mcp_server.tools.command_tools import extract_service_name, route_command, parse_update_summary
from mcp_server.tools.docker_tools import (
    get_docker_logs, restart_docker_container,
    check_restart_success, docker_ps, run_docker_update,
)
from mcp_server.tools.notification_tools import (
    send_ok_notification, send_error_notification,
    send_analyzing_status, send_log_analysis,
    send_restart_message, send_restart_success, send_restart_failed,
    send_docker_status, send_update_started, send_update_result,
)


class TestWebhookTools(unittest.TestCase):
    def test_receive_uptime_webhook(self) -> None:
        result = json.loads(receive_uptime_webhook(
            heartbeat_msg="running",
            heartbeat_time="2026-04-23T05:00:00Z",
            monitor_name="nginx-monitor",
            monitor_docker_container="nginx",
        ))
        self.assertEqual(result["body"]["heartbeat"]["msg"], "running")
        self.assertEqual(result["body"]["monitor"]["docker_container"], "nginx")

    def test_check_heartbeat_running(self) -> None:
        webhook = receive_uptime_webhook("running", "2026-04-23T05:00:00Z", "mon", "nginx")
        result = json.loads(check_heartbeat_status(webhook))
        self.assertEqual(result["route"], "ok")

    def test_check_heartbeat_error(self) -> None:
        webhook = receive_uptime_webhook("Service unavailable", "2026-04-23T05:00:00Z", "mon", "nginx")
        result = json.loads(check_heartbeat_status(webhook))
        self.assertEqual(result["route"], "error")
        self.assertIn("nginx", result["docker_container"])


class TestCommandTools(unittest.TestCase):
    def test_extract_service_name(self) -> None:
        result = json.loads(extract_service_name("nginx logs"))
        self.assertEqual(result["service_name"], "nginx")

    def test_extract_service_name_single_word(self) -> None:
        result = json.loads(extract_service_name("status"))
        self.assertEqual(result["service_name"], "status")

    def test_route_command_logs(self) -> None:
        result = json.loads(route_command("nginx logs"))
        self.assertEqual(result["command"], "logs")
        self.assertEqual(result["service_name"], "nginx")

    def test_route_command_restart(self) -> None:
        result = json.loads(route_command("nginx restart"))
        self.assertEqual(result["command"], "restart")

    def test_route_command_status(self) -> None:
        result = json.loads(route_command("status"))
        self.assertEqual(result["command"], "status")

    def test_route_command_update(self) -> None:
        result = json.loads(route_command("update"))
        self.assertEqual(result["command"], "update")

    def test_route_command_unknown(self) -> None:
        result = json.loads(route_command("hello world"))
        self.assertEqual(result["command"], "unknown")

    def test_parse_update_summary(self) -> None:
        stdout = (
            'Update Summary:\n'
            '{"nginx-compose.yaml": ["nginx:latest: updated"], '
            '"redis-compose.yaml": ["redis:7: updated"]}'
        )
        result = json.loads(parse_update_summary(stdout))
        self.assertIn("nginx", result["message"])
        self.assertIn("redis", result["message"])

    def test_parse_update_summary_no_match(self) -> None:
        result = json.loads(parse_update_summary("some random output"))
        self.assertIn("No summary", result["message"])


class TestDockerTools(unittest.TestCase):
    def test_get_docker_logs_known_service(self) -> None:
        result = json.loads(get_docker_logs("nginx"))
        self.assertIn("nginx", result["stdout"].lower())
        self.assertEqual(result["service_name"], "nginx")

    def test_get_docker_logs_unknown_service(self) -> None:
        result = json.loads(get_docker_logs("myapp"))
        self.assertIn("myapp", result["stdout"])

    def test_restart_docker_container_success(self) -> None:
        result = json.loads(restart_docker_container("nginx"))
        self.assertEqual(result["stdout"], "nginx")
        self.assertEqual(result["stderr"], "")

    def test_restart_docker_container_unknown(self) -> None:
        result = json.loads(restart_docker_container("unknown"))
        self.assertIn("stderr", result)
        self.assertNotEqual(result["stderr"], "")

    def test_check_restart_success_true(self) -> None:
        restart_data = json.dumps({"stdout": "nginx", "stderr": "", "service_name": "nginx"})
        result = json.loads(check_restart_success(restart_data))
        self.assertTrue(result["success"])

    def test_check_restart_success_false(self) -> None:
        restart_data = json.dumps({"stdout": "", "stderr": "Error: No such container", "service_name": "bad"})
        result = json.loads(check_restart_success(restart_data))
        self.assertFalse(result["success"])

    def test_docker_ps(self) -> None:
        result = json.loads(docker_ps())
        self.assertIn("stdout", result)
        self.assertIn("nginx", result["stdout"])

    def test_run_docker_update(self) -> None:
        result = json.loads(run_docker_update())
        self.assertIn("Update Summary", result["stdout"])


class TestNotificationTools(unittest.TestCase):
    def test_send_ok_notification(self) -> None:
        result = json.loads(send_ok_notification("All good"))
        self.assertEqual(result["status"], "sent_mock")
        self.assertEqual(result["type"], "ok")
        self.assertTrue(os.path.exists(result["file"]))

    def test_send_error_notification(self) -> None:
        result = json.loads(send_error_notification("nginx", "Connection refused", "2026-04-23T05:00:00Z"))
        self.assertEqual(result["type"], "error")
        self.assertEqual(len(result["keyboard"]), 2)
        self.assertTrue(os.path.exists(result["file"]))

    def test_send_restart_success(self) -> None:
        result = json.loads(send_restart_success("nginx"))
        self.assertEqual(result["type"], "restart_success")
        self.assertIn("nginx", result["message"])

    def test_send_restart_failed(self) -> None:
        result = json.loads(send_restart_failed("Error: container not found"))
        self.assertEqual(result["type"], "restart_failed")

    def test_send_docker_status(self) -> None:
        result = json.loads(send_docker_status("nginx\tUp 2 hours"))
        self.assertEqual(result["type"], "docker_status")

    def test_send_update_result(self) -> None:
        result = json.loads(send_update_result("nginx: Updated; redis: Updated"))
        self.assertEqual(result["type"], "update_result")


class TestAITools(unittest.TestCase):
    @patch("mcp_server.tools.ai_tools.OpenAI")
    def test_analyze_logs_with_ai(self, mock_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = (
            "Summary\nNginx is experiencing upstream connection failures.\n\n"
            "Most Likely Root Cause\nBackend service is down on port 8080.\n\n"
            "Severity Level\n4 - Service degraded, upstream errors affect users."
        )
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        from mcp_server.tools.ai_tools import analyze_logs_with_ai
        result = json.loads(analyze_logs_with_ai("some log text"))
        self.assertIn("analysis", result)
        self.assertIn("Summary", result["analysis"])


if __name__ == "__main__":
    unittest.main()
