"""Tests for get_change_task in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import get_change_task
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

TASK_SYS_ID = "a" * 32
CHG_SYS_ID = "b" * 32
USER_SYS_ID = "c" * 32
GROUP_SYS_ID = "d" * 32

FAKE_TASK_RECORD = {
    "sys_id": TASK_SYS_ID,
    "number": "CTASK0001234",
    "short_description": "Deploy database patch",
    "description": "Apply critical security patch to DB server",
    "state": {"display_value": "Open", "value": "1"},
    "priority": {"display_value": "2 - High", "value": "2"},
    "assigned_to": {"display_value": "John Smith", "value": USER_SYS_ID},
    "assignment_group": {"display_value": "DBA Team", "value": GROUP_SYS_ID},
    "change_request": {"display_value": "CHG0010001", "value": CHG_SYS_ID},
    "planned_start_date": "2026-07-01 08:00:00",
    "planned_end_date": "2026-07-01 10:00:00",
    "close_notes": "",
    "order": "100",
    "sys_created_on": "2026-06-15 08:00:00",
    "sys_updated_on": "2026-06-15 09:00:00",
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
# Happy path — lookup by sys_id (no resolution needed)
# ---------------------------------------------------------------------------


class TestGetChangeTaskBySysId(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_normalised_task(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_TASK_RECORD})
        result = get_change_task(_make_auth_manager(), _make_config(), {"task_id": TASK_SYS_ID})
        self.assertTrue(result["success"])
        task = result["task"]
        self.assertEqual(task["sys_id"], TASK_SYS_ID)
        self.assertEqual(task["number"], "CTASK0001234")
        self.assertEqual(task["short_description"], "Deploy database patch")
        self.assertEqual(task["state"], "Open")
        self.assertEqual(task["priority"], "2 - High")
        self.assertEqual(task["assigned_to"], "John Smith")
        self.assertEqual(task["assignment_group"], "DBA Team")
        self.assertEqual(task["change_request"], "CHG0010001")
        self.assertEqual(task["planned_start_date"], "2026-07-01 08:00:00")
        self.assertEqual(task["planned_end_date"], "2026-07-01 10:00:00")
        self.assertEqual(task["created_on"], "2026-06-15 08:00:00")
        self.assertEqual(task["updated_on"], "2026-06-15 09:00:00")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_url_contains_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_TASK_RECORD})
        get_change_task(_make_auth_manager(), _make_config(), {"task_id": TASK_SYS_ID})
        call_args = mock_req.call_args
        url = call_args[0][1]
        self.assertIn(TASK_SYS_ID, url)
        self.assertIn("change_task", url)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_display_value_param_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_TASK_RECORD})
        get_change_task(_make_auth_manager(), _make_config(), {"task_id": TASK_SYS_ID})
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        self.assertEqual(params.get("sysparm_display_value"), "true")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_exclude_reference_link_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_TASK_RECORD})
        get_change_task(_make_auth_manager(), _make_config(), {"task_id": TASK_SYS_ID})
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        self.assertEqual(params.get("sysparm_exclude_reference_link"), "true")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_raw_string_reference_fields(self, mock_req):
        record = dict(FAKE_TASK_RECORD)
        record["assigned_to"] = "john.smith"
        record["assignment_group"] = "dba_team"
        record["change_request"] = "CHG0010001"
        record["state"] = "1"
        record["priority"] = "2"
        mock_req.return_value = _make_response(200, {"result": record})
        result = get_change_task(_make_auth_manager(), _make_config(), {"task_id": TASK_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["task"]["assigned_to"], "john.smith")
        self.assertEqual(result["task"]["change_request"], "CHG0010001")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_only_one_request_for_sys_id(self, mock_req):
        """When task_id is already a sys_id no resolution GET is needed."""
        mock_req.return_value = _make_response(200, {"result": FAKE_TASK_RECORD})
        get_change_task(_make_auth_manager(), _make_config(), {"task_id": TASK_SYS_ID})
        self.assertEqual(mock_req.call_count, 1)


# ---------------------------------------------------------------------------
# Happy path — lookup by CTASK number (resolution required)
# ---------------------------------------------------------------------------


class TestGetChangeTaskByCTASKNumber(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_resolves_ctask_number_then_fetches(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": TASK_SYS_ID}]})
        fetch_resp = _make_response(200, {"result": FAKE_TASK_RECORD})
        mock_req.side_effect = [resolve_resp, fetch_resp]
        result = get_change_task(_make_auth_manager(), _make_config(), {"task_id": "CTASK0001234"})
        self.assertTrue(result["success"])
        self.assertEqual(result["task"]["number"], "CTASK0001234")
        self.assertEqual(mock_req.call_count, 2)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_resolution_uses_number_query(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": TASK_SYS_ID}]})
        fetch_resp = _make_response(200, {"result": FAKE_TASK_RECORD})
        mock_req.side_effect = [resolve_resp, fetch_resp]
        get_change_task(_make_auth_manager(), _make_config(), {"task_id": "CTASK0001234"})
        first_call = mock_req.call_args_list[0]
        params = first_call[1].get("params", {})
        self.assertIn("number=CTASK0001234", params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_ctask_not_found_returns_failure(self, mock_req):
        resolve_resp = _make_response(200, {"result": []})
        mock_req.return_value = resolve_resp
        result = get_change_task(_make_auth_manager(), _make_config(), {"task_id": "CTASK9999999"})
        self.assertFalse(result["success"])
        self.assertIn("CTASK9999999", result["message"])


# ---------------------------------------------------------------------------
# 404 and empty result guards
# ---------------------------------------------------------------------------


class TestGetChangeTask404(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_status_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        result = get_change_task(_make_auth_manager(), _make_config(), {"task_id": TASK_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())
        self.assertIn(TASK_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_empty_dict_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_change_task(_make_auth_manager(), _make_config(), {"task_id": TASK_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_none_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": None})
        result = get_change_task(_make_auth_manager(), _make_config(), {"task_id": TASK_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())


# ---------------------------------------------------------------------------
# Network errors
# ---------------------------------------------------------------------------


class TestGetChangeTaskNetworkErrors(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_500_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = get_change_task(_make_auth_manager(), _make_config(), {"task_id": TASK_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving change task", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("unreachable")
        result = get_change_task(_make_auth_manager(), _make_config(), {"task_id": TASK_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving change task", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_timeout_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.Timeout("timed out")
        result = get_change_task(_make_auth_manager(), _make_config(), {"task_id": TASK_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving change task", result["message"])


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestGetChangeTaskParams(unittest.TestCase):
    def test_missing_task_id_returns_failure(self):
        result = get_change_task(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_missing_instance_url_returns_failure(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = {}
        auth_manager.instance_url = None
        config = MagicMock()
        config.instance_url = None
        config.auth = None
        result = get_change_task(auth_manager, config, {"task_id": TASK_SYS_ID})
        self.assertFalse(result["success"])

    def test_missing_headers_returns_failure(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = "https://dev99999.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"
        config.auth = None
        result = get_change_task(auth_manager, config, {"task_id": TASK_SYS_ID})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_params_wrapped_in_params_key(self, mock_req):
        """Tool should handle params nested under a 'params' key."""
        mock_req.return_value = _make_response(200, {"result": FAKE_TASK_RECORD})
        result = get_change_task(
            _make_auth_manager(), _make_config(), {"params": {"task_id": TASK_SYS_ID}}
        )
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
