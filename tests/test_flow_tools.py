"""Tests for flow_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.flow_tools import (
    _format_flow,
    _resolve_flow_sys_id,
    get_flow,
    list_flows,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
FAKE_SCOPE_SYS_ID = "b" * 32

FAKE_FLOW_RECORD = {
    "sys_id": FAKE_SYS_ID,
    "name": "Incident Auto-Resolve",
    "description": "Automatically resolves stale incidents",
    "active": "true",
    "status": "published",
    "category": "flow",
    "sys_scope": {"display_value": "Global", "value": FAKE_SCOPE_SYS_ID},
    "trigger_type": "record_inserted",
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-06-01 00:00:00",
    "sys_created_by": "admin",
    "sys_updated_by": "admin",
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
# _format_flow
# ---------------------------------------------------------------------------

class TestFormatFlow(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_flow(FAKE_FLOW_RECORD)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["name"], "Incident Auto-Resolve")
        self.assertEqual(result["description"], "Automatically resolves stale incidents")
        self.assertEqual(result["active"], "true")
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["category"], "flow")
        self.assertEqual(result["scope"], "Global")
        self.assertEqual(result["trigger_type"], "record_inserted")
        self.assertEqual(result["created_on"], "2026-01-01 00:00:00")
        self.assertEqual(result["updated_on"], "2026-06-01 00:00:00")
        self.assertEqual(result["created_by"], "admin")
        self.assertEqual(result["updated_by"], "admin")

    def test_scope_as_string(self):
        record = {**FAKE_FLOW_RECORD, "sys_scope": "global"}
        result = _format_flow(record)
        self.assertEqual(result["scope"], "global")

    def test_scope_dict_fallback_to_value(self):
        record = {**FAKE_FLOW_RECORD, "sys_scope": {"value": FAKE_SCOPE_SYS_ID}}
        result = _format_flow(record)
        self.assertEqual(result["scope"], FAKE_SCOPE_SYS_ID)

    def test_missing_fields_default_none(self):
        result = _format_flow({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["name"])
        self.assertIsNone(result["scope"])


# ---------------------------------------------------------------------------
# _resolve_flow_sys_id
# ---------------------------------------------------------------------------

class TestResolveFlowSysId(unittest.TestCase):
    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_passes_through_32char_hex(self, mock_req):
        result = _resolve_flow_sys_id("https://dev.service-now.com", {}, FAKE_SYS_ID)
        self.assertEqual(result, FAKE_SYS_ID)
        mock_req.assert_not_called()

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_resolves_by_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        result = _resolve_flow_sys_id("https://dev.service-now.com", {}, "My Flow")
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_returns_none_when_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = _resolve_flow_sys_id("https://dev.service-now.com", {}, "Unknown")
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_returns_none_on_request_exception(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = _resolve_flow_sys_id("https://dev.service-now.com", {}, "My Flow")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# list_flows
# ---------------------------------------------------------------------------

class TestListFlows(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.cfg = _make_config()

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_returns_flows_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_FLOW_RECORD]})
        result = list_flows(self.auth, self.cfg, {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["flows"]), 1)
        self.assertEqual(result["flows"][0]["name"], "Incident Auto-Resolve")
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_flows(self.auth, self.cfg, {})
        self.assertTrue(result["success"])
        self.assertEqual(result["flows"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_name_filter_applied(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flows(self.auth, self.cfg, {"name": "Incident"})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("nameLIKEIncident", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_active_filter_true(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flows(self.auth, self.cfg, {"active": True})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=true", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_active_filter_false(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flows(self.auth, self.cfg, {"active": False})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=false", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_status_filter_applied(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flows(self.auth, self.cfg, {"status": "published"})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("status=published", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_category_filter_applied(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flows(self.auth, self.cfg, {"category": "subflow"})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("category=subflow", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_scope_filter_applied(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flows(self.auth, self.cfg, {"scope": "Global"})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("sys_scope.nameLIKEGlobal", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_pagination_params(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flows(self.auth, self.cfg, {"limit": 5, "offset": 10})
        call_params = mock_req.call_args[1]["params"]
        self.assertEqual(call_params["sysparm_limit"], 5)
        self.assertEqual(call_params["sysparm_offset"], 10)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_has_more_pagination(self, mock_req):
        flows = [FAKE_FLOW_RECORD] * 5
        mock_req.return_value = _make_response(200, {"result": flows})
        result = list_flows(self.auth, self.cfg, {"limit": 5, "offset": 0})
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 5)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_network_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_flows(self.auth, self.cfg, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing flows", result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_multiple_filters_combined(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flows(self.auth, self.cfg, {"name": "Auto", "active": True, "status": "published"})
        call_params = mock_req.call_args[1]["params"]
        query = call_params.get("sysparm_query", "")
        self.assertIn("nameLIKEAuto", query)
        self.assertIn("active=true", query)
        self.assertIn("status=published", query)


# ---------------------------------------------------------------------------
# get_flow
# ---------------------------------------------------------------------------

class TestGetFlow(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.cfg = _make_config()

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_get_by_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_FLOW_RECORD})
        result = get_flow(self.auth, self.cfg, {"flow_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["flow"]["name"], "Incident Auto-Resolve")

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_get_by_name_resolves_sys_id(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        get_resp = _make_response(200, {"result": FAKE_FLOW_RECORD})
        mock_req.side_effect = [resolve_resp, get_resp]
        result = get_flow(self.auth, self.cfg, {"flow_id": "Incident Auto-Resolve"})
        self.assertTrue(result["success"])
        self.assertEqual(result["flow"]["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_flow_not_found_by_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = get_flow(self.auth, self.cfg, {"flow_id": "Nonexistent Flow"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_404_response(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        result = get_flow(self.auth, self.cfg, {"flow_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_empty_result_body(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_flow(self.auth, self.cfg, {"flow_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_network_error(self, mock_req):
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]}),
            requests.exceptions.ConnectionError("timeout"),
        ]
        result = get_flow(self.auth, self.cfg, {"flow_id": "My Flow"})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving flow", result["message"])

    def test_missing_flow_id(self):
        result = get_flow(self.auth, self.cfg, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_scope_normalised_from_dict(self, mock_req):
        record = {**FAKE_FLOW_RECORD, "sys_scope": {"display_value": "ITSM", "value": FAKE_SCOPE_SYS_ID}}
        mock_req.return_value = _make_response(200, {"result": record})
        result = get_flow(self.auth, self.cfg, {"flow_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["flow"]["scope"], "ITSM")


if __name__ == "__main__":
    unittest.main()
