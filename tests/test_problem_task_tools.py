"""Tests for problem_task_tools (create_problem_task, list_problem_tasks, close_problem_task)."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.problem_task_tools import (
    close_problem_task,
    create_problem_task,
    list_problem_tasks,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

PROBLEM_SYS_ID = "a" * 32
TASK_SYS_ID = "b" * 32

SAMPLE_TASK_RECORD = {
    "sys_id": TASK_SYS_ID,
    "number": "PTASK0010001",
    "short_description": "Investigate root cause",
    "description": "Deep dive on memory leak",
    "state": "1",
    "priority": "2",
    "assigned_to": {"display_value": "jane.doe", "value": "c" * 32},
    "assignment_group": {"display_value": "Platform Ops", "value": "d" * 32},
    "problem": {"display_value": "PRB0001234", "value": PROBLEM_SYS_ID},
    "close_notes": None,
    "sys_created_on": "2026-07-01 08:00:00",
    "sys_updated_on": "2026-07-01 08:00:00",
}

CLOSED_TASK_RECORD = {
    **SAMPLE_TASK_RECORD,
    "state": "3",
    "close_notes": "Fixed by updating the driver",
}


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev12345.service-now.com", auth=auth_config)


def _make_auth_manager():
    auth_manager = MagicMock(spec=AuthManager)
    auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    auth_manager.instance_url = "https://dev12345.service-now.com"
    return auth_manager


def _make_response(status_code, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


# ============================================================= #
# create_problem_task                                            #
# ============================================================= #

class TestCreateProblemTask(unittest.TestCase):

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_create_success_by_sys_id(self, mock_req):
        """Create a task when problem_id is already a sys_id (no lookup needed)."""
        mock_req.return_value = _make_response(201, {"result": SAMPLE_TASK_RECORD})

        result = create_problem_task(
            _make_auth_manager(),
            _make_config(),
            {
                "problem_id": PROBLEM_SYS_ID,
                "short_description": "Investigate root cause",
            },
        )

        self.assertTrue(result["success"])
        self.assertIn("PTASK0010001", result["message"])
        self.assertEqual(result["sys_id"], TASK_SYS_ID)
        self.assertEqual(result["number"], "PTASK0010001")
        self.assertEqual(result["task"]["assigned_to"], "jane.doe")
        self.assertEqual(result["task"]["assignment_group"], "Platform Ops")
        self.assertEqual(result["task"]["problem"], "PRB0001234")
        mock_req.assert_called_once()
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["problem"], PROBLEM_SYS_ID)

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_create_success_by_problem_number(self, mock_req):
        """Create a task using a PRB number; lookup resolves to sys_id first."""
        lookup_resp = _make_response(200, {"result": [{"sys_id": PROBLEM_SYS_ID}]})
        post_resp = _make_response(201, {"result": SAMPLE_TASK_RECORD})
        mock_req.side_effect = [lookup_resp, post_resp]

        result = create_problem_task(
            _make_auth_manager(),
            _make_config(),
            {
                "problem_id": "PRB0001234",
                "short_description": "Investigate root cause",
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(mock_req.call_count, 2)
        # First call is the lookup GET, second is the POST
        get_call, post_call = mock_req.call_args_list
        self.assertEqual(get_call[0][0], "GET")
        self.assertEqual(post_call[0][0], "POST")
        body = post_call[1]["json"]
        self.assertEqual(body["problem"], PROBLEM_SYS_ID)

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_create_with_all_optional_fields(self, mock_req):
        """All optional fields are forwarded in the POST body."""
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": PROBLEM_SYS_ID}]}),
            _make_response(201, {"result": SAMPLE_TASK_RECORD}),
        ]

        result = create_problem_task(
            _make_auth_manager(),
            _make_config(),
            {
                "problem_id": "PRB0001234",
                "short_description": "Task with all fields",
                "description": "Detailed description",
                "assigned_to": "jane.doe",
                "assignment_group": "Platform Ops",
                "priority": "2",
                "state": "2",
                "work_notes": "Starting investigation",
            },
        )

        self.assertTrue(result["success"])
        body = mock_req.call_args_list[1][1]["json"]
        self.assertEqual(body["description"], "Detailed description")
        self.assertEqual(body["assigned_to"], "jane.doe")
        self.assertEqual(body["assignment_group"], "Platform Ops")
        self.assertEqual(body["priority"], "2")
        self.assertEqual(body["state"], "2")
        self.assertEqual(body["work_notes"], "Starting investigation")

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_create_problem_not_found(self, mock_req):
        """Return failure when the problem number resolves to nothing."""
        mock_req.return_value = _make_response(200, {"result": []})

        result = create_problem_task(
            _make_auth_manager(),
            _make_config(),
            {"problem_id": "PRB9999999", "short_description": "Task for missing PRB"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        mock_req.assert_called_once()

    def test_create_missing_required_params(self):
        """Empty params should fail validation."""
        result = create_problem_task(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_create_missing_short_description(self):
        """Missing short_description should fail validation."""
        result = create_problem_task(
            _make_auth_manager(), _make_config(), {"problem_id": "PRB0001234"}
        )
        self.assertFalse(result["success"])
        self.assertIn("short_description", result["message"])

    def test_create_missing_problem_id(self):
        """Missing problem_id should fail validation."""
        result = create_problem_task(
            _make_auth_manager(),
            _make_config(),
            {"short_description": "Task without problem"},
        )
        self.assertFalse(result["success"])
        self.assertIn("problem_id", result["message"])

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_create_api_error(self, mock_req):
        """HTTP error on POST returns failure with message."""
        # problem_id is a sys_id so lookup is skipped; only the POST fires
        err_resp = _make_response(500)
        err_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=err_resp)
        mock_req.return_value = err_resp

        result = create_problem_task(
            _make_auth_manager(),
            _make_config(),
            {"problem_id": PROBLEM_SYS_ID, "short_description": "Task"},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error creating problem task", result["message"])

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_create_lookup_exception(self, mock_req):
        """RequestException during problem lookup returns failure."""
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")

        result = create_problem_task(
            _make_auth_manager(),
            _make_config(),
            {"problem_id": "PRB0001234", "short_description": "Task"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])


# ============================================================= #
# list_problem_tasks                                             #
# ============================================================= #

class TestListProblemTasks(unittest.TestCase):

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_list_success_by_sys_id(self, mock_req):
        """List tasks when problem_id is a sys_id (no lookup needed)."""
        mock_req.return_value = _make_response(
            200, {"result": [SAMPLE_TASK_RECORD, {**SAMPLE_TASK_RECORD, "number": "PTASK0010002"}]}
        )

        result = list_problem_tasks(
            _make_auth_manager(),
            _make_config(),
            {"problem_id": PROBLEM_SYS_ID},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["tasks"]), 2)
        mock_req.assert_called_once()

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_list_success_by_problem_number(self, mock_req):
        """List tasks using a PRB number; lookup resolves to sys_id first."""
        lookup_resp = _make_response(200, {"result": [{"sys_id": PROBLEM_SYS_ID}]})
        list_resp = _make_response(200, {"result": [SAMPLE_TASK_RECORD]})
        mock_req.side_effect = [lookup_resp, list_resp]

        result = list_problem_tasks(
            _make_auth_manager(),
            _make_config(),
            {"problem_id": "PRB0001234"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(mock_req.call_count, 2)

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_list_with_state_filter(self, mock_req):
        """State filter is included in the query."""
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": PROBLEM_SYS_ID}]}),
            _make_response(200, {"result": [SAMPLE_TASK_RECORD]}),
        ]

        result = list_problem_tasks(
            _make_auth_manager(),
            _make_config(),
            {"problem_id": "PRB0001234", "state": "1"},
        )

        self.assertTrue(result["success"])
        list_call = mock_req.call_args_list[1]
        query = list_call[1]["params"]["sysparm_query"]
        self.assertIn("state=1", query)

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_list_empty_result(self, mock_req):
        """Empty result list returns success with empty tasks."""
        mock_req.return_value = _make_response(200, {"result": []})

        result = list_problem_tasks(
            _make_auth_manager(),
            _make_config(),
            {"problem_id": PROBLEM_SYS_ID},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["tasks"], [])

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_list_pagination(self, mock_req):
        """has_more is True when result count equals the limit."""
        tasks = [SAMPLE_TASK_RECORD] * 5
        mock_req.return_value = _make_response(200, {"result": tasks})

        result = list_problem_tasks(
            _make_auth_manager(),
            _make_config(),
            {"problem_id": PROBLEM_SYS_ID, "limit": 5, "offset": 0},
        )

        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 5)

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_list_problem_not_found(self, mock_req):
        """Return failure when the problem number resolves to nothing."""
        mock_req.return_value = _make_response(200, {"result": []})

        result = list_problem_tasks(
            _make_auth_manager(),
            _make_config(),
            {"problem_id": "PRB9999999"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_list_missing_problem_id(self):
        """Missing problem_id should fail validation."""
        result = list_problem_tasks(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("problem_id", result["message"])

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_list_api_error(self, mock_req):
        """HTTP error on list GET returns failure."""
        # problem_id is a sys_id so lookup is skipped; only the list GET fires
        err_resp = _make_response(500)
        err_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=err_resp)
        mock_req.return_value = err_resp

        result = list_problem_tasks(
            _make_auth_manager(),
            _make_config(),
            {"problem_id": PROBLEM_SYS_ID},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error listing problem tasks", result["message"])

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_list_query_includes_problem_sys_id(self, mock_req):
        """sysparm_query must contain the resolved problem sys_id."""
        mock_req.return_value = _make_response(200, {"result": []})

        list_problem_tasks(
            _make_auth_manager(),
            _make_config(),
            {"problem_id": PROBLEM_SYS_ID},
        )

        params = mock_req.call_args[1]["params"]
        self.assertIn(PROBLEM_SYS_ID, params["sysparm_query"])

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_list_normalises_reference_fields(self, mock_req):
        """assigned_to and assignment_group are normalised to display values."""
        mock_req.return_value = _make_response(200, {"result": [SAMPLE_TASK_RECORD]})

        result = list_problem_tasks(
            _make_auth_manager(),
            _make_config(),
            {"problem_id": PROBLEM_SYS_ID},
        )

        task = result["tasks"][0]
        self.assertEqual(task["assigned_to"], "jane.doe")
        self.assertEqual(task["assignment_group"], "Platform Ops")
        self.assertEqual(task["problem"], "PRB0001234")


# ============================================================= #
# close_problem_task                                             #
# ============================================================= #

class TestCloseProblemTask(unittest.TestCase):

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_close_by_sys_id_skips_lookup(self, mock_req):
        """Supplying a 32-char hex sys_id skips the lookup GET."""
        mock_req.return_value = _make_response(200, {"result": CLOSED_TASK_RECORD})

        result = close_problem_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], TASK_SYS_ID)
        self.assertEqual(result["task"]["state"], "3")
        mock_req.assert_called_once()
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["state"], "3")

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_close_by_task_number(self, mock_req):
        """Close a task using its PTASK number; lookup resolves to sys_id."""
        lookup_resp = _make_response(200, {"result": [{"sys_id": TASK_SYS_ID}]})
        patch_resp = _make_response(200, {"result": CLOSED_TASK_RECORD})
        mock_req.side_effect = [lookup_resp, patch_resp]

        result = close_problem_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": "PTASK0010001"},
        )

        self.assertTrue(result["success"])
        self.assertIn("PTASK0010001", result["message"])
        self.assertEqual(mock_req.call_count, 2)
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["state"], "3")

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_close_with_close_notes(self, mock_req):
        """close_notes are forwarded in the PATCH body."""
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": TASK_SYS_ID}]}),
            _make_response(200, {"result": CLOSED_TASK_RECORD}),
        ]

        result = close_problem_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": "PTASK0010001", "close_notes": "Fixed by updating the driver"},
        )

        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["close_notes"], "Fixed by updating the driver")

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_close_with_work_notes(self, mock_req):
        """work_notes are forwarded in the PATCH body."""
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": TASK_SYS_ID}]}),
            _make_response(200, {"result": CLOSED_TASK_RECORD}),
        ]

        result = close_problem_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": "PTASK0010001", "work_notes": "Closing after review"},
        )

        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["work_notes"], "Closing after review")

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_close_task_not_found_by_number(self, mock_req):
        """Return failure when the task number resolves to nothing."""
        mock_req.return_value = _make_response(200, {"result": []})

        result = close_problem_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": "PTASK9999999"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_close_404_response(self, mock_req):
        """404 from the PATCH returns a not-found failure."""
        lookup_resp = _make_response(200, {"result": [{"sys_id": TASK_SYS_ID}]})
        patch_resp = _make_response(404)
        mock_req.side_effect = [lookup_resp, patch_resp]

        result = close_problem_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": "PTASK0010001"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_close_missing_task_id(self):
        """Missing task_id should fail validation."""
        result = close_problem_task(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("task_id", result["message"])

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_close_api_error(self, mock_req):
        """HTTP error on PATCH returns failure with message."""
        err_resp = _make_response(500)
        err_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=err_resp)
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": TASK_SYS_ID}]}),
            err_resp,
        ]

        result = close_problem_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": "PTASK0010001"},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error closing problem task", result["message"])

    @patch("servicenow_mcp.tools.problem_task_tools._make_request")
    def test_close_returns_task_fields(self, mock_req):
        """Returned task dict contains normalised fields."""
        mock_req.return_value = _make_response(200, {"result": CLOSED_TASK_RECORD})

        result = close_problem_task(
            _make_auth_manager(),
            _make_config(),
            {"task_id": TASK_SYS_ID},
        )

        task = result["task"]
        self.assertEqual(task["sys_id"], TASK_SYS_ID)
        self.assertEqual(task["state"], "3")
        self.assertEqual(task["close_notes"], "Fixed by updating the driver")
        self.assertEqual(task["assigned_to"], "jane.doe")


if __name__ == "__main__":
    unittest.main()
