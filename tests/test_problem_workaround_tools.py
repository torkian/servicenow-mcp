"""Tests for create_problem_workaround and get_problem_workaround in problem_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.problem_tools import (
    create_problem_workaround,
    get_problem_workaround,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
FAKE_NUMBER = "PRB0001234"

FAKE_PROBLEM_RECORD = {
    "sys_id": FAKE_SYS_ID,
    "number": FAKE_NUMBER,
    "short_description": "Database is slow",
    "description": "Query response times exceed 30s",
    "state": "1",
    "problem_state": "1",
    "priority": "2",
    "impact": "1",
    "urgency": "2",
    "category": "database",
    "subcategory": "performance",
    "assigned_to": {"display_value": "John Doe"},
    "assignment_group": {"display_value": "DBA Team"},
    "cause_notes": "",
    "fix_notes": "",
    "workaround": "Restart the DB service to clear the query cache",
    "known_error": "true",
    "sys_created_on": "2026-01-01 08:00:00",
    "sys_updated_on": "2026-01-02 09:00:00",
    "resolved_at": "",
    "closed_at": "",
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


def _make_response(status_code=200, json_body=None):
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.json.return_value = json_body or {}
    response.raise_for_status = MagicMock()
    return response


# ---------------------------------------------------------------------------
# create_problem_workaround
# ---------------------------------------------------------------------------

class TestCreateProblemWorkaround(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    # -- validation --

    def test_missing_problem_id_returns_error(self):
        result = create_problem_workaround(self.auth, self.config, {"workaround": "Use X instead"})
        self.assertFalse(result["success"])

    def test_missing_workaround_returns_error(self):
        result = create_problem_workaround(self.auth, self.config, {"problem_id": FAKE_NUMBER})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer X"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = create_problem_workaround(
            auth, config, {"problem_id": FAKE_NUMBER, "workaround": "Use X"}
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev99999.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"
        result = create_problem_workaround(
            auth, config, {"problem_id": FAKE_NUMBER, "workaround": "Use X"}
        )
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    # -- resolver fail --

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_resolve_fails_propagates(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = create_problem_workaround(
            self.auth, self.config, {"problem_id": FAKE_NUMBER, "workaround": "Use X"}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_resolve_request_exception(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = create_problem_workaround(
            self.auth, self.config, {"problem_id": FAKE_NUMBER, "workaround": "Use X"}
        )
        self.assertFalse(result["success"])

    # -- success with PRB number --

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_success_by_number(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        patch_resp = _make_response(200, {"result": FAKE_PROBLEM_RECORD})
        mock_req.side_effect = [resolve_resp, patch_resp]

        result = create_problem_workaround(
            self.auth,
            self.config,
            {"problem_id": FAKE_NUMBER, "workaround": "Restart the DB service"},
        )
        self.assertTrue(result["success"])
        self.assertIn("workaround", result["message"].lower())
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["number"], FAKE_NUMBER)
        self.assertIn("problem", result)

    # -- success with sys_id --

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_success_by_sys_id(self, mock_req):
        patch_resp = _make_response(200, {"result": FAKE_PROBLEM_RECORD})
        mock_req.return_value = patch_resp

        result = create_problem_workaround(
            self.auth,
            self.config,
            {
                "problem_id": FAKE_SYS_ID,
                "workaround": "Restart the DB service",
                "known_error": True,
            },
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    # -- known_error false --

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_known_error_false_included(self, mock_req):
        patch_resp = _make_response(200, {"result": FAKE_PROBLEM_RECORD})
        mock_req.return_value = patch_resp

        create_problem_workaround(
            self.auth,
            self.config,
            {
                "problem_id": FAKE_SYS_ID,
                "workaround": "Use read replica",
                "known_error": False,
            },
        )
        call_kwargs = mock_req.call_args
        body = call_kwargs[1]["json"]
        self.assertEqual(body["known_error"], "false")

    # -- work_notes included --

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_work_notes_included_in_body(self, mock_req):
        patch_resp = _make_response(200, {"result": FAKE_PROBLEM_RECORD})
        mock_req.return_value = patch_resp

        create_problem_workaround(
            self.auth,
            self.config,
            {
                "problem_id": FAKE_SYS_ID,
                "workaround": "Use read replica",
                "work_notes": "Workaround documented by SRE team",
            },
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["work_notes"], "Workaround documented by SRE team")

    # -- 404 from PATCH --

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_patch_404_returns_error(self, mock_req):
        not_found_resp = _make_response(404, {})
        not_found_resp.raise_for_status = MagicMock()
        mock_req.return_value = not_found_resp

        result = create_problem_workaround(
            self.auth,
            self.config,
            {"problem_id": FAKE_SYS_ID, "workaround": "Use X"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    # -- request exception on PATCH --

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_patch_request_exception(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        mock_req.side_effect = [resolve_resp, requests.exceptions.ConnectionError("err")]

        result = create_problem_workaround(
            self.auth,
            self.config,
            {"problem_id": FAKE_NUMBER, "workaround": "Use X"},
        )
        self.assertFalse(result["success"])
        self.assertIn("workaround", result["message"].lower())


# ---------------------------------------------------------------------------
# get_problem_workaround
# ---------------------------------------------------------------------------

class TestGetProblemWorkaround(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    # -- validation --

    def test_missing_problem_id_returns_error(self):
        result = get_problem_workaround(self.auth, self.config, {})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer X"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = get_problem_workaround(auth, config, {"problem_id": FAKE_NUMBER})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev99999.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"
        result = get_problem_workaround(auth, config, {"problem_id": FAKE_NUMBER})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    # -- sys_id path --

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_success_by_sys_id(self, mock_req):
        workaround_record = {
            "sys_id": FAKE_SYS_ID,
            "number": FAKE_NUMBER,
            "short_description": "Database is slow",
            "workaround": "Restart the DB service",
            "known_error": "true",
            "state": "1",
            "problem_state": "107",
        }
        mock_req.return_value = _make_response(200, {"result": workaround_record})

        result = get_problem_workaround(self.auth, self.config, {"problem_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        info = result["workaround_info"]
        self.assertEqual(info["sys_id"], FAKE_SYS_ID)
        self.assertEqual(info["number"], FAKE_NUMBER)
        self.assertEqual(info["workaround"], "Restart the DB service")
        self.assertTrue(info["has_workaround"])
        self.assertTrue(info["known_error"])
        self.assertEqual(info["state"], "1")
        self.assertEqual(info["problem_state"], "107")

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_sys_id_404_returns_error(self, mock_req):
        resp = _make_response(404, {})
        resp.raise_for_status = MagicMock()
        mock_req.return_value = resp

        result = get_problem_workaround(self.auth, self.config, {"problem_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_sys_id_empty_result_returns_error(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})

        result = get_problem_workaround(self.auth, self.config, {"problem_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_sys_id_request_exception(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")

        result = get_problem_workaround(self.auth, self.config, {"problem_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("workaround", result["message"].lower())

    # -- PRB number path --

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_success_by_number(self, mock_req):
        workaround_record = {
            "sys_id": FAKE_SYS_ID,
            "number": FAKE_NUMBER,
            "short_description": "Database is slow",
            "workaround": "Restart the DB service",
            "known_error": "false",
            "state": "1",
            "problem_state": "1",
        }
        mock_req.return_value = _make_response(200, {"result": [workaround_record]})

        result = get_problem_workaround(self.auth, self.config, {"problem_id": FAKE_NUMBER})
        self.assertTrue(result["success"])
        info = result["workaround_info"]
        self.assertEqual(info["workaround"], "Restart the DB service")
        self.assertTrue(info["has_workaround"])
        self.assertFalse(info["known_error"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_number_not_found_returns_error(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        result = get_problem_workaround(self.auth, self.config, {"problem_id": FAKE_NUMBER})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_number_request_exception(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")

        result = get_problem_workaround(self.auth, self.config, {"problem_id": FAKE_NUMBER})
        self.assertFalse(result["success"])
        self.assertIn("workaround", result["message"].lower())

    # -- has_workaround flag --

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_no_workaround_has_workaround_false(self, mock_req):
        record = {
            "sys_id": FAKE_SYS_ID,
            "number": FAKE_NUMBER,
            "short_description": "DB slow",
            "workaround": "",
            "known_error": "false",
            "state": "1",
            "problem_state": "1",
        }
        mock_req.return_value = _make_response(200, {"result": [record]})

        result = get_problem_workaround(self.auth, self.config, {"problem_id": FAKE_NUMBER})
        self.assertTrue(result["success"])
        self.assertFalse(result["workaround_info"]["has_workaround"])
        self.assertEqual(result["workaround_info"]["workaround"], "")

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_known_error_true_boolean_variant(self, mock_req):
        """known_error returned as Python True (not a string) is handled."""
        record = {
            "sys_id": FAKE_SYS_ID,
            "number": FAKE_NUMBER,
            "short_description": "DB slow",
            "workaround": "Use replica",
            "known_error": True,
            "state": "107",
            "problem_state": "107",
        }
        mock_req.return_value = _make_response(200, {"result": [record]})

        result = get_problem_workaround(self.auth, self.config, {"problem_id": FAKE_NUMBER})
        self.assertTrue(result["success"])
        self.assertTrue(result["workaround_info"]["known_error"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_workaround_none_returns_empty_string(self, mock_req):
        """workaround=None in the API response converts to empty string."""
        record = {
            "sys_id": FAKE_SYS_ID,
            "number": FAKE_NUMBER,
            "short_description": "DB slow",
            "workaround": None,
            "known_error": "false",
            "state": "1",
            "problem_state": "1",
        }
        mock_req.return_value = _make_response(200, {"result": [record]})

        result = get_problem_workaround(self.auth, self.config, {"problem_id": FAKE_NUMBER})
        self.assertTrue(result["success"])
        self.assertEqual(result["workaround_info"]["workaround"], "")
        self.assertFalse(result["workaround_info"]["has_workaround"])


if __name__ == "__main__":
    unittest.main()
