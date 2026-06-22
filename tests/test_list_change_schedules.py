"""Tests for list_change_schedules in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import (
    _format_change_schedule,
    list_change_schedules,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
PARENT_SYS_ID = "b" * 32


FAKE_SCHEDULE = {
    "sys_id": FAKE_SYS_ID,
    "name": "Change Window - Weekend",
    "description": "Saturday and Sunday change window",
    "type": {"display_value": "Change Window", "value": "change_window"},
    "time_zone": "US/Eastern",
    "active": "true",
    "parent": {"display_value": "Global Change Windows", "value": PARENT_SYS_ID},
    "sys_created_by": "admin",
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-06-01 12:00:00",
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
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


# ---------------------------------------------------------------------------
# _format_change_schedule
# ---------------------------------------------------------------------------


class TestFormatChangeSchedule(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_change_schedule(FAKE_SCHEDULE)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["name"], "Change Window - Weekend")
        self.assertEqual(result["description"], "Saturday and Sunday change window")
        self.assertEqual(result["type"], "Change Window")
        self.assertEqual(result["time_zone"], "US/Eastern")
        self.assertEqual(result["active"], "true")
        self.assertEqual(result["parent"], "Global Change Windows")
        self.assertEqual(result["created_by"], "admin")
        self.assertEqual(result["created_on"], "2026-01-01 00:00:00")
        self.assertEqual(result["updated_on"], "2026-06-01 12:00:00")

    def test_handles_raw_string_type(self):
        record = dict(FAKE_SCHEDULE, type="change_window")
        result = _format_change_schedule(record)
        self.assertEqual(result["type"], "change_window")

    def test_handles_raw_string_parent(self):
        record = dict(FAKE_SCHEDULE, parent="Global")
        result = _format_change_schedule(record)
        self.assertEqual(result["parent"], "Global")

    def test_handles_missing_fields(self):
        result = _format_change_schedule({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["name"])
        self.assertIsNone(result["description"])
        self.assertIsNone(result["type"])
        self.assertIsNone(result["time_zone"])
        self.assertIsNone(result["active"])
        self.assertIsNone(result["parent"])
        self.assertIsNone(result["created_by"])
        self.assertIsNone(result["created_on"])
        self.assertIsNone(result["updated_on"])

    def test_dict_type_value_fallback(self):
        record = dict(FAKE_SCHEDULE, type={"display_value": None, "value": "change_window"})
        result = _format_change_schedule(record)
        self.assertEqual(result["type"], "change_window")

    def test_dict_parent_value_fallback(self):
        record = dict(FAKE_SCHEDULE, parent={"display_value": None, "value": PARENT_SYS_ID})
        result = _format_change_schedule(record)
        self.assertEqual(result["parent"], PARENT_SYS_ID)


# ---------------------------------------------------------------------------
# list_change_schedules — no filters
# ---------------------------------------------------------------------------


class TestListChangeSchedulesNoFilter(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SCHEDULE]})

        result = list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {"limit": 20, "offset": 0},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])
        schedules = result["schedules"]
        self.assertEqual(len(schedules), 1)
        self.assertEqual(schedules[0]["sys_id"], FAKE_SYS_ID)
        self.assertEqual(schedules[0]["name"], "Change Window - Weekend")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_empty_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        result = list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["schedules"], [])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_no_query_param_when_no_filters(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedules(_make_auth_manager(), _make_config(), {})

        params = mock_req.call_args[1]["params"]
        self.assertNotIn("sysparm_query", params)


# ---------------------------------------------------------------------------
# list_change_schedules — individual filters
# ---------------------------------------------------------------------------


class TestListChangeSchedulesFilters(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_name_query_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SCHEDULE]})

        list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {"name_query": "Weekend"},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("nameLIKEWeekend", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_type_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SCHEDULE]})

        list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {"schedule_type": "change_window"},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("type=change_window", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_active_true_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SCHEDULE]})

        list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {"active": True},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("active=true", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_active_false_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {"active": False},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("active=false", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_time_zone_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SCHEDULE]})

        list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {"time_zone": "US/Eastern"},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("time_zone=US/Eastern", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_combined_filters(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SCHEDULE]})

        list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {
                "name_query": "Change",
                "schedule_type": "change_window",
                "active": True,
                "time_zone": "UTC",
            },
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("nameLIKEChange", query)
        self.assertIn("type=change_window", query)
        self.assertIn("active=true", query)
        self.assertIn("time_zone=UTC", query)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestListChangeSchedulesPagination(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_has_more_when_full_page(self, mock_req):
        records = [dict(FAKE_SCHEDULE, sys_id=f"{i:032x}") for i in range(5)]
        mock_req.return_value = _make_response(200, {"result": records})

        result = list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {"limit": 5, "offset": 0},
        )

        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 5)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_no_has_more_when_partial_page(self, mock_req):
        records = [dict(FAKE_SCHEDULE, sys_id=f"{i:032x}") for i in range(3)]
        mock_req.return_value = _make_response(200, {"result": records})

        result = list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {"limit": 5, "offset": 10},
        )

        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_offset_and_limit_passed_to_api(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {"limit": 10, "offset": 30},
        )

        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["sysparm_limit"], 10)
        self.assertEqual(params["sysparm_offset"], 30)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_fields_param_included(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedules(_make_auth_manager(), _make_config(), {})

        params = mock_req.call_args[1]["params"]
        self.assertIn("sys_id", params["sysparm_fields"])
        self.assertIn("name", params["sysparm_fields"])
        self.assertIn("type", params["sysparm_fields"])
        self.assertIn("time_zone", params["sysparm_fields"])
        self.assertIn("active", params["sysparm_fields"])


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestListChangeSchedulesErrors(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {"error": {"message": "Internal error"}})

        result = list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error listing change schedules", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("connection refused")

        result = list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error listing change schedules", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_instance_url", return_value=None)
    def test_missing_instance_url(self, _mock_url):
        result = list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {},
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_headers", return_value=None)
    def test_missing_headers(self, _mock_headers):
        result = list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {},
        )
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    def test_invalid_params_returns_failure(self):
        result = list_change_schedules(
            _make_auth_manager(),
            _make_config(),
            {"limit": "not_a_number"},
        )
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
