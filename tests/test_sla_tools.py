"""Tests for sla_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.tools.sla_tools import (
    _format_sla,
    _format_task_sla,
    get_sla,
    get_sla_breach,
    list_sla_breach_definitions,
    list_sla_breaches,
    list_slas,
    resolve_sla_breach,
)
from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


FAKE_SYS_ID = "b" * 32
FAKE_SLA_NAME = "Priority 1 Response"

FAKE_SLA = {
    "sys_id": FAKE_SYS_ID,
    "name": FAKE_SLA_NAME,
    "description": "Response SLA for P1 incidents",
    "type": "SLA",
    "duration": "01:00:00",
    "active": "true",
    "table": "incident",
    "condition": "priority=1",
    "start_condition": "state=1",
    "pause_condition": "",
    "stop_condition": "state=6",
    "sys_created_on": "2026-01-01 08:00:00",
    "sys_updated_on": "2026-01-02 09:00:00",
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
# _format_sla
# ---------------------------------------------------------------------------

class TestFormatSLA(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_sla(FAKE_SLA)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["name"], FAKE_SLA_NAME)
        self.assertEqual(result["type"], "SLA")
        self.assertEqual(result["duration"], "01:00:00")
        self.assertEqual(result["active"], "true")
        self.assertEqual(result["table"], "incident")
        self.assertEqual(result["condition"], "priority=1")
        self.assertEqual(result["start_condition"], "state=1")
        self.assertEqual(result["stop_condition"], "state=6")
        self.assertEqual(result["created_on"], "2026-01-01 08:00:00")
        self.assertEqual(result["updated_on"], "2026-01-02 09:00:00")

    def test_handles_missing_fields(self):
        result = _format_sla({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["name"])
        self.assertIsNone(result["duration"])


# ---------------------------------------------------------------------------
# list_sla_breach_definitions
# ---------------------------------------------------------------------------


class TestListSLABreachDefinitions(unittest.TestCase):
    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_success_returns_definitions(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SLA]})
        result = list_sla_breach_definitions(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertIn("sla_breach_definitions", result)
        self.assertEqual(len(result["sla_breach_definitions"]), 1)
        self.assertEqual(result["sla_breach_definitions"][0]["name"], FAKE_SLA_NAME)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_always_applies_active_and_duration_filters(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breach_definitions(_make_auth_manager(), _make_config(), {})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("active=true", query)
        self.assertIn("durationISNOTEMPTY", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_type_filter_added(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breach_definitions(_make_auth_manager(), _make_config(), {"type": "OLA"})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("type=OLA", query)
        self.assertIn("active=true", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_table_filter_added(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breach_definitions(
            _make_auth_manager(), _make_config(), {"table": "change_request"}
        )
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("table=change_request", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_query_filter_searches_by_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breach_definitions(_make_auth_manager(), _make_config(), {"query": "Priority"})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("nameLIKEPriority", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_all_optional_filters_combined(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breach_definitions(
            _make_auth_manager(),
            _make_config(),
            {"type": "SLA", "table": "incident", "query": "P1"},
        )
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("active=true", query)
        self.assertIn("durationISNOTEMPTY", query)
        self.assertIn("type=SLA", query)
        self.assertIn("table=incident", query)
        self.assertIn("nameLIKEP1", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_pagination_params_forwarded(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breach_definitions(
            _make_auth_manager(), _make_config(), {"limit": 5, "offset": 10}
        )
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        self.assertEqual(params.get("sysparm_limit"), 5)
        self.assertEqual(params.get("sysparm_offset"), 10)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = list_sla_breach_definitions(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing SLA breach definitions", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_uses_contract_sla_table_url(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breach_definitions(_make_auth_manager(), _make_config(), {})
        args, _ = mock_req.call_args
        url = args[1]
        self.assertIn("contract_sla", url)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_response_includes_count_and_pagination(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SLA]})
        result = list_sla_breach_definitions(_make_auth_manager(), _make_config(), {})
        self.assertIn("count", result)
        self.assertEqual(result["count"], 1)
        self.assertIn("has_more", result)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_sla_breach_definitions(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(result["sla_breach_definitions"], [])
        self.assertEqual(result["count"], 0)


# ---------------------------------------------------------------------------
# list_slas
# ---------------------------------------------------------------------------

class TestListSLAs(unittest.TestCase):
    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_success_returns_slas(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SLA]})
        result = list_slas(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["slas"]), 1)
        self.assertEqual(result["slas"][0]["name"], FAKE_SLA_NAME)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_slas(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(result["slas"], [])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_active_true_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_slas(_make_auth_manager(), _make_config(), {"active": True})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("active=true", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_active_false_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_slas(_make_auth_manager(), _make_config(), {"active": False})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("active=false", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_type_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_slas(_make_auth_manager(), _make_config(), {"type": "OLA"})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("type=OLA", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_table_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_slas(_make_auth_manager(), _make_config(), {"table": "incident"})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("table=incident", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_query_filter_searches_name_and_description(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_slas(_make_auth_manager(), _make_config(), {"query": "Priority"})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("nameLIKEPriority", query)
        self.assertIn("descriptionLIKEPriority", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_pagination_params(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_slas(_make_auth_manager(), _make_config(), {"limit": 5, "offset": 10})
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        self.assertEqual(params.get("sysparm_limit"), 5)
        self.assertEqual(params.get("sysparm_offset"), 10)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = list_slas(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing SLAs", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_multiple_filters_combined(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_slas(
            _make_auth_manager(),
            _make_config(),
            {"active": True, "type": "SLA", "table": "incident"},
        )
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("active=true", query)
        self.assertIn("type=SLA", query)
        self.assertIn("table=incident", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_pagination_response_has_count(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SLA]})
        result = list_slas(_make_auth_manager(), _make_config(), {})
        self.assertIn("count", result)
        self.assertEqual(result["count"], 1)


# ---------------------------------------------------------------------------
# get_sla
# ---------------------------------------------------------------------------

class TestGetSLA(unittest.TestCase):
    def test_missing_sla_id_returns_failure(self):
        result = get_sla(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_sys_id_success(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_SLA})
        result = get_sla(_make_auth_manager(), _make_config(), {"sla_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["sla"]["name"], FAKE_SLA_NAME)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_sys_id_404_returns_failure(self, mock_req):
        resp = MagicMock()
        resp.status_code = 404
        resp.raise_for_status = MagicMock()
        mock_req.return_value = resp
        result = get_sla(_make_auth_manager(), _make_config(), {"sla_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_sys_id_empty_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_sla(_make_auth_manager(), _make_config(), {"sla_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_name_success(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SLA]})
        result = get_sla(_make_auth_manager(), _make_config(), {"sla_id": FAKE_SLA_NAME})
        self.assertTrue(result["success"])
        self.assertEqual(result["sla"]["name"], FAKE_SLA_NAME)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_name_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = get_sla(_make_auth_manager(), _make_config(), {"sla_id": "Nonexistent SLA"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_name_uses_name_query_param(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SLA]})
        get_sla(_make_auth_manager(), _make_config(), {"sla_id": FAKE_SLA_NAME})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn(f"name={FAKE_SLA_NAME}", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_sys_id_uses_direct_url(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_SLA})
        get_sla(_make_auth_manager(), _make_config(), {"sla_id": FAKE_SYS_ID})
        args, _ = mock_req.call_args
        url = args[1]
        self.assertTrue(url.endswith(f"/{FAKE_SYS_ID}"))

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_sys_id_http_error(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = get_sla(_make_auth_manager(), _make_config(), {"sla_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving SLA", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_name_http_error(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = get_sla(_make_auth_manager(), _make_config(), {"sla_id": "My SLA"})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving SLA", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_sys_id_returns_sla_object(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_SLA})
        result = get_sla(_make_auth_manager(), _make_config(), {"sla_id": FAKE_SYS_ID})
        self.assertIn("sla", result)
        self.assertEqual(result["sla"]["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["sla"]["table"], "incident")


FAKE_TASK_SYS_ID = "c" * 32
FAKE_SLA_DEF_SYS_ID = "d" * 32

FAKE_TASK_SLA = {
    "sys_id": "e" * 32,
    "task": {"display_value": "INC0012345", "value": FAKE_TASK_SYS_ID},
    "sla": {"display_value": "Priority 1 Response", "value": FAKE_SLA_DEF_SYS_ID},
    "stage": "breached",
    "has_breached": "true",
    "breach_time": "2026-05-20 10:00:00",
    "start_time": "2026-05-20 08:00:00",
    "end_time": "",
    "business_duration": "02:00:00",
    "duration": "02:00:00",
    "percentage": "110",
    "table_name": "incident",
    "sys_created_on": "2026-05-20 08:00:00",
    "sys_updated_on": "2026-05-20 10:05:00",
}


# ---------------------------------------------------------------------------
# _format_task_sla
# ---------------------------------------------------------------------------


class TestFormatTaskSLA(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_task_sla(FAKE_TASK_SLA)
        self.assertEqual(result["sys_id"], "e" * 32)
        self.assertEqual(result["task"], "INC0012345")
        self.assertEqual(result["sla"], "Priority 1 Response")
        self.assertEqual(result["stage"], "breached")
        self.assertEqual(result["has_breached"], "true")
        self.assertEqual(result["breach_time"], "2026-05-20 10:00:00")
        self.assertEqual(result["start_time"], "2026-05-20 08:00:00")
        self.assertEqual(result["business_duration"], "02:00:00")
        self.assertEqual(result["percentage"], "110")
        self.assertEqual(result["table_name"], "incident")
        self.assertEqual(result["created_on"], "2026-05-20 08:00:00")
        self.assertEqual(result["updated_on"], "2026-05-20 10:05:00")

    def test_handles_missing_fields(self):
        result = _format_task_sla({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["task"])
        self.assertIsNone(result["stage"])
        self.assertIsNone(result["has_breached"])

    def test_raw_string_reference_fields(self):
        """task and sla can also be plain strings (not dicts)."""
        record = {**FAKE_TASK_SLA, "task": FAKE_TASK_SYS_ID, "sla": FAKE_SLA_DEF_SYS_ID}
        result = _format_task_sla(record)
        self.assertEqual(result["task"], FAKE_TASK_SYS_ID)
        self.assertEqual(result["sla"], FAKE_SLA_DEF_SYS_ID)

    def test_reference_field_falls_back_to_value_key(self):
        record = {**FAKE_TASK_SLA, "task": {"display_value": None, "value": FAKE_TASK_SYS_ID}}
        result = _format_task_sla(record)
        self.assertEqual(result["task"], FAKE_TASK_SYS_ID)


# ---------------------------------------------------------------------------
# list_sla_breaches
# ---------------------------------------------------------------------------


class TestListSLABreaches(unittest.TestCase):
    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_success_returns_breaches(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_TASK_SLA]})
        result = list_sla_breaches(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["sla_breaches"]), 1)
        self.assertEqual(result["sla_breaches"][0]["stage"], "breached")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_sla_breaches(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(result["sla_breaches"], [])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_has_breached_true_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breaches(_make_auth_manager(), _make_config(), {"has_breached": True})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("has_breached=true", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_has_breached_false_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breaches(_make_auth_manager(), _make_config(), {"has_breached": False})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("has_breached=false", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_stage_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breaches(_make_auth_manager(), _make_config(), {"stage": "in_progress"})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("stage=in_progress", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_table_name_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breaches(_make_auth_manager(), _make_config(), {"table_name": "incident"})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("table_name=incident", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_task_sys_id_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breaches(
            _make_auth_manager(), _make_config(), {"task_sys_id": FAKE_TASK_SYS_ID}
        )
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn(f"task={FAKE_TASK_SYS_ID}", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_sla_sys_id_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breaches(
            _make_auth_manager(), _make_config(), {"sla_sys_id": FAKE_SLA_DEF_SYS_ID}
        )
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn(f"sla={FAKE_SLA_DEF_SYS_ID}", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_pagination_params_forwarded(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breaches(
            _make_auth_manager(), _make_config(), {"limit": 5, "offset": 15}
        )
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        self.assertEqual(params.get("sysparm_limit"), 5)
        self.assertEqual(params.get("sysparm_offset"), 15)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = list_sla_breaches(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing SLA breaches", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_multiple_filters_combined(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breaches(
            _make_auth_manager(),
            _make_config(),
            {"has_breached": True, "stage": "breached", "table_name": "incident"},
        )
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("has_breached=true", query)
        self.assertIn("stage=breached", query)
        self.assertIn("table_name=incident", query)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_response_includes_count(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_TASK_SLA]})
        result = list_sla_breaches(_make_auth_manager(), _make_config(), {})
        self.assertIn("count", result)
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_uses_task_sla_table_url(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breaches(_make_auth_manager(), _make_config(), {})
        args, _ = mock_req.call_args
        url = args[1]
        self.assertIn("task_sla", url)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_no_filter_no_query_param(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_breaches(_make_auth_manager(), _make_config(), {})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertEqual(query, "")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_has_more_pagination_flag(self, mock_req):
        items = [FAKE_TASK_SLA] * 3
        mock_req.return_value = _make_response(200, {"result": items})
        result = list_sla_breaches(
            _make_auth_manager(), _make_config(), {"limit": 3, "offset": 0}
        )
        self.assertIn("has_more", result)


# ---------------------------------------------------------------------------
# get_sla_breach
# ---------------------------------------------------------------------------

FAKE_BREACH_SYS_ID = "e" * 32


class TestGetSLABreach(unittest.TestCase):
    def test_missing_task_sla_id_returns_failure(self):
        result = get_sla_breach(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_success_returns_sla_breach(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_TASK_SLA})
        result = get_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_BREACH_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertIn("sla_breach", result)
        self.assertEqual(result["sla_breach"]["stage"], "breached")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_success_formats_all_fields(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_TASK_SLA})
        result = get_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_BREACH_SYS_ID}
        )
        breach = result["sla_breach"]
        self.assertEqual(breach["task"], "INC0012345")
        self.assertEqual(breach["sla"], "Priority 1 Response")
        self.assertEqual(breach["has_breached"], "true")
        self.assertEqual(breach["breach_time"], "2026-05-20 10:00:00")
        self.assertEqual(breach["start_time"], "2026-05-20 08:00:00")
        self.assertEqual(breach["percentage"], "110")
        self.assertEqual(breach["table_name"], "incident")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_404_returns_failure(self, mock_req):
        resp = MagicMock()
        resp.status_code = 404
        resp.raise_for_status = MagicMock()
        mock_req.return_value = resp
        result = get_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_BREACH_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertIn(FAKE_BREACH_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_empty_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_BREACH_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = get_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_BREACH_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving SLA breach record", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_uses_direct_sys_id_url(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_TASK_SLA})
        get_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_BREACH_SYS_ID}
        )
        args, _ = mock_req.call_args
        url = args[1]
        self.assertTrue(url.endswith(f"/{FAKE_BREACH_SYS_ID}"))
        self.assertIn("task_sla", url)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_display_value_requested(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_TASK_SLA})
        get_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_BREACH_SYS_ID}
        )
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        self.assertEqual(params.get("sysparm_display_value"), "true")
        self.assertEqual(params.get("sysparm_exclude_reference_link"), "true")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_fields_param_includes_task_sla_fields(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_TASK_SLA})
        get_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_BREACH_SYS_ID}
        )
        _, kwargs = mock_req.call_args
        fields = kwargs.get("params", {}).get("sysparm_fields", "")
        self.assertIn("has_breached", fields)
        self.assertIn("breach_time", fields)
        self.assertIn("stage", fields)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_uses_get_method(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_TASK_SLA})
        get_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_BREACH_SYS_ID}
        )
        args, _ = mock_req.call_args
        self.assertEqual(args[0], "GET")


# ---------------------------------------------------------------------------
# resolve_sla_breach
# ---------------------------------------------------------------------------

FAKE_RESOLVED_TASK_SLA = {
    **FAKE_TASK_SLA,
    "stage": "completed",
    "paused": "true",
    "end_time": "2026-05-20 11:00:00",
}

FAKE_RESOLVE_SYS_ID = "f" * 32


class TestResolveSLABreach(unittest.TestCase):
    def test_missing_task_sla_id_returns_failure(self):
        result = resolve_sla_breach(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_success_returns_resolved_breach(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_RESOLVED_TASK_SLA})
        result = resolve_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_RESOLVE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "SLA breach resolved successfully")
        self.assertIn("sla_breach", result)
        self.assertEqual(result["sla_breach"]["stage"], "completed")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_body_contains_paused_and_stage(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_RESOLVED_TASK_SLA})
        resolve_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_RESOLVE_SYS_ID}
        )
        _, kwargs = mock_req.call_args
        body = kwargs.get("json", {})
        self.assertEqual(body.get("paused"), "true")
        self.assertEqual(body.get("stage"), "completed")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_work_notes_included_in_body_when_provided(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_RESOLVED_TASK_SLA})
        resolve_sla_breach(
            _make_auth_manager(),
            _make_config(),
            {"task_sla_id": FAKE_RESOLVE_SYS_ID, "work_notes": "Resolved after task closure"},
        )
        _, kwargs = mock_req.call_args
        body = kwargs.get("json", {})
        self.assertEqual(body.get("work_notes"), "Resolved after task closure")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_work_notes_absent_when_not_provided(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_RESOLVED_TASK_SLA})
        resolve_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_RESOLVE_SYS_ID}
        )
        _, kwargs = mock_req.call_args
        body = kwargs.get("json", {})
        self.assertNotIn("work_notes", body)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_404_returns_failure_with_sys_id(self, mock_req):
        resp = MagicMock()
        resp.status_code = 404
        resp.raise_for_status = MagicMock()
        mock_req.return_value = resp
        result = resolve_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_RESOLVE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertIn(FAKE_RESOLVE_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = resolve_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_RESOLVE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error resolving SLA breach", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_uses_patch_method(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_RESOLVED_TASK_SLA})
        resolve_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_RESOLVE_SYS_ID}
        )
        args, _ = mock_req.call_args
        self.assertEqual(args[0], "PATCH")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_uses_task_sla_url_with_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_RESOLVED_TASK_SLA})
        resolve_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_RESOLVE_SYS_ID}
        )
        args, _ = mock_req.call_args
        url = args[1]
        self.assertIn("task_sla", url)
        self.assertTrue(url.endswith(f"/{FAKE_RESOLVE_SYS_ID}"))

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_response_includes_sys_id(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": {**FAKE_RESOLVED_TASK_SLA, "sys_id": FAKE_RESOLVE_SYS_ID}}
        )
        result = resolve_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_RESOLVE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_RESOLVE_SYS_ID)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_falls_back_to_param_sys_id_when_result_missing(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = resolve_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_RESOLVE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_RESOLVE_SYS_ID)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_sla_breach_fields_normalised(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_RESOLVED_TASK_SLA})
        result = resolve_sla_breach(
            _make_auth_manager(), _make_config(), {"task_sla_id": FAKE_RESOLVE_SYS_ID}
        )
        breach = result["sla_breach"]
        self.assertEqual(breach["task"], "INC0012345")
        self.assertEqual(breach["sla"], "Priority 1 Response")
        self.assertEqual(breach["table_name"], "incident")


if __name__ == "__main__":
    unittest.main()
