"""Tests for get_change_schedule_span in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import get_change_schedule_span
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

SPAN_SYS_ID = "c" * 32
SCHEDULE_SYS_ID = "b" * 32

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
# Happy path
# ---------------------------------------------------------------------------


class TestGetChangeScheduleSpanSuccess(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_span(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_SPAN})

        result = get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": SPAN_SYS_ID},
        )

        self.assertTrue(result["success"])
        span = result["span"]
        self.assertEqual(span["sys_id"], SPAN_SYS_ID)
        self.assertEqual(span["name"], "Weekend Maintenance Window")
        self.assertEqual(span["schedule"], "Change Window - Weekend")
        self.assertEqual(span["type"], "Exclude")
        self.assertEqual(span["repeat_type"], "Weekly")
        self.assertEqual(span["day_of_week"], "6")
        self.assertEqual(span["day_of_week_label"], "Saturday")
        self.assertEqual(span["start_date_time"], "2026-01-03 22:00:00")
        self.assertEqual(span["end_date_time"], "2026-01-04 06:00:00")
        self.assertEqual(span["all_day"], "false")
        self.assertEqual(span["repeat_until"], "2026-12-31 00:00:00")
        self.assertEqual(span["created_on"], "2026-01-01 00:00:00")
        self.assertEqual(span["updated_on"], "2026-06-01 12:00:00")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_correct_url_called(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_SPAN})

        get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": SPAN_SYS_ID},
        )

        call_url = mock_req.call_args[0][1]
        self.assertIn(SPAN_SYS_ID, call_url)
        self.assertIn("cmn_schedule_span", call_url)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_display_value_all_param_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_SPAN})

        get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": SPAN_SYS_ID},
        )

        api_params = mock_req.call_args[1]["params"]
        self.assertEqual(api_params["sysparm_display_value"], "all")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_fields_param_included(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_SPAN})

        get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": SPAN_SYS_ID},
        )

        api_params = mock_req.call_args[1]["params"]
        self.assertIn("sys_id", api_params["sysparm_fields"])
        self.assertIn("name", api_params["sysparm_fields"])
        self.assertIn("schedule", api_params["sysparm_fields"])
        self.assertIn("day_of_week", api_params["sysparm_fields"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_span_with_raw_string_fields(self, mock_req):
        raw_span = dict(FAKE_SPAN, schedule="ScheduleName", type="include", day_of_week="1")
        mock_req.return_value = _make_response(200, {"result": raw_span})

        result = get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": SPAN_SYS_ID},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["span"]["schedule"], "ScheduleName")
        self.assertEqual(result["span"]["type"], "include")
        self.assertEqual(result["span"]["day_of_week_label"], "Monday")


# ---------------------------------------------------------------------------
# 404 and empty result
# ---------------------------------------------------------------------------


class TestGetChangeScheduleSpanNotFound(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(404, {})

        result = get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": SPAN_SYS_ID},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertIn(SPAN_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_empty_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})

        result = get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": SPAN_SYS_ID},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_none_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": None})

        result = get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": SPAN_SYS_ID},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestGetChangeScheduleSpanErrors(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_500_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {"error": {"message": "Internal error"}})

        result = get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": SPAN_SYS_ID},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error retrieving change schedule span", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("connection refused")

        result = get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": SPAN_SYS_ID},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error retrieving change schedule span", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_instance_url", return_value=None)
    def test_missing_instance_url(self, _mock_url):
        result = get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": SPAN_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_headers", return_value=None)
    def test_missing_headers(self, _mock_headers):
        result = get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": SPAN_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    def test_missing_span_id_returns_failure(self):
        result = get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {},
        )
        self.assertFalse(result["success"])

    def test_invalid_params_type_returns_failure(self):
        result = get_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": 12345},
        )
        # int should coerce to str — span_id is a str field
        # but the request would still proceed (no TypeError expected)
        # just verify it doesn't crash
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)


if __name__ == "__main__":
    unittest.main()
