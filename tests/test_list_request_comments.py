"""Tests for list_request_comments tool."""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.request_tools import list_request_comments
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestListRequestComments(unittest.TestCase):

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
                "element_id": "req_sys_id_001",
                "value": f"Comment text {i}",
                "sys_created_on": f"2026-10-0{i+1} 10:00:00",
                "sys_created_by": "admin",
            }
            for i in range(count)
        ]

    # ------------------------------------------------------------------ #
    # Success paths                                                        #
    # ------------------------------------------------------------------ #

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_by_sys_id(self, mock_get):
        """Fetch all journal entries when given a 32-char sys_id (no lookup needed)."""
        req_sys_id = "a" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": self._make_journal_entries(3)}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_request_comments(
            self.auth_manager, self.config, {"request_id": req_sys_id}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["comments"]), 3)
        self.assertEqual(result["request_id"], req_sys_id)
        # Only one GET call (no number lookup)
        mock_get.assert_called_once()

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_by_request_number(self, mock_get):
        """Lookup request number before querying journal table."""
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = {"result": [{"sys_id": "req_sys_id_abc"}]}
        lookup_resp.raise_for_status = MagicMock()

        journal_resp = MagicMock()
        journal_resp.json.return_value = {"result": self._make_journal_entries(1)}
        journal_resp.raise_for_status = MagicMock()

        mock_get.side_effect = [lookup_resp, journal_resp]

        result = list_request_comments(
            self.auth_manager, self.config, {"request_id": "REQ0010001"}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(mock_get.call_count, 2)
        # Second call should target sys_journal_field
        journal_url = mock_get.call_args_list[1][0][0]
        self.assertIn("sys_journal_field", journal_url)

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_query_contains_sc_request_name(self, mock_get):
        """Query must include name=sc_request to scope to the right table."""
        req_sys_id = "b" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        list_request_comments(
            self.auth_manager, self.config, {"request_id": req_sys_id}
        )

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("name=sc_request", query)

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_entry_type_filter_comments(self, mock_get):
        """entry_type=comments is included in sysparm_query."""
        req_sys_id = "c" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        list_request_comments(
            self.auth_manager,
            self.config,
            {"request_id": req_sys_id, "entry_type": "comments"},
        )

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("element=comments", query)

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_entry_type_filter_work_notes(self, mock_get):
        """entry_type=work_notes is included in sysparm_query."""
        req_sys_id = "d" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        list_request_comments(
            self.auth_manager,
            self.config,
            {"request_id": req_sys_id, "entry_type": "work_notes"},
        )

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("element=work_notes", query)

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_no_entry_type_omits_filter(self, mock_get):
        """When entry_type is not supplied the query does not contain element=."""
        req_sys_id = "e" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        list_request_comments(
            self.auth_manager, self.config, {"request_id": req_sys_id}
        )

        query = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertNotIn("element=", query)

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_pagination_params(self, mock_get):
        """limit and offset are forwarded to the API call."""
        req_sys_id = "f" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        list_request_comments(
            self.auth_manager,
            self.config,
            {"request_id": req_sys_id, "limit": 50, "offset": 100},
        )

        call_params = mock_get.call_args[1]["params"]
        self.assertEqual(call_params["sysparm_limit"], 50)
        self.assertEqual(call_params["sysparm_offset"], 100)

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_has_more_true(self, mock_get):
        """has_more is True when result count equals limit."""
        req_sys_id = "1" * 32
        entries = self._make_journal_entries(5)

        resp = MagicMock()
        resp.json.return_value = {"result": entries}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_request_comments(
            self.auth_manager, self.config, {"request_id": req_sys_id, "limit": 5}
        )

        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 5)

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_has_more_false(self, mock_get):
        """has_more is False when result count is less than limit."""
        req_sys_id = "2" * 32
        entries = self._make_journal_entries(2)

        resp = MagicMock()
        resp.json.return_value = {"result": entries}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_request_comments(
            self.auth_manager, self.config, {"request_id": req_sys_id, "limit": 20}
        )

        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_entry_shape(self, mock_get):
        """Each returned comment has the expected keys."""
        req_sys_id = "3" * 32

        entry = {
            "sys_id": "je_001",
            "element": "work_notes",
            "element_id": req_sys_id,
            "value": "Internal note here",
            "sys_created_on": "2026-10-01 09:00:00",
            "sys_created_by": "john.doe",
        }
        resp = MagicMock()
        resp.json.return_value = {"result": [entry]}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_request_comments(
            self.auth_manager, self.config, {"request_id": req_sys_id}
        )

        comment = result["comments"][0]
        self.assertEqual(comment["sys_id"], "je_001")
        self.assertEqual(comment["type"], "work_notes")
        self.assertEqual(comment["value"], "Internal note here")
        self.assertEqual(comment["created_on"], "2026-10-01 09:00:00")
        self.assertEqual(comment["created_by"], "john.doe")

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_sysparm_fields_requested(self, mock_get):
        """The request asks for specific sysparm_fields."""
        req_sys_id = "4" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        list_request_comments(
            self.auth_manager, self.config, {"request_id": req_sys_id}
        )

        fields = mock_get.call_args[1]["params"]["sysparm_fields"]
        for expected in ("sys_id", "element", "value", "sys_created_on", "sys_created_by"):
            self.assertIn(expected, fields)

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_unwraps_nested_params(self, mock_get):
        """Params wrapped in {"params": {...}} are properly unwrapped."""
        req_sys_id = "5" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_request_comments(
            self.auth_manager,
            self.config,
            {"params": {"request_id": req_sys_id}},
        )

        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_message_in_response(self, mock_get):
        """Response includes a human-readable message with the count."""
        req_sys_id = "6" * 32
        entries = self._make_journal_entries(2)

        resp = MagicMock()
        resp.json.return_value = {"result": entries}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_request_comments(
            self.auth_manager, self.config, {"request_id": req_sys_id}
        )

        self.assertIn("2", result["message"])

    # ------------------------------------------------------------------ #
    # Failure paths                                                        #
    # ------------------------------------------------------------------ #

    def test_list_comments_missing_request_id(self):
        """Missing request_id fails validation."""
        result = list_request_comments(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("request_id", result["message"])

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_request_not_found(self, mock_get):
        """Return failure when request number resolves to nothing."""
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = {"result": []}
        lookup_resp.raise_for_status = MagicMock()
        mock_get.return_value = lookup_resp

        result = list_request_comments(
            self.auth_manager, self.config, {"request_id": "REQ9999999"}
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_http_error_on_journal_fetch(self, mock_get):
        """GET failure on journal table returns success=False."""
        req_sys_id = "7" * 32

        import requests as req
        mock_get.side_effect = req.exceptions.RequestException("503 Service Unavailable")

        result = list_request_comments(
            self.auth_manager, self.config, {"request_id": req_sys_id}
        )

        self.assertFalse(result["success"])
        self.assertIn("Error listing request comments", result["message"])

    @patch("servicenow_mcp.tools.request_tools.requests.get")
    def test_list_comments_empty_result(self, mock_get):
        """An empty result set is handled gracefully."""
        req_sys_id = "8" * 32

        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = list_request_comments(
            self.auth_manager, self.config, {"request_id": req_sys_id}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["comments"], [])
        self.assertFalse(result["has_more"])

    def test_no_instance_url(self):
        """Return failure when instance_url is missing."""
        config = ServerConfig(
            instance_url="",
            auth=self.config.auth,
        )
        result = list_request_comments(
            self.auth_manager, config, {"request_id": "a" * 32}
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])


if __name__ == "__main__":
    unittest.main()
