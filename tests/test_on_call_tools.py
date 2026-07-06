"""Tests for on_call_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.on_call_tools import (
    _format_on_call_rotation,
    list_on_call_rotations,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
FAKE_GROUP_SYS_ID = "b" * 32
FAKE_MANAGER_SYS_ID = "c" * 32
FAKE_SCHEDULE_SYS_ID = "d" * 32

FAKE_ROTATION = {
    "sys_id": FAKE_SYS_ID,
    "name": "Network Team On-call",
    "active": "true",
    "description": "Primary on-call rotation for the network ops team",
    "group": {"display_value": "Network Operations", "value": FAKE_GROUP_SYS_ID},
    "manager": {"display_value": "Jane Doe", "value": FAKE_MANAGER_SYS_ID},
    "schedule": {"display_value": "Business Hours", "value": FAKE_SCHEDULE_SYS_ID},
    "escalation": {"display_value": "Escalation Policy A", "value": "e" * 32},
    "type": "primary",
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-06-01 00:00:00",
    "sys_created_by": "admin",
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
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=resp
        )
    return resp


# ---------------------------------------------------------------------------
# _format_on_call_rotation
# ---------------------------------------------------------------------------

class TestFormatOnCallRotation(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_on_call_rotation(FAKE_ROTATION)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["name"], "Network Team On-call")
        self.assertEqual(result["active"], "true")
        self.assertEqual(result["description"], "Primary on-call rotation for the network ops team")
        self.assertEqual(result["type"], "primary")
        self.assertEqual(result["created_on"], "2026-01-01 00:00:00")
        self.assertEqual(result["updated_on"], "2026-06-01 00:00:00")
        self.assertEqual(result["created_by"], "admin")

    def test_normalises_group_reference(self):
        result = _format_on_call_rotation(FAKE_ROTATION)
        self.assertEqual(result["group"], "Network Operations")

    def test_normalises_manager_reference(self):
        result = _format_on_call_rotation(FAKE_ROTATION)
        self.assertEqual(result["manager"], "Jane Doe")

    def test_normalises_schedule_reference(self):
        result = _format_on_call_rotation(FAKE_ROTATION)
        self.assertEqual(result["schedule"], "Business Hours")

    def test_normalises_escalation_reference(self):
        result = _format_on_call_rotation(FAKE_ROTATION)
        self.assertEqual(result["escalation"], "Escalation Policy A")

    def test_handles_string_fields(self):
        rotation = {**FAKE_ROTATION, "group": "plain_group", "manager": "plain_manager"}
        result = _format_on_call_rotation(rotation)
        self.assertEqual(result["group"], "plain_group")
        self.assertEqual(result["manager"], "plain_manager")

    def test_handles_value_fallback(self):
        rotation = {**FAKE_ROTATION, "group": {"value": FAKE_GROUP_SYS_ID}}
        result = _format_on_call_rotation(rotation)
        self.assertEqual(result["group"], FAKE_GROUP_SYS_ID)

    def test_handles_missing_fields(self):
        result = _format_on_call_rotation({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["name"])
        self.assertIsNone(result["active"])
        self.assertIsNone(result["group"])
        self.assertIsNone(result["manager"])
        self.assertIsNone(result["schedule"])
        self.assertIsNone(result["escalation"])


# ---------------------------------------------------------------------------
# list_on_call_rotations
# ---------------------------------------------------------------------------

class TestListOnCallRotations(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_returns_rotations_on_success(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_ROTATION]})
        result = list_on_call_rotations(self.auth, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["rotations"]), 1)
        self.assertEqual(result["rotations"][0]["name"], "Network Team On-call")
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_empty_result_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_on_call_rotations(self.auth, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(result["rotations"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_filter_by_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_ROTATION]})
        list_on_call_rotations(self.auth, self.config, {"name": "Network"})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("nameLIKENetwork", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_filter_active_true(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {"active": True})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=true", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_filter_active_false(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {"active": False})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=false", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_filter_by_group_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {"group": "Network Ops"})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("group.nameLIKENetwork Ops", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_filter_by_group_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {"group": FAKE_GROUP_SYS_ID})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn(f"group={FAKE_GROUP_SYS_ID}", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_pagination_params(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {"limit": 5, "offset": 10})
        call_params = mock_req.call_args[1]["params"]
        self.assertEqual(call_params["sysparm_limit"], 5)
        self.assertEqual(call_params["sysparm_offset"], 10)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_has_more_when_full_page(self, mock_req):
        rotations = [dict(FAKE_ROTATION, sys_id=str(i) * 32) for i in range(20)]
        mock_req.return_value = _make_response(200, {"result": rotations})
        result = list_on_call_rotations(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 20)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = list_on_call_rotations(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing on-call rotations", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_on_call_rotations(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing on-call rotations", result["message"])

    def test_invalid_params_returns_failure(self):
        result = list_on_call_rotations(self.auth, self.config, {"limit": "not-an-int"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.on_call_tools._get_instance_url")
    def test_missing_instance_url_returns_failure(self, mock_url):
        mock_url.return_value = None
        result = list_on_call_rotations(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._get_headers")
    def test_missing_headers_returns_failure(self, mock_headers):
        mock_headers.return_value = None
        result = list_on_call_rotations(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_multiple_filters_combined(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(
            self.auth, self.config,
            {"name": "Primary", "active": True, "group": "NOC"},
        )
        call_params = mock_req.call_args[1]["params"]
        query = call_params.get("sysparm_query", "")
        self.assertIn("nameLIKEPrimary", query)
        self.assertIn("active=true", query)
        self.assertIn("group.nameLIKENOC", query)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_default_order_by_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {})
        call_params = mock_req.call_args[1]["params"]
        self.assertEqual(call_params.get("sysparm_orderby"), "name")

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_url_targets_cmn_rota(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {})
        url = mock_req.call_args[0][1]
        self.assertIn("cmn_rota", url)


if __name__ == "__main__":
    unittest.main()
