"""Tests for the reopen_incident tool."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.incident_tools import ReopenIncidentParams, reopen_incident
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
FAKE_NUMBER = "INC0010001"


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


def _make_response(status_code, json_data):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


class TestReopenIncidentBySysId(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_reopen_by_sys_id_defaults_to_new(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": {"sys_id": FAKE_SYS_ID, "number": FAKE_NUMBER}}
        )
        params = ReopenIncidentParams(incident_id=FAKE_SYS_ID)
        result = reopen_incident(self.config, self.auth, params)

        self.assertTrue(result.success)
        self.assertIn("New", result.message)
        self.assertEqual(result.incident_id, FAKE_SYS_ID)
        self.assertEqual(result.incident_number, FAKE_NUMBER)

        call_args = mock_req.call_args
        self.assertEqual(call_args[0][0], "PATCH")
        self.assertIn(FAKE_SYS_ID, call_args[0][1])
        self.assertEqual(call_args[1]["json"]["state"], "1")

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_reopen_by_sys_id_in_progress(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": {"sys_id": FAKE_SYS_ID, "number": FAKE_NUMBER}}
        )
        params = ReopenIncidentParams(incident_id=FAKE_SYS_ID, state="2")
        result = reopen_incident(self.config, self.auth, params)

        self.assertTrue(result.success)
        self.assertIn("In Progress", result.message)
        self.assertEqual(mock_req.call_args[1]["json"]["state"], "2")

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_reopen_includes_work_notes(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": {"sys_id": FAKE_SYS_ID, "number": FAKE_NUMBER}}
        )
        params = ReopenIncidentParams(incident_id=FAKE_SYS_ID, work_notes="Customer called back")
        reopen_incident(self.config, self.auth, params)

        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["work_notes"], "Customer called back")

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_reopen_without_work_notes_omits_key(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": {"sys_id": FAKE_SYS_ID, "number": FAKE_NUMBER}}
        )
        params = ReopenIncidentParams(incident_id=FAKE_SYS_ID)
        reopen_incident(self.config, self.auth, params)

        body = mock_req.call_args[1]["json"]
        self.assertNotIn("work_notes", body)

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_reopen_patch_fails_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("connection refused")
        params = ReopenIncidentParams(incident_id=FAKE_SYS_ID)
        result = reopen_incident(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to reopen incident", result.message)


class TestReopenIncidentByNumber(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_reopen_by_number_resolves_sys_id(self, mock_req):
        lookup_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        patch_resp = _make_response(200, {"result": {"sys_id": FAKE_SYS_ID, "number": FAKE_NUMBER}})
        mock_req.side_effect = [lookup_resp, patch_resp]

        params = ReopenIncidentParams(incident_id=FAKE_NUMBER)
        result = reopen_incident(self.config, self.auth, params)

        self.assertTrue(result.success)
        self.assertEqual(mock_req.call_count, 2)
        get_call = mock_req.call_args_list[0]
        self.assertEqual(get_call[0][0], "GET")
        patch_call = mock_req.call_args_list[1]
        self.assertEqual(patch_call[0][0], "PATCH")
        self.assertIn(FAKE_SYS_ID, patch_call[0][1])

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_reopen_by_number_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = ReopenIncidentParams(incident_id="INC9999999")
        result = reopen_incident(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("not found", result.message.lower())

    @patch("servicenow_mcp.tools.incident_tools._make_request")
    def test_reopen_by_number_lookup_fails(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("timeout")
        params = ReopenIncidentParams(incident_id="INC0010001")
        result = reopen_incident(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to find incident", result.message)


class TestReopenIncidentParams(unittest.TestCase):
    def test_default_state_is_new(self):
        params = ReopenIncidentParams(incident_id="INC001")
        self.assertEqual(params.state, "1")

    def test_explicit_in_progress_state(self):
        params = ReopenIncidentParams(incident_id="INC001", state="2")
        self.assertEqual(params.state, "2")

    def test_work_notes_optional(self):
        params = ReopenIncidentParams(incident_id="INC001")
        self.assertIsNone(params.work_notes)


if __name__ == "__main__":
    unittest.main()
