"""Additional coverage tests for project_tools.py targeting uncovered paths."""

import unittest
from unittest.mock import MagicMock, patch


from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.project_tools import create_project, list_projects, update_project
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestProjectToolsCoverage(unittest.TestCase):
    def setUp(self):
        self.config = ServerConfig(
            instance_url="https://dev99999.service-now.com",
            auth=AuthConfig(
                type=AuthType.BASIC,
                basic=BasicAuthConfig(username="test", password="test"),
            ),
        )
        self.auth = MagicMock(spec=AuthManager)
        self.auth.get_headers.return_value = {"Authorization": "Bearer TOKEN"}

    # ---- create_project ----

    @patch("servicenow_mcp.tools.project_tools.requests.post")
    def test_create_project_all_optional_fields(self, mock_post):
        """Cover lines 45 (date validator) and 116-132 (all optional fields)."""
        mock_post.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": {"sys_id": "abc"}}),
        )
        result = create_project(
            self.config,
            self.auth,
            {
                "short_description": "Full Project",
                "description": "Detailed desc",
                "status": "green",
                "state": "1",
                "project_manager": "admin",
                "percentage_complete": 50,
                "assignment_group": "PMO",
                "assigned_to": "admin",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
            },
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.project_tools._get_instance_url", return_value=None)
    def test_create_project_no_instance_url(self, _mock):
        """Cover line 137: no instance_url."""
        result = create_project(self.config, self.auth, {"short_description": "P"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.project_tools._get_headers", return_value=None)
    def test_create_project_no_headers(self, _mock):
        """Cover line 145: no headers."""
        result = create_project(self.config, self.auth, {"short_description": "P"})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    # ---- update_project ----

    def test_update_project_missing_project_id(self):
        """Cover line 198: validation failure path in update_project."""
        result = update_project(self.config, self.auth, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.project_tools.requests.put")
    def test_update_project_with_description(self, mock_put):
        """Cover line 209: description optional field."""
        mock_put.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": {"sys_id": "p1"}}),
        )
        result = update_project(
            self.config,
            self.auth,
            {"project_id": "p1", "description": "Updated description"},
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.project_tools._get_instance_url", return_value=None)
    def test_update_project_no_instance_url(self, _mock):
        """Cover line 230: no instance_url in update_project."""
        result = update_project(self.config, self.auth, {"project_id": "p1"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.project_tools._get_headers", return_value=None)
    def test_update_project_no_headers(self, _mock):
        """Cover line 238: no headers in update_project."""
        result = update_project(self.config, self.auth, {"project_id": "p1"})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    # ---- list_projects ----

    def test_list_projects_invalid_limit(self):
        """Cover line 290: validation failure path in list_projects."""
        result = list_projects(self.config, self.auth, {"limit": "not-an-int"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.project_tools.requests.get")
    def test_list_projects_timeframe_upcoming(self, mock_get):
        """Cover lines 304-307: timeframe=upcoming."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_projects(self.config, self.auth, {"timeframe": "upcoming"})
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.project_tools.requests.get")
    def test_list_projects_timeframe_in_progress(self, mock_get):
        """Cover lines 308-309: timeframe=in-progress."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_projects(self.config, self.auth, {"timeframe": "in-progress"})
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.project_tools.requests.get")
    def test_list_projects_timeframe_completed(self, mock_get):
        """Cover line 310+: timeframe=completed."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_projects(self.config, self.auth, {"timeframe": "completed"})
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.project_tools.requests.get")
    def test_list_projects_with_extra_query(self, mock_get):
        """Cover line 314: additional query param."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_projects(self.config, self.auth, {"query": "active=true"})
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.project_tools._get_instance_url", return_value=None)
    def test_list_projects_no_instance_url(self, _mock):
        """Cover line 322: no instance_url in list_projects."""
        result = list_projects(self.config, self.auth, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.project_tools._get_headers", return_value=None)
    def test_list_projects_no_headers(self, _mock):
        """Cover line 330: no headers in list_projects."""
        result = list_projects(self.config, self.auth, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


if __name__ == "__main__":
    unittest.main()
