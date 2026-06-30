"""Tests for list_change_conflicts in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import (
    _format_change_conflict,
    list_change_conflicts,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
CHANGE_SYS_ID = "b" * 32
CONFLICT_CI_SYS_ID = "c" * 32
CONFLICT_CHANGE_SYS_ID = "d" * 32
CONFLICT_SYS_ID = "e" * 32


FAKE_CONFLICT = {
    "sys_id": CONFLICT_SYS_ID,
    "change_request": {"display_value": "CHG0012345", "value": CHANGE_SYS_ID},
    "conflict_ci": {"display_value": "web-server-01", "value": CONFLICT_CI_SYS_ID},
    "conflict_change": {"display_value": "CHG0012346", "value": CONFLICT_CHANGE_SYS_ID},
    "type": {"display_value": "CI Conflict", "value": "ci_conflict"},
    "state": {"display_value": "Unresolved", "value": "unresolved"},
    "blackout_window": {"display_value": "", "value": ""},
    "sys_created_on": "2026-06-01 10:00:00",
    "sys_updated_on": "2026-06-02 14:30:00",
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


def _make_response(status_code, json_data):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


# ---------------------------------------------------------------------------
# _format_change_conflict
# ---------------------------------------------------------------------------


class TestFormatChangeConflict(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_change_conflict(FAKE_CONFLICT)
        self.assertEqual(result["sys_id"], CONFLICT_SYS_ID)
        self.assertEqual(result["change_request"], "CHG0012345")
        self.assertEqual(result["conflict_ci"], "web-server-01")
        self.assertEqual(result["conflict_change"], "CHG0012346")
        self.assertEqual(result["type"], "CI Conflict")
        self.assertEqual(result["state"], "Unresolved")
        self.assertEqual(result["created_on"], "2026-06-01 10:00:00")
        self.assertEqual(result["updated_on"], "2026-06-02 14:30:00")

    def test_handles_raw_string_values(self):
        record = {
            "sys_id": CONFLICT_SYS_ID,
            "change_request": CHANGE_SYS_ID,
            "conflict_ci": "web-server-01",
            "conflict_change": "CHG0012346",
            "type": "schedule_conflict",
            "state": "accepted",
            "blackout_window": "some_blackout",
            "sys_created_on": "2026-06-01 10:00:00",
            "sys_updated_on": "2026-06-01 10:00:00",
        }
        result = _format_change_conflict(record)
        self.assertEqual(result["change_request"], CHANGE_SYS_ID)
        self.assertEqual(result["conflict_ci"], "web-server-01")
        self.assertEqual(result["type"], "schedule_conflict")
        self.assertEqual(result["state"], "accepted")
        self.assertEqual(result["blackout_window"], "some_blackout")

    def test_handles_empty_dict(self):
        result = _format_change_conflict({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["change_request"])
        self.assertIsNone(result["conflict_ci"])
        self.assertIsNone(result["conflict_change"])
        self.assertIsNone(result["type"])
        self.assertIsNone(result["state"])
        self.assertIsNone(result["blackout_window"])
        self.assertIsNone(result["created_on"])
        self.assertIsNone(result["updated_on"])

    def test_dict_value_fallback(self):
        record = dict(FAKE_CONFLICT, type={"display_value": None, "value": "ci_conflict"})
        result = _format_change_conflict(record)
        self.assertEqual(result["type"], "ci_conflict")


# ---------------------------------------------------------------------------
# list_change_conflicts — no filters
# ---------------------------------------------------------------------------


class TestListChangeConflictsNoFilter(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_CONFLICT]})

        result = list_change_conflicts(
            _make_auth_manager(),
            _make_config(),
            {"limit": 20, "offset": 0},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])
        conflicts = result["conflicts"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["sys_id"], CONFLICT_SYS_ID)
        self.assertEqual(conflicts[0]["type"], "CI Conflict")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_empty_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        result = list_change_conflicts(_make_auth_manager(), _make_config(), {})

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["conflicts"], [])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_display_value_all_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_conflicts(_make_auth_manager(), _make_config(), {})

        api_params = mock_req.call_args[1]["params"]
        self.assertEqual(api_params["sysparm_display_value"], "all")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_no_query_when_no_filters(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_conflicts(_make_auth_manager(), _make_config(), {})

        api_params = mock_req.call_args[1]["params"]
        self.assertNotIn("sysparm_query", api_params)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_fields_param_included(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_conflicts(_make_auth_manager(), _make_config(), {})

        api_params = mock_req.call_args[1]["params"]
        self.assertIn("sys_id", api_params["sysparm_fields"])
        self.assertIn("change_request", api_params["sysparm_fields"])
        self.assertIn("type", api_params["sysparm_fields"])
        self.assertIn("state", api_params["sysparm_fields"])


# ---------------------------------------------------------------------------
# list_change_conflicts — change_id filter
# ---------------------------------------------------------------------------


class TestListChangeConflictsChangeIdFilter(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._resolve_change_request_sys_id")
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_chg_number_resolved(self, mock_req, mock_resolve):
        mock_resolve.return_value = CHANGE_SYS_ID
        mock_req.return_value = _make_response(200, {"result": [FAKE_CONFLICT]})

        result = list_change_conflicts(
            _make_auth_manager(),
            _make_config(),
            {"change_id": "CHG0012345"},
        )

        self.assertTrue(result["success"])
        mock_resolve.assert_called_once()
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn(f"change_request={CHANGE_SYS_ID}", query)

    @patch("servicenow_mcp.tools.change_tools._resolve_change_request_sys_id")
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_sys_id_passthrough(self, mock_req, mock_resolve):
        mock_resolve.return_value = CHANGE_SYS_ID
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_conflicts(
            _make_auth_manager(),
            _make_config(),
            {"change_id": CHANGE_SYS_ID},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn(f"change_request={CHANGE_SYS_ID}", query)

    @patch("servicenow_mcp.tools.change_tools._resolve_change_request_sys_id")
    def test_change_not_found_returns_failure(self, mock_resolve):
        mock_resolve.return_value = None

        result = list_change_conflicts(
            _make_auth_manager(),
            _make_config(),
            {"change_id": "CHG9999999"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])


# ---------------------------------------------------------------------------
# list_change_conflicts — type and state filters
# ---------------------------------------------------------------------------


class TestListChangeConflictsFilters(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_type_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_conflicts(
            _make_auth_manager(),
            _make_config(),
            {"type": "ci_conflict"},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("type=ci_conflict", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_state_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_conflicts(
            _make_auth_manager(),
            _make_config(),
            {"state": "unresolved"},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("state=unresolved", query)

    @patch("servicenow_mcp.tools.change_tools._resolve_change_request_sys_id")
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_combined_filters(self, mock_req, mock_resolve):
        mock_resolve.return_value = CHANGE_SYS_ID
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_conflicts(
            _make_auth_manager(),
            _make_config(),
            {
                "change_id": "CHG0012345",
                "type": "ci_conflict",
                "state": "unresolved",
            },
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn(f"change_request={CHANGE_SYS_ID}", query)
        self.assertIn("type=ci_conflict", query)
        self.assertIn("state=unresolved", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_state_accepted(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_conflicts(
            _make_auth_manager(),
            _make_config(),
            {"state": "accepted"},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("state=accepted", query)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestListChangeConflictsPagination(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_has_more_when_full_page(self, mock_req):
        records = [dict(FAKE_CONFLICT, sys_id=f"{i:032x}") for i in range(5)]
        mock_req.return_value = _make_response(200, {"result": records})

        result = list_change_conflicts(
            _make_auth_manager(),
            _make_config(),
            {"limit": 5, "offset": 0},
        )

        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 5)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_no_has_more_when_partial_page(self, mock_req):
        records = [dict(FAKE_CONFLICT, sys_id=f"{i:032x}") for i in range(3)]
        mock_req.return_value = _make_response(200, {"result": records})

        result = list_change_conflicts(
            _make_auth_manager(),
            _make_config(),
            {"limit": 5, "offset": 10},
        )

        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_offset_and_limit_passed_to_api(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_conflicts(
            _make_auth_manager(),
            _make_config(),
            {"limit": 10, "offset": 30},
        )

        api_params = mock_req.call_args[1]["params"]
        self.assertEqual(api_params["sysparm_limit"], 10)
        self.assertEqual(api_params["sysparm_offset"], 30)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestListChangeConflictsErrors(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {"error": {"message": "Internal error"}})

        result = list_change_conflicts(_make_auth_manager(), _make_config(), {})

        self.assertFalse(result["success"])
        self.assertIn("Error listing change conflicts", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("connection refused")

        result = list_change_conflicts(_make_auth_manager(), _make_config(), {})

        self.assertFalse(result["success"])
        self.assertIn("Error listing change conflicts", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_instance_url", return_value=None)
    def test_missing_instance_url(self, _mock_url):
        result = list_change_conflicts(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_headers", return_value=None)
    def test_missing_headers(self, _mock_headers):
        result = list_change_conflicts(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    def test_invalid_params_returns_failure(self):
        result = list_change_conflicts(
            _make_auth_manager(),
            _make_config(),
            {"limit": "not_a_number"},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_multiple_conflicts_returned(self, mock_req):
        records = [dict(FAKE_CONFLICT, sys_id=f"{i:032x}") for i in range(3)]
        mock_req.return_value = _make_response(200, {"result": records})

        result = list_change_conflicts(_make_auth_manager(), _make_config(), {"limit": 20})

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)


if __name__ == "__main__":
    unittest.main()
