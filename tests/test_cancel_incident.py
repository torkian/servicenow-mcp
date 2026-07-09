"""Tests for the cancel_incident tool."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.incident_tools import CancelIncidentParams, cancel_incident
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "b" * 32
FAKE_NUMBER = "INC0020002"


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev99999.service-now.com", auth=auth_config)


def _make_auth():
    auth = MagicMock(spec=AuthManager)
    auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    return auth


def _make_response(status_code, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


class TestCancelIncidentBySysId(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_cancel_by_sys_id_success(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": {"sys_id": FAKE_SYS_ID, "number": FAKE_NUMBER}}
        )
        params = CancelIncidentParams(incident_id=FAKE_SYS_ID)
        result = cancel_incident(self.config, self.auth, params)

        self.assertTrue(result.success)
        self.assertIn("cancelled", result.message.lower())
        self.assertEqual(result.incident_id, FAKE_SYS_ID)
        self.assertEqual(result.incident_number, FAKE_NUMBER)

        call_args = mock_req.call_args
        self.assertEqual(call_args[0][0], "PATCH")
        self.assertIn(FAKE_SYS_ID, call_args[0][1])
        self.assertEqual(call_args[1]["json"]["state"], "8")

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_cancel_sets_state_8(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": {"sys_id": FAKE_SYS_ID, "number": FAKE_NUMBER}}
        )
        params = CancelIncidentParams(incident_id=FAKE_SYS_ID)
        cancel_incident(self.config, self.auth, params)

        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["state"], "8")

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_cancel_with_reason_includes_work_notes(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": {"sys_id": FAKE_SYS_ID, "number": FAKE_NUMBER}}
        )
        params = CancelIncidentParams(incident_id=FAKE_SYS_ID, cancel_reason="Duplicate ticket")
        cancel_incident(self.config, self.auth, params)

        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["work_notes"], "Duplicate ticket")

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_cancel_without_reason_omits_work_notes(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": {"sys_id": FAKE_SYS_ID, "number": FAKE_NUMBER}}
        )
        params = CancelIncidentParams(incident_id=FAKE_SYS_ID)
        cancel_incident(self.config, self.auth, params)

        body = mock_req.call_args[1]["json"]
        self.assertNotIn("work_notes", body)

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_cancel_404_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(404)
        params = CancelIncidentParams(incident_id=FAKE_SYS_ID)
        result = cancel_incident(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("not found", result.message.lower())

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_cancel_patch_fails_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("connection refused")
        params = CancelIncidentParams(incident_id=FAKE_SYS_ID)
        result = cancel_incident(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to cancel incident", result.message)

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_cancel_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        params = CancelIncidentParams(incident_id=FAKE_SYS_ID)
        result = cancel_incident(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to cancel incident", result.message)


class TestCancelIncidentByNumber(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_cancel_by_number_resolves_sys_id(self, mock_req):
        lookup_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        patch_resp = _make_response(
            200, {"result": {"sys_id": FAKE_SYS_ID, "number": FAKE_NUMBER}}
        )
        mock_req.side_effect = [lookup_resp, patch_resp]

        params = CancelIncidentParams(incident_id=FAKE_NUMBER)
        result = cancel_incident(self.config, self.auth, params)

        self.assertTrue(result.success)
        self.assertEqual(mock_req.call_count, 2)
        get_call = mock_req.call_args_list[0]
        self.assertEqual(get_call[0][0], "GET")
        patch_call = mock_req.call_args_list[1]
        self.assertEqual(patch_call[0][0], "PATCH")
        self.assertIn(FAKE_SYS_ID, patch_call[0][1])

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_cancel_by_number_queries_correct_field(self, mock_req):
        lookup_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        patch_resp = _make_response(
            200, {"result": {"sys_id": FAKE_SYS_ID, "number": FAKE_NUMBER}}
        )
        mock_req.side_effect = [lookup_resp, patch_resp]

        params = CancelIncidentParams(incident_id=FAKE_NUMBER)
        cancel_incident(self.config, self.auth, params)

        get_call = mock_req.call_args_list[0]
        self.assertIn(f"number={FAKE_NUMBER}", get_call[1]["params"]["sysparm_query"])

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_cancel_by_number_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = CancelIncidentParams(incident_id="INC9999999")
        result = cancel_incident(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("not found", result.message.lower())

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_cancel_by_number_lookup_fails(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("timeout")
        params = CancelIncidentParams(incident_id="INC0020002")
        result = cancel_incident(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to find incident", result.message)

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_cancel_by_number_with_reason(self, mock_req):
        lookup_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        patch_resp = _make_response(
            200, {"result": {"sys_id": FAKE_SYS_ID, "number": FAKE_NUMBER}}
        )
        mock_req.side_effect = [lookup_resp, patch_resp]

        params = CancelIncidentParams(incident_id=FAKE_NUMBER, cancel_reason="Resolved by change")
        cancel_incident(self.config, self.auth, params)

        patch_call = mock_req.call_args_list[1]
        self.assertEqual(patch_call[1]["json"]["work_notes"], "Resolved by change")
        self.assertEqual(patch_call[1]["json"]["state"], "8")


class TestCancelIncidentParams(unittest.TestCase):
    def test_cancel_reason_optional(self):
        params = CancelIncidentParams(incident_id="INC001")
        self.assertIsNone(params.cancel_reason)

    def test_cancel_reason_set(self):
        params = CancelIncidentParams(incident_id="INC001", cancel_reason="No longer needed")
        self.assertEqual(params.cancel_reason, "No longer needed")

    def test_incident_id_required(self):
        with self.assertRaises(Exception):
            CancelIncidentParams()


if __name__ == "__main__":
    unittest.main()
