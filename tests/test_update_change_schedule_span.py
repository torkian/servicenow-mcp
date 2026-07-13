"""Tests for update_change_schedule_span in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import update_change_schedule_span
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
SCHEDULE_SYS_ID = "b" * 32

FAKE_UPDATED_SPAN = {
    "sys_id": FAKE_SYS_ID,
    "name": "Updated Night Window",
    "schedule": {"display_value": "Change Window - Prod", "value": SCHEDULE_SYS_ID},
    "type": {"display_value": "Include", "value": "include"},
    "repeat_type": "weekly",
    "day_of_week": "6",
    "start_date_time": "2026-07-12 23:00:00",
    "end_date_time": "2026-07-13 07:00:00",
    "all_day": "false",
    "repeat_until": "2027-06-30",
    "sys_created_on": "2026-07-01 00:00:00",
    "sys_updated_on": "2026-07-12 10:00:00",
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


class TestUpdateChangeScheduleSpanSuccess(unittest.TestCase):
    """Happy-path tests."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_name_only(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_UPDATED_SPAN})
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "name": "Updated Night Window"},
        )
        self.assertTrue(result["success"])
        self.assertIn("span", result)
        self.assertEqual(result["span"]["name"], "Updated Night Window")
        self.assertEqual(result["span"]["sys_id"], FAKE_SYS_ID)
        mock_req.assert_called_once()

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_times(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_UPDATED_SPAN})
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {
                "span_id": FAKE_SYS_ID,
                "start_date_time": "2026-07-12 23:00:00",
                "end_date_time": "2026-07-13 07:00:00",
            },
        )
        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["start_date_time"], "2026-07-12 23:00:00")
        self.assertEqual(body["end_date_time"], "2026-07-13 07:00:00")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_all_optional_fields(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_UPDATED_SPAN})
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {
                "span_id": FAKE_SYS_ID,
                "name": "Updated Night Window",
                "schedule": SCHEDULE_SYS_ID,
                "start_date_time": "2026-07-12 23:00:00",
                "end_date_time": "2026-07-13 07:00:00",
                "repeat_type": "weekly",
                "day_of_week": 6,
                "all_day": False,
                "repeat_until": "2027-06-30",
                "span_type": "include",
            },
        )
        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["repeat_type"], "weekly")
        self.assertEqual(body["day_of_week"], "6")
        self.assertEqual(body["all_day"], "false")
        self.assertEqual(body["repeat_until"], "2027-06-30")
        self.assertEqual(body["type"], "include")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_with_schedule_name(self, mock_req):
        """schedule provided as name — resolver GET then PATCH."""
        resolve_resp = _make_response(200, {"result": [{"sys_id": SCHEDULE_SYS_ID}]})
        update_resp = _make_response(200, {"result": FAKE_UPDATED_SPAN})
        mock_req.side_effect = [resolve_resp, update_resp]

        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "schedule": "Change Window - Prod"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(mock_req.call_count, 2)
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["schedule"], SCHEDULE_SYS_ID)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_all_day_true_serialised_as_string(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_UPDATED_SPAN})
        update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "all_day": True},
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["all_day"], "true")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_content_type_header_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_UPDATED_SPAN})
        update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "name": "Updated"},
        )
        sent_headers = mock_req.call_args[1]["headers"]
        self.assertEqual(sent_headers.get("Content-Type"), "application/json")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_url_contains_span_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_UPDATED_SPAN})
        update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "name": "Updated"},
        )
        called_url = mock_req.call_args[0][1]
        self.assertIn(FAKE_SYS_ID, called_url)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_method_is_patch(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_UPDATED_SPAN})
        update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "name": "Updated"},
        )
        self.assertEqual(mock_req.call_args[0][0], "PATCH")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_span_fields_normalised(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_UPDATED_SPAN})
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "name": "Updated Night Window"},
        )
        span = result["span"]
        self.assertEqual(span["schedule"], "Change Window - Prod")
        self.assertEqual(span["day_of_week_label"], "Saturday")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_message_contains_span_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_UPDATED_SPAN})
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "name": "Updated"},
        )
        self.assertIn(FAKE_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_params_nested_under_params_key(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_UPDATED_SPAN})
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"params": {"span_id": FAKE_SYS_ID, "name": "Updated"}},
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_display_value_query_params_sent(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_UPDATED_SPAN})
        update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "name": "Updated"},
        )
        query_params = mock_req.call_args[1]["params"]
        self.assertEqual(query_params.get("sysparm_display_value"), "true")
        self.assertEqual(query_params.get("sysparm_exclude_reference_link"), "true")


class TestUpdateChangeScheduleSpanErrors(unittest.TestCase):
    """Error-path tests."""

    def test_missing_span_id_returns_failure(self):
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"name": "Updated"},
        )
        self.assertFalse(result["success"])

    def test_no_fields_to_update_returns_failure(self):
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("No fields provided", result["message"])

    def test_invalid_start_datetime_format(self):
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "start_date_time": "not-a-date"},
        )
        self.assertFalse(result["success"])

    def test_invalid_end_datetime_format(self):
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "end_date_time": "2026/07/13 06:00"},
        )
        self.assertFalse(result["success"])

    def test_invalid_repeat_until_format(self):
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "repeat_until": "not-a-date"},
        )
        self.assertFalse(result["success"])

    def test_invalid_day_of_week_too_high(self):
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "day_of_week": 7},
        )
        self.assertFalse(result["success"])

    def test_invalid_day_of_week_negative(self):
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "day_of_week": -1},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "name": "Updated"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertIn(FAKE_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "name": "Updated"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating change schedule span", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "name": "Updated"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating change schedule span", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "schedule": "Nonexistent Schedule"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Parent schedule not found", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_schedule_resolver_connection_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("net error")
        result = update_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID, "schedule": "Some Schedule"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Parent schedule not found", result["message"])

    def test_no_instance_url(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = None
        server_config = _make_config()
        server_config.instance_url = None
        result = update_change_schedule_span(
            auth_manager,
            server_config,
            {"span_id": FAKE_SYS_ID, "name": "Updated"},
        )
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
