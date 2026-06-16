"""Tests for approve_change_approval and reject_change_approval in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import (
    approve_change_approval,
    reject_change_approval,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

APPROVAL_SYS_ID = "a" * 32
CHANGE_SYS_ID = "b" * 32

FAKE_APPROVAL_RECORD = {
    "sys_id": APPROVAL_SYS_ID,
    "document_id": {"display_value": "CHG0010001", "value": CHANGE_SYS_ID},
    "source_table": "change_request",
    "approver": {"display_value": "Jane Approver", "value": "c" * 32},
    "state": "approved",
    "comments": "Looks good",
    "due_date": "2026-07-01 00:00:00",
    "sys_created_on": "2026-06-14 08:00:00",
    "sys_updated_on": "2026-06-16 10:00:00",
}

FAKE_REJECTED_RECORD = dict(FAKE_APPROVAL_RECORD, state="rejected", comments="Not ready")


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
# approve_change_approval
# ---------------------------------------------------------------------------


class TestApproveChangeApprovalSuccess(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_success_returns_approval(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_APPROVAL_RECORD})
        result = approve_change_approval(
            _make_auth_manager(), _make_config(), {"sys_id": APPROVAL_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertIn("approval", result)
        self.assertEqual(result["approval"]["state"], "approved")
        self.assertIn("approved successfully", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_patches_correct_url(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_APPROVAL_RECORD})
        approve_change_approval(
            _make_auth_manager(), _make_config(), {"sys_id": APPROVAL_SYS_ID}
        )
        args, _ = mock_req.call_args
        self.assertEqual(args[0], "PATCH")
        self.assertIn(APPROVAL_SYS_ID, args[1])
        self.assertIn("sysapproval_approver", args[1])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_body_contains_state_approved(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_APPROVAL_RECORD})
        approve_change_approval(
            _make_auth_manager(), _make_config(), {"sys_id": APPROVAL_SYS_ID}
        )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["json"]["state"], "approved")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_optional_comments_included_in_body(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_APPROVAL_RECORD})
        approve_change_approval(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": APPROVAL_SYS_ID, "comments": "Approved per CAB decision"},
        )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["json"]["comments"], "Approved per CAB decision")

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_no_comments_omitted_from_body(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_APPROVAL_RECORD})
        approve_change_approval(
            _make_auth_manager(), _make_config(), {"sys_id": APPROVAL_SYS_ID}
        )
        _, kwargs = mock_req.call_args
        self.assertNotIn("comments", kwargs["json"])


class TestApproveChangeApprovalErrors(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_returns_not_found(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        result = approve_change_approval(
            _make_auth_manager(), _make_config(), {"sys_id": APPROVAL_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_500_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = approve_change_approval(
            _make_auth_manager(), _make_config(), {"sys_id": APPROVAL_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error approving", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_network_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("network down")
        result = approve_change_approval(
            _make_auth_manager(), _make_config(), {"sys_id": APPROVAL_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error approving", result["message"])

    def test_missing_sys_id_returns_failure(self):
        result = approve_change_approval(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_missing_instance_url_returns_failure(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = {}
        auth_manager.instance_url = None
        config = MagicMock()
        config.instance_url = None
        config.auth = None
        result = approve_change_approval(auth_manager, config, {"sys_id": APPROVAL_SYS_ID})
        self.assertFalse(result["success"])

    def test_missing_headers_returns_failure(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = "https://dev99999.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"
        config.auth = None
        result = approve_change_approval(auth_manager, config, {"sys_id": APPROVAL_SYS_ID})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# reject_change_approval
# ---------------------------------------------------------------------------


class TestRejectChangeApprovalSuccess(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_success_returns_approval(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_REJECTED_RECORD})
        result = reject_change_approval(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": APPROVAL_SYS_ID, "rejection_reason": "Incomplete risk assessment"},
        )
        self.assertTrue(result["success"])
        self.assertIn("approval", result)
        self.assertEqual(result["approval"]["state"], "rejected")
        self.assertIn("rejected successfully", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_patches_correct_url(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_REJECTED_RECORD})
        reject_change_approval(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": APPROVAL_SYS_ID, "rejection_reason": "Risk not assessed"},
        )
        args, _ = mock_req.call_args
        self.assertEqual(args[0], "PATCH")
        self.assertIn(APPROVAL_SYS_ID, args[1])
        self.assertIn("sysapproval_approver", args[1])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_body_contains_state_rejected_and_reason(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_REJECTED_RECORD})
        reject_change_approval(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": APPROVAL_SYS_ID, "rejection_reason": "Change window conflict"},
        )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["json"]["state"], "rejected")
        self.assertEqual(kwargs["json"]["comments"], "Change window conflict")


class TestRejectChangeApprovalErrors(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_returns_not_found(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        result = reject_change_approval(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": APPROVAL_SYS_ID, "rejection_reason": "No reason"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_500_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = reject_change_approval(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": APPROVAL_SYS_ID, "rejection_reason": "No reason"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error rejecting", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_network_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = reject_change_approval(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": APPROVAL_SYS_ID, "rejection_reason": "No reason"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error rejecting", result["message"])

    def test_missing_sys_id_returns_failure(self):
        result = reject_change_approval(
            _make_auth_manager(),
            _make_config(),
            {"rejection_reason": "No reason"},
        )
        self.assertFalse(result["success"])

    def test_missing_rejection_reason_returns_failure(self):
        result = reject_change_approval(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": APPROVAL_SYS_ID},
        )
        self.assertFalse(result["success"])

    def test_missing_instance_url_returns_failure(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = {}
        auth_manager.instance_url = None
        config = MagicMock()
        config.instance_url = None
        config.auth = None
        result = reject_change_approval(
            auth_manager,
            config,
            {"sys_id": APPROVAL_SYS_ID, "rejection_reason": "No reason"},
        )
        self.assertFalse(result["success"])

    def test_missing_headers_returns_failure(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = "https://dev99999.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"
        config.auth = None
        result = reject_change_approval(
            auth_manager,
            config,
            {"sys_id": APPROVAL_SYS_ID, "rejection_reason": "No reason"},
        )
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
