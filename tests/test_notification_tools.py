"""Tests for notification_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.notification_tools import (
    _format_notification,
    get_notification,
    list_notifications,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "c" * 32
FAKE_SOURCE_SYS_ID = "d" * 32

FAKE_NOTIFICATION = {
    "sys_id": FAKE_SYS_ID,
    "type": "Incident Resolved",
    "source": FAKE_SOURCE_SYS_ID,
    "target": {"display_value": "John Doe", "value": "e" * 32},
    "subject": "Your incident INC0001234 has been resolved",
    "email_address": "jdoe@example.com",
    "state": "sent",
    "error_string": "",
    "weight": "0",
    "sys_created_on": "2026-06-01 10:00:00",
    "sys_updated_on": "2026-06-01 10:00:05",
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
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=resp
        )
    return resp


# ---------------------------------------------------------------------------
# _format_notification
# ---------------------------------------------------------------------------

class TestFormatNotification(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_notification(FAKE_NOTIFICATION)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["type"], "Incident Resolved")
        self.assertEqual(result["source"], FAKE_SOURCE_SYS_ID)
        self.assertEqual(result["subject"], "Your incident INC0001234 has been resolved")
        self.assertEqual(result["email_address"], "jdoe@example.com")
        self.assertEqual(result["state"], "sent")
        self.assertEqual(result["created_on"], "2026-06-01 10:00:00")

    def test_normalises_target_reference_dict(self):
        result = _format_notification(FAKE_NOTIFICATION)
        self.assertEqual(result["target"], "John Doe")

    def test_handles_string_target(self):
        rec = {**FAKE_NOTIFICATION, "target": "plain_string"}
        result = _format_notification(rec)
        self.assertEqual(result["target"], "plain_string")

    def test_handles_missing_fields(self):
        result = _format_notification({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["type"])
        self.assertIsNone(result["email_address"])


# ---------------------------------------------------------------------------
# list_notifications
# ---------------------------------------------------------------------------

class TestListNotifications(unittest.TestCase):
    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_success_returns_notifications(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_NOTIFICATION]})
        result = list_notifications(
            _make_auth_manager(), _make_config(), {}
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["notifications"]), 1)
        self.assertEqual(result["notifications"][0]["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_notifications(
            _make_auth_manager(), _make_config(), {}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["notifications"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_state_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_notifications(
            _make_auth_manager(), _make_config(), {"state": "failed"}
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("state=failed", query)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_type_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_notifications(
            _make_auth_manager(), _make_config(), {"type": "Incident"}
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("typeLIKEIncident", query)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_email_address_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_notifications(
            _make_auth_manager(), _make_config(), {"email_address": "jdoe@example.com"}
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("email_addressLIKEjdoe@example.com", query)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_source_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_notifications(
            _make_auth_manager(), _make_config(), {"source": FAKE_SOURCE_SYS_ID}
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn(f"source={FAKE_SOURCE_SYS_ID}", query)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_created_after_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_notifications(
            _make_auth_manager(), _make_config(), {"created_after": "2026-06-01"}
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("sys_created_on>=2026-06-01", query)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_created_before_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_notifications(
            _make_auth_manager(), _make_config(), {"created_before": "2026-06-10"}
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("sys_created_on<=2026-06-10", query)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_date_range_combined(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_notifications(
            _make_auth_manager(),
            _make_config(),
            {"created_after": "2026-06-01", "created_before": "2026-06-10"},
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("sys_created_on>=2026-06-01", query)
        self.assertIn("sys_created_on<=2026-06-10", query)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_pagination_params(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_notifications(
            _make_auth_manager(), _make_config(), {"limit": 5, "offset": 10}
        )
        call_kwargs = mock_req.call_args
        params = call_kwargs[1]["params"]
        self.assertEqual(params["sysparm_limit"], 5)
        self.assertEqual(params["sysparm_offset"], 10)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_has_more_flag(self, mock_req):
        records = [FAKE_NOTIFICATION] * 20
        mock_req.return_value = _make_response(200, {"result": records})
        result = list_notifications(
            _make_auth_manager(), _make_config(), {"limit": 20, "offset": 0}
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 20)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_uses_get_method(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_notifications(_make_auth_manager(), _make_config(), {})
        method = mock_req.call_args[0][0]
        self.assertEqual(method, "GET")

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_url_targets_correct_table(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_notifications(_make_auth_manager(), _make_config(), {})
        url = mock_req.call_args[0][1]
        self.assertIn("sysevent_email_log", url)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = list_notifications(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing notifications", result["message"])

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_notifications(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing notifications", result["message"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = list_notifications(auth, config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_multiple_filters_combined(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_notifications(
            _make_auth_manager(),
            _make_config(),
            {"state": "sent", "email_address": "admin@example.com"},
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("state=sent", query)
        self.assertIn("email_addressLIKEadmin@example.com", query)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_returns_count(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": [FAKE_NOTIFICATION, FAKE_NOTIFICATION]}
        )
        result = list_notifications(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)


# ---------------------------------------------------------------------------
# get_notification
# ---------------------------------------------------------------------------

class TestGetNotification(unittest.TestCase):
    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_success_returns_notification(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_NOTIFICATION})
        result = get_notification(
            _make_auth_manager(), _make_config(), {"notification_id": FAKE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["notification"]["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["notification"]["state"], "sent")

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_url_contains_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_NOTIFICATION})
        get_notification(
            _make_auth_manager(), _make_config(), {"notification_id": FAKE_SYS_ID}
        )
        url = mock_req.call_args[0][1]
        self.assertIn(FAKE_SYS_ID, url)
        self.assertIn("sysevent_email_log", url)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_uses_get_method(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_NOTIFICATION})
        get_notification(
            _make_auth_manager(), _make_config(), {"notification_id": FAKE_SYS_ID}
        )
        self.assertEqual(mock_req.call_args[0][0], "GET")

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_404_returns_failure(self, mock_req):
        resp = MagicMock()
        resp.status_code = 404
        resp.raise_for_status = MagicMock()
        mock_req.return_value = resp
        result = get_notification(
            _make_auth_manager(), _make_config(), {"notification_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertIn(FAKE_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_empty_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_notification(
            _make_auth_manager(), _make_config(), {"notification_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = get_notification(
            _make_auth_manager(), _make_config(), {"notification_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving notification record", result["message"])

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("network down")
        result = get_notification(
            _make_auth_manager(), _make_config(), {"notification_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving notification record", result["message"])

    def test_missing_notification_id_returns_failure(self):
        result = get_notification(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_no_instance_url_returns_failure(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = get_notification(auth, config, {"notification_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_display_value_params_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_NOTIFICATION})
        get_notification(
            _make_auth_manager(), _make_config(), {"notification_id": FAKE_SYS_ID}
        )
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params.get("sysparm_display_value"), "true")
        self.assertEqual(params.get("sysparm_exclude_reference_link"), "true")

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_notification_fields_requested(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_NOTIFICATION})
        get_notification(
            _make_auth_manager(), _make_config(), {"notification_id": FAKE_SYS_ID}
        )
        params = mock_req.call_args[1]["params"]
        fields = params.get("sysparm_fields", "")
        self.assertIn("sys_id", fields)
        self.assertIn("state", fields)
        self.assertIn("email_address", fields)

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_normalises_reference_fields(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_NOTIFICATION})
        result = get_notification(
            _make_auth_manager(), _make_config(), {"notification_id": FAKE_SYS_ID}
        )
        self.assertEqual(result["notification"]["target"], "John Doe")

    @patch("servicenow_mcp.tools.notification_tools._make_request")
    def test_failed_notification_with_error_string(self, mock_req):
        failed_notif = {**FAKE_NOTIFICATION, "state": "failed", "error_string": "SMTP timeout"}
        mock_req.return_value = _make_response(200, {"result": failed_notif})
        result = get_notification(
            _make_auth_manager(), _make_config(), {"notification_id": FAKE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["notification"]["state"], "failed")
        self.assertEqual(result["notification"]["error_string"], "SMTP timeout")


if __name__ == "__main__":
    unittest.main()
