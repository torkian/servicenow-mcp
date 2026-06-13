"""Tests for problem_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.problem_tools import (
    _format_problem,
    _resolve_problem_sys_id,
    close_problem,
    create_problem,
    get_problem,
    list_problems,
    update_problem,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
FAKE_NUMBER = "PRB0001234"

FAKE_PROBLEM = {
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
    "workaround": "Restart DB service",
    "known_error": "false",
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
# _format_problem
# ---------------------------------------------------------------------------

class TestFormatProblem(unittest.TestCase):
    def test_all_fields_mapped(self):
        result = _format_problem(FAKE_PROBLEM)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["number"], FAKE_NUMBER)
        self.assertEqual(result["short_description"], "Database is slow")
        self.assertEqual(result["state"], "1")
        self.assertEqual(result["priority"], "2")
        self.assertEqual(result["assigned_to"], "John Doe")
        self.assertEqual(result["assignment_group"], "DBA Team")
        self.assertEqual(result["category"], "database")
        self.assertEqual(result["workaround"], "Restart DB service")

    def test_reference_fields_as_string(self):
        record = dict(FAKE_PROBLEM, assigned_to="jdoe", assignment_group="dba")
        result = _format_problem(record)
        self.assertEqual(result["assigned_to"], "jdoe")
        self.assertEqual(result["assignment_group"], "dba")

    def test_empty_record_returns_nones(self):
        result = _format_problem({})
        for key in ("sys_id", "number", "short_description", "state", "priority"):
            self.assertIsNone(result[key], f"{key} should be None for empty record")


# ---------------------------------------------------------------------------
# _resolve_problem_sys_id
# ---------------------------------------------------------------------------

class TestResolveProblemSysId(unittest.TestCase):
    def test_hex_sys_id_passthrough(self):
        result = _resolve_problem_sys_id(FAKE_SYS_ID, "https://x.com", {})
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_number_lookup_success(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        result = _resolve_problem_sys_id(FAKE_NUMBER, "https://x.com", {})
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_number_lookup_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = _resolve_problem_sys_id(FAKE_NUMBER, "https://x.com", {})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_number_lookup_request_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        result = _resolve_problem_sys_id(FAKE_NUMBER, "https://x.com", {})
        self.assertFalse(result["success"])
        self.assertIn("Error looking up problem", result["message"])


# ---------------------------------------------------------------------------
# list_problems
# ---------------------------------------------------------------------------

class TestListProblems(unittest.TestCase):
    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_success_returns_problems(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_PROBLEM]})
        result = list_problems(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["problems"]), 1)
        self.assertEqual(result["problems"][0]["number"], FAKE_NUMBER)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_problems(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(result["problems"], [])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_state_filter_in_query(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_problems(_make_auth_manager(), _make_config(), {"state": "1"})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("state=1", query)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_known_error_true_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_problems(_make_auth_manager(), _make_config(), {"known_error": True})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("known_error=true", query)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_known_error_false_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_problems(_make_auth_manager(), _make_config(), {"known_error": False})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("known_error=false", query)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_query_filter_searches_description(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_problems(_make_auth_manager(), _make_config(), {"query": "database"})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("short_descriptionLIKEdatabase", query)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_category_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_problems(_make_auth_manager(), _make_config(), {"category": "network"})
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("category=network", query)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_pagination_params_forwarded(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_problems(_make_auth_manager(), _make_config(), {"limit": 5, "offset": 10})
        _, kwargs = mock_req.call_args
        p = kwargs.get("params", {})
        self.assertEqual(p.get("sysparm_limit"), 5)
        self.assertEqual(p.get("sysparm_offset"), 10)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_request_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_problems(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing problems", result["message"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_has_more_flag(self, mock_req):
        records = [dict(FAKE_PROBLEM, sys_id=f"{'a'*31}{i}") for i in range(5)]
        mock_req.return_value = _make_response(200, {"result": records})
        result = list_problems(
            _make_auth_manager(), _make_config(), {"limit": 5, "offset": 0}
        )
        self.assertTrue(result["success"])
        self.assertIn("has_more", result)


# ---------------------------------------------------------------------------
# get_problem
# ---------------------------------------------------------------------------

class TestGetProblem(unittest.TestCase):
    def test_missing_problem_id(self):
        result = get_problem(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_success_by_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_PROBLEM})
        result = get_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["problem"]["number"], FAKE_NUMBER)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_404_by_sys_id(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        result = get_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_empty_result_by_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_success_by_number(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_PROBLEM]})
        result = get_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_NUMBER})
        self.assertTrue(result["success"])
        self.assertEqual(result["problem"]["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_not_found_by_number(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = get_problem(_make_auth_manager(), _make_config(), {"problem_id": "PRB9999999"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_request_error_by_number(self, mock_req):
        mock_req.side_effect = requests.exceptions.Timeout("timeout")
        result = get_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_NUMBER})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving problem", result["message"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_request_error_by_sys_id(self, mock_req):
        mock_req.side_effect = requests.exceptions.Timeout("timeout")
        result = get_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving problem", result["message"])


# ---------------------------------------------------------------------------
# create_problem
# ---------------------------------------------------------------------------

class TestCreateProblem(unittest.TestCase):
    def test_missing_short_description(self):
        result = create_problem(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_success_minimal(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_PROBLEM})
        result = create_problem(
            _make_auth_manager(), _make_config(), {"short_description": "DB slow"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["number"], FAKE_NUMBER)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_optional_fields_included_in_body(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_PROBLEM})
        create_problem(
            _make_auth_manager(),
            _make_config(),
            {
                "short_description": "DB slow",
                "priority": "2",
                "impact": "1",
                "urgency": "2",
                "category": "database",
                "known_error": True,
                "workaround": "Restart",
            },
        )
        _, kwargs = mock_req.call_args
        body = kwargs.get("json", {})
        self.assertEqual(body.get("priority"), "2")
        self.assertEqual(body.get("category"), "database")
        self.assertEqual(body.get("known_error"), "true")
        self.assertEqual(body.get("workaround"), "Restart")

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_known_error_false_serialised(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_PROBLEM})
        create_problem(
            _make_auth_manager(), _make_config(),
            {"short_description": "x", "known_error": False},
        )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs.get("json", {}).get("known_error"), "false")

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_request_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        result = create_problem(
            _make_auth_manager(), _make_config(), {"short_description": "DB slow"}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error creating problem", result["message"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_problem_in_response(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_PROBLEM})
        result = create_problem(
            _make_auth_manager(), _make_config(), {"short_description": "DB slow"}
        )
        self.assertIn("problem", result)
        self.assertEqual(result["problem"]["number"], FAKE_NUMBER)


# ---------------------------------------------------------------------------
# update_problem
# ---------------------------------------------------------------------------

class TestUpdateProblem(unittest.TestCase):
    def test_missing_problem_id(self):
        result = update_problem(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_no_fields_returns_failure(self, mock_req):
        result = update_problem(
            _make_auth_manager(), _make_config(), {"problem_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("No fields", result["message"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_success_by_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_PROBLEM})
        result = update_problem(
            _make_auth_manager(), _make_config(),
            {"problem_id": FAKE_SYS_ID, "state": "4"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_success_by_number(self, mock_req):
        # First call resolves number -> sys_id; second call is PATCH
        lookup_response = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        patch_response = _make_response(200, {"result": FAKE_PROBLEM})
        mock_req.side_effect = [lookup_response, patch_response]
        result = update_problem(
            _make_auth_manager(), _make_config(),
            {"problem_id": FAKE_NUMBER, "priority": "1"},
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_update_body_contains_only_provided_fields(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_PROBLEM})
        update_problem(
            _make_auth_manager(), _make_config(),
            {"problem_id": FAKE_SYS_ID, "cause_notes": "OOM killer fired"},
        )
        _, kwargs = mock_req.call_args
        body = kwargs.get("json", {})
        self.assertIn("cause_notes", body)
        self.assertNotIn("state", body)
        self.assertNotIn("priority", body)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_known_error_serialised_in_update(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_PROBLEM})
        update_problem(
            _make_auth_manager(), _make_config(),
            {"problem_id": FAKE_SYS_ID, "known_error": True},
        )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs.get("json", {}).get("known_error"), "true")

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_number_lookup_failure_propagated(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = update_problem(
            _make_auth_manager(), _make_config(),
            {"problem_id": "PRB9999999", "state": "4"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_request_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.Timeout("timeout")
        result = update_problem(
            _make_auth_manager(), _make_config(),
            {"problem_id": FAKE_SYS_ID, "state": "2"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating problem", result["message"])


# ---------------------------------------------------------------------------
# close_problem
# ---------------------------------------------------------------------------

class TestCloseProblem(unittest.TestCase):
    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_success_by_sys_id(self, mock_req):
        closed = dict(FAKE_PROBLEM, state="4", closed_at="2026-05-28 10:00:00")
        mock_req.return_value = _make_response(200, {"result": closed})
        result = close_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertIn("closed", result["message"].lower())
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["problem"]["state"], "4")

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_success_by_number(self, mock_req):
        closed = dict(FAKE_PROBLEM, state="4")
        # First call: number lookup; second call: PATCH
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]}),
            _make_response(200, {"result": closed}),
        ]
        result = close_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_NUMBER})
        self.assertTrue(result["success"])
        self.assertEqual(result["number"], FAKE_NUMBER)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_state_4_sent_in_body(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_PROBLEM})
        close_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_SYS_ID})
        patch_call = mock_req.call_args_list[-1]
        body = patch_call[1].get("json", {})
        self.assertEqual(body.get("state"), "4")

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_close_notes_included_when_provided(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_PROBLEM})
        close_problem(
            _make_auth_manager(), _make_config(),
            {"problem_id": FAKE_SYS_ID, "close_notes": "Fixed by patching DB"},
        )
        patch_call = mock_req.call_args_list[-1]
        body = patch_call[1].get("json", {})
        self.assertEqual(body.get("close_notes"), "Fixed by patching DB")

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_fix_notes_and_cause_notes_included(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_PROBLEM})
        close_problem(
            _make_auth_manager(), _make_config(),
            {
                "problem_id": FAKE_SYS_ID,
                "fix_notes": "Applied hotfix",
                "cause_notes": "Memory leak in indexer",
            },
        )
        patch_call = mock_req.call_args_list[-1]
        body = patch_call[1].get("json", {})
        self.assertEqual(body.get("fix_notes"), "Applied hotfix")
        self.assertEqual(body.get("cause_notes"), "Memory leak in indexer")

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_work_notes_included(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_PROBLEM})
        close_problem(
            _make_auth_manager(), _make_config(),
            {"problem_id": FAKE_SYS_ID, "work_notes": "Closing after validation"},
        )
        patch_call = mock_req.call_args_list[-1]
        body = patch_call[1].get("json", {})
        self.assertEqual(body.get("work_notes"), "Closing after validation")

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_optional_fields_omitted_when_not_provided(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_PROBLEM})
        close_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_SYS_ID})
        patch_call = mock_req.call_args_list[-1]
        body = patch_call[1].get("json", {})
        self.assertNotIn("close_notes", body)
        self.assertNotIn("fix_notes", body)
        self.assertNotIn("cause_notes", body)
        self.assertNotIn("work_notes", body)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_404_returns_not_found_message(self, mock_req):
        not_found = _make_response(404)
        not_found.raise_for_status = MagicMock()
        mock_req.return_value = not_found
        result = close_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_number_lookup_not_found_propagated(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = close_problem(_make_auth_manager(), _make_config(), {"problem_id": "PRB9999999"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_request_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.Timeout("timeout")
        result = close_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error closing problem", result["message"])

    def test_missing_problem_id_returns_failure(self):
        result = close_problem(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_sys_id_fallback_when_result_missing(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = close_problem(_make_auth_manager(), _make_config(), {"problem_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        # sys_id falls back to the resolved sys_id when API returns empty result
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)


if __name__ == "__main__":
    unittest.main()
