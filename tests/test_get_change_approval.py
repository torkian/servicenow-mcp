"""Tests for get_change_approval in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import get_change_approval
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
CHANGE_SYS_ID = "b" * 32
APPROVER_SYS_ID = "c" * 32

FAKE_APPROVAL_RECORD = {
    "sys_id": FAKE_SYS_ID,
    "document_id": {"display_value": "CHG0010001", "value": CHANGE_SYS_ID},
    "source_table": "change_request",
    "approver": {"display_value": "Jane Approver", "value": APPROVER_SYS_ID},
    "state": "requested",
    "comments": "Please review",
    "due_date": "2026-07-01 00:00:00",
    "sys_created_on": "2026-06-15 08:00:00",
    "sys_updated_on": "2026-06-15 09:00:00",
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


def _make_response(status_code, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestGetChangeApprovalSuccess(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_normalised_approval(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_APPROVAL_RECORD})
        result = get_change_approval(_make_auth_manager(), _make_config(), {"sys_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        approval = result["approval"]
        self.assertEqual(approval["sys_id"], FAKE_SYS_ID)
        self.assertEqual(approval["change_request"], "CHG0010001")
        self.assertEqual(approval["approver"], "Jane Approver")
        self.assertEqual(approval["state"], "requested")
        self.assertEqual(approval["comments"], "Please review")
        self.assertEqual(approval["due_date"], "2026-07-01 00:00:00")
        self.assertEqual(approval["created_on"], "2026-06-15 08:00:00")
        self.assertEqual(approval["updated_on"], "2026-06-15 09:00:00")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_url_contains_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_APPROVAL_RECORD})
        get_change_approval(_make_auth_manager(), _make_config(), {"sys_id": FAKE_SYS_ID})
        call_args = mock_req.call_args
        url = call_args[0][1]
        self.assertIn(FAKE_SYS_ID, url)
        self.assertIn("sysapproval_approver", url)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_display_value_param_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_APPROVAL_RECORD})
        get_change_approval(_make_auth_manager(), _make_config(), {"sys_id": FAKE_SYS_ID})
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        self.assertEqual(params.get("sysparm_display_value"), "true")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_raw_string_reference_fields(self, mock_req):
        record = dict(FAKE_APPROVAL_RECORD)
        record["document_id"] = "CHG0010001"
        record["approver"] = "jane.approver"
        mock_req.return_value = _make_response(200, {"result": record})
        result = get_change_approval(_make_auth_manager(), _make_config(), {"sys_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["approval"]["change_request"], "CHG0010001")
        self.assertEqual(result["approval"]["approver"], "jane.approver")


# ---------------------------------------------------------------------------
# 404 guard
# ---------------------------------------------------------------------------


class TestGetChangeApproval404(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_status_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        result = get_change_approval(_make_auth_manager(), _make_config(), {"sys_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())
        self.assertIn(FAKE_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_empty_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_change_approval(_make_auth_manager(), _make_config(), {"sys_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_none_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": None})
        result = get_change_approval(_make_auth_manager(), _make_config(), {"sys_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())


# ---------------------------------------------------------------------------
# Network errors
# ---------------------------------------------------------------------------


class TestGetChangeApprovalNetworkErrors(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_500_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = get_change_approval(_make_auth_manager(), _make_config(), {"sys_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving change approval", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = get_change_approval(_make_auth_manager(), _make_config(), {"sys_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving change approval", result["message"])


# ---------------------------------------------------------------------------
# Missing / invalid params
# ---------------------------------------------------------------------------


class TestGetChangeApprovalParams(unittest.TestCase):
    def test_missing_sys_id_returns_failure(self):
        result = get_change_approval(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_missing_instance_url_returns_failure(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = {}
        auth_manager.instance_url = None
        config = MagicMock()
        config.instance_url = None
        config.auth = None
        result = get_change_approval(auth_manager, config, {"sys_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])

    def test_missing_headers_returns_failure(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = "https://dev99999.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"
        config.auth = None
        result = get_change_approval(auth_manager, config, {"sys_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
