"""Extended tests for story management tools — coverage improvements."""

import unittest
from unittest.mock import MagicMock, patch

from requests.exceptions import RequestException

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.story_tools import (
    create_story,
    create_story_dependency,
    delete_story_dependency,
    list_stories,
    list_story_dependencies,
    update_story,
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


# ---------------------------------------------------------------------------
# create_story
# ---------------------------------------------------------------------------

class TestCreateStoryExtended(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.story_tools.requests.post")
    def test_create_with_all_optional_fields(self, mock_post):
        """All optional fields populated — hits every assignment branch."""
        mock_post.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": {"sys_id": "s1"}}),
        )
        result = create_story(self.auth, self.config, {
            "short_description": "Full story",
            "acceptance_criteria": "All tests pass",
            "description": "Detailed desc",
            "state": "1",
            "assignment_group": "AgileTeam",
            "story_points": 5,
            "assigned_to": "dev1",
            "epic": "epic-sys-id",
            "project": "proj-sys-id",
            "work_notes": "Starting sprint",
        })
        self.assertTrue(result["success"])

    def test_create_missing_instance_url(self):
        auth = MagicMock()
        del auth.instance_url
        config = MagicMock()
        del config.instance_url

        result = create_story(auth, config, {
            "short_description": "T",
            "acceptance_criteria": "AC",
        })
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_create_missing_headers(self):
        auth = MagicMock()
        auth.instance_url = "https://dev12345.service-now.com"
        del auth.get_headers
        config = MagicMock()
        del config.instance_url
        del config.get_headers

        result = create_story(auth, config, {
            "short_description": "T",
            "acceptance_criteria": "AC",
        })
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


# ---------------------------------------------------------------------------
# update_story
# ---------------------------------------------------------------------------

class TestUpdateStoryExtended(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    def test_update_missing_required_param(self):
        """Missing story_id → validation failure."""
        result = update_story(self.auth, self.config, {"state": "2"})
        self.assertFalse(result["success"])
        self.assertIn("story_id", result["message"])

    @patch("servicenow_mcp.tools.story_tools.requests.put")
    def test_update_with_all_optional_fields(self, mock_put):
        """All optional fields populated — every assignment branch is hit."""
        mock_put.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": {"sys_id": "s1"}}),
        )
        result = update_story(self.auth, self.config, {
            "story_id": "s1",
            "short_description": "Updated",
            "acceptance_criteria": "New AC",
            "description": "New desc",
            "state": "3",
            "assignment_group": "Scrum",
            "story_points": 8,
            "assigned_to": "dev2",
            "epic": "epic2",
            "project": "proj2",
            "work_notes": "Nearly done",
        })
        self.assertTrue(result["success"])

    def test_update_missing_instance_url(self):
        auth = MagicMock()
        del auth.instance_url
        config = MagicMock()
        del config.instance_url

        result = update_story(auth, config, {"story_id": "s1", "state": "2"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_update_missing_headers(self):
        auth = MagicMock()
        auth.instance_url = "https://dev12345.service-now.com"
        del auth.get_headers
        config = MagicMock()
        del config.instance_url
        del config.get_headers

        result = update_story(auth, config, {"story_id": "s1", "state": "2"})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


# ---------------------------------------------------------------------------
# list_stories
# ---------------------------------------------------------------------------

class TestListStoriesExtended(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    def test_list_validation_failure(self):
        """Invalid limit triggers Pydantic validation error."""
        result = list_stories(self.auth, self.config, {"limit": "not-an-int"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.story_tools.requests.get")
    def test_list_timeframe_upcoming(self, mock_get):
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_stories(self.auth, self.config, {"timeframe": "upcoming"})
        self.assertTrue(result["success"])
        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("start_date>", query)

    @patch("servicenow_mcp.tools.story_tools.requests.get")
    def test_list_timeframe_in_progress(self, mock_get):
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_stories(self.auth, self.config, {"timeframe": "in-progress"})
        self.assertTrue(result["success"])
        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("start_date<", query)
        self.assertIn("end_date>", query)

    @patch("servicenow_mcp.tools.story_tools.requests.get")
    def test_list_timeframe_completed(self, mock_get):
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_stories(self.auth, self.config, {"timeframe": "completed"})
        self.assertTrue(result["success"])
        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("end_date<", query)

    @patch("servicenow_mcp.tools.story_tools.requests.get")
    def test_list_with_extra_query(self, mock_get):
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_stories(self.auth, self.config, {"query": "epic=someepic"})
        self.assertTrue(result["success"])
        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("epic=someepic", query)

    def test_list_missing_instance_url(self):
        auth = MagicMock()
        del auth.instance_url
        config = MagicMock()
        del config.instance_url

        result = list_stories(auth, config, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_list_missing_headers(self):
        auth = MagicMock()
        auth.instance_url = "https://dev12345.service-now.com"
        del auth.get_headers
        config = MagicMock()
        del config.instance_url
        del config.get_headers

        result = list_stories(auth, config, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


# ---------------------------------------------------------------------------
# list_story_dependencies
# ---------------------------------------------------------------------------

class TestListStoryDependenciesExtended(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    def test_list_deps_validation_failure(self):
        result = list_story_dependencies(self.auth, self.config, {"limit": "bad"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.story_tools.requests.get")
    def test_list_deps_with_filters(self, mock_get):
        """dependent_story, prerequisite_story, and query filters all appended."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_story_dependencies(self.auth, self.config, {
            "dependent_story": "dep-sys-id",
            "prerequisite_story": "pre-sys-id",
            "query": "active=true",
        })
        self.assertTrue(result["success"])
        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("dep-sys-id", query)
        self.assertIn("pre-sys-id", query)
        self.assertIn("active=true", query)

    def test_list_deps_missing_instance_url(self):
        auth = MagicMock()
        del auth.instance_url
        config = MagicMock()
        del config.instance_url

        result = list_story_dependencies(auth, config, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_list_deps_missing_headers(self):
        auth = MagicMock()
        auth.instance_url = "https://dev12345.service-now.com"
        del auth.get_headers
        config = MagicMock()
        del config.instance_url
        del config.get_headers

        result = list_story_dependencies(auth, config, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.story_tools.requests.get")
    def test_list_deps_request_exception(self, mock_get):
        mock_get.side_effect = RequestException("fail")
        result = list_story_dependencies(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing story dependencies", result["message"])


# ---------------------------------------------------------------------------
# create_story_dependency
# ---------------------------------------------------------------------------

class TestCreateStoryDependencyExtended(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    def test_create_dep_missing_instance_url(self):
        auth = MagicMock()
        del auth.instance_url
        config = MagicMock()
        del config.instance_url

        result = create_story_dependency(auth, config, {
            "dependent_story": "s1",
            "prerequisite_story": "s2",
        })
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_create_dep_missing_headers(self):
        auth = MagicMock()
        auth.instance_url = "https://dev12345.service-now.com"
        del auth.get_headers
        config = MagicMock()
        del config.instance_url
        del config.get_headers

        result = create_story_dependency(auth, config, {
            "dependent_story": "s1",
            "prerequisite_story": "s2",
        })
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.story_tools.requests.post")
    def test_create_dep_request_exception(self, mock_post):
        mock_post.side_effect = RequestException("network error")
        result = create_story_dependency(self.auth, self.config, {
            "dependent_story": "s1",
            "prerequisite_story": "s2",
        })
        self.assertFalse(result["success"])
        self.assertIn("Error creating story dependency", result["message"])

    def test_create_dep_missing_required_fields(self):
        result = create_story_dependency(self.auth, self.config, {
            "dependent_story": "s1",
            # prerequisite_story missing
        })
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# delete_story_dependency
# ---------------------------------------------------------------------------

class TestDeleteStoryDependencyExtended(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    def test_delete_dep_missing_instance_url(self):
        auth = MagicMock()
        del auth.instance_url
        config = MagicMock()
        del config.instance_url

        result = delete_story_dependency(auth, config, {"dependency_id": "d1"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_delete_dep_missing_headers(self):
        auth = MagicMock()
        auth.instance_url = "https://dev12345.service-now.com"
        del auth.get_headers
        config = MagicMock()
        del config.instance_url
        del config.get_headers

        result = delete_story_dependency(auth, config, {"dependency_id": "d1"})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    def test_delete_dep_missing_dependency_id(self):
        result = delete_story_dependency(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("dependency_id", result["message"])


if __name__ == "__main__":
    unittest.main()
