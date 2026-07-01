"""Tests for incident task tools (create_incident_task, list_incident_tasks)."""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.incident_task_tools import (
    create_incident_task,
    list_incident_tasks,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestIncidentTaskTools(unittest.TestCase):
    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test", password="test"),
        )
        self.config = ServerConfig(
            instance_url="https://dev12345.service-now.com",
            auth=auth_config,
        )
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE_TOKEN"}

    # ------------------------------------------------------------------ #
    # create_incident_task                                                 #
    # ------------------------------------------------------------------ #

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    @patch("servicenow_mcp.tools.incident_task_tools.requests.post")
    def test_create_incident_task_success_by_number(self, mock_post, mock_get):
        """Create a task using an incident number; lookup resolves to sys_id."""
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = {"result": [{"sys_id": "inc_sys_id_001"}]}
        lookup_resp.raise_for_status = MagicMock()
        mock_get.return_value = lookup_resp

        post_resp = MagicMock()
        post_resp.json.return_value = {
            "result": {
                "sys_id": "task_sys_001",
                "number": "TASK0010001",
                "short_description": "Investigate disk usage",
                "state": "1",
                "priority": "3",
                "assigned_to": "john.doe",
                "assignment_group": "Linux Admins",
            }
        }
        post_resp.raise_for_status = MagicMock()
        mock_post.return_value = post_resp

        result = create_incident_task(
            self.auth_manager,
            self.config,
            {
                "incident_id": "INC0010001",
                "short_description": "Investigate disk usage",
                "assigned_to": "john.doe",
                "priority": "3",
            },
        )

        self.assertTrue(result["success"])
        self.assertIn("TASK0010001", result["message"])
        self.assertEqual(result["task"]["sys_id"], "task_sys_001")
        self.assertEqual(result["task"]["parent_incident"], "inc_sys_id_001")
        mock_post.assert_called_once()

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    @patch("servicenow_mcp.tools.incident_task_tools.requests.post")
    def test_create_incident_task_success_by_sys_id(self, mock_post, mock_get):
        """Skip lookup when a 32-char hex sys_id is supplied."""
        inc_sys_id = "a" * 32

        post_resp = MagicMock()
        post_resp.json.return_value = {
            "result": {
                "sys_id": "task_sys_002",
                "number": "TASK0010002",
                "short_description": "Check logs",
                "state": "1",
                "priority": None,
                "assigned_to": None,
                "assignment_group": None,
            }
        }
        post_resp.raise_for_status = MagicMock()
        mock_post.return_value = post_resp

        result = create_incident_task(
            self.auth_manager,
            self.config,
            {"incident_id": inc_sys_id, "short_description": "Check logs"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["task"]["parent_incident"], inc_sys_id)
        mock_get.assert_not_called()

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_create_incident_task_incident_not_found(self, mock_get):
        """Return failure when the incident number resolves to nothing."""
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = {"result": []}
        lookup_resp.raise_for_status = MagicMock()
        mock_get.return_value = lookup_resp

        result = create_incident_task(
            self.auth_manager,
            self.config,
            {"incident_id": "INC9999999", "short_description": "Task for missing inc"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_create_incident_task_missing_required_params(self):
        """Missing both incident_id and short_description should fail validation."""
        result = create_incident_task(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])

    def test_create_incident_task_missing_short_description(self):
        """Missing short_description alone should fail validation."""
        result = create_incident_task(self.auth_manager, self.config, {"incident_id": "INC0010001"})
        self.assertFalse(result["success"])
        self.assertIn("short_description", result["message"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    @patch("servicenow_mcp.tools.incident_task_tools.requests.post")
    def test_create_incident_task_with_all_optional_fields(self, mock_post, mock_get):
        """All optional fields are forwarded to the POST body."""
        inc_sys_id = "b" * 32

        post_resp = MagicMock()
        post_resp.json.return_value = {
            "result": {
                "sys_id": "task_sys_003",
                "number": "TASK0010003",
                "short_description": "Full task",
                "state": "2",
                "priority": "1",
                "assigned_to": "jane.doe",
                "assignment_group": "Network Ops",
            }
        }
        post_resp.raise_for_status = MagicMock()
        mock_post.return_value = post_resp

        result = create_incident_task(
            self.auth_manager,
            self.config,
            {
                "incident_id": inc_sys_id,
                "short_description": "Full task",
                "description": "Detailed description",
                "assigned_to": "jane.doe",
                "assignment_group": "Network Ops",
                "priority": "1",
                "state": "2",
                "work_notes": "Starting now",
            },
        )

        self.assertTrue(result["success"])
        body_sent = mock_post.call_args[1]["json"]
        self.assertEqual(body_sent["description"], "Detailed description")
        self.assertEqual(body_sent["work_notes"], "Starting now")
        self.assertEqual(body_sent["state"], "2")

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    @patch("servicenow_mcp.tools.incident_task_tools.requests.post")
    def test_create_incident_task_http_error(self, mock_post, mock_get):
        """POST failure returns success=False."""
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = {"result": [{"sys_id": "inc_sys_id_001"}]}
        lookup_resp.raise_for_status = MagicMock()
        mock_get.return_value = lookup_resp

        import requests as req

        mock_post.side_effect = req.exceptions.RequestException("500 Server Error")

        result = create_incident_task(
            self.auth_manager,
            self.config,
            {"incident_id": "INC0010001", "short_description": "Failing task"},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error creating incident task", result["message"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    @patch("servicenow_mcp.tools.incident_task_tools.requests.post")
    def test_create_incident_task_unwraps_nested_params(self, mock_post, mock_get):
        """Params wrapped in {"params": {...}} are properly unwrapped."""
        inc_sys_id = "c" * 32

        post_resp = MagicMock()
        post_resp.json.return_value = {
            "result": {
                "sys_id": "task_sys_004",
                "number": "TASK0010004",
                "short_description": "Wrapped",
                "state": "1",
                "priority": None,
                "assigned_to": None,
                "assignment_group": None,
            }
        }
        post_resp.raise_for_status = MagicMock()
        mock_post.return_value = post_resp

        result = create_incident_task(
            self.auth_manager,
            self.config,
            {"params": {"incident_id": inc_sys_id, "short_description": "Wrapped"}},
        )

        self.assertTrue(result["success"])

    # ------------------------------------------------------------------ #
    # list_incident_tasks                                                  #
    # ------------------------------------------------------------------ #

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_incident_tasks_success(self, mock_get):
        """List returns tasks for a given incident."""
        inc_sys_id = "d" * 32

        list_resp = MagicMock()
        list_resp.json.return_value = {
            "result": [
                {"sys_id": "t1", "number": "TASK001", "short_description": "First task"},
                {"sys_id": "t2", "number": "TASK002", "short_description": "Second task"},
            ]
        }
        list_resp.raise_for_status = MagicMock()
        mock_get.return_value = list_resp

        result = list_incident_tasks(
            self.auth_manager,
            self.config,
            {"incident_id": inc_sys_id},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["tasks"]), 2)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_incident_tasks_by_number(self, mock_get):
        """Lookup by incident number resolves then lists tasks."""
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = {"result": [{"sys_id": "inc_sys_id_002"}]}
        lookup_resp.raise_for_status = MagicMock()

        list_resp = MagicMock()
        list_resp.json.return_value = {"result": [{"sys_id": "t3", "number": "TASK003"}]}
        list_resp.raise_for_status = MagicMock()

        mock_get.side_effect = [lookup_resp, list_resp]

        result = list_incident_tasks(
            self.auth_manager,
            self.config,
            {"incident_id": "INC0010002"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("inc_sys_id_002", query)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_incident_tasks_with_state_filter(self, mock_get):
        """State filter is included in the sysparm_query."""
        inc_sys_id = "e" * 32

        list_resp = MagicMock()
        list_resp.json.return_value = {"result": []}
        list_resp.raise_for_status = MagicMock()
        mock_get.return_value = list_resp

        result = list_incident_tasks(
            self.auth_manager,
            self.config,
            {"incident_id": inc_sys_id, "state": "2"},
        )

        self.assertTrue(result["success"])
        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("state=2", query)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_incident_tasks_incident_not_found(self, mock_get):
        """Return failure when incident cannot be resolved."""
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = {"result": []}
        lookup_resp.raise_for_status = MagicMock()
        mock_get.return_value = lookup_resp

        result = list_incident_tasks(
            self.auth_manager,
            self.config,
            {"incident_id": "INC9999999"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_list_incident_tasks_missing_incident_id(self):
        """Missing incident_id should fail validation."""
        result = list_incident_tasks(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("incident_id", result["message"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_incident_tasks_http_error(self, mock_get):
        """GET failure returns success=False."""
        inc_sys_id = "f" * 32

        import requests as req

        mock_get.side_effect = req.exceptions.RequestException("503 Service Unavailable")

        result = list_incident_tasks(
            self.auth_manager,
            self.config,
            {"incident_id": inc_sys_id},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error listing incident tasks", result["message"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_incident_tasks_has_more_flag(self, mock_get):
        """has_more is True when the result count equals the limit."""
        inc_sys_id = "0" * 32

        tasks = [{"sys_id": f"t{i}", "number": f"TASK{i:04d}"} for i in range(5)]
        list_resp = MagicMock()
        list_resp.json.return_value = {"result": tasks}
        list_resp.raise_for_status = MagicMock()
        mock_get.return_value = list_resp

        result = list_incident_tasks(
            self.auth_manager,
            self.config,
            {"incident_id": inc_sys_id, "limit": 5},
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["has_more"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_incident_tasks_pagination_params(self, mock_get):
        """limit and offset are forwarded to the API call."""
        inc_sys_id = "1" * 32

        list_resp = MagicMock()
        list_resp.json.return_value = {"result": []}
        list_resp.raise_for_status = MagicMock()
        mock_get.return_value = list_resp

        list_incident_tasks(
            self.auth_manager,
            self.config,
            {"incident_id": inc_sys_id, "limit": 25, "offset": 50},
        )

        call_params = mock_get.call_args[1]["params"]
        self.assertEqual(call_params["sysparm_limit"], 25)
        self.assertEqual(call_params["sysparm_offset"], 50)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_incident_tasks_unwraps_nested_params(self, mock_get):
        """Params wrapped in {"params": {...}} are properly unwrapped."""
        inc_sys_id = "2" * 32

        list_resp = MagicMock()
        list_resp.json.return_value = {"result": []}
        list_resp.raise_for_status = MagicMock()
        mock_get.return_value = list_resp

        result = list_incident_tasks(
            self.auth_manager,
            self.config,
            {"params": {"incident_id": inc_sys_id}},
        )

        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
