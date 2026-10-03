"""Tests for sla_notification_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.sla_notification_tools import (
    _format_sysevent,
    _format_task_sla,
    create_sla_breach_notification,
    list_at_risk_slas,
    list_sla_breach_events,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "c" * 32
FAKE_TASK_ID = "d" * 32

FAKE_TASK_SLA = {
    "sys_id": FAKE_SYS_ID,
    "task": {"display_value": "INC0001234", "value": FAKE_TASK_ID},
    "sla": {"display_value": "P1 SLA", "value": "e" * 32},
    "stage": "In Progress",
    "has_breached": "false",
    "percentage": "85",
    "business_percentage": "87",
    "business_time_left": "00:30:00",
    "time_left": "00:29:00",
    "breach_time": "2026-10-03 14:00:00",
    "start_time": "2026-10-03 10:00:00",
    "end_time": "2026-10-03 14:00:00",
    "table_name": "incident",
    "sys_updated_on": "2026-10-03 12:00:00",
}

FAKE_SYSEVENT = {
    "sys_id": FAKE_SYS_ID,
    "name": "sla.breach",
    "parm1": FAKE_TASK_ID,
    "parm2": "f" * 32,
    "source": "servicenow-mcp",
    "state": "ready",
    "processed": "",
    "process_on": "",
    "sys_created_on": "2026-10-03 12:01:00",
    "sys_updated_on": "2026-10-03 12:01:00",
}


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev99999.service-now.com", auth=auth_config)


def _make_auth_manager():
    am = MagicMock(spec=AuthManager)
    am.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    am.instance_url = "https://dev99999.service-now.com"
    return am


def _make_response(status_code, json_data):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


# ---------------------------------------------------------------------------
# _format_task_sla
# ---------------------------------------------------------------------------


class TestFormatTaskSLA(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_task_sla(FAKE_TASK_SLA)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["task"], "INC0001234")
        self.assertEqual(result["sla"], "P1 SLA")
        self.assertEqual(result["stage"], "In Progress")
        self.assertFalse(result["has_breached"])
        self.assertEqual(result["percentage"], "85")
        self.assertEqual(result["table_name"], "incident")

    def test_handles_string_fields(self):
        record = {k: str(v) if not isinstance(v, dict) else v for k, v in FAKE_TASK_SLA.items()}
        result = _format_task_sla(record)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    def test_has_breached_true(self):
        record = dict(FAKE_TASK_SLA, has_breached="true")
        result = _format_task_sla(record)
        self.assertTrue(result["has_breached"])

    def test_has_breached_bool_true(self):
        record = dict(FAKE_TASK_SLA, has_breached=True)
        result = _format_task_sla(record)
        self.assertTrue(result["has_breached"])


# ---------------------------------------------------------------------------
# _format_sysevent
# ---------------------------------------------------------------------------


class TestFormatSysevent(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_sysevent(FAKE_SYSEVENT)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["name"], "sla.breach")
        self.assertEqual(result["parm1"], FAKE_TASK_ID)
        self.assertEqual(result["source"], "servicenow-mcp")
        self.assertEqual(result["state"], "ready")

    def test_handles_dict_values(self):
        record = dict(FAKE_SYSEVENT, name={"display_value": "sla.breach", "value": "sla.breach"})
        result = _format_sysevent(record)
        self.assertEqual(result["name"], "sla.breach")

    def test_handles_missing_fields(self):
        result = _format_sysevent({})
        self.assertEqual(result["sys_id"], "")
        self.assertEqual(result["name"], "")


# ---------------------------------------------------------------------------
# list_at_risk_slas
# ---------------------------------------------------------------------------


class TestListAtRiskSLAs(unittest.TestCase):
    def _run(self, params, mock_resp):
        with patch("servicenow_mcp.tools.sla_notification_tools._make_request") as mock_req:
            mock_req.return_value = mock_resp
            return list_at_risk_slas(_make_auth_manager(), _make_config(), params)

    def test_success_default_threshold(self):
        resp = _make_response(200, {"result": [FAKE_TASK_SLA]})
        result = self._run({}, resp)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["at_risk_slas"][0]["table_name"], "incident")

    def test_success_custom_threshold(self):
        resp = _make_response(200, {"result": [FAKE_TASK_SLA]})
        result = self._run({"threshold": 90}, resp)
        self.assertTrue(result["success"])

    def test_success_with_table_name_filter(self):
        resp = _make_response(200, {"result": [FAKE_TASK_SLA]})
        result = self._run({"table_name": "incident"}, resp)
        self.assertTrue(result["success"])

    def test_success_with_stage_filter(self):
        resp = _make_response(200, {"result": [FAKE_TASK_SLA]})
        result = self._run({"stage": "In Progress"}, resp)
        self.assertTrue(result["success"])

    def test_success_with_pagination(self):
        resp = _make_response(200, {"result": []})
        result = self._run({"limit": 5, "offset": 10}, resp)
        self.assertTrue(result["success"])

    def test_empty_result(self):
        resp = _make_response(200, {"result": []})
        result = self._run({}, resp)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    def test_http_error(self):
        resp = _make_response(500, {"error": {"message": "Internal Error", "detail": ""}})
        result = self._run({}, resp)
        self.assertFalse(result["success"])
        self.assertIn("Error", result["message"])

    def test_request_exception(self):
        with patch("servicenow_mcp.tools.sla_notification_tools._make_request") as mock_req:
            mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
            result = list_at_risk_slas(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        am = _make_auth_manager()
        am.instance_url = None
        cfg = _make_config()
        cfg.instance_url = None
        result = list_at_risk_slas(am, cfg, {})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        am = _make_auth_manager()
        am.get_headers.return_value = None
        cfg = _make_config()
        cfg.instance_url = None
        with patch("servicenow_mcp.tools.sla_notification_tools._get_headers", return_value=None):
            result = list_at_risk_slas(am, _make_config(), {})
        self.assertFalse(result["success"])

    def test_invalid_threshold_zero(self):
        result = list_at_risk_slas(_make_auth_manager(), _make_config(), {"threshold": 0})
        self.assertFalse(result["success"])

    def test_invalid_threshold_100(self):
        result = list_at_risk_slas(_make_auth_manager(), _make_config(), {"threshold": 100})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# create_sla_breach_notification
# ---------------------------------------------------------------------------


class TestCreateSLABreachNotification(unittest.TestCase):
    def _run(self, params, mock_resp):
        with patch("servicenow_mcp.tools.sla_notification_tools._make_request") as mock_req:
            mock_req.return_value = mock_resp
            return create_sla_breach_notification(_make_auth_manager(), _make_config(), params)

    def test_success_minimal(self):
        resp = _make_response(200, {"result": FAKE_SYSEVENT})
        result = self._run({"task_sys_id": FAKE_TASK_ID}, resp)
        self.assertTrue(result["success"])
        self.assertEqual(result["event"]["name"], "sla.breach")

    def test_success_with_sla_sys_id(self):
        resp = _make_response(200, {"result": FAKE_SYSEVENT})
        result = self._run(
            {"task_sys_id": FAKE_TASK_ID, "sla_sys_id": "f" * 32}, resp
        )
        self.assertTrue(result["success"])

    def test_success_custom_event_name(self):
        resp = _make_response(200, {"result": dict(FAKE_SYSEVENT, name="sla.warning")})
        result = self._run(
            {"task_sys_id": FAKE_TASK_ID, "event_name": "sla.warning"}, resp
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["event"]["name"], "sla.warning")

    def test_success_custom_source(self):
        resp = _make_response(200, {"result": FAKE_SYSEVENT})
        result = self._run({"task_sys_id": FAKE_TASK_ID, "source": "custom-src"}, resp)
        self.assertTrue(result["success"])

    def test_missing_task_sys_id(self):
        result = create_sla_breach_notification(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_empty_task_sys_id(self):
        result = create_sla_breach_notification(
            _make_auth_manager(), _make_config(), {"task_sys_id": "   "}
        )
        self.assertFalse(result["success"])

    def test_http_error(self):
        resp = _make_response(403, {"error": {"message": "Forbidden", "detail": ""}})
        result = self._run({"task_sys_id": FAKE_TASK_ID}, resp)
        self.assertFalse(result["success"])

    def test_request_exception(self):
        with patch("servicenow_mcp.tools.sla_notification_tools._make_request") as mock_req:
            mock_req.side_effect = requests.exceptions.ConnectionError("conn refused")
            result = create_sla_breach_notification(
                _make_auth_manager(), _make_config(), {"task_sys_id": FAKE_TASK_ID}
            )
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        cfg = _make_config()
        cfg.instance_url = None
        result = create_sla_breach_notification(_make_auth_manager(), cfg, {"task_sys_id": FAKE_TASK_ID})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        with patch("servicenow_mcp.tools.sla_notification_tools._get_headers", return_value=None):
            result = create_sla_breach_notification(
                _make_auth_manager(), _make_config(), {"task_sys_id": FAKE_TASK_ID}
            )
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# list_sla_breach_events
# ---------------------------------------------------------------------------


class TestListSLABreachEvents(unittest.TestCase):
    def _run(self, params, mock_resp):
        with patch("servicenow_mcp.tools.sla_notification_tools._make_request") as mock_req:
            mock_req.return_value = mock_resp
            return list_sla_breach_events(_make_auth_manager(), _make_config(), params)

    def test_success_default_event_name(self):
        resp = _make_response(200, {"result": [FAKE_SYSEVENT]})
        result = self._run({}, resp)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["events"][0]["name"], "sla.breach")

    def test_success_custom_event_name(self):
        resp = _make_response(200, {"result": [FAKE_SYSEVENT]})
        result = self._run({"event_name": "sla.warning"}, resp)
        self.assertTrue(result["success"])

    def test_success_with_state_filter(self):
        resp = _make_response(200, {"result": [FAKE_SYSEVENT]})
        result = self._run({"state": "ready"}, resp)
        self.assertTrue(result["success"])

    def test_success_with_source_filter(self):
        resp = _make_response(200, {"result": [FAKE_SYSEVENT]})
        result = self._run({"source": "servicenow-mcp"}, resp)
        self.assertTrue(result["success"])

    def test_success_with_pagination(self):
        resp = _make_response(200, {"result": []})
        result = self._run({"limit": 10, "offset": 5}, resp)
        self.assertTrue(result["success"])

    def test_empty_result(self):
        resp = _make_response(200, {"result": []})
        result = self._run({}, resp)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    def test_http_error(self):
        resp = _make_response(500, {"error": {"message": "Server Error", "detail": ""}})
        result = self._run({}, resp)
        self.assertFalse(result["success"])

    def test_request_exception(self):
        with patch("servicenow_mcp.tools.sla_notification_tools._make_request") as mock_req:
            mock_req.side_effect = requests.exceptions.Timeout("timeout")
            result = list_sla_breach_events(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        cfg = _make_config()
        cfg.instance_url = None
        result = list_sla_breach_events(_make_auth_manager(), cfg, {})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        with patch("servicenow_mcp.tools.sla_notification_tools._get_headers", return_value=None):
            result = list_sla_breach_events(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_none_event_name_uses_default(self):
        resp = _make_response(200, {"result": []})
        result = self._run({"event_name": None}, resp)
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
