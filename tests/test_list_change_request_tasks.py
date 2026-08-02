"""Tests for list_change_request_tasks shortcut."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import (
    ListChangeRequestTasksParams,
    list_change_request_tasks,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
FAKE_CHG = "CHG0009999"
FAKE_TASK_SYS_ID = "c" * 32


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="u", password="p"),
    )
    return ServerConfig(instance_url="https://dev12345.service-now.com", auth=auth_config)


def _make_auth():
    auth = MagicMock(spec=AuthManager)
    auth.get_headers.return_value = {"Authorization": "Bearer TOKEN"}
    return auth


def _ok(json_data):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def _err(status_code):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"error": {"message": "Not Found", "detail": ""}}
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


_TASK_RECORD = {
    "sys_id": FAKE_TASK_SYS_ID,
    "number": "CTASK0001",
    "short_description": "Deploy config",
    "description": "Full description",
    "state": {"display_value": "Open", "value": "1"},
    "priority": {"display_value": "High", "value": "2"},
    "assigned_to": {"display_value": "Jane Doe", "value": "u1"},
    "assignment_group": {"display_value": "CAB", "value": "g1"},
    "change_request": {"display_value": FAKE_CHG, "value": FAKE_SYS_ID},
    "planned_start_date": "2026-08-05 10:00:00",
    "planned_end_date": "2026-08-05 12:00:00",
    "close_notes": "",
    "order": "100",
    "sys_created_on": "2026-08-01 08:00:00",
    "sys_updated_on": "2026-08-01 09:00:00",
}


class TestListChangeRequestTasksParams(unittest.TestCase):
    def test_defaults(self):
        p = ListChangeRequestTasksParams(change_id="CHG0001234")
        self.assertEqual(p.change_id, "CHG0001234")
        self.assertEqual(p.limit, 20)
        self.assertEqual(p.offset, 0)
        self.assertIsNone(p.state)
        self.assertIsNone(p.priority)
        self.assertIsNone(p.assigned_to)

    def test_all_fields(self):
        p = ListChangeRequestTasksParams(
            change_id=FAKE_SYS_ID,
            limit=5,
            offset=10,
            state="1",
            priority="2",
            assigned_to="jdoe",
        )
        self.assertEqual(p.limit, 5)
        self.assertEqual(p.state, "1")
        self.assertEqual(p.priority, "2")
        self.assertEqual(p.assigned_to, "jdoe")


class TestListChangeRequestTasksMissingChangeId(unittest.TestCase):
    def test_missing_change_id_returns_error(self):
        config = _make_config()
        auth = _make_auth()
        result = list_change_request_tasks(auth, config, {})
        self.assertFalse(result["success"])


class TestListChangeRequestTasksBySysId(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_list_by_sys_id(self, mock_req):
        mock_req.return_value = _ok({"result": [_TASK_RECORD]})
        result = list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        task = result["tasks"][0]
        self.assertEqual(task["number"], "CTASK0001")
        self.assertEqual(task["state"], "Open")
        self.assertEqual(task["priority"], "High")
        self.assertEqual(task["assigned_to"], "Jane Doe")
        self.assertEqual(task["assignment_group"], "CAB")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_list_by_chg_number(self, mock_req):
        mock_req.side_effect = [
            _ok({"result": [{"sys_id": FAKE_SYS_ID}]}),
            _ok({"result": [_TASK_RECORD]}),
        ]
        result = list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_CHG}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        # verify the CHG number lookup was called
        first_call = mock_req.call_args_list[0]
        self.assertIn("change_request", first_call[0][1])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_change_not_found(self, mock_req):
        mock_req.return_value = _ok({"result": []})
        result = list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_CHG}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _ok({"result": []})
        result = list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["tasks"], [])
        self.assertFalse(result["has_more"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_state_filter_applied(self, mock_req):
        mock_req.return_value = _ok({"result": []})
        list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_SYS_ID, "state": "1"}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("state=1", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_priority_filter_applied(self, mock_req):
        mock_req.return_value = _ok({"result": []})
        list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_SYS_ID, "priority": "2"}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("priority=2", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_assigned_to_filter_applied(self, mock_req):
        mock_req.return_value = _ok({"result": []})
        list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_SYS_ID, "assigned_to": "jdoe"}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("assigned_to=jdoe", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_pagination_limit_offset(self, mock_req):
        tasks = [dict(_TASK_RECORD, sys_id=f"{'d'*32}")] * 5
        mock_req.return_value = _ok({"result": tasks})
        result = list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_SYS_ID, "limit": 5, "offset": 0}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 5)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 5)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_has_more_false_when_below_limit(self, mock_req):
        tasks = [_TASK_RECORD, dict(_TASK_RECORD, sys_id="e" * 32)]
        mock_req.return_value = _ok({"result": tasks})
        result = list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_SYS_ID, "limit": 5}
        )
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_network_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("error", result["message"].lower())

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error(self, mock_req):
        mock_req.return_value = _err(500)
        result = list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_multiple_filters_combined(self, mock_req):
        mock_req.return_value = _ok({"result": []})
        list_change_request_tasks(
            self.auth,
            self.config,
            {"change_id": FAKE_SYS_ID, "state": "2", "priority": "1", "assigned_to": "sysadmin"},
        )
        call_params = mock_req.call_args[1]["params"]
        query = call_params["sysparm_query"]
        self.assertIn("state=2", query)
        self.assertIn("priority=1", query)
        self.assertIn("assigned_to=sysadmin", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_change_id_filter_in_query(self, mock_req):
        mock_req.return_value = _ok({"result": []})
        list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_SYS_ID}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn(f"change_request={FAKE_SYS_ID}", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_order_by_set(self, mock_req):
        mock_req.return_value = _ok({"result": []})
        list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_SYS_ID}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("sysparm_orderby", call_params)
        self.assertEqual(call_params["sysparm_orderby"], "order")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_format_task_normalises_reference_fields(self, mock_req):
        mock_req.return_value = _ok({"result": [_TASK_RECORD]})
        result = list_change_request_tasks(
            self.auth, self.config, {"change_id": FAKE_SYS_ID}
        )
        task = result["tasks"][0]
        # reference fields must be display values, not raw dicts
        self.assertIsInstance(task["state"], str)
        self.assertIsInstance(task["priority"], str)
        self.assertIsInstance(task["assigned_to"], str)
        self.assertIsInstance(task["assignment_group"], str)


if __name__ == "__main__":
    unittest.main()
