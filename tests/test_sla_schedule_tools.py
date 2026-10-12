"""Tests for list_sla_schedules and get_sla_schedule in sla_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.sla_tools import (
    get_sla_schedule,
    list_sla_schedules,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "c" * 32
FAKE_SLA_SYS_ID = "a" * 32
FAKE_SCHEDULE_SYS_ID = "b" * 32
FAKE_SCHEDULE_NAME = "Business Hours"

FAKE_SCHEDULE = {
    "sys_id": FAKE_SCHEDULE_SYS_ID,
    "name": FAKE_SCHEDULE_NAME,
    "description": "Mon-Fri 9-5",
    "type": "business_hours",
    "time_zone": "US/Eastern",
    "active": "true",
    "parent": "",
    "sys_created_by": "admin",
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


class TestListSLASchedules(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_all_schedules(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": [FAKE_SCHEDULE]})
        result = list_sla_schedules(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["sla_schedules"]), 1)
        self.assertEqual(result["sla_schedules"][0]["name"], FAKE_SCHEDULE_NAME)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_schedules_with_name_query(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": [FAKE_SCHEDULE]})
        result = list_sla_schedules(
            self.auth, self.config, {"name_query": "Business", "limit": 20, "offset": 0}
        )
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("nameLIKEBusiness", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_schedules_active_filter(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": [FAKE_SCHEDULE]})
        result = list_sla_schedules(
            self.auth, self.config, {"active": True, "limit": 20, "offset": 0}
        )
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=true", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_schedules_time_zone_filter(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": [FAKE_SCHEDULE]})
        result = list_sla_schedules(
            self.auth, self.config, {"time_zone": "US/Eastern", "limit": 20, "offset": 0}
        )
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("time_zone=US/Eastern", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_schedules_scoped_to_sla(self, mock_req):
        # First call resolves the SLA (schedule field lookup)
        sla_record_resp = _make_response(
            json_data={"result": {"schedule": {"value": FAKE_SCHEDULE_SYS_ID}}}
        )
        # Second call lists schedules filtered to that sys_id
        schedules_resp = _make_response(json_data={"result": [FAKE_SCHEDULE]})
        mock_req.side_effect = [sla_record_resp, schedules_resp]

        result = list_sla_schedules(
            self.auth, self.config, {"sla_id": FAKE_SLA_SYS_ID, "limit": 20, "offset": 0}
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["sla_schedules"]), 1)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_schedules_sla_name_resolved(self, mock_req):
        # Call 1: resolve name -> sys_id
        name_lookup = _make_response(
            json_data={"result": [{"sys_id": FAKE_SLA_SYS_ID}]}
        )
        # Call 2: fetch SLA schedule field
        sla_schedule_field = _make_response(
            json_data={"result": {"schedule": FAKE_SCHEDULE_SYS_ID}}
        )
        # Call 3: list schedules
        schedules_resp = _make_response(json_data={"result": [FAKE_SCHEDULE]})
        mock_req.side_effect = [name_lookup, sla_schedule_field, schedules_resp]

        result = list_sla_schedules(
            self.auth, self.config, {"sla_id": "Priority 1 SLA", "limit": 20, "offset": 0}
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_schedules_sla_not_found(self, mock_req):
        # First call: SLA name resolve returns nothing
        mock_req.return_value = _make_response(json_data={"result": []})
        result = list_sla_schedules(
            self.auth, self.config, {"sla_id": "Nonexistent SLA", "limit": 20, "offset": 0}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_schedules_sla_no_schedule_assigned(self, mock_req):
        # Call 1: resolve sys_id (passthrough)
        # Call 2: SLA record has empty schedule field
        sla_record_resp = _make_response(
            json_data={"result": {"schedule": ""}}
        )
        mock_req.return_value = sla_record_resp

        result = list_sla_schedules(
            self.auth, self.config, {"sla_id": FAKE_SLA_SYS_ID, "limit": 20, "offset": 0}
        )
        self.assertFalse(result["success"])
        self.assertIn("no schedule assigned", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_schedules_http_error(self, mock_req):
        mock_req.return_value = _make_response(status_code=500)
        result = list_sla_schedules(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertFalse(result["success"])
        self.assertIn("Error listing SLA schedules", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_schedules_empty_result(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": []})
        result = list_sla_schedules(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertTrue(result["success"])
        self.assertEqual(result["sla_schedules"], [])

    def test_list_schedules_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = list_sla_schedules(auth, config, {"limit": 20, "offset": 0})
        self.assertFalse(result["success"])

    def test_list_schedules_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev99999.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"
        result = list_sla_schedules(auth, config, {"limit": 20, "offset": 0})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_schedules_request_exception(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_sla_schedules(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertFalse(result["success"])
        self.assertIn("Error listing SLA schedules", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_list_schedules_pagination(self, mock_req):
        schedules = [dict(FAKE_SCHEDULE, sys_id=f"{'c' * 31}{i}") for i in range(5)]
        mock_req.return_value = _make_response(json_data={"result": schedules})
        result = list_sla_schedules(self.auth, self.config, {"limit": 5, "offset": 0})
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 5)


class TestGetSLASchedule(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    def test_missing_both_params(self):
        result = get_sla_schedule(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("must be provided", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_schedule_sys_id(self, mock_req):
        mock_req.return_value = _make_response(
            json_data={"result": FAKE_SCHEDULE}
        )
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": FAKE_SCHEDULE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sla_schedule"]["name"], FAKE_SCHEDULE_NAME)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_schedule_name(self, mock_req):
        # Call 1: name -> sys_id lookup
        name_lookup = _make_response(
            json_data={"result": [{"sys_id": FAKE_SCHEDULE_SYS_ID}]}
        )
        # Call 2: fetch the schedule record
        fetch_resp = _make_response(json_data={"result": FAKE_SCHEDULE})
        mock_req.side_effect = [name_lookup, fetch_resp]

        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": FAKE_SCHEDULE_NAME}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sla_schedule"]["name"], FAKE_SCHEDULE_NAME)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_schedule_name_not_found(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": []})
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": "No Such Schedule"}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_sla_id(self, mock_req):
        # Call 1: SLA record schedule field
        sla_resp = _make_response(
            json_data={"result": {"schedule": {"value": FAKE_SCHEDULE_SYS_ID}}}
        )
        # Call 2: fetch the schedule
        sched_resp = _make_response(json_data={"result": FAKE_SCHEDULE})
        mock_req.side_effect = [sla_resp, sched_resp]

        result = get_sla_schedule(
            self.auth, self.config, {"sla_id": FAKE_SLA_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sla_schedule"]["name"], FAKE_SCHEDULE_NAME)

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_sla_name(self, mock_req):
        # Call 1: SLA name -> sys_id
        sla_name_lookup = _make_response(
            json_data={"result": [{"sys_id": FAKE_SLA_SYS_ID}]}
        )
        # Call 2: SLA record schedule field
        sla_resp = _make_response(
            json_data={"result": {"schedule": FAKE_SCHEDULE_SYS_ID}}
        )
        # Call 3: fetch the schedule
        sched_resp = _make_response(json_data={"result": FAKE_SCHEDULE})
        mock_req.side_effect = [sla_name_lookup, sla_resp, sched_resp]

        result = get_sla_schedule(
            self.auth, self.config, {"sla_id": "Priority 1 SLA"}
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_sla_not_found(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": []})
        result = get_sla_schedule(
            self.auth, self.config, {"sla_id": "Nonexistent SLA"}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_schedule_404(self, mock_req):
        mock_req.return_value = _make_response(status_code=404)
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": FAKE_SCHEDULE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_schedule_empty_result(self, mock_req):
        mock_req.return_value = _make_response(json_data={"result": {}})
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": FAKE_SCHEDULE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_schedule_http_error(self, mock_req):
        mock_req.return_value = _make_response(status_code=500)
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": FAKE_SCHEDULE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving SLA schedule", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_schedule_request_exception(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": FAKE_SCHEDULE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving SLA schedule", result["message"])

    def test_get_schedule_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = get_sla_schedule(auth, config, {"schedule_id": FAKE_SCHEDULE_SYS_ID})
        self.assertFalse(result["success"])

    def test_get_schedule_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev99999.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"
        result = get_sla_schedule(auth, config, {"schedule_id": FAKE_SCHEDULE_SYS_ID})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_get_by_schedule_name_lookup_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": "Business Hours"}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error looking up schedule", result["message"])

    @patch("servicenow_mcp.tools.sla_tools._make_request")
    def test_format_sla_schedule_dict_fields(self, mock_req):
        schedule_with_dicts = dict(FAKE_SCHEDULE)
        schedule_with_dicts["type"] = {"display_value": "Business Hours", "value": "bh"}
        schedule_with_dicts["parent"] = {"display_value": "Global", "value": "global_sys_id"}
        mock_req.return_value = _make_response(json_data={"result": schedule_with_dicts})
        result = get_sla_schedule(
            self.auth, self.config, {"schedule_id": FAKE_SCHEDULE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sla_schedule"]["type"], "Business Hours")
        self.assertEqual(result["sla_schedule"]["parent"], "Global")


if __name__ == "__main__":
    unittest.main()
