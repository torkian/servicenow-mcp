"""Tests for close_change_task in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import close_change_task
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

TASK_SYS_ID = "a" * 32
CHG_SYS_ID = "b" * 32

CLOSED_RECORD = {
    "sys_id": TASK_SYS_ID,
    "number": "CTASK0005678",
    "short_description": "Deploy DB schema",
    "description": "Apply migration scripts",
    "state": {"display_value": "Closed Complete", "value": "3"},
    "priority": {"display_value": "3 - Moderate", "value": "3"},
    "assigned_to": {"display_value": "Bob Smith", "value": "c" * 32},
    "assignment_group": {"display_value": "DBA Team", "value": "d" * 32},
    "change_request": {"display_value": "CHG0010002", "value": CHG_SYS_ID},
    "planned_start_date": "2026-07-01 08:00:00",
    "planned_end_date": "2026-07-01 10:00:00",
    "close_notes": "Migration applied successfully",
    "order": "100",
    "sys_created_on": "2026-06-10 08:00:00",
    "sys_updated_on": "2026-06-19 09:00:00",
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


class TestCloseChangeTaskBySysId(unittest.TestCase):
    """Happy path — task_id is already a sys_id (no resolution needed)."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_close_complete_default_state(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": CLOSED_RECORD})
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID},
        )
        self.assertTrue(result["success"])
        self.assertIn("closed successfully", result["message"])
        task = result["task"]
        self.assertEqual(task["state"], "Closed Complete")
        self.assertEqual(task["sys_id"], TASK_SYS_ID)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_close_with_close_notes(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": CLOSED_RECORD})
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID, "close_notes": "Migration applied successfully"},
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args[1]
        body = call_kwargs.get("json", {})
        self.assertEqual(body["close_notes"], "Migration applied successfully")
        self.assertEqual(body["state"], "3")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_close_with_work_notes(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": CLOSED_RECORD})
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID, "work_notes": "All steps completed"},
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args[1]
        body = call_kwargs.get("json", {})
        self.assertEqual(body["work_notes"], "All steps completed")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_close_incomplete_state(self, mock_req):
        incomplete_record = dict(CLOSED_RECORD)
        incomplete_record["state"] = {"display_value": "Closed Incomplete", "value": "4"}
        mock_req.return_value = _make_response(200, {"result": incomplete_record})
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID, "state": "4"},
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args[1]
        body = call_kwargs.get("json", {})
        self.assertEqual(body["state"], "4")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_close_skipped_state(self, mock_req):
        skipped_record = dict(CLOSED_RECORD)
        skipped_record["state"] = {"display_value": "Closed Skipped", "value": "7"}
        mock_req.return_value = _make_response(200, {"result": skipped_record})
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID, "state": "7"},
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args[1]
        body = call_kwargs.get("json", {})
        self.assertEqual(body["state"], "7")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_close_all_fields(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": CLOSED_RECORD})
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {
                "task_id": TASK_SYS_ID,
                "state": "3",
                "close_notes": "Done",
                "work_notes": "Everything went well",
            },
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args[1]
        body = call_kwargs.get("json", {})
        self.assertEqual(body["state"], "3")
        self.assertEqual(body["close_notes"], "Done")
        self.assertEqual(body["work_notes"], "Everything went well")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_patch_method_and_url(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": CLOSED_RECORD})
        close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID},
        )
        call_args = mock_req.call_args
        self.assertEqual(call_args[0][0], "PATCH")
        self.assertIn(f"/change_task/{TASK_SYS_ID}", call_args[0][1])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_task_fields_returned(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": CLOSED_RECORD})
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID},
        )
        task = result["task"]
        self.assertIn("sys_id", task)
        self.assertIn("number", task)
        self.assertIn("state", task)
        self.assertIn("close_notes", task)
        self.assertIn("change_request", task)


class TestCloseChangeTaskByNumber(unittest.TestCase):
    """Task resolved by CTASK number."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_resolves_ctask_number(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": TASK_SYS_ID}]})
        close_resp = _make_response(200, {"result": CLOSED_RECORD})
        mock_req.side_effect = [resolve_resp, close_resp]

        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": "CTASK0005678"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(mock_req.call_count, 2)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_ctask_not_found_returns_error(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": "CTASK0000000"},
        )
        self.assertFalse(result["success"])
        self.assertIn("CTASK0000000", result["message"])


class TestCloseChangeTaskEdgeCases(unittest.TestCase):

    def test_missing_task_id_returns_error(self):
        result = close_change_task(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_returns_not_found(self, mock_req):
        mock_req.return_value = _make_response(404)
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_request_exception_returns_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("timeout")
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error closing", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_resolve_exception_returns_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("network error")
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": "CTASK0005678"},
        )
        self.assertFalse(result["success"])

    def test_no_instance_url_returns_error(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = {}
        auth_manager.instance_url = None
        config = MagicMock(spec=ServerConfig)
        config.instance_url = None
        result = close_change_task(auth_manager, config, {"task_id": TASK_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_params_wrapped_in_dict(self):
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"params": {"task_id": TASK_SYS_ID}},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_message_includes_task_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": CLOSED_RECORD})
        result = close_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID},
        )
        self.assertIn(TASK_SYS_ID, result["message"])


if __name__ == "__main__":
    unittest.main()
