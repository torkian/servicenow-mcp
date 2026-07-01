"""Tests for list_incident_comments tool."""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.incident_task_tools import list_incident_comments
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestListIncidentComments(unittest.TestCase):
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

    def _make_journal_entries(self, count=2):
        return [
            {
                "sys_id": f"je_sys_{i:03d}",
                "element": "comments",
                "element_id": "inc_sys_id_001",
                "value": f"Comment text {i}",
                "sys_created_on": f"2026-06-0{i + 1} 10:00:00",
                "sys_created_by": "admin",
            }
            for i in range(count)
        ]

    # ------------------------------------------------------------------ #
    # Success paths                                                        #
    # ------------------------------------------------------------------ #

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_by_sys_id(self, mock_get):
        """Fetch all journal entries when given a 32-char sys_id (no lookup needed)."""
        inc_sys_id = "a" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": self._make_journal_entries(3)}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_incident_comments(self.auth_manager, self.config, {"incident_id": inc_sys_id})

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["comments"]), 3)
        self.assertEqual(result["incident_id"], inc_sys_id)
        # Only one GET call (no number lookup)
        mock_get.assert_called_once()

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_by_incident_number(self, mock_get):
        """Lookup incident number before querying journal table."""
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = {"result": [{"sys_id": "inc_sys_id_abc"}]}
        lookup_resp.raise_for_status = MagicMock()

        journal_resp = MagicMock()
        journal_resp.json.return_value = {"result": self._make_journal_entries(1)}
        journal_resp.raise_for_status = MagicMock()

        mock_get.side_effect = [lookup_resp, journal_resp]

        result = list_incident_comments(
            self.auth_manager, self.config, {"incident_id": "INC0010001"}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(mock_get.call_count, 2)
        # Second call should target sys_journal_field
        journal_url = mock_get.call_args_list[1][0][0]
        self.assertIn("sys_journal_field", journal_url)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_entry_type_filter(self, mock_get):
        """entry_type=comments is included in sysparm_query."""
        inc_sys_id = "b" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        list_incident_comments(
            self.auth_manager,
            self.config,
            {"incident_id": inc_sys_id, "entry_type": "comments"},
        )

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("element=comments", query)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_work_notes_entry_type_filter(self, mock_get):
        """entry_type=work_notes is included in sysparm_query."""
        inc_sys_id = "c" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        list_incident_comments(
            self.auth_manager,
            self.config,
            {"incident_id": inc_sys_id, "entry_type": "work_notes"},
        )

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("element=work_notes", query)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_no_entry_type_omits_filter(self, mock_get):
        """When entry_type is not supplied the query does not contain element=."""
        inc_sys_id = "d" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        list_incident_comments(self.auth_manager, self.config, {"incident_id": inc_sys_id})

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertNotIn("element=", query)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_pagination_params(self, mock_get):
        """limit and offset are forwarded to the API call."""
        inc_sys_id = "e" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        list_incident_comments(
            self.auth_manager,
            self.config,
            {"incident_id": inc_sys_id, "limit": 50, "offset": 100},
        )

        call_params = mock_get.call_args[1]["params"]
        self.assertEqual(call_params["sysparm_limit"], 50)
        self.assertEqual(call_params["sysparm_offset"], 100)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_has_more_true(self, mock_get):
        """has_more is True when result count equals limit."""
        inc_sys_id = "f" * 32
        entries = self._make_journal_entries(5)

        resp = MagicMock()
        resp.json.return_value = {"result": entries}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_incident_comments(
            self.auth_manager, self.config, {"incident_id": inc_sys_id, "limit": 5}
        )

        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 5)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_has_more_false(self, mock_get):
        """has_more is False when result count is less than limit."""
        inc_sys_id = "0" * 32
        entries = self._make_journal_entries(2)

        resp = MagicMock()
        resp.json.return_value = {"result": entries}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_incident_comments(
            self.auth_manager, self.config, {"incident_id": inc_sys_id, "limit": 20}
        )

        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_entry_shape(self, mock_get):
        """Each returned comment has the expected keys."""
        inc_sys_id = "1" * 32

        entry = {
            "sys_id": "je_001",
            "element": "comments",
            "element_id": inc_sys_id,
            "value": "Hello from a comment",
            "sys_created_on": "2026-06-01 09:00:00",
            "sys_created_by": "john.doe",
        }
        resp = MagicMock()
        resp.json.return_value = {"result": [entry]}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_incident_comments(self.auth_manager, self.config, {"incident_id": inc_sys_id})

        comment = result["comments"][0]
        self.assertEqual(comment["sys_id"], "je_001")
        self.assertEqual(comment["type"], "comments")
        self.assertEqual(comment["value"], "Hello from a comment")
        self.assertEqual(comment["created_on"], "2026-06-01 09:00:00")
        self.assertEqual(comment["created_by"], "john.doe")

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_sysparm_fields_requested(self, mock_get):
        """The request asks for specific sysparm_fields."""
        inc_sys_id = "2" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        list_incident_comments(self.auth_manager, self.config, {"incident_id": inc_sys_id})

        fields = mock_get.call_args[1]["params"]["sysparm_fields"]
        for expected in ("sys_id", "element", "value", "sys_created_on", "sys_created_by"):
            self.assertIn(expected, fields)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_unwraps_nested_params(self, mock_get):
        """Params wrapped in {"params": {...}} are properly unwrapped."""
        inc_sys_id = "3" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_incident_comments(
            self.auth_manager,
            self.config,
            {"params": {"incident_id": inc_sys_id}},
        )

        self.assertTrue(result["success"])

    # ------------------------------------------------------------------ #
    # Failure paths                                                        #
    # ------------------------------------------------------------------ #

    def test_list_comments_missing_incident_id(self):
        """Missing incident_id fails validation."""
        result = list_incident_comments(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("incident_id", result["message"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_incident_not_found(self, mock_get):
        """Return failure when incident number resolves to nothing."""
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = {"result": []}
        lookup_resp.raise_for_status = MagicMock()
        mock_get.return_value = lookup_resp

        result = list_incident_comments(
            self.auth_manager, self.config, {"incident_id": "INC9999999"}
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_http_error_on_journal_fetch(self, mock_get):
        """GET failure on journal table returns success=False."""
        inc_sys_id = "4" * 32

        import requests as req

        mock_get.side_effect = req.exceptions.RequestException("503 Service Unavailable")

        result = list_incident_comments(self.auth_manager, self.config, {"incident_id": inc_sys_id})

        self.assertFalse(result["success"])
        self.assertIn("Error listing incident comments", result["message"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_list_comments_empty_result(self, mock_get):
        """An empty result set is handled gracefully."""
        inc_sys_id = "5" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_incident_comments(self.auth_manager, self.config, {"incident_id": inc_sys_id})

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["comments"], [])
        self.assertFalse(result["has_more"])


if __name__ == "__main__":
    unittest.main()
