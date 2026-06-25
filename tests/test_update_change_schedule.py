"""Tests for update_change_schedule in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import update_change_schedule
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
PARENT_SYS_ID = "b" * 32

FAKE_SCHEDULE = {
    "sys_id": FAKE_SYS_ID,
    "name": "Change Window - Saturday Night",
    "description": "Updated description",
    "type": {"display_value": "Change Window", "value": "change_window"},
    "time_zone": "US/Pacific",
    "active": "true",
    "parent": {"display_value": "Global Change Windows", "value": PARENT_SYS_ID},
    "sys_created_by": "admin",
    "sys_created_on": "2026-06-01 00:00:00",
    "sys_updated_on": "2026-06-25 00:00:00",
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


def _make_response(status_code, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestUpdateChangeScheduleSuccess(unittest.TestCase):
    """Happy-path tests."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_by_sys_id_single_field(self, mock_req):
        """Update name only when schedule_id is a sys_id."""
        mock_req.side_effect = [
            # resolver: 32-char hex → returned as-is (no HTTP call)
            _make_response(200, {"result": FAKE_SCHEDULE}),
        ]
        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "name": "New Name"},
        )
        self.assertTrue(result["success"])
        self.assertIn("schedule", result)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_by_name_resolver(self, mock_req):
        """schedule_id provided as name → resolver GET then PATCH."""
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        patch_resp = _make_response(200, {"result": FAKE_SCHEDULE})
        mock_req.side_effect = [resolve_resp, patch_resp]

        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": "Change Window - Saturday Night", "name": "New Name"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(mock_req.call_count, 2)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_all_optional_fields(self, mock_req):
        """All optional fields supplied (no parent)."""
        mock_req.side_effect = [
            _make_response(200, {"result": FAKE_SCHEDULE}),
        ]
        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {
                "schedule_id": FAKE_SYS_ID,
                "name": "Updated Name",
                "schedule_type": "holiday_schedule",
                "time_zone": "US/Pacific",
                "active": False,
                "description": "Updated description",
            },
        )
        self.assertTrue(result["success"])
        called_body = mock_req.call_args[1]["json"]
        self.assertEqual(called_body["name"], "Updated Name")
        self.assertEqual(called_body["type"], "holiday_schedule")
        self.assertEqual(called_body["time_zone"], "US/Pacific")
        self.assertEqual(called_body["active"], "false")
        self.assertEqual(called_body["description"], "Updated description")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_active_true_serialised_as_string(self, mock_req):
        """active=True must be sent as the string 'true'."""
        mock_req.side_effect = [_make_response(200, {"result": FAKE_SCHEDULE})]
        update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "active": True},
        )
        called_body = mock_req.call_args[1]["json"]
        self.assertEqual(called_body["active"], "true")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_active_false_serialised_as_string(self, mock_req):
        """active=False must be sent as the string 'false'."""
        mock_req.side_effect = [_make_response(200, {"result": FAKE_SCHEDULE})]
        update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "active": False},
        )
        called_body = mock_req.call_args[1]["json"]
        self.assertEqual(called_body["active"], "false")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_with_parent_sys_id(self, mock_req):
        """Parent provided as sys_id — resolver returns it directly, 1 PATCH call."""
        mock_req.side_effect = [_make_response(200, {"result": FAKE_SCHEDULE})]
        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "parent": PARENT_SYS_ID},
        )
        self.assertTrue(result["success"])
        called_body = mock_req.call_args[1]["json"]
        self.assertEqual(called_body["parent"], PARENT_SYS_ID)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_with_parent_name(self, mock_req):
        """Parent as name → resolver GET + PATCH (schedule resolver + parent resolver + PATCH)."""
        parent_resolve = _make_response(200, {"result": [{"sys_id": PARENT_SYS_ID}]})
        patch_resp = _make_response(200, {"result": FAKE_SCHEDULE})
        mock_req.side_effect = [parent_resolve, patch_resp]

        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "parent": "Global Change Windows"},
        )
        self.assertTrue(result["success"])
        called_body = mock_req.call_args[1]["json"]
        self.assertEqual(called_body["parent"], PARENT_SYS_ID)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_message_contains_schedule_id(self, mock_req):
        """Success message should include the schedule_id."""
        mock_req.side_effect = [_make_response(200, {"result": FAKE_SCHEDULE})]
        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "name": "Updated"},
        )
        self.assertIn(FAKE_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_fields_normalised(self, mock_req):
        """_format_change_schedule should flatten type and parent dicts."""
        mock_req.side_effect = [_make_response(200, {"result": FAKE_SCHEDULE})]
        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "name": "Updated"},
        )
        sched = result["schedule"]
        self.assertEqual(sched["type"], "Change Window")
        self.assertEqual(sched["parent"], "Global Change Windows")
        self.assertEqual(sched["time_zone"], "US/Pacific")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_content_type_header_set(self, mock_req):
        """Content-Type: application/json must be set for PATCH."""
        mock_req.side_effect = [_make_response(200, {"result": FAKE_SCHEDULE})]
        update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "name": "Updated"},
        )
        sent_headers = mock_req.call_args[1]["headers"]
        self.assertEqual(sent_headers.get("Content-Type"), "application/json")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_query_params_include_display_value(self, mock_req):
        """PATCH request should include sysparm_display_value=true."""
        mock_req.side_effect = [_make_response(200, {"result": FAKE_SCHEDULE})]
        update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "name": "Updated"},
        )
        sent_params = mock_req.call_args[1]["params"]
        self.assertEqual(sent_params.get("sysparm_display_value"), "true")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_body_excludes_none_optional_fields(self, mock_req):
        """Optional fields not supplied should NOT appear in the PATCH body."""
        mock_req.side_effect = [_make_response(200, {"result": FAKE_SCHEDULE})]
        update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "name": "Only Name"},
        )
        called_body = mock_req.call_args[1]["json"]
        self.assertNotIn("type", called_body)
        self.assertNotIn("time_zone", called_body)
        self.assertNotIn("active", called_body)
        self.assertNotIn("parent", called_body)
        self.assertNotIn("description", called_body)


class TestUpdateChangeScheduleErrors(unittest.TestCase):
    """Error-path tests."""

    def test_missing_schedule_id_returns_failure(self):
        """schedule_id is required — validation should fail."""
        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Some Name"},
        )
        self.assertFalse(result["success"])

    def test_empty_body_guard(self):
        """No optional fields → should fail before making any HTTP request."""
        with patch("servicenow_mcp.tools.change_tools._make_request") as mock_req:
            mock_req.return_value = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
            result = update_change_schedule(
                _make_auth_manager(),
                _make_config(),
                {"schedule_id": FAKE_SYS_ID},
            )
        self.assertFalse(result["success"])
        self.assertIn("No fields provided", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_not_found_by_name(self, mock_req):
        """If name resolution returns empty, tool should fail."""
        mock_req.return_value = _make_response(200, {"result": []})
        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": "Nonexistent Schedule", "name": "New Name"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Nonexistent Schedule", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_on_patch(self, mock_req):
        """A 404 from PATCH should return success=False with clear message."""
        mock_req.side_effect = [_make_response(404, {})]
        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "name": "Updated"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_on_patch(self, mock_req):
        """A 500 from PATCH should return success=False."""
        mock_req.side_effect = [_make_response(500, {})]
        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "name": "Updated"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating change schedule", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_on_patch(self, mock_req):
        """Network failure should return success=False."""
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "name": "Updated"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating change schedule", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_parent_not_found_returns_failure(self, mock_req):
        """If parent name resolution returns empty, tool must fail."""
        mock_req.return_value = _make_response(200, {"result": []})
        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID, "parent": "Nonexistent Parent"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Parent schedule not found", result["message"])

    def test_no_instance_url(self):
        """If instance_url is None, return failure immediately."""
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = None
        server_config = _make_config()
        server_config.instance_url = None
        result = update_change_schedule(
            auth_manager,
            server_config,
            {"schedule_id": FAKE_SYS_ID, "name": "Test"},
        )
        self.assertFalse(result["success"])


class TestUpdateChangeScheduleWrappedParams(unittest.TestCase):
    """Tests for the params-dict-unwrap variant."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_params_nested_under_params_key(self, mock_req):
        """Params may arrive wrapped under a 'params' key."""
        mock_req.side_effect = [_make_response(200, {"result": FAKE_SCHEDULE})]
        result = update_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"params": {"schedule_id": FAKE_SYS_ID, "name": "Updated"}},
        )
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
