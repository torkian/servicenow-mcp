"""Tests for problem root cause analysis tools."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.problem_tools import (
    get_problem_root_cause,
    link_incident_to_problem,
    list_problem_related_incidents,
    set_problem_root_cause,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
FAKE_PROB_SYS_ID = "b" * 32
FAKE_INC_SYS_ID = "c" * 32
FAKE_PRB_NUMBER = "PRB0009999"
FAKE_INC_NUMBER = "INC0009999"


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev99999.service-now.com", auth=auth_config)


def _make_auth():
    auth = MagicMock(spec=AuthManager)
    auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    auth.instance_url = "https://dev99999.service-now.com"
    return auth


def _make_response(status_code=200, json_body=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.raise_for_status = MagicMock()
    return resp


FAKE_PROBLEM_RECORD = {
    "sys_id": FAKE_PROB_SYS_ID,
    "number": FAKE_PRB_NUMBER,
    "short_description": "DB slow",
    "state": "2",
    "problem_state": "2",
    "cause_notes": "Index missing on orders table",
    "fix_notes": "Added composite index",
    "workaround": "Restart query cache",
    "known_error": "false",
    "resolution_code": "fix_applied",
    "resolved_at": "2026-10-05 12:00:00",
    "closed_at": "",
    "assigned_to": {"display_value": "Jane Smith"},
    "assignment_group": {"display_value": "DBA Team"},
    "priority": "2",
    "impact": "1",
    "urgency": "2",
    "category": "database",
    "subcategory": "",
    "description": "",
    "sys_created_on": "2026-10-01 08:00:00",
    "sys_updated_on": "2026-10-05 12:00:00",
}


# ---------------------------------------------------------------------------
# set_problem_root_cause
# ---------------------------------------------------------------------------

class TestSetProblemRootCause(unittest.TestCase):
    def _run(self, params, side_effect=None):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            if side_effect:
                mock_req.side_effect = side_effect
            else:
                # First call: resolve sys_id; second call: PATCH
                resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
                patch_resp = _make_response(200, {"result": FAKE_PROBLEM_RECORD})
                mock_req.side_effect = [resolve_resp, patch_resp]
            return set_problem_root_cause(auth, config, params)

    def test_set_cause_notes_success(self):
        result = self._run({"problem_id": FAKE_PRB_NUMBER, "cause_notes": "Missing index"})
        self.assertTrue(result["success"])
        self.assertIn("root cause analysis updated", result["message"])
        self.assertEqual(result["sys_id"], FAKE_PROB_SYS_ID)

    def test_set_all_fields(self):
        result = self._run({
            "problem_id": FAKE_PRB_NUMBER,
            "cause_notes": "Missing index",
            "fix_notes": "Added index",
            "corrective_actions": "Monitor query plans weekly",
            "resolution_code": "fix_applied",
            "problem_state": "3",
            "work_notes": "RCA completed",
        })
        self.assertTrue(result["success"])

    def test_no_fields_provided(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
            mock_req.return_value = resolve_resp
            result = set_problem_root_cause(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertFalse(result["success"])
        self.assertIn("No root cause fields", result["message"])

    def test_problem_not_found(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
            patch_404 = _make_response(404, {})
            mock_req.side_effect = [resolve_resp, patch_404]
            result = set_problem_root_cause(auth, config, {
                "problem_id": FAKE_PRB_NUMBER,
                "cause_notes": "test",
            })
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_network_error(self):
        result = self._run(
            {"problem_id": FAKE_PRB_NUMBER, "cause_notes": "test"},
            side_effect=requests.exceptions.ConnectionError("timeout"),
        )
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        config = _make_config()
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        config.instance_url = None
        result = set_problem_root_cause(auth, config, {"problem_id": FAKE_PRB_NUMBER, "cause_notes": "x"})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        config = _make_config()
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev99999.service-now.com"
        result = set_problem_root_cause(auth, config, {"problem_id": FAKE_PRB_NUMBER, "cause_notes": "x"})
        self.assertFalse(result["success"])

    def test_missing_required_param(self):
        config = _make_config()
        auth = _make_auth()
        result = set_problem_root_cause(auth, config, {"cause_notes": "Missing index"})
        self.assertFalse(result["success"])

    def test_sys_id_direct(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            # sys_id path: _resolve uses direct lookup
            resolve_resp = _make_response(200, {"result": {"sys_id": FAKE_PROB_SYS_ID}})
            patch_resp = _make_response(200, {"result": FAKE_PROBLEM_RECORD})
            mock_req.side_effect = [resolve_resp, patch_resp]
            result = set_problem_root_cause(auth, config, {
                "problem_id": FAKE_PROB_SYS_ID,
                "fix_notes": "Applied patch",
            })
        self.assertTrue(result["success"])


# ---------------------------------------------------------------------------
# get_problem_root_cause
# ---------------------------------------------------------------------------

class TestGetProblemRootCause(unittest.TestCase):
    def _run_number(self, params, side_effect=None):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            if side_effect:
                mock_req.side_effect = side_effect
            else:
                # number-based: single GET with sysparm_query=number=...
                get_resp = _make_response(200, {"result": [FAKE_PROBLEM_RECORD]})
                mock_req.return_value = get_resp
            return get_problem_root_cause(auth, config, params)

    def test_get_by_number(self):
        result = self._run_number({"problem_id": FAKE_PRB_NUMBER})
        self.assertTrue(result["success"])
        rca = result["rca_info"]
        self.assertEqual(rca["cause_notes"], "Index missing on orders table")
        self.assertTrue(rca["has_root_cause"])
        self.assertEqual(rca["fix_notes"], "Added composite index")
        self.assertFalse(rca["known_error"])
        self.assertEqual(rca["assigned_to"], "Jane Smith")

    def test_get_by_sys_id(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            # sys_id path: direct GET
            get_resp = _make_response(200, {"result": FAKE_PROBLEM_RECORD})
            mock_req.return_value = get_resp
            result = get_problem_root_cause(auth, config, {"problem_id": FAKE_PROB_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["rca_info"]["number"], FAKE_PRB_NUMBER)

    def test_problem_not_found_sys_id(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            mock_req.return_value = _make_response(404, {})
            result = get_problem_root_cause(auth, config, {"problem_id": FAKE_PROB_SYS_ID})
        self.assertFalse(result["success"])

    def test_problem_not_found_number(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            mock_req.return_value = _make_response(200, {"result": []})
            result = get_problem_root_cause(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertFalse(result["success"])

    def test_network_error_sys_id(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            mock_req.side_effect = requests.exceptions.ConnectionError("down")
            result = get_problem_root_cause(auth, config, {"problem_id": FAKE_PROB_SYS_ID})
        self.assertFalse(result["success"])

    def test_network_error_number(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            mock_req.side_effect = requests.exceptions.ConnectionError("down")
            result = get_problem_root_cause(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        config = _make_config()
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        config.instance_url = None
        result = get_problem_root_cause(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        config = _make_config()
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev99999.service-now.com"
        result = get_problem_root_cause(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertFalse(result["success"])

    def test_empty_result_sys_id(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            mock_req.return_value = _make_response(200, {"result": {}})
            result = get_problem_root_cause(auth, config, {"problem_id": FAKE_PROB_SYS_ID})
        self.assertFalse(result["success"])

    def test_problem_state_label_mapping(self):
        config = _make_config()
        auth = _make_auth()
        rec = dict(FAKE_PROBLEM_RECORD)
        rec["problem_state"] = "107"
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            mock_req.return_value = _make_response(200, {"result": rec})
            result = get_problem_root_cause(auth, config, {"problem_id": FAKE_PROB_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["rca_info"]["problem_state"], "Known Error")

    def test_missing_required_param(self):
        config = _make_config()
        auth = _make_auth()
        result = get_problem_root_cause(auth, config, {})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# link_incident_to_problem
# ---------------------------------------------------------------------------

class TestLinkIncidentToProblem(unittest.TestCase):
    def _run(self, params, side_effect=None):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            if side_effect:
                mock_req.side_effect = side_effect
            else:
                # 1: resolve problem (number→sys_id)
                # 2: resolve incident (number→sys_id)
                # 3: PATCH incident
                prob_resolve = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
                inc_resolve = _make_response(200, {"result": [{"sys_id": FAKE_INC_SYS_ID}]})
                patch_resp = _make_response(200, {"result": {}})
                mock_req.side_effect = [prob_resolve, inc_resolve, patch_resp]
            return link_incident_to_problem(auth, config, params)

    def test_link_by_numbers(self):
        result = self._run({"incident_id": FAKE_INC_NUMBER, "problem_id": FAKE_PRB_NUMBER})
        self.assertTrue(result["success"])
        self.assertIn("linked to problem", result["message"])
        self.assertEqual(result["incident_sys_id"], FAKE_INC_SYS_ID)
        self.assertEqual(result["problem_sys_id"], FAKE_PROB_SYS_ID)

    def test_link_by_sys_ids(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            # prob and inc are already sys_ids; prob still does lookup, inc is direct
            prob_resolve = _make_response(200, {"result": {"sys_id": FAKE_PROB_SYS_ID}})
            patch_resp = _make_response(200, {"result": {}})
            mock_req.side_effect = [prob_resolve, patch_resp]
            result = link_incident_to_problem(auth, config, {
                "incident_id": FAKE_INC_SYS_ID,
                "problem_id": FAKE_PROB_SYS_ID,
            })
        self.assertTrue(result["success"])

    def test_with_work_notes(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            prob_resolve = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
            inc_resolve = _make_response(200, {"result": [{"sys_id": FAKE_INC_SYS_ID}]})
            patch_resp = _make_response(200, {"result": {}})
            mock_req.side_effect = [prob_resolve, inc_resolve, patch_resp]
            result = link_incident_to_problem(auth, config, {
                "incident_id": FAKE_INC_NUMBER,
                "problem_id": FAKE_PRB_NUMBER,
                "work_notes": "Linked during RCA",
            })
        self.assertTrue(result["success"])

    def test_problem_not_found(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            mock_req.return_value = _make_response(200, {"result": []})
            result = link_incident_to_problem(auth, config, {
                "incident_id": FAKE_INC_NUMBER,
                "problem_id": FAKE_PRB_NUMBER,
            })
        self.assertFalse(result["success"])

    def test_incident_not_found(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            prob_resolve = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
            inc_resolve = _make_response(200, {"result": []})
            mock_req.side_effect = [prob_resolve, inc_resolve]
            result = link_incident_to_problem(auth, config, {
                "incident_id": FAKE_INC_NUMBER,
                "problem_id": FAKE_PRB_NUMBER,
            })
        self.assertFalse(result["success"])
        self.assertIn("Incident not found", result["message"])

    def test_patch_404(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            prob_resolve = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
            inc_resolve = _make_response(200, {"result": [{"sys_id": FAKE_INC_SYS_ID}]})
            patch_404 = _make_response(404, {})
            mock_req.side_effect = [prob_resolve, inc_resolve, patch_404]
            result = link_incident_to_problem(auth, config, {
                "incident_id": FAKE_INC_NUMBER,
                "problem_id": FAKE_PRB_NUMBER,
            })
        self.assertFalse(result["success"])

    def test_incident_resolve_error(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            prob_resolve = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
            mock_req.side_effect = [prob_resolve, requests.exceptions.ConnectionError("down")]
            result = link_incident_to_problem(auth, config, {
                "incident_id": FAKE_INC_NUMBER,
                "problem_id": FAKE_PRB_NUMBER,
            })
        self.assertFalse(result["success"])

    def test_patch_network_error(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            prob_resolve = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
            inc_resolve = _make_response(200, {"result": [{"sys_id": FAKE_INC_SYS_ID}]})
            mock_req.side_effect = [prob_resolve, inc_resolve, requests.exceptions.ConnectionError("down")]
            result = link_incident_to_problem(auth, config, {
                "incident_id": FAKE_INC_NUMBER,
                "problem_id": FAKE_PRB_NUMBER,
            })
        self.assertFalse(result["success"])

    def test_missing_required_params(self):
        config = _make_config()
        auth = _make_auth()
        result = link_incident_to_problem(auth, config, {"incident_id": FAKE_INC_NUMBER})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        config = _make_config()
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        config.instance_url = None
        result = link_incident_to_problem(auth, config, {
            "incident_id": FAKE_INC_NUMBER,
            "problem_id": FAKE_PRB_NUMBER,
        })
        self.assertFalse(result["success"])

    def test_no_headers(self):
        config = _make_config()
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev99999.service-now.com"
        result = link_incident_to_problem(auth, config, {
            "incident_id": FAKE_INC_NUMBER,
            "problem_id": FAKE_PRB_NUMBER,
        })
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# list_problem_related_incidents
# ---------------------------------------------------------------------------

FAKE_INCIDENT = {
    "sys_id": FAKE_INC_SYS_ID,
    "number": FAKE_INC_NUMBER,
    "short_description": "App is down",
    "state": "1",
    "priority": "2",
    "assigned_to": {"display_value": "John Doe"},
    "assignment_group": {"display_value": "L2 Support"},
    "sys_created_on": "2026-10-01 09:00:00",
    "sys_updated_on": "2026-10-05 10:00:00",
    "resolved_at": "",
}


class TestListProblemRelatedIncidents(unittest.TestCase):
    def _run(self, params, side_effect=None):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            if side_effect:
                mock_req.side_effect = side_effect
            else:
                resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
                list_resp = _make_response(200, {"result": [FAKE_INCIDENT]})
                mock_req.side_effect = [resolve_resp, list_resp]
            return list_problem_related_incidents(auth, config, params)

    def test_list_success(self):
        result = self._run({"problem_id": FAKE_PRB_NUMBER})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["incidents"]), 1)
        inc = result["incidents"][0]
        self.assertEqual(inc["number"], FAKE_INC_NUMBER)
        self.assertEqual(inc["assigned_to"], "John Doe")
        self.assertEqual(inc["assignment_group"], "L2 Support")

    def test_list_with_state_filter(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
            list_resp = _make_response(200, {"result": [FAKE_INCIDENT]})
            mock_req.side_effect = [resolve_resp, list_resp]
            result = list_problem_related_incidents(auth, config, {
                "problem_id": FAKE_PRB_NUMBER,
                "state": "1",
            })
        self.assertTrue(result["success"])
        # Verify the query included state filter
        call_args = mock_req.call_args_list[1]
        query = call_args[1]["params"]["sysparm_query"]
        self.assertIn("state=1", query)

    def test_pagination(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
            incidents = [dict(FAKE_INCIDENT, sys_id=f"{'d' * 31}{i}") for i in range(5)]
            list_resp = _make_response(200, {"result": incidents})
            mock_req.side_effect = [resolve_resp, list_resp]
            result = list_problem_related_incidents(auth, config, {
                "problem_id": FAKE_PRB_NUMBER,
                "limit": 5,
                "offset": 0,
            })
        self.assertTrue(result["success"])
        self.assertEqual(len(result["incidents"]), 5)

    def test_empty_result(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
            list_resp = _make_response(200, {"result": []})
            mock_req.side_effect = [resolve_resp, list_resp]
            result = list_problem_related_incidents(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertTrue(result["success"])
        self.assertEqual(result["incidents"], [])

    def test_problem_not_found(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            mock_req.return_value = _make_response(200, {"result": []})
            result = list_problem_related_incidents(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertFalse(result["success"])

    def test_network_error(self):
        config = _make_config()
        auth = _make_auth()
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
            mock_req.side_effect = [resolve_resp, requests.exceptions.ConnectionError("down")]
            result = list_problem_related_incidents(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        config = _make_config()
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        config.instance_url = None
        result = list_problem_related_incidents(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        config = _make_config()
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev99999.service-now.com"
        result = list_problem_related_incidents(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertFalse(result["success"])

    def test_missing_required_param(self):
        config = _make_config()
        auth = _make_auth()
        result = list_problem_related_incidents(auth, config, {})
        self.assertFalse(result["success"])

    def test_scalar_fields_normalised(self):
        config = _make_config()
        auth = _make_auth()
        inc_scalar = dict(FAKE_INCIDENT)
        inc_scalar["assigned_to"] = "Jane"
        inc_scalar["assignment_group"] = "DBA"
        with patch("servicenow_mcp.tools.problem_tools._make_request") as mock_req:
            resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
            list_resp = _make_response(200, {"result": [inc_scalar]})
            mock_req.side_effect = [resolve_resp, list_resp]
            result = list_problem_related_incidents(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertEqual(result["incidents"][0]["assigned_to"], "Jane")


if __name__ == "__main__":
    unittest.main()
