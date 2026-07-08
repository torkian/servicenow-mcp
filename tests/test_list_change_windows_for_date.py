"""Tests for list_change_windows_for_date in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import list_change_windows_for_date
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
SCHEDULE_SYS_ID = "b" * 32
SPAN_SYS_ID = "c" * 32

FAKE_SPAN = {
    "sys_id": SPAN_SYS_ID,
    "name": "Tuesday Maintenance Window",
    "schedule": {"display_value": "Change Window - Weekly", "value": SCHEDULE_SYS_ID},
    "type": {"display_value": "Include", "value": "include"},
    "repeat_type": {"display_value": "Weekly", "value": "weekly"},
    "day_of_week": {"display_value": "Tuesday", "value": "2"},
    "start_date_time": "2026-01-06 22:00:00",
    "end_date_time": "2026-01-07 06:00:00",
    "all_day": "false",
    "repeat_until": "2026-12-31 00:00:00",
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-06-01 12:00:00",
}

FAKE_NONREPEATING_SPAN = {
    "sys_id": FAKE_SYS_ID,
    "name": "One-Off Maintenance",
    "schedule": {"display_value": "Ad-Hoc", "value": SCHEDULE_SYS_ID},
    "type": {"display_value": "Include", "value": "include"},
    "repeat_type": {"display_value": "None", "value": "none"},
    "day_of_week": None,
    "start_date_time": "2026-07-08 00:00:00",
    "end_date_time": "2026-07-08 23:59:59",
    "all_day": "true",
    "repeat_until": "",
    "sys_created_on": "2026-07-01 00:00:00",
    "sys_updated_on": "2026-07-01 12:00:00",
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
# Basic success path
# ---------------------------------------------------------------------------


class TestListChangeWindowsForDateSuccess(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_windows(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SPAN]})

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["query_date"], "2026-07-08")
        self.assertEqual(result["count"], 1)
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])
        self.assertIn("windows", result)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_empty_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["windows"], [])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_includes_day_of_week_metadata(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        # 2026-07-08 is a Wednesday (Python weekday 2 → SN weekday 3)
        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["day_of_week"], 3)
        self.assertEqual(result["day_of_week_label"], "Wednesday")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_sunday_mapped_to_sn_zero(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        # 2026-07-12 is a Sunday
        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-12"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["day_of_week"], 0)
        self.assertEqual(result["day_of_week_label"], "Sunday")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_monday_mapped_to_sn_one(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        # 2026-07-06 is a Monday
        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-06"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["day_of_week"], 1)
        self.assertEqual(result["day_of_week_label"], "Monday")


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------


class TestListChangeWindowsForDateQuery(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_nq_query_includes_three_groups(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        api_params = mock_req.call_args[1]["params"]
        query = api_params["sysparm_query"]
        # Three ^NQ groups
        self.assertEqual(query.count("^NQ"), 2)
        # Non-repeating group
        self.assertIn("repeat_type=none", query)
        # Weekly group with correct day (Wednesday=3)
        self.assertIn("repeat_type=weekly", query)
        self.assertIn("day_of_week=3", query)
        # Daily group
        self.assertIn("repeat_type=daily", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_date_bounds_in_query(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        api_params = mock_req.call_args[1]["params"]
        query = api_params["sysparm_query"]
        self.assertIn("2026-07-08 23:59:59", query)
        self.assertIn("2026-07-08 00:00:00", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_display_value_param_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_windows_for_date(_make_auth_manager(), _make_config(), {"query_date": "2026-07-08"})

        api_params = mock_req.call_args[1]["params"]
        self.assertEqual(api_params["sysparm_display_value"], "all")


# ---------------------------------------------------------------------------
# schedule_id scoping
# ---------------------------------------------------------------------------


class TestListChangeWindowsForDateScheduleFilter(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._resolve_change_schedule_sys_id")
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_id_prepended_to_each_group(self, mock_req, mock_resolve):
        mock_resolve.return_value = SCHEDULE_SYS_ID
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08", "schedule_id": SCHEDULE_SYS_ID},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        # schedule= appears in each of the 3 NQ groups
        self.assertEqual(query.count(f"schedule={SCHEDULE_SYS_ID}"), 3)

    @patch("servicenow_mcp.tools.change_tools._resolve_change_schedule_sys_id")
    def test_schedule_not_found_returns_failure(self, mock_resolve):
        mock_resolve.return_value = None

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08", "schedule_id": "No Such Schedule"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.change_tools._resolve_change_schedule_sys_id")
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_name_resolved(self, mock_req, mock_resolve):
        mock_resolve.return_value = SCHEDULE_SYS_ID
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08", "schedule_id": "Change Window - Weekly"},
        )

        mock_resolve.assert_called_once()
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn(f"schedule={SCHEDULE_SYS_ID}", query)


# ---------------------------------------------------------------------------
# repeat_until post-filtering
# ---------------------------------------------------------------------------


class TestListChangeWindowsForDateExpiredFilter(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_expired_span_filtered_out(self, mock_req):
        expired_span = dict(FAKE_SPAN, repeat_until="2026-01-01 00:00:00")
        mock_req.return_value = _make_response(200, {"result": [expired_span]})

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_active_span_not_filtered(self, mock_req):
        active_span = dict(FAKE_SPAN, repeat_until="2026-12-31 00:00:00")
        mock_req.return_value = _make_response(200, {"result": [active_span]})

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_empty_repeat_until_not_filtered(self, mock_req):
        # Empty repeat_until means no expiry
        span = dict(FAKE_SPAN, repeat_until="")
        mock_req.return_value = _make_response(200, {"result": [span]})

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_none_repeat_until_not_filtered(self, mock_req):
        span = dict(FAKE_SPAN, repeat_until=None)
        mock_req.return_value = _make_response(200, {"result": [span]})

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_repeat_until_as_dict_expired(self, mock_req):
        span = dict(FAKE_SPAN, repeat_until={"value": "2026-01-01 00:00:00", "display_value": "2026-01-01"})
        mock_req.return_value = _make_response(200, {"result": [span]})

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_repeat_until_as_dict_active(self, mock_req):
        span = dict(FAKE_SPAN, repeat_until={"value": "2027-01-01 00:00:00", "display_value": "2027-01-01"})
        mock_req.return_value = _make_response(200, {"result": [span]})

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestListChangeWindowsForDatePagination(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_has_more_when_over_limit(self, mock_req):
        records = [dict(FAKE_SPAN, sys_id=f"{i:032x}", repeat_until="2027-01-01 00:00:00") for i in range(6)]
        mock_req.return_value = _make_response(200, {"result": records})

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08", "limit": 5, "offset": 0},
        )

        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 5)
        self.assertEqual(result["count"], 5)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_no_has_more_when_partial_page(self, mock_req):
        records = [dict(FAKE_SPAN, sys_id=f"{i:032x}", repeat_until="2027-01-01 00:00:00") for i in range(3)]
        mock_req.return_value = _make_response(200, {"result": records})

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08", "limit": 5, "offset": 0},
        )

        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_offset_applied_to_filtered_results(self, mock_req):
        records = [dict(FAKE_SPAN, sys_id=f"{i:032x}", repeat_until="2027-01-01 00:00:00") for i in range(10)]
        mock_req.return_value = _make_response(200, {"result": records})

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08", "limit": 3, "offset": 5},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestListChangeWindowsForDateValidation(unittest.TestCase):
    def test_missing_query_date_returns_failure(self):
        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {},
        )
        self.assertFalse(result["success"])

    def test_invalid_date_format_returns_failure(self):
        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "08-07-2026"},
        )
        self.assertFalse(result["success"])

    def test_invalid_date_string_returns_failure(self):
        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "not-a-date"},
        )
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestListChangeWindowsForDateErrors(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {"error": {"message": "Server error"}})

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error listing change windows", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")

        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error listing change windows", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_instance_url", return_value=None)
    def test_missing_instance_url(self, _mock):
        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_headers", return_value=None)
    def test_missing_headers(self, _mock):
        result = list_change_windows_for_date(
            _make_auth_manager(),
            _make_config(),
            {"query_date": "2026-07-08"},
        )
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


if __name__ == "__main__":
    unittest.main()
