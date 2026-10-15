"""Tests for list_problem_related_cis tool."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.problem_tools import list_problem_related_cis
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_PROB_SYS_ID = "b" * 32
FAKE_CI_SYS_ID_1 = "c" * 32
FAKE_CI_SYS_ID_2 = "d" * 32
FAKE_PRB_NUMBER = "PRB0009001"


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


FAKE_CI_RECORD_1 = {
    "sys_id": FAKE_CI_SYS_ID_1,
    "name": "web-server-01",
    "sys_class_name": {"display_value": "Linux Server"},
    "category": "Hardware",
    "operational_status": {"display_value": "Operational"},
    "environment": "Production",
    "short_description": "Web server",
    "ip_address": "10.0.0.1",
    "serial_number": "SN001",
    "asset_tag": "P1000",
    "install_status": {"display_value": "Installed"},
    "managed_by": {"display_value": "IT Ops"},
    "owned_by": {"display_value": "Web Team"},
    "location": {"display_value": "DC1"},
    "company": {"display_value": "Acme Corp"},
    "sys_created_on": "2025-01-01 00:00:00",
    "sys_updated_on": "2025-06-01 00:00:00",
}

FAKE_CI_RECORD_2 = {
    "sys_id": FAKE_CI_SYS_ID_2,
    "name": "db-server-01",
    "sys_class_name": {"display_value": "Database Server"},
    "category": "Hardware",
    "operational_status": {"display_value": "Operational"},
    "environment": "Production",
    "short_description": "DB server",
    "ip_address": "10.0.0.2",
    "serial_number": "SN002",
    "asset_tag": "P1001",
    "install_status": {"display_value": "Installed"},
    "managed_by": {"display_value": "DBA Team"},
    "owned_by": {"display_value": "DB Team"},
    "location": {"display_value": "DC1"},
    "company": {"display_value": "Acme Corp"},
    "sys_created_on": "2025-01-01 00:00:00",
    "sys_updated_on": "2025-06-01 00:00:00",
}


class TestListProblemRelatedCIsInvalidParams(unittest.TestCase):
    def test_missing_problem_id(self):
        result = list_problem_related_cis(_make_auth(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = list_problem_related_cis(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        config = _make_config()
        result = list_problem_related_cis(auth, config, {"problem_id": FAKE_PRB_NUMBER})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


class TestListProblemRelatedCIsProblemResolve(unittest.TestCase):
    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_problem_number_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PRB_NUMBER}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_problem_resolve_request_exception(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("fail")
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PRB_NUMBER}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_problem_404_on_detail_fetch(self, mock_req):
        # resolve -> found; detail fetch -> 404
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
        detail_resp = _make_response(404, {})
        detail_resp.raise_for_status = MagicMock()
        mock_req.side_effect = [resolve_resp, detail_resp]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PRB_NUMBER}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_problem_detail_request_exception(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_PROB_SYS_ID}]})
        mock_req.side_effect = [resolve_resp, requests.exceptions.ConnectionError("fail")]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PRB_NUMBER}
        )
        self.assertFalse(result["success"])


class TestListProblemRelatedCIsNoCIs(unittest.TestCase):
    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_no_cis_linked(self, mock_req):
        # resolve -> sys_id passthrough (32-char hex)
        detail_resp = _make_response(200, {"result": {"cmdb_ci": ""}})
        task_resp = _make_response(200, {"result": []})
        mock_req.side_effect = [detail_resp, task_resp]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PROB_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["cis"], [])
        self.assertEqual(result["total"], 0)
        self.assertFalse(result["has_more"])
        self.assertEqual(result["source_count"], 0)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_no_cis_skip_problem_tasks(self, mock_req):
        detail_resp = _make_response(200, {"result": {"cmdb_ci": ""}})
        mock_req.side_effect = [detail_resp]
        result = list_problem_related_cis(
            _make_auth(),
            _make_config(),
            {"problem_id": FAKE_PROB_SYS_ID, "include_problem_tasks": False},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["cis"], [])
        self.assertEqual(result["source_count"], 0)


class TestListProblemRelatedCIsSuccess(unittest.TestCase):
    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_ci_from_problem_direct_field(self, mock_req):
        # resolve: sys_id passthrough
        detail_resp = _make_response(200, {"result": {"cmdb_ci": FAKE_CI_SYS_ID_1}})
        task_resp = _make_response(200, {"result": []})
        ci_resp = _make_response(200, {"result": [FAKE_CI_RECORD_1]})
        mock_req.side_effect = [detail_resp, task_resp, ci_resp]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PROB_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["cis"]), 1)
        ci = result["cis"][0]
        self.assertEqual(ci["sys_id"], FAKE_CI_SYS_ID_1)
        self.assertEqual(ci["name"], "web-server-01")
        self.assertEqual(ci["ci_class"], "Linux Server")
        self.assertEqual(result["source_count"], 1)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_ci_from_problem_dict_field(self, mock_req):
        # cmdb_ci as dict with value key
        detail_resp = _make_response(
            200, {"result": {"cmdb_ci": {"value": FAKE_CI_SYS_ID_1, "display_value": "web-server-01"}}}
        )
        task_resp = _make_response(200, {"result": []})
        ci_resp = _make_response(200, {"result": [FAKE_CI_RECORD_1]})
        mock_req.side_effect = [detail_resp, task_resp, ci_resp]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PROB_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["cis"]), 1)
        self.assertEqual(result["source_count"], 1)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_ci_from_problem_task(self, mock_req):
        # problem has no direct CI, but task has one
        detail_resp = _make_response(200, {"result": {"cmdb_ci": ""}})
        task_resp = _make_response(
            200, {"result": [{"cmdb_ci": FAKE_CI_SYS_ID_2}]}
        )
        ci_resp = _make_response(200, {"result": [FAKE_CI_RECORD_2]})
        mock_req.side_effect = [detail_resp, task_resp, ci_resp]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PROB_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["cis"]), 1)
        self.assertEqual(result["cis"][0]["sys_id"], FAKE_CI_SYS_ID_2)
        self.assertEqual(result["source_count"], 1)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_ci_deduplication(self, mock_req):
        # Same CI in both problem direct field and problem task
        detail_resp = _make_response(200, {"result": {"cmdb_ci": FAKE_CI_SYS_ID_1}})
        task_resp = _make_response(
            200, {"result": [{"cmdb_ci": FAKE_CI_SYS_ID_1}]}
        )
        ci_resp = _make_response(200, {"result": [FAKE_CI_RECORD_1]})
        mock_req.side_effect = [detail_resp, task_resp, ci_resp]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PROB_SYS_ID}
        )
        self.assertTrue(result["success"])
        # Deduplicated: only 1 unique CI
        self.assertEqual(result["source_count"], 1)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_two_cis_from_different_sources(self, mock_req):
        # Problem has CI1 directly; task has CI2
        detail_resp = _make_response(200, {"result": {"cmdb_ci": FAKE_CI_SYS_ID_1}})
        task_resp = _make_response(
            200, {"result": [{"cmdb_ci": FAKE_CI_SYS_ID_2}]}
        )
        ci_resp = _make_response(200, {"result": [FAKE_CI_RECORD_1, FAKE_CI_RECORD_2]})
        mock_req.side_effect = [detail_resp, task_resp, ci_resp]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PROB_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["source_count"], 2)
        self.assertEqual(len(result["cis"]), 2)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_ci_class_filter_applied(self, mock_req):
        detail_resp = _make_response(200, {"result": {"cmdb_ci": FAKE_CI_SYS_ID_1}})
        task_resp = _make_response(200, {"result": []})
        ci_resp = _make_response(200, {"result": [FAKE_CI_RECORD_1]})
        mock_req.side_effect = [detail_resp, task_resp, ci_resp]
        result = list_problem_related_cis(
            _make_auth(),
            _make_config(),
            {"problem_id": FAKE_PROB_SYS_ID, "ci_class": "cmdb_ci_server"},
        )
        self.assertTrue(result["success"])
        # Verify ci_class filter was passed in query
        ci_call_kwargs = mock_req.call_args_list[2]
        query = ci_call_kwargs[1]["params"]["sysparm_query"]
        self.assertIn("sys_class_name=cmdb_ci_server", query)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_include_problem_tasks_false(self, mock_req):
        detail_resp = _make_response(200, {"result": {"cmdb_ci": FAKE_CI_SYS_ID_1}})
        ci_resp = _make_response(200, {"result": [FAKE_CI_RECORD_1]})
        mock_req.side_effect = [detail_resp, ci_resp]
        result = list_problem_related_cis(
            _make_auth(),
            _make_config(),
            {"problem_id": FAKE_PROB_SYS_ID, "include_problem_tasks": False},
        )
        self.assertTrue(result["success"])
        # Should only make 2 calls: problem detail + CI fetch (no problem_task call)
        self.assertEqual(mock_req.call_count, 2)
        self.assertEqual(len(result["cis"]), 1)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_problem_task_ci_as_dict(self, mock_req):
        detail_resp = _make_response(200, {"result": {"cmdb_ci": ""}})
        task_resp = _make_response(
            200,
            {"result": [{"cmdb_ci": {"value": FAKE_CI_SYS_ID_2, "display_value": "db-server"}}]},
        )
        ci_resp = _make_response(200, {"result": [FAKE_CI_RECORD_2]})
        mock_req.side_effect = [detail_resp, task_resp, ci_resp]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PROB_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["source_count"], 1)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_problem_task_request_exception(self, mock_req):
        detail_resp = _make_response(200, {"result": {"cmdb_ci": ""}})
        mock_req.side_effect = [detail_resp, requests.exceptions.ConnectionError("fail")]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PROB_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("problem task CIs", result["message"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_ci_fetch_request_exception(self, mock_req):
        detail_resp = _make_response(200, {"result": {"cmdb_ci": FAKE_CI_SYS_ID_1}})
        task_resp = _make_response(200, {"result": []})
        mock_req.side_effect = [
            detail_resp,
            task_resp,
            requests.exceptions.ConnectionError("fail"),
        ]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PROB_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("CI records", result["message"])

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_pagination(self, mock_req):
        detail_resp = _make_response(200, {"result": {"cmdb_ci": FAKE_CI_SYS_ID_1}})
        task_resp = _make_response(200, {"result": []})
        ci_resp = _make_response(200, {"result": [FAKE_CI_RECORD_1]})
        mock_req.side_effect = [detail_resp, task_resp, ci_resp]
        result = list_problem_related_cis(
            _make_auth(),
            _make_config(),
            {"problem_id": FAKE_PROB_SYS_ID, "limit": 5, "offset": 0},
        )
        self.assertTrue(result["success"])
        self.assertIn("has_more", result)
        self.assertIn("next_offset", result)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_sys_id_passed_directly(self, mock_req):
        # When problem_id is a 32-char hex, skip the resolve lookup
        detail_resp = _make_response(200, {"result": {"cmdb_ci": FAKE_CI_SYS_ID_1}})
        task_resp = _make_response(200, {"result": []})
        ci_resp = _make_response(200, {"result": [FAKE_CI_RECORD_1]})
        mock_req.side_effect = [detail_resp, task_resp, ci_resp]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PROB_SYS_ID}
        )
        self.assertTrue(result["success"])
        # First call should be the problem detail fetch (not a resolve lookup)
        first_call_url = mock_req.call_args_list[0][0][1]
        self.assertIn(FAKE_PROB_SYS_ID, first_call_url)

    @patch("servicenow_mcp.tools.problem_tools._make_request")
    def test_ci_string_fields_normalised(self, mock_req):
        # ci record with plain string values (not dicts)
        plain_ci = {
            "sys_id": FAKE_CI_SYS_ID_1,
            "name": "web-server-01",
            "sys_class_name": "cmdb_ci_server",
            "category": "Hardware",
            "operational_status": "1",
            "environment": "production",
            "short_description": "Web server",
            "ip_address": "10.0.0.1",
            "serial_number": "SN001",
            "asset_tag": "P1000",
            "install_status": "1",
            "managed_by": "IT Ops",
            "owned_by": "Web Team",
            "location": "DC1",
            "company": "Acme Corp",
            "sys_created_on": "2025-01-01 00:00:00",
            "sys_updated_on": "2025-06-01 00:00:00",
        }
        detail_resp = _make_response(200, {"result": {"cmdb_ci": FAKE_CI_SYS_ID_1}})
        task_resp = _make_response(200, {"result": []})
        ci_resp = _make_response(200, {"result": [plain_ci]})
        mock_req.side_effect = [detail_resp, task_resp, ci_resp]
        result = list_problem_related_cis(
            _make_auth(), _make_config(), {"problem_id": FAKE_PROB_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["cis"][0]["name"], "web-server-01")
        self.assertEqual(result["cis"][0]["ci_class"], "cmdb_ci_server")


if __name__ == "__main__":
    unittest.main()
