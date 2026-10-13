"""Tests for list_sla_exceptions in sla_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.sla_tools import list_sla_exceptions
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SCHEDULE_SYS_ID = "b" * 32
FAKE_SLA_SYS_ID = "a" * 32

FAKE_EXCEPTION = {
    "sys_id": "e" * 32,
    "name": "Christmas Blackout",
    "schedule": {"display_value": "24/7 Schedule", "value": FAKE_SCHEDULE_SYS_ID},
    "type": "on",
    "repeat_type": "yearly",
    "day_of_week": "",
    "start_date_time": "2026-12-25 00:00:00",
    "end_date_time": "2026-12-26 00:00:00",
    "all_day": "true",
    "repeat_until": "",
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


def _make_response(status_code=200, json_data=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp
        )
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


class TestListSLAExceptions(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    # ── no-scope: all type=on spans ──────────────────────────────────────────

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_all_exceptions(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": [FAKE_EXCEPTION]})
        result = list_sla_exceptions(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["sla_exceptions"]), 1)
        self.assertEqual(result["sla_exceptions"][0]["name"], "Christmas Blackout")
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("type=on", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_exceptions_empty(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": []})
        result = list_sla_exceptions(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertTrue(result["success"])
        self.assertEqual(result["sla_exceptions"], [])
        self.assertEqual(result["count"], 0)

    # ── name_query filter ────────────────────────────────────────────────────

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_exceptions_name_query(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": [FAKE_EXCEPTION]})
        result = list_sla_exceptions(
            self.auth, self.config, {"name_query": "Christmas", "limit": 20, "offset": 0}
        )
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("nameLIKEChristmas", call_params.get("sysparm_query", ""))

    # ── repeat_type filter ───────────────────────────────────────────────────

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_exceptions_repeat_type(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": [FAKE_EXCEPTION]})
        result = list_sla_exceptions(
            self.auth, self.config, {"repeat_type": "yearly", "limit": 20, "offset": 0}
        )
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("repeat_type=yearly", call_params.get("sysparm_query", ""))

    # ── scope by schedule_id (sys_id passthrough) ───────────────────────────

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_scoped_to_schedule_sys_id(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": [FAKE_EXCEPTION]})
        result = list_sla_exceptions(
            self.auth,
            self.config,
            {"schedule_id": FAKE_SCHEDULE_SYS_ID, "limit": 20, "offset": 0},
        )
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn(f"schedule={FAKE_SCHEDULE_SYS_ID}", call_params.get("sysparm_query", ""))

    # ── scope by schedule_id (name lookup) ──────────────────────────────────

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_scoped_to_schedule_name(self, mock_req):
        # Call 1: resolve schedule name → sys_id
        name_resp = _make_response(json_data={"result": [{"sys_id": FAKE_SCHEDULE_SYS_ID}]})
        # Call 2: fetch exceptions
        spans_resp = _make_response(json_data={"result": [FAKE_EXCEPTION]})
        mock_req.side_effect = [name_resp, spans_resp]

        result = list_sla_exceptions(
            self.auth,
            self.config,
            {"schedule_id": "24/7 Schedule", "limit": 20, "offset": 0},
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["sla_exceptions"]), 1)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_schedule_name_not_found(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": []})
        result = list_sla_exceptions(
            self.auth,
            self.config,
            {"schedule_id": "Nonexistent Schedule", "limit": 20, "offset": 0},
        )
        self.assertFalse(result["success"])
        self.assertIn("Schedule not found", result["message"])

    # ── scope by sla_id (sys_id, schedule field present) ────────────────────

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_scoped_to_sla_sys_id(self, mock_req):
        # Call 1: fetch SLA record to read schedule field
        sla_resp = _make_response(
            json_data={"result": {"schedule": {"value": FAKE_SCHEDULE_SYS_ID}}}
        )
        # Call 2: fetch exceptions
        spans_resp = _make_response(json_data={"result": [FAKE_EXCEPTION]})
        mock_req.side_effect = [sla_resp, spans_resp]

        result = list_sla_exceptions(
            self.auth,
            self.config,
            {"sla_id": FAKE_SLA_SYS_ID, "limit": 20, "offset": 0},
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["sla_exceptions"]), 1)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_scoped_to_sla_name(self, mock_req):
        # Call 1: SLA name → sys_id
        name_lookup = _make_response(json_data={"result": [{"sys_id": FAKE_SLA_SYS_ID}]})
        # Call 2: SLA schedule field
        sla_resp = _make_response(
            json_data={"result": {"schedule": FAKE_SCHEDULE_SYS_ID}}
        )
        # Call 3: exceptions
        spans_resp = _make_response(json_data={"result": [FAKE_EXCEPTION]})
        mock_req.side_effect = [name_lookup, sla_resp, spans_resp]

        result = list_sla_exceptions(
            self.auth,
            self.config,
            {"sla_id": "Priority 1 SLA", "limit": 20, "offset": 0},
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["sla_exceptions"]), 1)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_sla_not_found(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": []})
        result = list_sla_exceptions(
            self.auth,
            self.config,
            {"sla_id": "Nonexistent SLA", "limit": 20, "offset": 0},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_sla_no_schedule_assigned(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": {"schedule": ""}})
        result = list_sla_exceptions(
            self.auth,
            self.config,
            {"sla_id": FAKE_SLA_SYS_ID, "limit": 20, "offset": 0},
        )
        self.assertFalse(result["success"])
        self.assertIn("no schedule assigned", result["message"])

    # ── error paths ──────────────────────────────────────────────────────────

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_http_error(self, mock_req):
        mock_req.return_value = _make_response(status_code=500)
        result = list_sla_exceptions(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertFalse(result["success"])
        self.assertIn("Error listing SLA exceptions", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_sla_exceptions(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertFalse(result["success"])
        self.assertIn("Error listing SLA exceptions", result["message"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = list_sla_exceptions(auth, config, {"limit": 20, "offset": 0})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev99999.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"
        result = list_sla_exceptions(auth, config, {"limit": 20, "offset": 0})
        self.assertFalse(result["success"])

    # ── normalisation helpers ─────────────────────────────────────────────────

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_format_day_of_week_label(self, mock_req):
        exc = dict(FAKE_EXCEPTION, day_of_week="1", repeat_type="weekly")
        mock_req.return_value = _make_response(json_data={"result": [exc]})
        result = list_sla_exceptions(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertTrue(result["success"])
        item = result["sla_exceptions"][0]
        self.assertEqual(item["day_of_week"], "1")
        self.assertEqual(item["day_of_week_label"], "Monday")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_format_day_of_week_dict(self, mock_req):
        exc = dict(FAKE_EXCEPTION, day_of_week={"value": "5", "display_value": "Friday"})
        mock_req.return_value = _make_response(json_data={"result": [exc]})
        result = list_sla_exceptions(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertTrue(result["success"])
        item = result["sla_exceptions"][0]
        self.assertEqual(item["day_of_week"], "5")
        self.assertEqual(item["day_of_week_label"], "Friday")

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_format_none_day_of_week(self, mock_req):
        exc = dict(FAKE_EXCEPTION, day_of_week=None)
        mock_req.return_value = _make_response(json_data={"result": [exc]})
        result = list_sla_exceptions(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertTrue(result["success"])
        self.assertIsNone(result["sla_exceptions"][0]["day_of_week_label"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_format_schedule_display_value(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": [FAKE_EXCEPTION]})
        result = list_sla_exceptions(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertTrue(result["success"])
        self.assertEqual(result["sla_exceptions"][0]["schedule"], "24/7 Schedule")

    # ── pagination ────────────────────────────────────────────────────────────

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_pagination(self, mock_req):
        items = [dict(FAKE_EXCEPTION, sys_id=f"{'e' * 31}{i}") for i in range(5)]
        mock_req.return_value = _make_response(json_data={"result": items})
        result = list_sla_exceptions(self.auth, self.config, {"limit": 5, "offset": 0})
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 5)

    # ── combined filters ──────────────────────────────────────────────────────

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_combined_name_and_repeat_type(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": [FAKE_EXCEPTION]})
        result = list_sla_exceptions(
            self.auth,
            self.config,
            {"name_query": "Holiday", "repeat_type": "yearly", "limit": 20, "offset": 0},
        )
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        query = call_params.get("sysparm_query", "")
        self.assertIn("nameLIKEHoliday", query)
        self.assertIn("repeat_type=yearly", query)
        self.assertIn("type=on", query)


if __name__ == "__main__":
    unittest.main()
