"""Tests for list_ci_audit_history in cmdb_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.cmdb_tools import (
    ListCIAuditHistoryParams,
    list_ci_audit_history,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


def _make_entry(sys_id, field_name, old_value, new_value, changed_on="2026-07-20 10:00:00"):
    return {
        "sys_id": sys_id,
        "tablename": "cmdb_ci",
        "fieldname": field_name,
        "oldvalue": old_value,
        "newvalue": new_value,
        "documentkey": "ci_abc",
        "record_checkpoint": "chk001",
        "sys_created_on": changed_on,
        "sys_created_by": "admin",
        "reason": "",
    }


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


class TestListCIAuditHistoryParams(unittest.TestCase):
    def test_defaults(self):
        p = ListCIAuditHistoryParams(ci_sys_id="abc123")
        self.assertEqual(p.ci_sys_id, "abc123")
        self.assertEqual(p.ci_table, "cmdb_ci")
        self.assertEqual(p.limit, 100)
        self.assertEqual(p.offset, 0)
        self.assertIsNone(p.field_name)
        self.assertIsNone(p.changed_by)
        self.assertIsNone(p.changed_after)
        self.assertIsNone(p.changed_before)

    def test_all_optional_fields(self):
        p = ListCIAuditHistoryParams(
            ci_sys_id="ci001",
            ci_table="cmdb_ci_server",
            field_name="ip_address",
            changed_by="jdoe",
            changed_after="2026-01-01",
            changed_before="2026-12-31",
            limit=50,
            offset=10,
        )
        self.assertEqual(p.ci_table, "cmdb_ci_server")
        self.assertEqual(p.field_name, "ip_address")
        self.assertEqual(p.changed_by, "jdoe")
        self.assertEqual(p.limit, 50)
        self.assertEqual(p.offset, 10)

    def test_invalid_date_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ListCIAuditHistoryParams(ci_sys_id="x", changed_after="not-a-date")

    def test_date_only_accepted(self):
        p = ListCIAuditHistoryParams(ci_sys_id="x", changed_after="2026-06-01")
        self.assertEqual(p.changed_after, "2026-06-01")


class TestListCIAuditHistory(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    def _mock_response(self, entries):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": entries}
        return mock_resp

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_requires_ci_sys_id(self, _mock_req):
        result = list_ci_audit_history(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = self._mock_response([])
        result = list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_abc"})
        self.assertTrue(result["success"])
        self.assertEqual(result["history"], [])
        self.assertEqual(result["fields_changed"], 0)
        self.assertEqual(result["ci_sys_id"], "ci_abc")

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_single_entry(self, mock_req):
        entries = [_make_entry("a1", "operational_status", "1", "2")]
        mock_req.return_value = self._mock_response(entries)
        result = list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_abc"})
        self.assertTrue(result["success"])
        self.assertEqual(result["fields_changed"], 1)
        self.assertEqual(result["history"][0]["field_name"], "operational_status")
        self.assertEqual(result["history"][0]["new_value"], "2")

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_deduplication_keeps_newest_per_field(self, mock_req):
        # Three entries: two for operational_status, one for ip_address
        # Listed newest-first as the API returns them
        entries = [
            _make_entry("a3", "operational_status", "2", "3", "2026-07-20 12:00:00"),  # newest
            _make_entry("a2", "ip_address", "10.0.0.1", "10.0.0.2", "2026-07-20 11:00:00"),
            _make_entry("a1", "operational_status", "1", "2", "2026-07-20 10:00:00"),  # older
        ]
        mock_req.return_value = self._mock_response(entries)
        result = list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_abc"})
        self.assertTrue(result["success"])
        self.assertEqual(result["fields_changed"], 2)
        field_names = [e["field_name"] for e in result["history"]]
        self.assertIn("operational_status", field_names)
        self.assertIn("ip_address", field_names)
        # The newest operational_status entry (a3) should be kept
        op_entry = next(e for e in result["history"] if e["field_name"] == "operational_status")
        self.assertEqual(op_entry["sys_id"], "a3")
        self.assertEqual(op_entry["new_value"], "3")

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_all_unique_fields_preserved(self, mock_req):
        entries = [
            _make_entry("a1", "name", "old", "new"),
            _make_entry("a2", "short_description", "x", "y"),
            _make_entry("a3", "category", "hw", "sw"),
        ]
        mock_req.return_value = self._mock_response(entries)
        result = list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_abc"})
        self.assertTrue(result["success"])
        self.assertEqual(result["fields_changed"], 3)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_ci_sys_id_in_query(self, mock_req):
        mock_req.return_value = self._mock_response([])
        list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_abc"})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("documentkey=ci_abc", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_default_ci_table_in_query(self, mock_req):
        mock_req.return_value = self._mock_response([])
        list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_abc"})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("tablename=cmdb_ci", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_custom_ci_table_in_query(self, mock_req):
        mock_req.return_value = self._mock_response([])
        list_ci_audit_history(
            self.auth, self.config, {"ci_sys_id": "ci_abc", "ci_table": "cmdb_ci_server"}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("tablename=cmdb_ci_server", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_field_name_filter_in_query(self, mock_req):
        mock_req.return_value = self._mock_response([])
        list_ci_audit_history(
            self.auth, self.config, {"ci_sys_id": "ci_abc", "field_name": "ip_address"}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("fieldname=ip_address", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_changed_by_filter_in_query(self, mock_req):
        mock_req.return_value = self._mock_response([])
        list_ci_audit_history(
            self.auth, self.config, {"ci_sys_id": "ci_abc", "changed_by": "jdoe"}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("sys_created_by=jdoe", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_date_range_filters_in_query(self, mock_req):
        mock_req.return_value = self._mock_response([])
        list_ci_audit_history(
            self.auth,
            self.config,
            {
                "ci_sys_id": "ci_abc",
                "changed_after": "2026-07-01 00:00:00",
                "changed_before": "2026-07-31 23:59:59",
            },
        )
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("sys_created_on>=2026-07-01 00:00:00", query)
        self.assertIn("sys_created_on<=2026-07-31 23:59:59", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_ordered_newest_first(self, mock_req):
        mock_req.return_value = self._mock_response([])
        list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_abc"})
        call_params = mock_req.call_args[1]["params"]
        combined = (
            call_params.get("sysparm_query", "")
            + call_params.get("sysparm_orderby", "")
        )
        self.assertIn("DESCsys_created_on", combined)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_fields_requested(self, mock_req):
        mock_req.return_value = self._mock_response([])
        list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_abc"})
        fields = mock_req.call_args[1]["params"]["sysparm_fields"]
        for f in ("sys_id", "tablename", "fieldname", "oldvalue", "newvalue", "documentkey"):
            self.assertIn(f, fields)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("down")
        result = list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_abc"})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving CI audit history", result["message"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_http_500_returns_failure(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp
        )
        mock_req.return_value = mock_resp
        result = list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_abc"})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving CI audit history", result["message"])

    def test_no_instance_url_returns_failure(self):
        bad_auth = MagicMock(spec=AuthManager)
        bad_auth.get_headers.return_value = None
        bad_auth.instance_url = None
        result = list_ci_audit_history(bad_auth, self.config, {"ci_sys_id": "ci_abc"})
        self.assertFalse(result["success"])

    def test_invalid_date_returns_failure(self):
        result = list_ci_audit_history(
            self.auth, self.config, {"ci_sys_id": "ci_abc", "changed_after": "bad-date"}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_ci_sys_id_in_response(self, mock_req):
        mock_req.return_value = self._mock_response([])
        result = list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_xyz"})
        self.assertTrue(result["success"])
        self.assertEqual(result["ci_sys_id"], "ci_xyz")

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_many_repeated_fields_deduped(self, mock_req):
        # 10 changes to 'status', only 1 should be returned
        entries = [
            _make_entry(f"a{i}", "status", str(i - 1), str(i), f"2026-07-{20 - i:02d} 10:00:00")
            for i in range(9, -1, -1)  # newest first
        ]
        mock_req.return_value = self._mock_response(entries)
        result = list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_abc"})
        self.assertTrue(result["success"])
        self.assertEqual(result["fields_changed"], 1)
        self.assertEqual(result["history"][0]["sys_id"], "a9")  # newest

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_limit_passed_to_api(self, mock_req):
        mock_req.return_value = self._mock_response([])
        list_ci_audit_history(self.auth, self.config, {"ci_sys_id": "ci_abc", "limit": 50})
        call_params = mock_req.call_args[1]["params"]
        self.assertEqual(int(call_params["sysparm_limit"]), 50)


if __name__ == "__main__":
    unittest.main()
