"""Tests for create_change_schedule in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import create_change_schedule
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
PARENT_SYS_ID = "b" * 32

FAKE_CREATED_SCHEDULE = {
    "sys_id": FAKE_SYS_ID,
    "name": "Change Window - Saturday Night",
    "description": "Weekend night change window",
    "type": {"display_value": "Change Window", "value": "change_window"},
    "time_zone": "US/Eastern",
    "active": "true",
    "parent": {"display_value": "Global Change Windows", "value": PARENT_SYS_ID},
    "sys_created_by": "admin",
    "sys_created_on": "2026-06-24 00:00:00",
    "sys_updated_on": "2026-06-24 00:00:00",
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


class TestCreateChangeScheduleSuccess(unittest.TestCase):
    """Happy-path tests."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_create_minimal(self, mock_req):
        """Only name provided — no optional fields."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SCHEDULE})
        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Change Window - Saturday Night"},
        )
        self.assertTrue(result["success"])
        self.assertIn("schedule", result)
        self.assertEqual(result["schedule"]["name"], "Change Window - Saturday Night")
        self.assertEqual(result["schedule"]["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_create_with_all_fields_no_parent(self, mock_req):
        """All optional fields except parent."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SCHEDULE})
        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {
                "name": "Change Window - Saturday Night",
                "schedule_type": "change_window",
                "time_zone": "US/Eastern",
                "active": True,
                "description": "Weekend night change window",
            },
        )
        self.assertTrue(result["success"])
        self.assertIn("Change Window - Saturday Night", result["message"])
        called_body = mock_req.call_args[1]["json"]
        self.assertEqual(called_body["type"], "change_window")
        self.assertEqual(called_body["time_zone"], "US/Eastern")
        self.assertEqual(called_body["active"], "true")
        self.assertEqual(called_body["description"], "Weekend night change window")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_create_inactive_schedule(self, mock_req):
        """active=False should send 'false' string in body."""
        inactive = {**FAKE_CREATED_SCHEDULE, "active": "false"}
        mock_req.return_value = _make_response(201, {"result": inactive})
        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Inactive Schedule", "active": False},
        )
        self.assertTrue(result["success"])
        called_body = mock_req.call_args[1]["json"]
        self.assertEqual(called_body["active"], "false")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_create_with_parent_sys_id(self, mock_req):
        """Parent provided as sys_id — no resolver lookup needed."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SCHEDULE})
        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Child Schedule", "parent": PARENT_SYS_ID},
        )
        self.assertTrue(result["success"])
        # Only 1 request: the POST (resolver sees 32-char hex, returns it immediately)
        self.assertEqual(mock_req.call_count, 1)
        called_body = mock_req.call_args[1]["json"]
        self.assertEqual(called_body["parent"], PARENT_SYS_ID)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_create_with_parent_name(self, mock_req):
        """Parent provided as name — resolver GET then POST."""
        resolve_resp = _make_response(200, {"result": [{"sys_id": PARENT_SYS_ID}]})
        create_resp = _make_response(201, {"result": FAKE_CREATED_SCHEDULE})
        mock_req.side_effect = [resolve_resp, create_resp]

        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Child Schedule", "parent": "Global Change Windows"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(mock_req.call_count, 2)
        called_body = mock_req.call_args[1]["json"]
        self.assertEqual(called_body["parent"], PARENT_SYS_ID)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_message_contains_schedule_name(self, mock_req):
        """Response message should include the new schedule's name."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SCHEDULE})
        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Change Window - Saturday Night"},
        )
        self.assertIn("Change Window - Saturday Night", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_fields_normalised(self, mock_req):
        """_format_change_schedule should flatten type and parent dicts."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SCHEDULE})
        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Change Window - Saturday Night"},
        )
        sched = result["schedule"]
        self.assertEqual(sched["type"], "Change Window")
        self.assertEqual(sched["parent"], "Global Change Windows")
        self.assertEqual(sched["time_zone"], "US/Eastern")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_content_type_header_set(self, mock_req):
        """Content-Type: application/json must be set for POST."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SCHEDULE})
        create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Test Schedule"},
        )
        sent_headers = mock_req.call_args[1]["headers"]
        self.assertEqual(sent_headers.get("Content-Type"), "application/json")


class TestCreateChangeScheduleErrors(unittest.TestCase):
    """Error-path tests."""

    def test_missing_name_returns_failure(self):
        """name is required — validation should fail."""
        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_parent_not_found_returns_failure(self, mock_req):
        """If parent name resolution returns empty, tool must fail."""
        mock_req.return_value = _make_response(200, {"result": []})
        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Child Schedule", "parent": "Nonexistent Parent"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Nonexistent Parent", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_on_post(self, mock_req):
        """A 500 from the table API should return success=False."""
        mock_req.return_value = _make_response(500, {})
        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Failing Schedule"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error creating change schedule", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_on_post(self, mock_req):
        """Network failure should return success=False with message."""
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Failing Schedule"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error creating change schedule", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_parent_resolver_connection_error(self, mock_req):
        """If resolver raises ConnectionError, parent lookup returns None → failure."""
        mock_req.side_effect = requests.exceptions.ConnectionError("net error")
        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Child Schedule", "parent": "Some Parent"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Parent schedule not found", result["message"])

    def test_no_instance_url(self):
        """If auth_manager has no instance_url method, return failure."""
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = None
        server_config = _make_config()
        server_config.instance_url = None
        result = create_change_schedule(
            auth_manager,
            server_config,
            {"name": "Test"},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_body_excludes_none_fields(self, mock_req):
        """Optional fields with None should NOT appear in the POST body."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SCHEDULE})
        create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Minimal Schedule"},
        )
        called_body = mock_req.call_args[1]["json"]
        self.assertNotIn("type", called_body)
        self.assertNotIn("time_zone", called_body)
        self.assertNotIn("parent", called_body)
        self.assertNotIn("description", called_body)


class TestCreateChangeScheduleWrappedParams(unittest.TestCase):
    """Tests for the params-dict-unwrap variants."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_params_nested_under_params_key(self, mock_req):
        """Params may arrive wrapped under a 'params' key."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SCHEDULE})
        result = create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"params": {"name": "Change Window - Saturday Night"}},
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_type_not_set_omits_type_field(self, mock_req):
        """When schedule_type is not provided, 'type' should not be in POST body."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SCHEDULE})
        create_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"name": "Generic Schedule"},
        )
        called_body = mock_req.call_args[1]["json"]
        self.assertNotIn("type", called_body)


if __name__ == "__main__":
    unittest.main()
