"""Tests for list_change_schedule_spans in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import (
    _format_change_schedule_span,
    list_change_schedule_spans,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
SCHEDULE_SYS_ID = "b" * 32
SPAN_SYS_ID = "c" * 32


FAKE_SPAN = {
    "sys_id": SPAN_SYS_ID,
    "name": "Weekend Maintenance Window",
    "schedule": {"display_value": "Change Window - Weekend", "value": SCHEDULE_SYS_ID},
    "type": {"display_value": "Exclude", "value": "exclude"},
    "repeat_type": {"display_value": "Weekly", "value": "weekly"},
    "day_of_week": {"display_value": "Saturday", "value": "6"},
    "start_date_time": "2026-01-03 22:00:00",
    "end_date_time": "2026-01-04 06:00:00",
    "all_day": "false",
    "repeat_until": "2026-12-31 00:00:00",
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
# _format_change_schedule_span
# ---------------------------------------------------------------------------


class TestFormatChangeScheduleSpan(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_change_schedule_span(FAKE_SPAN)
        self.assertEqual(result["sys_id"], SPAN_SYS_ID)
        self.assertEqual(result["name"], "Weekend Maintenance Window")
        self.assertEqual(result["schedule"], "Change Window - Weekend")
        self.assertEqual(result["type"], "Exclude")
        self.assertEqual(result["repeat_type"], "Weekly")
        self.assertEqual(result["day_of_week"], "6")
        self.assertEqual(result["day_of_week_label"], "Saturday")
        self.assertEqual(result["start_date_time"], "2026-01-03 22:00:00")
        self.assertEqual(result["end_date_time"], "2026-01-04 06:00:00")
        self.assertEqual(result["all_day"], "false")
        self.assertEqual(result["repeat_until"], "2026-12-31 00:00:00")
        self.assertEqual(result["created_on"], "2026-01-01 00:00:00")
        self.assertEqual(result["updated_on"], "2026-06-01 12:00:00")

    def test_handles_raw_string_day_of_week(self):
        record = dict(FAKE_SPAN, day_of_week="1")
        result = _format_change_schedule_span(record)
        self.assertEqual(result["day_of_week"], "1")
        self.assertEqual(result["day_of_week_label"], "Monday")

    def test_handles_raw_string_schedule(self):
        record = dict(FAKE_SPAN, schedule="SomeSchedule")
        result = _format_change_schedule_span(record)
        self.assertEqual(result["schedule"], "SomeSchedule")

    def test_handles_raw_string_type(self):
        record = dict(FAKE_SPAN, type="include")
        result = _format_change_schedule_span(record)
        self.assertEqual(result["type"], "include")

    def test_handles_missing_fields(self):
        result = _format_change_schedule_span({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["name"])
        self.assertIsNone(result["schedule"])
        self.assertIsNone(result["day_of_week"])
        self.assertIsNone(result["day_of_week_label"])
        self.assertIsNone(result["start_date_time"])
        self.assertIsNone(result["end_date_time"])

    def test_day_of_week_sunday(self):
        record = dict(FAKE_SPAN, day_of_week={"display_value": "Sunday", "value": "0"})
        result = _format_change_schedule_span(record)
        self.assertEqual(result["day_of_week_label"], "Sunday")

    def test_day_of_week_dict_value_fallback(self):
        record = dict(FAKE_SPAN, day_of_week={"display_value": None, "value": "3"})
        result = _format_change_schedule_span(record)
        self.assertEqual(result["day_of_week"], "3")
        self.assertEqual(result["day_of_week_label"], "Wednesday")

    def test_all_day_labels(self):
        for dow, label in [("0", "Sunday"), ("1", "Monday"), ("2", "Tuesday"),
                           ("3", "Wednesday"), ("4", "Thursday"), ("5", "Friday"), ("6", "Saturday")]:
            record = dict(FAKE_SPAN, day_of_week={"display_value": label, "value": dow})
            result = _format_change_schedule_span(record)
            self.assertEqual(result["day_of_week_label"], label)


# ---------------------------------------------------------------------------
# list_change_schedule_spans — no filters
# ---------------------------------------------------------------------------


class TestListChangeScheduleSpansNoFilter(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_SPAN]})

        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"limit": 20, "offset": 0},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])
        spans = result["spans"]
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]["sys_id"], SPAN_SYS_ID)
        self.assertEqual(spans[0]["name"], "Weekend Maintenance Window")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_empty_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["spans"], [])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_display_value_param_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedule_spans(_make_auth_manager(), _make_config(), {})

        api_params = mock_req.call_args[1]["params"]
        self.assertEqual(api_params["sysparm_display_value"], "all")


# ---------------------------------------------------------------------------
# list_change_schedule_spans — schedule_id filter
# ---------------------------------------------------------------------------


class TestListChangeScheduleSpansScheduleFilter(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._resolve_change_schedule_sys_id")
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_sys_id_filter(self, mock_req, mock_resolve):
        mock_resolve.return_value = SCHEDULE_SYS_ID
        mock_req.return_value = _make_response(200, {"result": [FAKE_SPAN]})

        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": SCHEDULE_SYS_ID},
        )

        self.assertTrue(result["success"])
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn(f"schedule={SCHEDULE_SYS_ID}", query)

    @patch("servicenow_mcp.tools.change_tools._resolve_change_schedule_sys_id")
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_name_resolved(self, mock_req, mock_resolve):
        mock_resolve.return_value = SCHEDULE_SYS_ID
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": "Change Window - Weekend"},
        )

        mock_resolve.assert_called_once()
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn(f"schedule={SCHEDULE_SYS_ID}", query)

    @patch("servicenow_mcp.tools.change_tools._resolve_change_schedule_sys_id")
    def test_schedule_not_found_returns_failure(self, mock_resolve):
        mock_resolve.return_value = None

        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": "nonexistent schedule"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])


# ---------------------------------------------------------------------------
# list_change_schedule_spans — individual filters
# ---------------------------------------------------------------------------


class TestListChangeScheduleSpansFilters(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_day_of_week_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"day_of_week": 6},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("day_of_week=6", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_day_of_week_zero_sunday(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"day_of_week": 0},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("day_of_week=0", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_repeat_type_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"repeat_type": "weekly"},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("repeat_type=weekly", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_name_query_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"name_query": "Weekend"},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("nameLIKEWeekend", query)

    @patch("servicenow_mcp.tools.change_tools._resolve_change_schedule_sys_id")
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_combined_filters(self, mock_req, mock_resolve):
        mock_resolve.return_value = SCHEDULE_SYS_ID
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {
                "schedule_id": SCHEDULE_SYS_ID,
                "day_of_week": 6,
                "repeat_type": "weekly",
                "name_query": "Maintenance",
            },
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn(f"schedule={SCHEDULE_SYS_ID}", query)
        self.assertIn("day_of_week=6", query)
        self.assertIn("repeat_type=weekly", query)
        self.assertIn("nameLIKEMaintenance", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_no_query_when_no_filters(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedule_spans(_make_auth_manager(), _make_config(), {})

        api_params = mock_req.call_args[1]["params"]
        self.assertNotIn("sysparm_query", api_params)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestListChangeScheduleSpansPagination(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_has_more_when_full_page(self, mock_req):
        records = [dict(FAKE_SPAN, sys_id=f"{i:032x}") for i in range(5)]
        mock_req.return_value = _make_response(200, {"result": records})

        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"limit": 5, "offset": 0},
        )

        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 5)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_no_has_more_when_partial_page(self, mock_req):
        records = [dict(FAKE_SPAN, sys_id=f"{i:032x}") for i in range(3)]
        mock_req.return_value = _make_response(200, {"result": records})

        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"limit": 5, "offset": 10},
        )

        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_offset_and_limit_passed_to_api(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"limit": 10, "offset": 30},
        )

        api_params = mock_req.call_args[1]["params"]
        self.assertEqual(api_params["sysparm_limit"], 10)
        self.assertEqual(api_params["sysparm_offset"], 30)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_fields_param_included(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_schedule_spans(_make_auth_manager(), _make_config(), {})

        api_params = mock_req.call_args[1]["params"]
        self.assertIn("sys_id", api_params["sysparm_fields"])
        self.assertIn("name", api_params["sysparm_fields"])
        self.assertIn("schedule", api_params["sysparm_fields"])
        self.assertIn("day_of_week", api_params["sysparm_fields"])
        self.assertIn("repeat_type", api_params["sysparm_fields"])


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestListChangeScheduleSpansErrors(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {"error": {"message": "Internal error"}})

        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error listing change schedule spans", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("connection refused")

        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error listing change schedule spans", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_instance_url", return_value=None)
    def test_missing_instance_url(self, _mock_url):
        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {},
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_headers", return_value=None)
    def test_missing_headers(self, _mock_headers):
        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {},
        )
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    def test_invalid_day_of_week_too_high(self):
        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"day_of_week": 7},
        )
        self.assertFalse(result["success"])

    def test_invalid_day_of_week_negative(self):
        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"day_of_week": -1},
        )
        self.assertFalse(result["success"])

    def test_invalid_params_returns_failure(self):
        result = list_change_schedule_spans(
            _make_auth_manager(),
            _make_config(),
            {"limit": "not_a_number"},
        )
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
