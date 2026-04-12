"""
Tests for the UI policy tools.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.tools.ui_policy_tools import (
    CreateUIPolicyParams,
    UIPolicyResponse,
    create_ui_policy,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestCreateUIPolicy(unittest.TestCase):
    """Tests for the create_ui_policy function."""

    def setUp(self):
        self.config = ServerConfig(
            instance_url="https://test.service-now.com",
            timeout=10,
            auth=AuthConfig(
                type=AuthType.BASIC,
                basic=BasicAuthConfig(username="test_user", password="test_password"),
            ),
        )
        self.auth_manager = MagicMock()
        self.auth_manager.get_headers.return_value = {"Content-Type": "application/json"}

    @patch("requests.post")
    def test_create_ui_policy_minimal(self, mock_post):
        """Create a UI policy with only required fields."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "ui_pol_001",
                "name": "Hide field on low priority",
                "table_name": "incident",
                "active": "true",
            }
        }
        mock_post.return_value = mock_response

        params = CreateUIPolicyParams(
            name="Hide field on low priority",
            table_name="incident",
        )
        result = create_ui_policy(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.policy_id, "ui_pol_001")
        self.assertIn("created successfully", result.message)

        call_args = mock_post.call_args
        sent_data = call_args.kwargs["json"]
        self.assertEqual(sent_data["name"], "Hide field on low priority")
        self.assertEqual(sent_data["table_name"], "incident")
        self.assertEqual(sent_data["active"], "true")
        self.assertEqual(sent_data["on_load"], "true")
        self.assertEqual(sent_data["reverse_if_false"], "true")
        self.assertEqual(sent_data["run_scripts"], "false")
        # Optional fields not set
        self.assertNotIn("conditions", sent_data)
        self.assertNotIn("short_description", sent_data)
        self.assertNotIn("catalog_item", sent_data)

    @patch("requests.post")
    def test_create_ui_policy_with_all_fields(self, mock_post):
        """Create a UI policy with all optional fields populated."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "ui_pol_002",
                "name": "Require approval notes",
                "table_name": "change_request",
            }
        }
        mock_post.return_value = mock_response

        params = CreateUIPolicyParams(
            name="Require approval notes",
            table_name="change_request",
            active=True,
            on_load=False,
            reverse_if_false=False,
            conditions="risk=3^state=2",
            short_description="Make notes mandatory on high-risk changes",
            run_scripts=True,
        )
        result = create_ui_policy(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        self.assertEqual(result.policy_id, "ui_pol_002")

        sent_data = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent_data["conditions"], "risk=3^state=2")
        self.assertEqual(sent_data["short_description"], "Make notes mandatory on high-risk changes")
        self.assertEqual(sent_data["on_load"], "false")
        self.assertEqual(sent_data["reverse_if_false"], "false")
        self.assertEqual(sent_data["run_scripts"], "true")

    @patch("requests.post")
    def test_create_ui_policy_for_catalog_item(self, mock_post):
        """Create a catalog-scoped UI policy with a catalog_item_id."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "sys_id": "ui_pol_003",
                "name": "Show notes on select",
                "table_name": "sc_cat_item",
                "catalog_item": "cat_item_abc",
            }
        }
        mock_post.return_value = mock_response

        params = CreateUIPolicyParams(
            name="Show notes on select",
            table_name="sc_cat_item",
            catalog_item_id="cat_item_abc",
            conditions="selection=yes",
        )
        result = create_ui_policy(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        sent_data = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent_data["catalog_item"], "cat_item_abc")
        self.assertEqual(sent_data["conditions"], "selection=yes")

    @patch("requests.post")
    def test_create_ui_policy_http_error(self, mock_post):
        """Returns failure response on HTTP error."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        mock_post.return_value = mock_response

        params = CreateUIPolicyParams(
            name="Bad policy",
            table_name="incident",
        )
        result = create_ui_policy(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to create UI policy", result.message)
        self.assertIsNone(result.policy_id)

    @patch("requests.post")
    def test_create_ui_policy_connection_error(self, mock_post):
        """Returns failure response on connection error."""
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        params = CreateUIPolicyParams(
            name="Unreachable policy",
            table_name="incident",
        )
        result = create_ui_policy(self.config, self.auth_manager, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to create UI policy", result.message)

    @patch("requests.post")
    def test_create_ui_policy_inactive(self, mock_post):
        """Create an inactive UI policy."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"sys_id": "ui_pol_004", "name": "Draft policy", "active": "false"}
        }
        mock_post.return_value = mock_response

        params = CreateUIPolicyParams(
            name="Draft policy",
            table_name="problem",
            active=False,
        )
        result = create_ui_policy(self.config, self.auth_manager, params)

        self.assertTrue(result.success)
        sent_data = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent_data["active"], "false")

    @patch("requests.post")
    def test_create_ui_policy_posts_to_correct_endpoint(self, mock_post):
        """Verifies the request targets sys_ui_policy table."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "x"}}
        mock_post.return_value = mock_response

        params = CreateUIPolicyParams(name="P", table_name="incident")
        create_ui_policy(self.config, self.auth_manager, params)

        url = mock_post.call_args.args[0]
        self.assertIn("/api/now/table/sys_ui_policy", url)

    def test_ui_policy_response_model(self):
        """UIPolicyResponse can be constructed with all fields."""
        r = UIPolicyResponse(
            success=True,
            message="ok",
            policy_id="abc",
            details={"key": "value"},
        )
        self.assertTrue(r.success)
        self.assertEqual(r.policy_id, "abc")

    def test_create_ui_policy_params_defaults(self):
        """Default values for optional boolean fields."""
        params = CreateUIPolicyParams(name="P", table_name="incident")
        self.assertTrue(params.active)
        self.assertTrue(params.on_load)
        self.assertTrue(params.reverse_if_false)
        self.assertFalse(params.run_scripts)
        self.assertIsNone(params.conditions)
        self.assertIsNone(params.short_description)
        self.assertIsNone(params.catalog_item_id)


if __name__ == "__main__":
    unittest.main()
