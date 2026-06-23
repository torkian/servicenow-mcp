"""Tests for get_change_schedule in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import (
    _resolve_change_schedule_sys_id,
    get_change_schedule,
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
    "sys_updated_on": "2026-06-20 12:00:00",
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
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


# ---------------------------------------------------------------------------
# _resolve_change_schedule_sys_id
# ---------------------------------------------------------------------------


class TestResolveChangeScheduleSysId(unittest.TestCase):
    def test_passthrough_sys_id(self):
        result = _resolve_change_schedule_sys_id("https://x.service-now.com", {}, FAKE_SYS_ID)
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_resolves_name_to_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        result = _resolve_change_schedule_sys_id(
            "https://x.service-now.com", {}, "Change Window - Weekend"
        )
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_name_not_found_returns_none(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = _resolve_change_schedule_sys_id(
            "https://x.service-now.com", {}, "Nonexistent Schedule"
        )
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_request_exception_returns_none(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = _resolve_change_schedule_sys_id(
            "https://x.service-now.com", {}, "Schedule Name"
        )
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Happy path — lookup by sys_id
# ---------------------------------------------------------------------------


class TestGetChangeScheduleBySysId(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_normalised_schedule(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_SCHEDULE})
        result = get_change_schedule(
            _make_auth_manager(), _make_config(), {"schedule_id": FAKE_SYS_ID}
        )
        self.assertTrue(result["success"])
        schedule = result["schedule"]
        self.assertEqual(schedule["sys_id"], FAKE_SYS_ID)
        self.assertEqual(schedule["name"], "Change Window - Weekend")
        self.assertEqual(schedule["description"], "Saturday and Sunday change window")
        self.assertEqual(schedule["type"], "Change Window")
        self.assertEqual(schedule["time_zone"], "US/Eastern")
        self.assertEqual(schedule["active"], "true")
        self.assertEqual(schedule["parent"], "Global Change Windows")
        self.assertEqual(schedule["created_by"], "admin")
        self.assertEqual(schedule["created_on"], "2026-01-01 00:00:00")
        self.assertEqual(schedule["updated_on"], "2026-06-20 12:00:00")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_url_contains_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_SCHEDULE})
        get_change_schedule(
            _make_auth_manager(), _make_config(), {"schedule_id": FAKE_SYS_ID}
        )
        url = mock_req.call_args[0][1]
        self.assertIn(FAKE_SYS_ID, url)
        self.assertIn("cmn_schedule", url)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_display_value_param_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_SCHEDULE})
        get_change_schedule(
            _make_auth_manager(), _make_config(), {"schedule_id": FAKE_SYS_ID}
        )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["params"].get("sysparm_display_value"), "true")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_exclude_reference_link_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_SCHEDULE})
        get_change_schedule(
            _make_auth_manager(), _make_config(), {"schedule_id": FAKE_SYS_ID}
        )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["params"].get("sysparm_exclude_reference_link"), "true")


# ---------------------------------------------------------------------------
# Happy path — lookup by name
# ---------------------------------------------------------------------------


class TestGetChangeScheduleByName(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_resolves_name_then_fetches(self, mock_req):
        # First call: name resolution; second call: GET by sys_id
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]}),
            _make_response(200, {"result": FAKE_SCHEDULE}),
        ]
        result = get_change_schedule(
            _make_auth_manager(), _make_config(), {"schedule_id": "Change Window - Weekend"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["schedule"]["sys_id"], FAKE_SYS_ID)
        self.assertEqual(mock_req.call_count, 2)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_name_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = get_change_schedule(
            _make_auth_manager(), _make_config(), {"schedule_id": "Nonexistent"}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())
        self.assertIn("Nonexistent", result["message"])


# ---------------------------------------------------------------------------
# 404 and empty result guards
# ---------------------------------------------------------------------------


class TestGetChangeScheduleNotFound(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_status_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        result = get_change_schedule(
            _make_auth_manager(), _make_config(), {"schedule_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())
        self.assertIn(FAKE_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_empty_result_dict_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_change_schedule(
            _make_auth_manager(), _make_config(), {"schedule_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_none_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": None})
        result = get_change_schedule(
            _make_auth_manager(), _make_config(), {"schedule_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())


# ---------------------------------------------------------------------------
# Network errors
# ---------------------------------------------------------------------------


class TestGetChangeScheduleNetworkErrors(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_500_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = get_change_schedule(
            _make_auth_manager(), _make_config(), {"schedule_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving change schedule", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = get_change_schedule(
            _make_auth_manager(), _make_config(), {"schedule_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving change schedule", result["message"])


# ---------------------------------------------------------------------------
# Missing / invalid params
# ---------------------------------------------------------------------------


class TestGetChangeScheduleParams(unittest.TestCase):
    def test_missing_schedule_id_returns_failure(self):
        result = get_change_schedule(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_missing_instance_url_returns_failure(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = {}
        auth_manager.instance_url = None
        config = MagicMock()
        config.instance_url = None
        config.auth = None
        result = get_change_schedule(auth_manager, config, {"schedule_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])

    def test_missing_headers_returns_failure(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = "https://dev99999.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"
        config.auth = None
        result = get_change_schedule(auth_manager, config, {"schedule_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_raw_string_reference_fields(self, mock_req):
        record = dict(FAKE_SCHEDULE, type="change_window", parent="Global")
        mock_req.return_value = _make_response(200, {"result": record})
        result = get_change_schedule(
            _make_auth_manager(), _make_config(), {"schedule_id": FAKE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["schedule"]["type"], "change_window")
        self.assertEqual(result["schedule"]["parent"], "Global")


if __name__ == "__main__":
    unittest.main()
