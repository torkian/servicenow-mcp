"""Tests for list_change_approvals in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import (
    _format_approval,
    list_change_approvals,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
CHANGE_SYS_ID = "b" * 32
APPROVER_SYS_ID = "c" * 32

FAKE_APPROVAL = {
    "sys_id": FAKE_SYS_ID,
    "document_id": {"display_value": "CHG0010001", "value": CHANGE_SYS_ID},
    "source_table": "change_request",
    "approver": {"display_value": "Jane Approver", "value": APPROVER_SYS_ID},
    "state": "requested",
    "comments": "Please review ASAP",
    "due_date": "2026-07-01 00:00:00",
    "sys_created_on": "2026-06-14 08:00:00",
    "sys_updated_on": "2026-06-14 09:00:00",
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
# _format_approval
# ---------------------------------------------------------------------------


class TestFormatApproval(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_approval(FAKE_APPROVAL)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["change_request"], "CHG0010001")
        self.assertEqual(result["approver"], "Jane Approver")
        self.assertEqual(result["state"], "requested")
        self.assertEqual(result["comments"], "Please review ASAP")
        self.assertEqual(result["due_date"], "2026-07-01 00:00:00")
        self.assertEqual(result["created_on"], "2026-06-14 08:00:00")
        self.assertEqual(result["updated_on"], "2026-06-14 09:00:00")

    def test_handles_raw_string_reference_fields(self):
        record = {
            "sys_id": FAKE_SYS_ID,
            "document_id": "CHG0010001",
            "approver": "jane.approver",
            "state": "approved",
            "comments": None,
            "due_date": None,
            "sys_created_on": None,
            "sys_updated_on": None,
        }
        result = _format_approval(record)
        self.assertEqual(result["change_request"], "CHG0010001")
        self.assertEqual(result["approver"], "jane.approver")

    def test_handles_missing_fields(self):
        result = _format_approval({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["change_request"])
        self.assertIsNone(result["approver"])
        self.assertIsNone(result["state"])


# ---------------------------------------------------------------------------
# list_change_approvals — no filter
# ---------------------------------------------------------------------------


class TestListChangeApprovalsNoFilter(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_success_returns_approvals(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_APPROVAL]})
        result = list_change_approvals(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertIn("approvals", result)
        self.assertEqual(len(result["approvals"]), 1)
        self.assertEqual(result["approvals"][0]["state"], "requested")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_always_scopes_to_change_request_source_table(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_change_approvals(_make_auth_manager(), _make_config(), {})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("source_table=change_request", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_empty_result_returns_success_with_empty_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_change_approvals(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(result["approvals"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = list_change_approvals(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing change approvals", result["message"])


# ---------------------------------------------------------------------------
# list_change_approvals — state filter
# ---------------------------------------------------------------------------


class TestListChangeApprovalsStateFilter(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_state_filter_appended(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_change_approvals(
            _make_auth_manager(), _make_config(), {"state": "approved"}
        )
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("state=approved", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_rejected_state_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_change_approvals(
            _make_auth_manager(), _make_config(), {"state": "rejected"}
        )
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("state=rejected", query)


# ---------------------------------------------------------------------------
# list_change_approvals — approver filter
# ---------------------------------------------------------------------------


class TestListChangeApprovalsApproverFilter(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_approver_filter_appended(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_change_approvals(
            _make_auth_manager(), _make_config(), {"approver": "jane.approver"}
        )
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("approver.name=jane.approver", query)


# ---------------------------------------------------------------------------
# list_change_approvals — change_id filter (sys_id path)
# ---------------------------------------------------------------------------


class TestListChangeApprovalsByChangeId(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_sys_id_passed_directly(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_APPROVAL]})
        result = list_change_approvals(
            _make_auth_manager(), _make_config(), {"change_id": CHANGE_SYS_ID}
        )
        self.assertTrue(result["success"])
        # Should only make one request (no CHG lookup needed for 32-char hex)
        mock_req.assert_called_once()
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn(f"document_id={CHANGE_SYS_ID}", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_chg_number_triggers_lookup(self, mock_req):
        lookup_resp = _make_response(200, {"result": [{"sys_id": CHANGE_SYS_ID}]})
        approval_resp = _make_response(200, {"result": [FAKE_APPROVAL]})
        mock_req.side_effect = [lookup_resp, approval_resp]

        result = list_change_approvals(
            _make_auth_manager(), _make_config(), {"change_id": "CHG0010001"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(mock_req.call_count, 2)
        # Second call targets the approval table
        second_call_kwargs = mock_req.call_args_list[1][1]
        query = second_call_kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn(f"document_id={CHANGE_SYS_ID}", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_chg_number_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_change_approvals(
            _make_auth_manager(), _make_config(), {"change_id": "CHG9999999"}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_chg_lookup_network_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_change_approvals(
            _make_auth_manager(), _make_config(), {"change_id": "CHG0010001"}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])


# ---------------------------------------------------------------------------
# list_change_approvals — pagination
# ---------------------------------------------------------------------------


class TestListChangeApprovalsPagination(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_pagination_keys_present(self, mock_req):
        approvals = [FAKE_APPROVAL] * 5
        mock_req.return_value = _make_response(200, {"result": approvals})
        result = list_change_approvals(
            _make_auth_manager(), _make_config(), {"limit": 5, "offset": 0}
        )
        self.assertIn("has_more", result)
        self.assertIn("count", result)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_limit_and_offset_forwarded(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_change_approvals(
            _make_auth_manager(), _make_config(), {"limit": 7, "offset": 14}
        )
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        self.assertEqual(params.get("sysparm_limit"), 7)
        self.assertEqual(params.get("sysparm_offset"), 14)


# ---------------------------------------------------------------------------
# list_change_approvals — invalid config
# ---------------------------------------------------------------------------


class TestListChangeApprovalsInvalidConfig(unittest.TestCase):
    def test_missing_instance_url_returns_failure(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = {}
        auth_manager.instance_url = None

        config = MagicMock()
        config.instance_url = None
        config.auth = None

        result = list_change_approvals(auth_manager, config, {})
        self.assertFalse(result["success"])

    def test_missing_headers_returns_failure(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = "https://dev99999.service-now.com"

        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"
        config.auth = None

        result = list_change_approvals(auth_manager, config, {})
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
