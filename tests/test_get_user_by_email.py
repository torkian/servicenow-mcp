"""Tests for get_user_by_email tool."""

import unittest
from unittest.mock import MagicMock, patch

from requests.exceptions import RequestException

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.user_tools import GetUserByEmailParams, get_user_by_email
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

USER_RECORD = {
    "sys_id": "abc123def456abc123def456abc12345",
    "user_name": "jane.doe",
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane.doe@example.com",
    "title": "Engineer",
    "department": "Engineering",
    "manager": "mgr001",
    "phone": "555-0100",
    "mobile_phone": "555-0101",
    "location": "Building A",
    "active": "true",
    "sys_created_on": "2024-01-01 00:00:00",
    "sys_updated_on": "2024-06-01 00:00:00",
}


class TestGetUserByEmail(unittest.TestCase):
    def setUp(self):
        self.config = ServerConfig(
            instance_url="https://dev99999.service-now.com",
            auth=AuthConfig(
                type=AuthType.BASIC,
                basic=BasicAuthConfig(username="admin", password="password"),
            ),
        )
        self.auth = MagicMock(spec=AuthManager)
        self.auth.get_headers.return_value = {"Authorization": "Basic dGVzdA=="}

    def _make_ok_response(self, records):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"result": records}
        return resp

    # --- happy path ---

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_exact_match_found(self, mock_get):
        mock_get.return_value = self._make_ok_response([USER_RECORD])
        params = GetUserByEmailParams(email="jane.doe@example.com")
        result = get_user_by_email(self.config, self.auth, params)

        self.assertTrue(result["success"])
        self.assertEqual(result["user"]["sys_id"], "abc123def456abc123def456abc12345")
        self.assertEqual(result["user"]["email"], "jane.doe@example.com")

        call_kwargs = mock_get.call_args[1]
        self.assertIn("email=jane.doe@example.com", call_kwargs["params"]["sysparm_query"])

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_partial_match_uses_like_operator(self, mock_get):
        mock_get.return_value = self._make_ok_response([USER_RECORD])
        params = GetUserByEmailParams(email="jane", exact=False)
        result = get_user_by_email(self.config, self.auth, params)

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args[1]
        self.assertIn("emailLIKEjane", call_kwargs["params"]["sysparm_query"])

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_exact_true_by_default(self, mock_get):
        mock_get.return_value = self._make_ok_response([USER_RECORD])
        params = GetUserByEmailParams(email="jane.doe@example.com")
        get_user_by_email(self.config, self.auth, params)

        call_kwargs = mock_get.call_args[1]
        self.assertIn("email=jane.doe@example.com", call_kwargs["params"]["sysparm_query"])

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_sysparm_fields_requested(self, mock_get):
        mock_get.return_value = self._make_ok_response([USER_RECORD])
        params = GetUserByEmailParams(email="jane.doe@example.com")
        get_user_by_email(self.config, self.auth, params)

        call_kwargs = mock_get.call_args[1]
        fields = call_kwargs["params"]["sysparm_fields"]
        self.assertIn("sys_id", fields)
        self.assertIn("email", fields)
        self.assertIn("user_name", fields)

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_limit_is_one(self, mock_get):
        mock_get.return_value = self._make_ok_response([USER_RECORD])
        params = GetUserByEmailParams(email="x@y.com")
        get_user_by_email(self.config, self.auth, params)

        call_kwargs = mock_get.call_args[1]
        self.assertEqual(call_kwargs["params"]["sysparm_limit"], "1")

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_display_value_true(self, mock_get):
        mock_get.return_value = self._make_ok_response([USER_RECORD])
        params = GetUserByEmailParams(email="x@y.com")
        get_user_by_email(self.config, self.auth, params)

        call_kwargs = mock_get.call_args[1]
        self.assertEqual(call_kwargs["params"]["sysparm_display_value"], "true")

    # --- not found ---

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_not_found(self, mock_get):
        mock_get.return_value = self._make_ok_response([])
        params = GetUserByEmailParams(email="nobody@nowhere.com")
        result = get_user_by_email(self.config, self.auth, params)

        self.assertFalse(result["success"])
        self.assertIn("nobody@nowhere.com", result["message"])

    # --- error handling ---

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_request_exception(self, mock_get):
        mock_get.side_effect = RequestException("connection refused")
        params = GetUserByEmailParams(email="x@y.com")
        result = get_user_by_email(self.config, self.auth, params)

        self.assertFalse(result["success"])
        self.assertIn("Failed to look up user by email", result["message"])

    # --- url construction ---

    @patch("servicenow_mcp.tools.user_tools.requests.get")
    def test_correct_endpoint(self, mock_get):
        mock_get.return_value = self._make_ok_response([USER_RECORD])
        params = GetUserByEmailParams(email="x@y.com")
        get_user_by_email(self.config, self.auth, params)

        call_url = mock_get.call_args[0][0]
        self.assertIn("/table/sys_user", call_url)


if __name__ == "__main__":
    unittest.main()
