"""Tests for create_change_schedule_span in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import create_change_schedule_span
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
SCHEDULE_SYS_ID = "b" * 32

FAKE_CREATED_SPAN = {
    "sys_id": FAKE_SYS_ID,
    "name": "Saturday Night Window",
    "schedule": {"display_value": "Change Window - Prod", "value": SCHEDULE_SYS_ID},
    "type": {"display_value": "Include", "value": "include"},
    "repeat_type": "weekly",
    "day_of_week": "6",
    "start_date_time": "2026-07-12 22:00:00",
    "end_date_time": "2026-07-13 06:00:00",
    "all_day": "false",
    "repeat_until": "2027-01-01",
    "sys_created_on": "2026-07-12 00:00:00",
    "sys_updated_on": "2026-07-12 00:00:00",
}

BASE_PARAMS = {
    "name": "Saturday Night Window",
    "schedule": SCHEDULE_SYS_ID,
    "start_date_time": "2026-07-12 22:00:00",
    "end_date_time": "2026-07-13 06:00:00",
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


def _make_response(status_code, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestCreateChangeScheduleSpanSuccess(unittest.TestCase):
    """Happy-path tests."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_create_minimal(self, mock_req):
        """Only required fields — schedule is a sys_id so no resolver lookup."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SPAN})
        result = create_change_schedule_span(_make_auth_manager(), _make_config(), BASE_PARAMS)
        self.assertTrue(result["success"])
        self.assertIn("span", result)
        self.assertEqual(result["span"]["name"], "Saturday Night Window")
        self.assertEqual(result["span"]["sys_id"], FAKE_SYS_ID)
        # Only one request: the POST (32-char hex schedule bypasses resolver)
        self.assertEqual(mock_req.call_count, 1)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_create_with_all_optional_fields(self, mock_req):
        """All optional fields included."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SPAN})
        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {
                **BASE_PARAMS,
                "repeat_type": "weekly",
                "day_of_week": 6,
                "all_day": False,
                "repeat_until": "2027-01-01",
                "span_type": "include",
            },
        )
        self.assertTrue(result["success"])
        called_body = mock_req.call_args[1]["json"]
        self.assertEqual(called_body["repeat_type"], "weekly")
        self.assertEqual(called_body["day_of_week"], "6")
        self.assertEqual(called_body["all_day"], "false")
        self.assertEqual(called_body["repeat_until"], "2027-01-01")
        self.assertEqual(called_body["type"], "include")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_create_with_schedule_name(self, mock_req):
        """Schedule provided as name — resolver GET then POST."""
        resolve_resp = _make_response(200, {"result": [{"sys_id": SCHEDULE_SYS_ID}]})
        create_resp = _make_response(201, {"result": FAKE_CREATED_SPAN})
        mock_req.side_effect = [resolve_resp, create_resp]

        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {**BASE_PARAMS, "schedule": "Change Window - Prod"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(mock_req.call_count, 2)
        called_body = mock_req.call_args[1]["json"]
        self.assertEqual(called_body["schedule"], SCHEDULE_SYS_ID)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_message_contains_span_name(self, mock_req):
        """Response message should include the new span's name."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SPAN})
        result = create_change_schedule_span(_make_auth_manager(), _make_config(), BASE_PARAMS)
        self.assertIn("Saturday Night Window", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_span_fields_normalised(self, mock_req):
        """_format_change_schedule_span should flatten schedule dict and set day_of_week_label."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SPAN})
        result = create_change_schedule_span(_make_auth_manager(), _make_config(), BASE_PARAMS)
        span = result["span"]
        self.assertEqual(span["schedule"], "Change Window - Prod")
        self.assertEqual(span["day_of_week"], "6")
        self.assertEqual(span["day_of_week_label"], "Saturday")
        self.assertEqual(span["start_date_time"], "2026-07-12 22:00:00")
        self.assertEqual(span["end_date_time"], "2026-07-13 06:00:00")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_content_type_header_set(self, mock_req):
        """Content-Type: application/json must be set for POST."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SPAN})
        create_change_schedule_span(_make_auth_manager(), _make_config(), BASE_PARAMS)
        sent_headers = mock_req.call_args[1]["headers"]
        self.assertEqual(sent_headers.get("Content-Type"), "application/json")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_all_day_true_serialised_as_string(self, mock_req):
        """all_day=True must be sent as the string 'true'."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SPAN})
        create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {**BASE_PARAMS, "all_day": True},
        )
        called_body = mock_req.call_args[1]["json"]
        self.assertEqual(called_body["all_day"], "true")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_required_fields_in_body(self, mock_req):
        """name, schedule, start_date_time, end_date_time must always be in the body."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SPAN})
        create_change_schedule_span(_make_auth_manager(), _make_config(), BASE_PARAMS)
        called_body = mock_req.call_args[1]["json"]
        self.assertIn("name", called_body)
        self.assertIn("schedule", called_body)
        self.assertIn("start_date_time", called_body)
        self.assertIn("end_date_time", called_body)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_optional_fields_absent_when_not_provided(self, mock_req):
        """Optional fields must not appear in the body when not provided."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SPAN})
        create_change_schedule_span(_make_auth_manager(), _make_config(), BASE_PARAMS)
        called_body = mock_req.call_args[1]["json"]
        self.assertNotIn("repeat_type", called_body)
        self.assertNotIn("day_of_week", called_body)
        self.assertNotIn("all_day", called_body)
        self.assertNotIn("repeat_until", called_body)
        self.assertNotIn("type", called_body)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_params_nested_under_params_key(self, mock_req):
        """Params may arrive wrapped under a 'params' key."""
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_SPAN})
        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"params": BASE_PARAMS},
        )
        self.assertTrue(result["success"])


class TestCreateChangeScheduleSpanErrors(unittest.TestCase):
    """Error-path tests."""

    def test_missing_name_returns_failure(self):
        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"schedule": SCHEDULE_SYS_ID, "start_date_time": "2026-07-12 22:00:00", "end_date_time": "2026-07-13 06:00:00"},
        )
        self.assertFalse(result["success"])

    def test_missing_schedule_returns_failure(self):
        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"name": "Span", "start_date_time": "2026-07-12 22:00:00", "end_date_time": "2026-07-13 06:00:00"},
        )
        self.assertFalse(result["success"])

    def test_missing_start_datetime_returns_failure(self):
        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"name": "Span", "schedule": SCHEDULE_SYS_ID, "end_date_time": "2026-07-13 06:00:00"},
        )
        self.assertFalse(result["success"])

    def test_missing_end_datetime_returns_failure(self):
        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"name": "Span", "schedule": SCHEDULE_SYS_ID, "start_date_time": "2026-07-12 22:00:00"},
        )
        self.assertFalse(result["success"])

    def test_invalid_start_datetime_format(self):
        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {**BASE_PARAMS, "start_date_time": "not-a-date"},
        )
        self.assertFalse(result["success"])

    def test_invalid_repeat_until_format(self):
        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {**BASE_PARAMS, "repeat_until": "not-a-date"},
        )
        self.assertFalse(result["success"])

    def test_invalid_day_of_week_too_high(self):
        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {**BASE_PARAMS, "day_of_week": 7},
        )
        self.assertFalse(result["success"])

    def test_invalid_day_of_week_negative(self):
        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {**BASE_PARAMS, "day_of_week": -1},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_not_found_returns_failure(self, mock_req):
        """If the schedule name can't be resolved, tool must fail."""
        mock_req.return_value = _make_response(200, {"result": []})
        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {**BASE_PARAMS, "schedule": "Nonexistent Schedule"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Nonexistent Schedule", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_on_post(self, mock_req):
        """A 500 from the table API should return success=False."""
        mock_req.return_value = _make_response(500, {})
        result = create_change_schedule_span(_make_auth_manager(), _make_config(), BASE_PARAMS)
        self.assertFalse(result["success"])
        self.assertIn("Error creating change schedule span", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_on_post(self, mock_req):
        """Network failure should return success=False."""
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = create_change_schedule_span(_make_auth_manager(), _make_config(), BASE_PARAMS)
        self.assertFalse(result["success"])
        self.assertIn("Error creating change schedule span", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_resolver_connection_error(self, mock_req):
        """If resolver raises ConnectionError, schedule lookup returns None → failure."""
        mock_req.side_effect = requests.exceptions.ConnectionError("net error")
        result = create_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {**BASE_PARAMS, "schedule": "Some Schedule"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Parent schedule not found", result["message"])

    def test_no_instance_url(self):
        """If instance_url is None, return failure."""
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = None
        server_config = _make_config()
        server_config.instance_url = None
        result = create_change_schedule_span(auth_manager, server_config, BASE_PARAMS)
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
