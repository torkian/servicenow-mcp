"""Additional coverage tests for Time Card tools targeting uncovered paths."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.time_card_tools import (
    create_time_card,
    list_time_cards,
    update_time_card,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestTimeCardToolsCoverage(unittest.TestCase):

    def setUp(self):
        self.auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test", password="test"),
        )
        self.config = ServerConfig(
            instance_url="https://dev99999.service-now.com",
            auth=self.auth_config,
        )
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer TOKEN"}

    # --- list_time_cards missing paths ---

    def test_list_time_cards_invalid_week_start(self):
        """Validation failure returns error without HTTP calls."""
        result = list_time_cards(
            self.auth_manager,
            self.config,
            {"week_start": "not-a-date"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error validating", result["message"])

    @patch("servicenow_mcp.tools.time_card_tools._get_instance_url", return_value=None)
    def test_list_time_cards_no_instance_url(self, _mock):
        result = list_time_cards(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.time_card_tools._get_headers", return_value=None)
    def test_list_time_cards_no_headers(self, _mock):
        result = list_time_cards(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.time_card_tools.requests.get")
    def test_list_time_cards_task_resolve_request_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("connection failed")
        result = list_time_cards(
            self.auth_manager,
            self.config,
            {"task_number": "SCTASK0001"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error resolving task", result["message"])

    @patch("servicenow_mcp.tools.time_card_tools.requests.get")
    def test_list_time_cards_by_task_sys_id(self, mock_get):
        """task_sys_id filter is appended directly without resolution."""
        mock_get.return_value = MagicMock(
            json=lambda: {"result": []},
            raise_for_status=MagicMock(),
        )
        result = list_time_cards(
            self.auth_manager,
            self.config,
            {"task_sys_id": "abc123"},
        )
        self.assertTrue(result["success"])
        call_params = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("task=abc123", call_params)

    @patch("servicenow_mcp.tools.time_card_tools.requests.get")
    def test_list_time_cards_request_exception(self, mock_get):
        """RequestException during main list call returns error."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise requests.exceptions.RequestException("list failed")

        mock_get.side_effect = side_effect
        result = list_time_cards(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing time cards", result["message"])

    # --- create_time_card missing paths ---

    @patch("servicenow_mcp.tools.time_card_tools._get_instance_url", return_value=None)
    def test_create_time_card_no_instance_url(self, _mock):
        result = create_time_card(
            self.auth_manager,
            self.config,
            {"task_number": "SCTASK0001", "week_start": "2025-01-06"},
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.time_card_tools._get_headers", return_value=None)
    def test_create_time_card_no_headers(self, _mock):
        result = create_time_card(
            self.auth_manager,
            self.config,
            {"task_number": "SCTASK0001", "week_start": "2025-01-06"},
        )
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.time_card_tools.requests.get")
    def test_create_time_card_resolve_request_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("network error")
        result = create_time_card(
            self.auth_manager,
            self.config,
            {"task_number": "SCTASK0001", "week_start": "2025-01-06"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error resolving task", result["message"])

    @patch("servicenow_mcp.tools.time_card_tools.requests.post")
    @patch("servicenow_mcp.tools.time_card_tools.requests.get")
    def test_create_time_card_post_request_exception(self, mock_get, mock_post):
        mock_get.return_value = MagicMock(
            json=lambda: {"result": [{"sys_id": "task_abc"}]},
            raise_for_status=MagicMock(),
        )
        mock_post.side_effect = requests.exceptions.RequestException("post failed")
        result = create_time_card(
            self.auth_manager,
            self.config,
            {"task_number": "SCTASK0001", "week_start": "2025-01-06"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error creating time card", result["message"])

    # --- update_time_card missing paths ---

    @patch("servicenow_mcp.tools.time_card_tools._get_instance_url", return_value=None)
    def test_update_time_card_no_instance_url(self, _mock):
        result = update_time_card(
            self.auth_manager,
            self.config,
            {"time_card_sys_id": "tc001", "monday": 8},
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.time_card_tools._get_headers", return_value=None)
    def test_update_time_card_no_headers(self, _mock):
        result = update_time_card(
            self.auth_manager,
            self.config,
            {"time_card_sys_id": "tc001", "monday": 8},
        )
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.time_card_tools.requests.patch")
    def test_update_time_card_request_exception(self, mock_patch):
        mock_patch.side_effect = requests.exceptions.RequestException("patch failed")
        result = update_time_card(
            self.auth_manager,
            self.config,
            {"time_card_sys_id": "tc001", "friday": 4},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating time card", result["message"])


if __name__ == "__main__":
    unittest.main()
