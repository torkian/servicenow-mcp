"""Tests for delete_change_schedule_span in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import delete_change_schedule_span
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


class TestDeleteChangeScheduleSpanSuccess(unittest.TestCase):
    """Happy-path tests."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_delete_returns_204(self, mock_req):
        """Standard DELETE returns 204 → success."""
        mock_req.return_value = _make_response(204)
        result = delete_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID},
        )
        self.assertTrue(result["success"])
        self.assertIn("deleted successfully", result["message"])
        mock_req.assert_called_once()

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_delete_returns_200(self, mock_req):
        """DELETE returning 200 (some SN versions) also succeeds."""
        mock_req.return_value = _make_response(200)
        result = delete_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID},
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_message_contains_span_id(self, mock_req):
        """Success message includes the original span_id."""
        mock_req.return_value = _make_response(204)
        result = delete_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID},
        )
        self.assertIn(FAKE_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_params_nested_under_params_key(self, mock_req):
        """Params may arrive wrapped under a 'params' key."""
        mock_req.return_value = _make_response(204)
        result = delete_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"params": {"span_id": FAKE_SYS_ID}},
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_correct_url_used(self, mock_req):
        """DELETE request must target cmn_schedule_span/{span_id}."""
        mock_req.return_value = _make_response(204)
        delete_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID},
        )
        called_url = mock_req.call_args[0][1]
        self.assertIn("cmn_schedule_span", called_url)
        self.assertIn(FAKE_SYS_ID, called_url)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_delete_method_used(self, mock_req):
        """HTTP method must be DELETE."""
        mock_req.return_value = _make_response(204)
        delete_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID},
        )
        called_method = mock_req.call_args[0][0]
        self.assertEqual(called_method, "DELETE")


class TestDeleteChangeScheduleSpan404(unittest.TestCase):
    """404 / not-found handling."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_on_delete(self, mock_req):
        """DELETE returning 404 → success=False."""
        mock_req.return_value = _make_response(404)
        result = delete_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_404_message_contains_span_id(self, mock_req):
        """Not-found message must contain the requested span_id."""
        mock_req.return_value = _make_response(404)
        result = delete_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID},
        )
        self.assertIn(FAKE_SYS_ID, result["message"])


class TestDeleteChangeScheduleSpanErrors(unittest.TestCase):
    """Error handling tests."""

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_on_delete(self, mock_req):
        """HTTP error during DELETE is caught and returned."""
        error_resp = _make_response(500)
        mock_req.side_effect = requests.exceptions.HTTPError(response=error_resp)
        result = delete_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error deleting change schedule span", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_on_delete(self, mock_req):
        """ConnectionError during DELETE is caught."""
        mock_req.side_effect = requests.exceptions.ConnectionError("reset")
        result = delete_change_schedule_span(
            _make_auth_manager(),
            _make_config(),
            {"span_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error deleting change schedule span", result["message"])

    def test_missing_span_id(self):
        """Missing required span_id returns validation error."""
        result = delete_change_schedule_span(
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

        result = delete_change_schedule_span(
            auth_manager,
            server_config,
            {"span_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])

    def test_no_headers(self):
        """If get_headers returns None, return failure before any HTTP call."""
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = "https://dev99999.service-now.com"

        result = delete_change_schedule_span(
            auth_manager,
            _make_config(),
            {"span_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])


class TestDeleteChangeScheduleSpanParamsModel(unittest.TestCase):
    """Pydantic model validation."""

    def test_valid_params(self):
        from servicenow_mcp.tools.change_tools import DeleteChangeScheduleSpanParams
        p = DeleteChangeScheduleSpanParams(span_id=FAKE_SYS_ID)
        self.assertEqual(p.span_id, FAKE_SYS_ID)

    def test_missing_span_id_raises(self):
        from servicenow_mcp.tools.change_tools import DeleteChangeScheduleSpanParams
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            DeleteChangeScheduleSpanParams()


if __name__ == "__main__":
    unittest.main()
