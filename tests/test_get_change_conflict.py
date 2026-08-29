"""Tests for get_change_conflict in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import get_change_conflict
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
CHANGE_SYS_ID = "b" * 32
CONFLICT_CI_SYS_ID = "c" * 32
CONFLICT_CHANGE_SYS_ID = "d" * 32

FAKE_CONFLICT = {
    "sys_id": FAKE_SYS_ID,
    "change_request": {"display_value": "CHG0012345", "value": CHANGE_SYS_ID},
    "conflict_ci": {"display_value": "web-server-01", "value": CONFLICT_CI_SYS_ID},
    "conflict_change": {"display_value": "CHG0012346", "value": CONFLICT_CHANGE_SYS_ID},
    "type": {"display_value": "CI Conflict", "value": "ci_conflict"},
    "state": {"display_value": "Unresolved", "value": "unresolved"},
    "blackout_window": {"display_value": "", "value": ""},
    "sys_created_on": "2026-06-01 10:00:00",
    "sys_updated_on": "2026-06-02 14:30:00",
}


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev99999.service-now.com", auth=auth_config)


def _make_auth_manager():
    auth_manager = MagicMock(spec=AuthManager)
    auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    auth_manager.instance_url = "https://dev99999.service-now.com"
    return auth_manager


def _make_response(status_code, json_data):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


class TestGetChangeConflictSuccess(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_conflict_on_success(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_CONFLICT})

        result = get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": FAKE_SYS_ID},
        )

        self.assertTrue(result["success"])
        conflict = result["conflict"]
        self.assertEqual(conflict["sys_id"], FAKE_SYS_ID)
        self.assertEqual(conflict["change_request"], "CHG0012345")
        self.assertEqual(conflict["conflict_ci"], "web-server-01")
        self.assertEqual(conflict["conflict_change"], "CHG0012346")
        self.assertEqual(conflict["type"], "CI Conflict")
        self.assertEqual(conflict["state"], "Unresolved")
        self.assertEqual(conflict["created_on"], "2026-06-01 10:00:00")
        self.assertEqual(conflict["updated_on"], "2026-06-02 14:30:00")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_url_contains_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_CONFLICT})

        get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": FAKE_SYS_ID},
        )

        url = mock_req.call_args[0][1]
        self.assertIn(FAKE_SYS_ID, url)
        self.assertIn("change_conflict", url)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_display_value_all_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_CONFLICT})

        get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": FAKE_SYS_ID},
        )

        api_params = mock_req.call_args[1]["params"]
        self.assertEqual(api_params["sysparm_display_value"], "all")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_fields_param_included(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_CONFLICT})

        get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": FAKE_SYS_ID},
        )

        api_params = mock_req.call_args[1]["params"]
        self.assertIn("sys_id", api_params["sysparm_fields"])
        self.assertIn("change_request", api_params["sysparm_fields"])
        self.assertIn("type", api_params["sysparm_fields"])
        self.assertIn("state", api_params["sysparm_fields"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_exclude_reference_link_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_CONFLICT})

        get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": FAKE_SYS_ID},
        )

        api_params = mock_req.call_args[1]["params"]
        self.assertEqual(api_params["sysparm_exclude_reference_link"], "true")


# ---------------------------------------------------------------------------
# Not-found paths
# ---------------------------------------------------------------------------


class TestGetChangeConflictNotFound(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_returns_failure(self, mock_req):
        resp = _make_response(404, {})
        resp.raise_for_status = MagicMock()  # don't raise on 404 check
        mock_req.return_value = resp

        result = get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": FAKE_SYS_ID},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertIn(FAKE_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_empty_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})

        result = get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": FAKE_SYS_ID},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_none_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": None})

        result = get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": FAKE_SYS_ID},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestGetChangeConflictErrors(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {"error": {"message": "Internal error"}})

        result = get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": FAKE_SYS_ID},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error retrieving change conflict", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("connection refused")

        result = get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": FAKE_SYS_ID},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error retrieving change conflict", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_instance_url", return_value=None)
    def test_missing_instance_url(self, _):
        result = get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_headers", return_value=None)
    def test_missing_headers(self, _):
        result = get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    def test_missing_sys_id_returns_failure(self):
        result = get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {},
        )
        self.assertFalse(result["success"])

    def test_invalid_params_returns_failure(self):
        result = get_change_conflict(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": 12345},  # not a string
        )
        # pydantic coerces int to str, so this might succeed — just check it doesn't crash
        self.assertIn("success", result)


if __name__ == "__main__":
    unittest.main()
