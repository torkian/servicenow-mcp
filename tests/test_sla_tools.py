"""Tests for sla_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.tools.sla_tools import (
    _format_sla,
    get_sla,
    list_slas,
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


if __name__ == "__main__":
    unittest.main()
