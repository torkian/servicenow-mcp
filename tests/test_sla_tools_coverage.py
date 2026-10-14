"""Coverage-gap tests for sla_tools.py.

Targets the branches not exercised by test_sla_tools.py and
test_sla_exception_tools.py:
  - no_instance_url / no_headers paths in list_slas, get_sla,
    list_sla_breach_definitions, list_sla_breaches, resolve_sla_breach,
    get_sla_breach, list_incident_slas, update_sla, delete_sla
  - invalid-params (validation-failure) paths in list_slas,
    list_sla_breach_definitions, list_sla_breaches, list_incident_slas,
    list_sla_exceptions
  - _format_sla_schedule (dict-value branch)
  - _resolve_sla_schedule_sys_id (404 path, RequestException path)
  - list_sla_schedules (full function)
  - get_sla_schedule (full function with all branches)
  - _resolve_schedule_sys_id (RequestException path)
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.sla_tools import (
    _format_sla_schedule,
    _resolve_sla_schedule_sys_id,
    _resolve_schedule_sys_id,
    delete_sla,
    get_sla,
    get_sla_breach,
    get_sla_schedule,
    list_incident_slas,
    list_sla_breach_definitions,
    list_sla_breaches,
    list_sla_exceptions,
    list_sla_schedules,
    list_slas,
    resolve_sla_breach,
    update_sla,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "b" * 32
FAKE_SCHEDULE_SYS_ID = "c" * 32
FAKE_SLA_SYS_ID = "a" * 32


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


def _no_instance_url_config():
    cfg = _make_config()
    cfg.instance_url = None
    auth = MagicMock(spec=AuthManager)
    auth.instance_url = None
    auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    return auth, cfg


def _no_headers_config():
    cfg = _make_config()
    auth = MagicMock(spec=AuthManager)
    auth.instance_url = "https://dev99999.service-now.com"
    auth.get_headers.return_value = None
    return auth, cfg


def _make_response(status_code=200, json_data=None):
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


FAKE_SCHEDULE = {
    "sys_id": FAKE_SCHEDULE_SYS_ID,
    "name": "24/7 Schedule",
    "description": "Always on",
    "type": {"display_value": "Exclude", "value": "exclude"},
    "time_zone": "UTC",
    "active": "true",
    "parent": {"display_value": "Parent Sched", "value": "p" * 32},
    "sys_created_by": "admin",
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-06-01 00:00:00",
}

FAKE_TASK_SLA_SYS_ID = "t" * 32


# ---------------------------------------------------------------------------
# _format_sla_schedule — dict-value branches
# ---------------------------------------------------------------------------

class TestFormatSLASchedule(unittest.TestCase):
    def test_dict_type_and_parent_resolved(self):
        result = _format_sla_schedule(FAKE_SCHEDULE)
        self.assertEqual(result["sys_id"], FAKE_SCHEDULE_SYS_ID)
        self.assertEqual(result["name"], "24/7 Schedule")
        self.assertEqual(result["type"], "Exclude")
        self.assertEqual(result["parent"], "Parent Sched")
        self.assertEqual(result["time_zone"], "UTC")
        self.assertEqual(result["created_by"], "admin")

    def test_scalar_type_and_parent_passthrough(self):
        record = dict(FAKE_SCHEDULE)
        record["type"] = "exclude"
        record["parent"] = "Parent Sched"
        result = _format_sla_schedule(record)
        self.assertEqual(result["type"], "exclude")
        self.assertEqual(result["parent"], "Parent Sched")

    def test_empty_record_returns_nones(self):
        result = _format_sla_schedule({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["name"])
        self.assertIsNone(result["type"])
        self.assertIsNone(result["parent"])


# ---------------------------------------------------------------------------
# _resolve_sla_schedule_sys_id — 404 path, RequestException path
# ---------------------------------------------------------------------------

class TestResolveSLAScheduleSysId(unittest.TestCase):
    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_404_returns_none(self, mock_req):
        # SLA resolve succeeds (first call returns the SLA)
        sla_resp = _make_response(200, {"result": [{"sys_id": FAKE_SLA_SYS_ID}]})
        # Schedule fetch returns 404
        schedule_resp = MagicMock()
        schedule_resp.status_code = 404
        schedule_resp.raise_for_status.return_value = None
        mock_req.side_effect = [sla_resp, schedule_resp]
        result = _resolve_sla_schedule_sys_id(
            "https://dev99999.service-now.com",
            {"Authorization": "Bearer FAKE"},
            "Priority 1 SLA",
        )
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_request_exception_returns_none(self, mock_req):
        sla_resp = _make_response(200, {"result": [{"sys_id": FAKE_SLA_SYS_ID}]})
        mock_req.side_effect = [
            sla_resp,
            requests.exceptions.ConnectionError("connection refused"),
        ]
        result = _resolve_sla_schedule_sys_id(
            "https://dev99999.service-now.com",
            {"Authorization": "Bearer FAKE"},
            "Priority 1 SLA",
        )
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_schedule_as_dict_returns_value(self, mock_req):
        sla_resp = _make_response(200, {"result": [{"sys_id": FAKE_SLA_SYS_ID}]})
        schedule_resp = _make_response(200, {
            "result": {"schedule": {"value": FAKE_SCHEDULE_SYS_ID, "display_value": "24/7"}}
        })
        mock_req.side_effect = [sla_resp, schedule_resp]
        result = _resolve_sla_schedule_sys_id(
            "https://dev99999.service-now.com",
            {"Authorization": "Bearer FAKE"},
            "Priority 1 SLA",
        )
        self.assertEqual(result, FAKE_SCHEDULE_SYS_ID)


# ---------------------------------------------------------------------------
# _resolve_schedule_sys_id — RequestException path
# ---------------------------------------------------------------------------

class TestResolveScheduleSysId(unittest.TestCase):
    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_request_exception_returns_none(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = _resolve_schedule_sys_id(
            "https://dev99999.service-now.com",
            {"Authorization": "Bearer FAKE"},
            "My Schedule",
        )
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_passthrough_for_hex_sys_id(self, mock_req):
        result = _resolve_schedule_sys_id(
            "https://dev99999.service-now.com",
            {"Authorization": "Bearer FAKE"},
            FAKE_SCHEDULE_SYS_ID,
        )
        self.assertEqual(result, FAKE_SCHEDULE_SYS_ID)
        mock_req.assert_not_called()

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_name_lookup_returns_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [{"sys_id": FAKE_SCHEDULE_SYS_ID}]})
        result = _resolve_schedule_sys_id(
            "https://dev99999.service-now.com",
            {"Authorization": "Bearer FAKE"},
            "My Schedule",
        )
        self.assertEqual(result, FAKE_SCHEDULE_SYS_ID)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_name_not_found_returns_none(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = _resolve_schedule_sys_id(
            "https://dev99999.service-now.com",
            {"Authorization": "Bearer FAKE"},
            "Nonexistent",
        )
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# list_slas — no_instance_url, no_headers, invalid_params
# ---------------------------------------------------------------------------

class TestListSLAsCoverage(unittest.TestCase):
    def test_no_instance_url_returns_failure(self):
        auth, cfg = _no_instance_url_config()
        result = list_slas(auth, cfg, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers_returns_failure(self):
        auth, cfg = _no_headers_config()
        result = list_slas(auth, cfg, {})
        self.assertFalse(result["success"])
        self.assertIn("headers", result["message"])


# ---------------------------------------------------------------------------
# get_sla — no_instance_url, no_headers
# ---------------------------------------------------------------------------

class TestGetSLACoverage(unittest.TestCase):
    def test_no_instance_url_returns_failure(self):
        auth, cfg = _no_instance_url_config()
        result = get_sla(auth, cfg, {"sla_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers_returns_failure(self):
        auth, cfg = _no_headers_config()
        result = get_sla(auth, cfg, {"sla_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("headers", result["message"])


# ---------------------------------------------------------------------------
# list_sla_breach_definitions — no_instance_url, no_headers, invalid_params
# ---------------------------------------------------------------------------

class TestListSLABreachDefinitionsCoverage(unittest.TestCase):
    def test_no_instance_url_returns_failure(self):
        auth, cfg = _no_instance_url_config()
        result = list_sla_breach_definitions(auth, cfg, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers_returns_failure(self):
        auth, cfg = _no_headers_config()
        result = list_sla_breach_definitions(auth, cfg, {})
        self.assertFalse(result["success"])
        self.assertIn("headers", result["message"])


# ---------------------------------------------------------------------------
# list_sla_breaches — no_instance_url, no_headers, invalid_params
# ---------------------------------------------------------------------------

class TestListSLABreachesCoverage(unittest.TestCase):
    def test_no_instance_url_returns_failure(self):
        auth, cfg = _no_instance_url_config()
        result = list_sla_breaches(auth, cfg, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers_returns_failure(self):
        auth, cfg = _no_headers_config()
        result = list_sla_breaches(auth, cfg, {})
        self.assertFalse(result["success"])
        self.assertIn("headers", result["message"])


# ---------------------------------------------------------------------------
# resolve_sla_breach — no_instance_url, no_headers
# ---------------------------------------------------------------------------

class TestResolveSLABreachCoverage(unittest.TestCase):
    def test_no_instance_url_returns_failure(self):
        auth, cfg = _no_instance_url_config()
        result = resolve_sla_breach(auth, cfg, {"task_sla_id": FAKE_TASK_SLA_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers_returns_failure(self):
        auth, cfg = _no_headers_config()
        result = resolve_sla_breach(auth, cfg, {"task_sla_id": FAKE_TASK_SLA_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("headers", result["message"])


# ---------------------------------------------------------------------------
# get_sla_breach — no_instance_url, no_headers
# ---------------------------------------------------------------------------

class TestGetSLABreachCoverage(unittest.TestCase):
    def test_no_instance_url_returns_failure(self):
        auth, cfg = _no_instance_url_config()
        result = get_sla_breach(auth, cfg, {"task_sla_id": FAKE_TASK_SLA_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers_returns_failure(self):
        auth, cfg = _no_headers_config()
        result = get_sla_breach(auth, cfg, {"task_sla_id": FAKE_TASK_SLA_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("headers", result["message"])


# ---------------------------------------------------------------------------
# list_incident_slas — no_headers, invalid_params
# ---------------------------------------------------------------------------

class TestListIncidentSLAsCoverage(unittest.TestCase):
    def test_no_headers_returns_failure(self):
        auth, cfg = _no_headers_config()
        result = list_incident_slas(auth, cfg, {})
        self.assertFalse(result["success"])
        self.assertIn("headers", result["message"])


# ---------------------------------------------------------------------------
# update_sla — no_instance_url, no_headers
# ---------------------------------------------------------------------------

class TestUpdateSLACoverage(unittest.TestCase):
    def test_no_instance_url_returns_failure(self):
        auth, cfg = _no_instance_url_config()
        result = update_sla(auth, cfg, {"sla_id": FAKE_SYS_ID, "name": "New Name"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers_returns_failure(self):
        auth, cfg = _no_headers_config()
        result = update_sla(auth, cfg, {"sla_id": FAKE_SYS_ID, "name": "New Name"})
        self.assertFalse(result["success"])
        self.assertIn("headers", result["message"])


# ---------------------------------------------------------------------------
# delete_sla — no_headers
# ---------------------------------------------------------------------------

class TestDeleteSLACoverage(unittest.TestCase):
    def test_no_headers_returns_failure(self):
        auth, cfg = _no_headers_config()
        result = delete_sla(auth, cfg, {"sla_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("headers", result["message"])


# ---------------------------------------------------------------------------
# list_sla_exceptions — invalid_params path (validation failure)
# ---------------------------------------------------------------------------

class TestListSLAExceptionsCoverage(unittest.TestCase):
    def test_invalid_limit_fails_validation(self):
        result = list_sla_exceptions(
            _make_auth_manager(), _make_config(), {"limit": "not-a-number"}
        )
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# list_sla_schedules — full coverage
# ---------------------------------------------------------------------------

class TestListSLASchedules(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_success_returns_schedules(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SCHEDULE]})
        result = list_sla_schedules(self.auth, self.config, {})
        self.assertTrue(result["success"])
        self.assertIn("sla_schedules", result)
        self.assertEqual(len(result["sla_schedules"]), 1)
        self.assertEqual(result["sla_schedules"][0]["name"], "24/7 Schedule")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_sla_schedules(self.auth, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(result["sla_schedules"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_name_query_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_schedules(self.auth, self.config, {"name_query": "24/7"})
        _, kwargs = mock_req.call_args
        self.assertIn("nameLIKE24/7", kwargs["params"].get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_active_true_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_schedules(self.auth, self.config, {"active": True})
        _, kwargs = mock_req.call_args
        self.assertIn("active=true", kwargs["params"].get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_active_false_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_schedules(self.auth, self.config, {"active": False})
        _, kwargs = mock_req.call_args
        self.assertIn("active=false", kwargs["params"].get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_time_zone_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_schedules(self.auth, self.config, {"time_zone": "US/Eastern"})
        _, kwargs = mock_req.call_args
        self.assertIn("time_zone=US/Eastern", kwargs["params"].get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_pagination_params_forwarded(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_schedules(self.auth, self.config, {"limit": 5, "offset": 10})
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["params"].get("sysparm_limit"), 5)
        self.assertEqual(kwargs["params"].get("sysparm_offset"), 10)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = list_sla_schedules(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing SLA schedules", result["message"])

    def test_no_instance_url_returns_failure(self):
        auth, cfg = _no_instance_url_config()
        result = list_sla_schedules(auth, cfg, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers_returns_failure(self):
        auth, cfg = _no_headers_config()
        result = list_sla_schedules(auth, cfg, {})
        self.assertFalse(result["success"])
        self.assertIn("headers", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    @patch("servicenow_mcp.tools.sla_tools._resolve_sla_schedule_sys_id")
    def test_sla_id_scoping_success(self, mock_resolve, mock_req):
        mock_resolve.return_value = FAKE_SCHEDULE_SYS_ID
        mock_req.return_value = _make_response(200, {"result": [FAKE_SCHEDULE]})
        result = list_sla_schedules(self.auth, self.config, {"sla_id": FAKE_SLA_SYS_ID})
        self.assertTrue(result["success"])
        _, kwargs = mock_req.call_args
        self.assertIn(f"sys_id={FAKE_SCHEDULE_SYS_ID}", kwargs["params"].get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.sla_tools._resolve_sla_schedule_sys_id")
    def test_sla_id_not_found_returns_failure(self, mock_resolve):
        mock_resolve.return_value = None
        result = list_sla_schedules(self.auth, self.config, {"sla_id": "Unknown SLA"})
        self.assertFalse(result["success"])
        self.assertIn("Unknown SLA", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_uses_cmn_schedule_table(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_sla_schedules(self.auth, self.config, {})
        args, _ = mock_req.call_args
        self.assertIn("cmn_schedule", args[1])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_response_includes_has_more(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SCHEDULE]})
        result = list_sla_schedules(self.auth, self.config, {})
        self.assertIn("has_more", result)


# ---------------------------------------------------------------------------
# get_sla_schedule — full coverage
# ---------------------------------------------------------------------------

class TestGetSLASchedule(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    def test_missing_both_params_returns_failure(self):
        result = get_sla_schedule(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("schedule_id or sla_id", result["message"])

    def test_no_instance_url_returns_failure(self):
        auth, cfg = _no_instance_url_config()
        result = get_sla_schedule(auth, cfg, {"schedule_id": FAKE_SCHEDULE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers_returns_failure(self):
        auth, cfg = _no_headers_config()
        result = get_sla_schedule(auth, cfg, {"schedule_id": FAKE_SCHEDULE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("headers", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_schedule_sys_id_success(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_SCHEDULE})
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": FAKE_SCHEDULE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertIn("sla_schedule", result)
        self.assertEqual(result["sla_schedule"]["name"], "24/7 Schedule")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_schedule_name_success(self, mock_req):
        # First call: name lookup returns a schedule record
        lookup_resp = _make_response(200, {"result": [{"sys_id": FAKE_SCHEDULE_SYS_ID}]})
        # Second call: fetch full record
        fetch_resp = _make_response(200, {"result": FAKE_SCHEDULE})
        mock_req.side_effect = [lookup_resp, fetch_resp]
        result = get_sla_schedule(self.auth, self.config, {"schedule_id": "24/7 Schedule"})
        self.assertTrue(result["success"])
        self.assertEqual(result["sla_schedule"]["sys_id"], FAKE_SCHEDULE_SYS_ID)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_schedule_name_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = get_sla_schedule(self.auth, self.config, {"schedule_id": "Nonexistent"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_schedule_name_lookup_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        result = get_sla_schedule(self.auth, self.config, {"schedule_id": "My Schedule"})
        self.assertFalse(result["success"])
        self.assertIn("Error looking up schedule", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    @patch("servicenow_mcp.tools.sla_tools._resolve_sla_schedule_sys_id")
    def test_get_by_sla_id_success(self, mock_resolve, mock_req):
        mock_resolve.return_value = FAKE_SCHEDULE_SYS_ID
        mock_req.return_value = _make_response(200, {"result": FAKE_SCHEDULE})
        result = get_sla_schedule(self.auth, self.config, {"sla_id": FAKE_SLA_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["sla_schedule"]["name"], "24/7 Schedule")

    @patch("servicenow_mcp.tools.sla_tools._resolve_sla_schedule_sys_id")
    def test_get_by_sla_id_not_found(self, mock_resolve):
        mock_resolve.return_value = None
        result = get_sla_schedule(self.auth, self.config, {"sla_id": "Unknown SLA"})
        self.assertFalse(result["success"])
        self.assertIn("Unknown SLA", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_fetch_404_returns_failure(self, mock_req):
        not_found = MagicMock()
        not_found.status_code = 404
        not_found.raise_for_status.return_value = None
        mock_req.return_value = not_found
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": FAKE_SCHEDULE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_fetch_empty_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": FAKE_SCHEDULE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_fetch_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": FAKE_SCHEDULE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving SLA schedule", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_fetch_request_exception_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": FAKE_SCHEDULE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving SLA schedule", result["message"])


# ---------------------------------------------------------------------------
# Validation-failure (return result) paths — lines 127, 325, 434, 714, 1229, 1327
# ---------------------------------------------------------------------------

class TestValidationFailurePaths(unittest.TestCase):
    def test_list_slas_invalid_limit(self):
        result = list_slas(
            _make_auth_manager(), _make_config(), {"limit": "not-an-int"}
        )
        self.assertFalse(result["success"])

    def test_list_sla_breach_definitions_invalid_limit(self):
        result = list_sla_breach_definitions(
            _make_auth_manager(), _make_config(), {"limit": "not-an-int"}
        )
        self.assertFalse(result["success"])

    def test_list_sla_breaches_invalid_limit(self):
        result = list_sla_breaches(
            _make_auth_manager(), _make_config(), {"limit": "not-an-int"}
        )
        self.assertFalse(result["success"])

    def test_list_incident_slas_invalid_limit(self):
        result = list_incident_slas(
            _make_auth_manager(), _make_config(), {"limit": "not-an-int"}
        )
        self.assertFalse(result["success"])

    def test_list_sla_schedules_invalid_limit(self):
        result = list_sla_schedules(
            _make_auth_manager(), _make_config(), {"limit": "not-an-int"}
        )
        self.assertFalse(result["success"])

    def test_get_sla_schedule_invalid_params_format(self):
        # Pass a non-dict that can't be converted to force the validation-failure path
        result = get_sla_schedule(_make_auth_manager(), _make_config(), 42)
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
