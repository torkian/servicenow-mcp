"""Tests for flow_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.flow_tools import (
    _format_execution,
    _format_flow,
    _format_flow_log,
    _resolve_flow_sys_id,
    cancel_flow_execution,
    get_flow,
    get_flow_execution,
    list_flow_executions,
    list_flow_logs,
    list_flows,
    trigger_flow,
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


FAKE_EXECUTION_SYS_ID = "e" * 32
FAKE_EXECUTION_RECORD = {
    "sys_id": FAKE_EXECUTION_SYS_ID,
    "name": "Incident Auto-Resolve",
    "state": "complete",
    "flow": {"display_value": "Incident Auto-Resolve", "value": FAKE_SYS_ID},
    "started_on": "2026-07-30 08:00:00",
    "ended_on": "2026-07-30 08:00:05",
    "error": "",
    "run_as": {"display_value": "admin", "value": "a" * 32},
}


# ---------------------------------------------------------------------------
# _format_execution
# ---------------------------------------------------------------------------

class TestFormatExecution(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_execution(FAKE_EXECUTION_RECORD)
        self.assertEqual(result["sys_id"], FAKE_EXECUTION_SYS_ID)
        self.assertEqual(result["name"], "Incident Auto-Resolve")
        self.assertEqual(result["state"], "complete")
        self.assertEqual(result["flow"], "Incident Auto-Resolve")
        self.assertEqual(result["started_on"], "2026-07-30 08:00:00")
        self.assertEqual(result["ended_on"], "2026-07-30 08:00:05")
        self.assertEqual(result["error"], "")
        self.assertEqual(result["run_as"], "admin")

    def test_flow_as_string(self):
        record = {**FAKE_EXECUTION_RECORD, "flow": "some-sys-id"}
        result = _format_execution(record)
        self.assertEqual(result["flow"], "some-sys-id")

    def test_run_as_fallback_to_value(self):
        record = {**FAKE_EXECUTION_RECORD, "run_as": {"value": "u" * 32}}
        result = _format_execution(record)
        self.assertEqual(result["run_as"], "u" * 32)

    def test_missing_fields_default_none(self):
        result = _format_execution({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["state"])
        self.assertIsNone(result["flow"])


# ---------------------------------------------------------------------------
# trigger_flow
# ---------------------------------------------------------------------------

class TestTriggerFlow(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.cfg = _make_config()

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_trigger_by_sys_id_success(self, mock_req):
        mock_req.return_value = _make_response(
            200,
            {"result": {"executionId": FAKE_EXECUTION_SYS_ID, "status": "started"}},
        )
        result = trigger_flow(self.auth, self.cfg, {"flow_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["execution_id"], FAKE_EXECUTION_SYS_ID)
        self.assertEqual(result["status"], "started")

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_trigger_by_name_resolves_sys_id(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        exec_resp = _make_response(
            200,
            {"result": {"executionId": FAKE_EXECUTION_SYS_ID, "status": "started"}},
        )
        mock_req.side_effect = [resolve_resp, exec_resp]
        result = trigger_flow(self.auth, self.cfg, {"flow_id": "Incident Auto-Resolve"})
        self.assertTrue(result["success"])
        self.assertEqual(result["execution_id"], FAKE_EXECUTION_SYS_ID)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_trigger_with_inputs(self, mock_req):
        mock_req.return_value = _make_response(
            200,
            {"result": {"executionId": FAKE_EXECUTION_SYS_ID, "status": "started"}},
        )
        result = trigger_flow(
            self.auth,
            self.cfg,
            {"flow_id": FAKE_SYS_ID, "inputs": {"incident_id": "INC001"}},
        )
        self.assertTrue(result["success"])
        call_json = mock_req.call_args[1].get("json", {})
        self.assertEqual(call_json.get("inputs"), {"incident_id": "INC001"})

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_trigger_without_inputs_sends_empty_body(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": {"executionId": FAKE_EXECUTION_SYS_ID, "status": "started"}}
        )
        trigger_flow(self.auth, self.cfg, {"flow_id": FAKE_SYS_ID})
        call_json = mock_req.call_args[1].get("json", {})
        self.assertNotIn("inputs", call_json)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_flow_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = trigger_flow(self.auth, self.cfg, {"flow_id": "Unknown Flow"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_404_response(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        result = trigger_flow(self.auth, self.cfg, {"flow_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_network_error(self, mock_req):
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]}),
            requests.exceptions.ConnectionError("timeout"),
        ]
        result = trigger_flow(self.auth, self.cfg, {"flow_id": "Incident Auto-Resolve"})
        self.assertFalse(result["success"])
        self.assertIn("Error triggering flow", result["message"])

    def test_missing_flow_id(self):
        result = trigger_flow(self.auth, self.cfg, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_result_with_sys_id_field(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": {"sys_id": FAKE_EXECUTION_SYS_ID}}
        )
        result = trigger_flow(self.auth, self.cfg, {"flow_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["execution_id"], FAKE_EXECUTION_SYS_ID)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_status_defaults_to_started_when_absent(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = trigger_flow(self.auth, self.cfg, {"flow_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "started")


# ---------------------------------------------------------------------------
# list_flow_executions
# ---------------------------------------------------------------------------

class TestListFlowExecutions(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.cfg = _make_config()

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_returns_executions_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_EXECUTION_RECORD]})
        result = list_flow_executions(self.auth, self.cfg, {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["executions"]), 1)
        self.assertEqual(result["executions"][0]["state"], "complete")
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_flow_executions(self.auth, self.cfg, {})
        self.assertTrue(result["success"])
        self.assertEqual(result["executions"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_flow_id_filter_resolves_sys_id(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        list_resp = _make_response(200, {"result": []})
        mock_req.side_effect = [resolve_resp, list_resp]
        result = list_flow_executions(
            self.auth, self.cfg, {"flow_id": "Incident Auto-Resolve"}
        )
        self.assertTrue(result["success"])
        list_call_params = mock_req.call_args_list[1][1]["params"]
        self.assertIn(f"flow={FAKE_SYS_ID}", list_call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_flow_id_as_sys_id_passthrough(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flow_executions(self.auth, self.cfg, {"flow_id": FAKE_SYS_ID})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn(f"flow={FAKE_SYS_ID}", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_state_filter_applied(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flow_executions(self.auth, self.cfg, {"state": "error"})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("state=error", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_started_after_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flow_executions(
            self.auth, self.cfg, {"started_after": "2026-07-01 00:00:00"}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("started_on>=2026-07-01 00:00:00", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_started_before_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flow_executions(
            self.auth, self.cfg, {"started_before": "2026-07-30 23:59:59"}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("started_on<=2026-07-30 23:59:59", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_pagination_params(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flow_executions(self.auth, self.cfg, {"limit": 5, "offset": 10})
        call_params = mock_req.call_args[1]["params"]
        self.assertEqual(call_params["sysparm_limit"], 5)
        self.assertEqual(call_params["sysparm_offset"], 10)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_has_more_pagination(self, mock_req):
        records = [FAKE_EXECUTION_RECORD] * 5
        mock_req.return_value = _make_response(200, {"result": records})
        result = list_flow_executions(self.auth, self.cfg, {"limit": 5, "offset": 0})
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 5)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_unknown_flow_id_returns_error(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_flow_executions(self.auth, self.cfg, {"flow_id": "Unknown Flow"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_network_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_flow_executions(self.auth, self.cfg, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing flow executions", result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_multiple_filters_combined(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flow_executions(
            self.auth,
            self.cfg,
            {
                "flow_id": FAKE_SYS_ID,
                "state": "running",
                "started_after": "2026-07-01 00:00:00",
            },
        )
        call_params = mock_req.call_args[1]["params"]
        query = call_params.get("sysparm_query", "")
        self.assertIn(f"flow={FAKE_SYS_ID}", query)
        self.assertIn("state=running", query)
        self.assertIn("started_on>=2026-07-01 00:00:00", query)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# get_flow_execution
# ---------------------------------------------------------------------------

FAKE_EXECUTION_DETAIL_RECORD = {
    "sys_id": FAKE_EXECUTION_SYS_ID,
    "name": "Incident Auto-Resolve",
    "state": "complete",
    "flow": {"display_value": "Incident Auto-Resolve", "value": FAKE_SYS_ID},
    "started_on": "2026-07-30 08:00:00",
    "ended_on": "2026-07-30 08:00:05",
    "error": "",
    "run_as": {"display_value": "admin", "value": "a" * 32},
    "trigger_type": "manual",
    "trigger": "Now Platform",
    "context_parameters": '{"assignment_group": "IT"}',
    "sys_created_on": "2026-07-30 07:59:55",
    "sys_updated_on": "2026-07-30 08:00:06",
}


class TestGetFlowExecution(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.cfg = _make_config()

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_success(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": FAKE_EXECUTION_DETAIL_RECORD}
        )
        result = get_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertTrue(result["success"])
        ex = result["execution"]
        self.assertEqual(ex["sys_id"], FAKE_EXECUTION_SYS_ID)
        self.assertEqual(ex["name"], "Incident Auto-Resolve")
        self.assertEqual(ex["state"], "complete")
        self.assertEqual(ex["flow"], "Incident Auto-Resolve")
        self.assertEqual(ex["started_on"], "2026-07-30 08:00:00")
        self.assertEqual(ex["ended_on"], "2026-07-30 08:00:05")
        self.assertEqual(ex["error"], "")
        self.assertEqual(ex["run_as"], "admin")
        self.assertEqual(ex["trigger_type"], "manual")
        self.assertEqual(ex["trigger"], "Now Platform")
        self.assertEqual(ex["context_parameters"], '{"assignment_group": "IT"}')
        self.assertEqual(ex["created_on"], "2026-07-30 07:59:55")
        self.assertEqual(ex["updated_on"], "2026-07-30 08:00:06")

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_hits_correct_url(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": FAKE_EXECUTION_DETAIL_RECORD}
        )
        get_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        call_url = mock_req.call_args[0][1]
        self.assertIn(f"/sys_flow_context/{FAKE_EXECUTION_SYS_ID}", call_url)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_display_value_param_set(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": FAKE_EXECUTION_DETAIL_RECORD}
        )
        get_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertEqual(call_params["sysparm_display_value"], "true")
        self.assertEqual(call_params["sysparm_exclude_reference_link"], "true")

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_404_returns_not_found(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        mock_req.return_value.raise_for_status = MagicMock()
        result = get_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertIn(FAKE_EXECUTION_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_empty_result_returns_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_missing_execution_id_returns_error(self):
        result = get_flow_execution(self.auth, self.cfg, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_network_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = get_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving flow execution", result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_run_as_as_string(self, mock_req):
        record = {**FAKE_EXECUTION_DETAIL_RECORD, "run_as": "svc_account"}
        mock_req.return_value = _make_response(200, {"result": record})
        result = get_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["execution"]["run_as"], "svc_account")

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_flow_ref_dict_fallback_to_value(self, mock_req):
        record = {
            **FAKE_EXECUTION_DETAIL_RECORD,
            "flow": {"value": FAKE_SYS_ID},
        }
        mock_req.return_value = _make_response(200, {"result": record})
        result = get_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["execution"]["flow"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_missing_optional_fields_none(self, mock_req):
        minimal = {
            "sys_id": FAKE_EXECUTION_SYS_ID,
            "state": "running",
        }
        mock_req.return_value = _make_response(200, {"result": minimal})
        result = get_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertTrue(result["success"])
        ex = result["execution"]
        self.assertIsNone(ex["name"])
        self.assertIsNone(ex["trigger_type"])
        self.assertIsNone(ex["trigger"])
        self.assertIsNone(ex["context_parameters"])
        self.assertIsNone(ex["created_on"])
        self.assertIsNone(ex["updated_on"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_error_state_returned(self, mock_req):
        record = {
            **FAKE_EXECUTION_DETAIL_RECORD,
            "state": "error",
            "error": "Script failed at step 3",
        }
        mock_req.return_value = _make_response(200, {"result": record})
        result = get_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["execution"]["state"], "error")
        self.assertEqual(result["execution"]["error"], "Script failed at step 3")

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_http_500_returns_error(self, mock_req):
        mock_req.return_value = _make_response(500, {"error": {"message": "Server error"}})
        result = get_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving flow execution", result["message"])


# ---------------------------------------------------------------------------
# cancel_flow_execution
# ---------------------------------------------------------------------------


class TestCancelFlowExecution(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.cfg = _make_config()

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_cancel_success(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": {"sys_id": FAKE_EXECUTION_SYS_ID, "state": "cancelled"}}
        )
        result = cancel_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["execution_id"], FAKE_EXECUTION_SYS_ID)
        self.assertIn("cancelled", result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_patches_correct_url(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        cancel_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        call_method = mock_req.call_args[0][0]
        call_url = mock_req.call_args[0][1]
        self.assertEqual(call_method, "PATCH")
        self.assertIn(f"/sys_flow_context/{FAKE_EXECUTION_SYS_ID}", call_url)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_state_cancelled_in_body(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        cancel_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        call_json = mock_req.call_args[1].get("json", {})
        self.assertEqual(call_json.get("state"), "cancelled")

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_cancel_reason_included_as_work_notes(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        cancel_flow_execution(
            self.auth,
            self.cfg,
            {
                "execution_id": FAKE_EXECUTION_SYS_ID,
                "cancel_reason": "Duplicate trigger",
            },
        )
        call_json = mock_req.call_args[1].get("json", {})
        self.assertEqual(call_json.get("work_notes"), "Duplicate trigger")
        self.assertEqual(call_json.get("state"), "cancelled")

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_no_cancel_reason_omits_work_notes(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        cancel_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        call_json = mock_req.call_args[1].get("json", {})
        self.assertNotIn("work_notes", call_json)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_404_returns_not_found(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        mock_req.return_value.raise_for_status = MagicMock()
        result = cancel_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertIn(FAKE_EXECUTION_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_http_500_returns_error(self, mock_req):
        mock_req.return_value = _make_response(
            500, {"error": {"message": "Internal Server Error"}}
        )
        result = cancel_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error cancelling flow execution", result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_network_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = cancel_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error cancelling flow execution", result["message"])

    def test_missing_execution_id_returns_error(self):
        result = cancel_flow_execution(self.auth, self.cfg, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_success_response_contains_execution_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = cancel_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["execution_id"], FAKE_EXECUTION_SYS_ID)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_204_response_succeeds(self, mock_req):
        resp = MagicMock()
        resp.status_code = 204
        resp.json.return_value = {}
        resp.raise_for_status = MagicMock()
        mock_req.return_value = resp
        result = cancel_flow_execution(
            self.auth, self.cfg, {"execution_id": FAKE_EXECUTION_SYS_ID}
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_cancel_reason_with_newline(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        reason = "Step 1 failed\nRetrying with new inputs"
        cancel_flow_execution(
            self.auth,
            self.cfg,
            {"execution_id": FAKE_EXECUTION_SYS_ID, "cancel_reason": reason},
        )
        call_json = mock_req.call_args[1].get("json", {})
        self.assertEqual(call_json.get("work_notes"), reason)


# ---------------------------------------------------------------------------
# list_flow_logs
# ---------------------------------------------------------------------------

FAKE_FLOW_LOG_EXECUTION_ID = "c" * 32

FAKE_LOG_RECORD = {
    "sys_id": "d" * 32,
    "flow_context": {
        "display_value": "My Flow Execution",
        "value": FAKE_FLOW_LOG_EXECUTION_ID,
    },
    "message": "Activity completed successfully.",
    "level": "info",
    "sequence": "10",
    "activity": {"display_value": "Assign Ticket", "value": "e" * 32},
    "sys_created_on": "2026-08-09 10:00:00",
}


class TestFormatFlowLog(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_flow_log(FAKE_LOG_RECORD)
        self.assertEqual(result["sys_id"], "d" * 32)
        self.assertEqual(result["execution_id"], "My Flow Execution")
        self.assertEqual(result["message"], "Activity completed successfully.")
        self.assertEqual(result["level"], "info")
        self.assertEqual(result["sequence"], "10")
        self.assertEqual(result["activity"], "Assign Ticket")
        self.assertEqual(result["created_on"], "2026-08-09 10:00:00")

    def test_reference_fields_as_strings(self):
        record = dict(FAKE_LOG_RECORD)
        record["flow_context"] = FAKE_FLOW_LOG_EXECUTION_ID
        record["activity"] = "e" * 32
        result = _format_flow_log(record)
        self.assertEqual(result["execution_id"], FAKE_FLOW_LOG_EXECUTION_ID)
        self.assertEqual(result["activity"], "e" * 32)

    def test_missing_fields_return_none(self):
        result = _format_flow_log({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["message"])
        self.assertIsNone(result["level"])


class TestListFlowLogs(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.cfg = _make_config()

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_success_returns_logs(self, mock_req):
        mock_req.return_value = _make_response(
            200,
            {"result": [FAKE_LOG_RECORD, FAKE_LOG_RECORD]},
        )
        result = list_flow_logs(
            self.auth, self.cfg, {"execution_id": FAKE_FLOW_LOG_EXECUTION_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["logs"]), 2)
        self.assertEqual(result["count"], 2)
        self.assertFalse(result["has_more"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_level_filter_passed_in_query(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flow_logs(
            self.auth,
            self.cfg,
            {"execution_id": FAKE_FLOW_LOG_EXECUTION_ID, "level": "error"},
        )
        call_params = mock_req.call_args[1].get("params", {})
        self.assertIn("level=error", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_execution_id_in_query(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flow_logs(self.auth, self.cfg, {"execution_id": FAKE_FLOW_LOG_EXECUTION_ID})
        call_params = mock_req.call_args[1].get("params", {})
        self.assertIn(FAKE_FLOW_LOG_EXECUTION_ID, call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_pagination_has_more(self, mock_req):
        records = [FAKE_LOG_RECORD] * 50
        mock_req.return_value = _make_response(200, {"result": records})
        result = list_flow_logs(
            self.auth,
            self.cfg,
            {"execution_id": FAKE_FLOW_LOG_EXECUTION_ID, "limit": 50, "offset": 0},
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 50)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_pagination_offset_passed(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flow_logs(
            self.auth,
            self.cfg,
            {"execution_id": FAKE_FLOW_LOG_EXECUTION_ID, "limit": 10, "offset": 20},
        )
        call_params = mock_req.call_args[1].get("params", {})
        self.assertEqual(call_params.get("sysparm_offset"), 20)
        self.assertEqual(call_params.get("sysparm_limit"), 10)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = list_flow_logs(
            self.auth, self.cfg, {"execution_id": FAKE_FLOW_LOG_EXECUTION_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error listing flow logs", result["message"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_flow_logs(
            self.auth, self.cfg, {"execution_id": FAKE_FLOW_LOG_EXECUTION_ID}
        )
        self.assertFalse(result["success"])

    def test_missing_execution_id_returns_failure(self):
        result = list_flow_logs(self.auth, self.cfg, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_empty_results(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_flow_logs(
            self.auth, self.cfg, {"execution_id": FAKE_FLOW_LOG_EXECUTION_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["logs"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_no_level_filter_no_level_in_query(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flow_logs(self.auth, self.cfg, {"execution_id": FAKE_FLOW_LOG_EXECUTION_ID})
        call_params = mock_req.call_args[1].get("params", {})
        query = call_params.get("sysparm_query", "")
        self.assertIn("flow_context=", query)
        self.assertNotIn("level=", query)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_ordered_by_sequence(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flow_logs(self.auth, self.cfg, {"execution_id": FAKE_FLOW_LOG_EXECUTION_ID})
        call_params = mock_req.call_args[1].get("params", {})
        self.assertEqual(call_params.get("sysparm_orderby"), "sequence")

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_correct_table_queried(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_flow_logs(self.auth, self.cfg, {"execution_id": FAKE_FLOW_LOG_EXECUTION_ID})
        call_url = mock_req.call_args[0][1]
        self.assertIn("sys_flow_log", call_url)

    @patch("servicenow_mcp.tools.flow_tools._make_request")
    def test_info_level_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_LOG_RECORD]})
        result = list_flow_logs(
            self.auth,
            self.cfg,
            {"execution_id": FAKE_FLOW_LOG_EXECUTION_ID, "level": "info"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["logs"][0]["level"], "info")


if __name__ == "__main__":
    unittest.main()
