"""Tests for update_change_task in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import update_change_task
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

TASK_SYS_ID = "a" * 32
USER_SYS_ID = "c" * 32
GROUP_SYS_ID = "d" * 32
CHG_SYS_ID = "b" * 32

UPDATED_RECORD = {
    "sys_id": TASK_SYS_ID,
    "number": "CTASK0001234",
    "short_description": "Updated description",
    "description": "More detail",
    "state": {"display_value": "Work In Progress", "value": "2"},
    "priority": {"display_value": "2 - High", "value": "2"},
    "assigned_to": {"display_value": "Jane Doe", "value": USER_SYS_ID},
    "assignment_group": {"display_value": "DBA Team", "value": GROUP_SYS_ID},
    "change_request": {"display_value": "CHG0010001", "value": CHG_SYS_ID},
    "planned_start_date": "2026-07-01 08:00:00",
    "planned_end_date": "2026-07-01 10:00:00",
    "close_notes": "",
    "order": "100",
    "sys_created_on": "2026-06-15 08:00:00",
    "sys_updated_on": "2026-06-18 09:00:00",
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


class TestUpdateChangeTaskBySysId(unittest.TestCase):
    """Happy path — task_id is already a sys_id (no resolution needed)."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_state(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": UPDATED_RECORD})
        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID, "state": "2"},
        )
        self.assertTrue(result["success"])
        self.assertIn("Change task updated", result["message"])
        task = result["task"]
        self.assertEqual(task["state"], "Work In Progress")
        self.assertEqual(task["sys_id"], TASK_SYS_ID)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_assignee_and_group(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": UPDATED_RECORD})
        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID, "assigned_to": "jane.doe", "assignment_group": "DBA Team"},
        )
        self.assertTrue(result["success"])
        task = result["task"]
        self.assertEqual(task["assigned_to"], "Jane Doe")
        self.assertEqual(task["assignment_group"], "DBA Team")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_short_description_and_work_notes(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": UPDATED_RECORD})
        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID, "short_description": "Updated description", "work_notes": "Progress update"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["task"]["short_description"], "Updated description")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_dates(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": UPDATED_RECORD})
        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {
                "task_id": TASK_SYS_ID,
                "planned_start_date": "2026-07-01 08:00:00",
                "planned_end_date": "2026-07-01 10:00:00",
            },
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_update_close_notes(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": UPDATED_RECORD})
        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID, "close_notes": "Task complete", "state": "3"},
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_patch_called_with_correct_method(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": UPDATED_RECORD})
        update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID, "state": "2"},
        )
        call_args = mock_req.call_args
        self.assertEqual(call_args[0][0], "PATCH")
        self.assertIn(f"/change_task/{TASK_SYS_ID}", call_args[0][1])


class TestUpdateChangeTaskByNumber(unittest.TestCase):
    """Task resolved by CTASK number."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_resolves_ctask_number(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": TASK_SYS_ID}]})
        update_resp = _make_response(200, {"result": UPDATED_RECORD})
        mock_req.side_effect = [resolve_resp, update_resp]

        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": "CTASK0001234", "state": "2"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(mock_req.call_count, 2)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_ctask_not_found_returns_error(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": "CTASK0000000", "state": "2"},
        )
        self.assertFalse(result["success"])
        self.assertIn("CTASK0000000", result["message"])


class TestUpdateChangeTaskEdgeCases(unittest.TestCase):

    def test_missing_task_id_returns_error(self):
        result = update_change_task(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_no_update_fields_returns_error(self):
        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("No fields provided", result["message"])

    def test_invalid_date_format_rejected(self):
        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID, "planned_start_date": "not-a-date"},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_returns_not_found(self, mock_req):
        mock_req.return_value = _make_response(404)
        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID, "state": "2"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_returns_message(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("timeout")
        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID, "state": "2"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_resolve_request_exception_returns_none(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("network error")
        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": "CTASK0001234", "state": "2"},
        )
        self.assertFalse(result["success"])

    def test_no_instance_url_returns_error(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = {}
        auth_manager.instance_url = None
        config = MagicMock(spec=ServerConfig)
        config.instance_url = None
        result = update_change_task(auth_manager, config, {"task_id": TASK_SYS_ID, "state": "2"})
        self.assertFalse(result["success"])

    def test_params_wrapped_in_dict(self):
        result = update_change_task(
            _make_auth_manager(),
            _make_config(),
            {"params": {"task_id": TASK_SYS_ID}},
        )
        self.assertFalse(result["success"])


class TestUpdateChangeTaskAllFields(unittest.TestCase):
    """Verify that all optional fields are forwarded to the PATCH body."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_all_fields_sent(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": UPDATED_RECORD})
        update_change_task(
            _make_auth_manager(),
            _make_config(),
            {
                "task_id": TASK_SYS_ID,
                "short_description": "s",
                "description": "d",
                "state": "2",
                "assigned_to": "jane.doe",
                "assignment_group": "DBA",
                "planned_start_date": "2026-07-01 08:00:00",
                "planned_end_date": "2026-07-01 10:00:00",
                "work_notes": "note",
                "close_notes": "done",
            },
        )
        call_kwargs = mock_req.call_args[1]
        body = call_kwargs.get("json", {})
        self.assertEqual(body["state"], "2")
        self.assertEqual(body["assigned_to"], "jane.doe")
        self.assertEqual(body["assignment_group"], "DBA")
        self.assertEqual(body["short_description"], "s")
        self.assertEqual(body["description"], "d")
        self.assertEqual(body["work_notes"], "note")
        self.assertEqual(body["close_notes"], "done")


if __name__ == "__main__":
    unittest.main()
