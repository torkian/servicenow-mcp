"""Extended tests for scrum task management tools — coverage improvements."""

import unittest
from unittest.mock import MagicMock, patch


from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.scrum_task_tools import (
    create_scrum_task,
    list_scrum_tasks,
    update_scrum_task,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


def _make_config():
    return ServerConfig(
        instance_url="https://dev12345.service-now.com",
        auth=AuthConfig(type=AuthType.BASIC, basic=BasicAuthConfig(username="u", password="p")),
    )


def _make_auth():
    auth = MagicMock(spec=AuthManager)
    auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    return auth


class TestCreateScrumTaskExtended(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.post")
    def test_create_with_nonzero_hours(self, mock_post):
        """Hours=1 (non-zero/truthy) hits the hours assignment branch."""
        mock_post.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": {"sys_id": "st1"}}),
        )
        result = create_scrum_task(self.auth, self.config, {
            "story": "s1",
            "short_description": "Task",
            "hours": 1,
        })
        self.assertTrue(result["success"])

    def test_create_missing_instance_url(self):
        """No instance_url on either auth or config → failure."""
        auth = MagicMock()
        del auth.instance_url
        config = MagicMock()
        del config.instance_url

        result = create_scrum_task(auth, config, {"story": "s1", "short_description": "T"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_create_missing_headers(self):
        """No get_headers on either auth or config → failure."""
        auth = MagicMock()
        auth.instance_url = "https://dev12345.service-now.com"
        del auth.get_headers
        config = MagicMock()
        del config.instance_url
        del config.get_headers

        result = create_scrum_task(auth, config, {"story": "s1", "short_description": "T"})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.post")
    def test_create_with_all_optional_fields(self, mock_post):
        """Every optional field populated — hits all assignment branches."""
        mock_post.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": {"sys_id": "st1"}}),
        )
        result = create_scrum_task(self.auth, self.config, {
            "story": "s1",
            "short_description": "Full task",
            "priority": "1",
            "planned_hours": 8,
            "remaining_hours": 4,
            "hours": 2,
            "description": "Detailed",
            "type": "2",
            "state": "1",
            "assignment_group": "DevTeam",
            "assigned_to": "admin",
            "work_notes": "Starting now",
        })
        self.assertTrue(result["success"])


class TestUpdateScrumTaskExtended(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    def test_update_missing_required_param(self):
        """Missing scrum_task_id → validation failure → early return."""
        result = update_scrum_task(self.auth, self.config, {"state": "2"})
        self.assertFalse(result["success"])
        self.assertIn("scrum_task_id", result["message"])

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.put")
    def test_update_with_all_optional_fields(self, mock_put):
        """All optional update fields populated — covers all assignment branches."""
        mock_put.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": {"sys_id": "st1"}}),
        )
        result = update_scrum_task(self.auth, self.config, {
            "scrum_task_id": "st1",
            "short_description": "Updated",
            "priority": "2",
            "planned_hours": 10,
            "remaining_hours": 5,
            "hours": 3,
            "description": "New desc",
            "type": "3",
            "state": "2",
            "assignment_group": "QA",
            "assigned_to": "tester",
            "work_notes": "In progress",
        })
        self.assertTrue(result["success"])

    def test_update_missing_instance_url(self):
        """No instance_url → failure."""
        auth = MagicMock()
        del auth.instance_url
        config = MagicMock()
        del config.instance_url

        result = update_scrum_task(auth, config, {"scrum_task_id": "st1", "state": "2"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_update_missing_headers(self):
        """No get_headers → failure."""
        auth = MagicMock()
        auth.instance_url = "https://dev12345.service-now.com"
        del auth.get_headers
        config = MagicMock()
        del config.instance_url
        del config.get_headers

        result = update_scrum_task(auth, config, {"scrum_task_id": "st1", "state": "2"})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


class TestListScrumTasksExtended(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    def test_list_validation_failure(self):
        """Invalid param type triggers validation error."""
        result = list_scrum_tasks(self.auth, self.config, {"limit": "not-a-number"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_list_timeframe_upcoming(self, mock_get):
        """timeframe='upcoming' builds the start_date> filter."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_scrum_tasks(self.auth, self.config, {"timeframe": "upcoming"})
        self.assertTrue(result["success"])
        call_params = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("start_date>", call_params)

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_list_timeframe_in_progress(self, mock_get):
        """timeframe='in-progress' builds start_date<...^end_date> filter."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_scrum_tasks(self.auth, self.config, {"timeframe": "in-progress"})
        self.assertTrue(result["success"])
        call_params = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("start_date<", call_params)
        self.assertIn("end_date>", call_params)

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_list_timeframe_completed(self, mock_get):
        """timeframe='completed' builds the end_date< filter."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_scrum_tasks(self.auth, self.config, {"timeframe": "completed"})
        self.assertTrue(result["success"])
        call_params = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("end_date<", call_params)

    @patch("servicenow_mcp.tools.scrum_task_tools.requests.get")
    def test_list_with_extra_query(self, mock_get):
        """Extra query string is appended to sysparm_query."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_scrum_tasks(self.auth, self.config, {"query": "sprint=Sprint1"})
        self.assertTrue(result["success"])
        call_params = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("sprint=Sprint1", call_params)

    def test_list_missing_instance_url(self):
        auth = MagicMock()
        del auth.instance_url
        config = MagicMock()
        del config.instance_url

        result = list_scrum_tasks(auth, config, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_list_missing_headers(self):
        auth = MagicMock()
        auth.instance_url = "https://dev12345.service-now.com"
        del auth.get_headers
        config = MagicMock()
        del config.instance_url
        del config.get_headers

        result = list_scrum_tasks(auth, config, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


if __name__ == "__main__":
    unittest.main()
