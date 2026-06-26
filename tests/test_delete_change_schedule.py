"""Tests for delete_change_schedule in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import delete_change_schedule
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32


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
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestDeleteChangeScheduleSuccess(unittest.TestCase):
    """Happy-path tests."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_delete_by_sys_id_returns_204(self, mock_req):
        """sys_id passthrough → single DELETE call → 204 success."""
        mock_req.return_value = _make_response(204)
        result = delete_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID},
        )
        self.assertTrue(result["success"])
        self.assertIn("deleted successfully", result["message"])
        mock_req.assert_called_once()

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_delete_by_sys_id_returns_200(self, mock_req):
        """DELETE returning 200 (some SN versions) also succeeds."""
        mock_req.return_value = _make_response(200)
        result = delete_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID},
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_delete_by_name_resolves_then_deletes(self, mock_req):
        """Non-hex schedule_id triggers resolver GET then DELETE."""
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        delete_resp = _make_response(204)
        mock_req.side_effect = [resolve_resp, delete_resp]
        result = delete_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": "Saturday Night Change Window"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(mock_req.call_count, 2)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_message_contains_schedule_id(self, mock_req):
        """Success message includes the original schedule_id."""
        mock_req.return_value = _make_response(204)
        result = delete_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID},
        )
        self.assertIn(FAKE_SYS_ID, result["message"])


class TestDeleteChangeSchedule404(unittest.TestCase):
    """404 / not-found handling."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_on_delete(self, mock_req):
        """DELETE returning 404 → success=False."""
        mock_req.return_value = _make_response(404)
        result = delete_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_name_resolve_returns_no_results(self, mock_req):
        """Resolver GET returns empty list → not-found before DELETE."""
        mock_req.return_value = _make_response(200, {"result": []})
        result = delete_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": "NonExistentSchedule"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        mock_req.assert_called_once()

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_name_resolve_raises_exception(self, mock_req):
        """Resolver network error → not-found guard."""
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = delete_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": "NonExistentSchedule"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])


class TestDeleteChangeScheduleErrors(unittest.TestCase):
    """Error handling tests."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_on_delete(self, mock_req):
        """HTTP error during DELETE is caught and returned."""
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        error_resp = _make_response(500)
        mock_req.side_effect = [resolve_resp, requests.exceptions.HTTPError(response=error_resp)]
        result = delete_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": "SomeName"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error deleting change schedule", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_on_delete(self, mock_req):
        """ConnectionError during DELETE is caught."""
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]}),
            requests.exceptions.ConnectionError("reset"),
        ]
        result = delete_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {"schedule_id": "SomeName"},
        )
        self.assertFalse(result["success"])

    def test_missing_schedule_id(self):
        """Missing required schedule_id returns validation error."""
        result = delete_change_schedule(
            _make_auth_manager(),
            _make_config(),
            {},
        )
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        """Missing instance_url returns error before any HTTP call."""
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth_manager.instance_url = None

        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test", password="test"),
        )
        server_config = ServerConfig(instance_url="", auth=auth_config)

        result = delete_change_schedule(
            auth_manager,
            server_config,
            {"schedule_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])


class TestDeleteChangeScheduleParamsModel(unittest.TestCase):
    """Pydantic model validation."""

    def test_valid_params(self):
        from servicenow_mcp.tools.change_tools import DeleteChangeScheduleParams
        p = DeleteChangeScheduleParams(schedule_id=FAKE_SYS_ID)
        self.assertEqual(p.schedule_id, FAKE_SYS_ID)

    def test_missing_schedule_id_raises(self):
        from servicenow_mcp.tools.change_tools import DeleteChangeScheduleParams
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            DeleteChangeScheduleParams()


if __name__ == "__main__":
    unittest.main()
