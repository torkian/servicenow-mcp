"""Tests for list_cmdb_audit_log in cmdb_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.cmdb_tools import (
    ListCMDBAuditLogParams,
    _format_audit_entry,
    list_cmdb_audit_log,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_AUDIT_ENTRY = {
    "sys_id": "aud001",
    "tablename": "cmdb_ci",
    "fieldname": "operational_status",
    "oldvalue": "1",
    "newvalue": "2",
    "documentkey": "ci001",
    "record_checkpoint": "chk001",
    "sys_created_on": "2026-07-20 10:30:00",
    "sys_created_by": "admin",
    "reason": "Maintenance window",
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


class TestFormatAuditEntry(unittest.TestCase):
    def test_all_fields_mapped(self):
        result = _format_audit_entry(FAKE_AUDIT_ENTRY)
        self.assertEqual(result["sys_id"], "aud001")
        self.assertEqual(result["table"], "cmdb_ci")
        self.assertEqual(result["field_name"], "operational_status")
        self.assertEqual(result["old_value"], "1")
        self.assertEqual(result["new_value"], "2")
        self.assertEqual(result["ci_sys_id"], "ci001")
        self.assertEqual(result["checkpoint"], "chk001")
        self.assertEqual(result["changed_on"], "2026-07-20 10:30:00")
        self.assertEqual(result["changed_by"], "admin")
        self.assertEqual(result["reason"], "Maintenance window")

    def test_missing_fields_return_none(self):
        result = _format_audit_entry({})
        for key in ("sys_id", "table", "field_name", "old_value", "new_value",
                    "ci_sys_id", "checkpoint", "changed_on", "changed_by", "reason"):
            self.assertIsNone(result[key])


class TestListCMDBAuditLog(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_default_table_filter(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_AUDIT_ENTRY]}
        mock_req.return_value = mock_resp

        result = list_cmdb_audit_log(self.auth, self.config, {})

        self.assertTrue(result["success"])
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(result["entries"][0]["table"], "cmdb_ci")

        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"]["sysparm_query"]
        self.assertIn("tablename=cmdb_ci", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_ci_sys_id_filter(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_AUDIT_ENTRY]}
        mock_req.return_value = mock_resp

        result = list_cmdb_audit_log(
            self.auth, self.config, {"ci_sys_id": "ci001"}
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"]["sysparm_query"]
        self.assertIn("documentkey=ci001", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_field_name_filter(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        result = list_cmdb_audit_log(
            self.auth, self.config, {"field_name": "operational_status"}
        )

        self.assertTrue(result["success"])
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("fieldname=operational_status", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_changed_by_filter(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        result = list_cmdb_audit_log(
            self.auth, self.config, {"changed_by": "admin"}
        )

        self.assertTrue(result["success"])
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("sys_created_by=admin", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_date_range_filters(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        result = list_cmdb_audit_log(
            self.auth,
            self.config,
            {
                "changed_after": "2026-07-01 00:00:00",
                "changed_before": "2026-07-20 23:59:59",
            },
        )

        self.assertTrue(result["success"])
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("sys_created_on>=2026-07-01 00:00:00", query)
        self.assertIn("sys_created_on<=2026-07-20 23:59:59", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_custom_ci_table(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        result = list_cmdb_audit_log(
            self.auth, self.config, {"ci_table": "cmdb_ci_server"}
        )

        self.assertTrue(result["success"])
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("tablename=cmdb_ci_server", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_all_filters_combined(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_AUDIT_ENTRY]}
        mock_req.return_value = mock_resp

        result = list_cmdb_audit_log(
            self.auth,
            self.config,
            {
                "ci_table": "cmdb_ci",
                "ci_sys_id": "ci001",
                "field_name": "operational_status",
                "changed_by": "admin",
                "changed_after": "2026-07-01",
                "changed_before": "2026-07-31",
                "limit": 10,
                "offset": 0,
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["entries"]), 1)
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("tablename=cmdb_ci", query)
        self.assertIn("documentkey=ci001", query)
        self.assertIn("fieldname=operational_status", query)
        self.assertIn("sys_created_by=admin", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        result = list_cmdb_audit_log(self.auth, self.config, {})

        self.assertTrue(result["success"])
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_pagination_has_more(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        entries = [dict(FAKE_AUDIT_ENTRY, sys_id=f"aud{i:03d}") for i in range(20)]
        mock_resp.json.return_value = {"result": entries}
        mock_req.return_value = mock_resp

        result = list_cmdb_audit_log(
            self.auth, self.config, {"limit": 20, "offset": 0}
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 20)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        import requests

        mock_req.side_effect = requests.exceptions.ConnectionError("Network down")

        result = list_cmdb_audit_log(self.auth, self.config, {})

        self.assertFalse(result["success"])
        self.assertIn("Error listing CMDB audit log", result["message"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_http_error_status_code(self, mock_req):
        import requests

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp
        )
        mock_req.return_value = mock_resp

        result = list_cmdb_audit_log(self.auth, self.config, {})

        self.assertFalse(result["success"])
        self.assertIn("Error listing CMDB audit log", result["message"])

    def test_invalid_date_format_rejected(self):
        result = list_cmdb_audit_log(
            self.auth, self.config, {"changed_after": "not-a-date"}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_date_only_format_accepted(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        result = list_cmdb_audit_log(
            self.auth, self.config, {"changed_after": "2026-07-01"}
        )
        self.assertTrue(result["success"])

    def test_no_instance_url_returns_failure(self):
        bad_auth = MagicMock(spec=AuthManager)
        bad_auth.get_headers.return_value = None
        bad_auth.instance_url = None

        result = list_cmdb_audit_log(bad_auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_ordered_newest_first(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        list_cmdb_audit_log(self.auth, self.config, {})

        call_params = mock_req.call_args[1]["params"]
        combined = call_params.get("sysparm_query", "") + call_params.get("sysparm_orderby", "")
        self.assertIn("DESCsys_created_on", combined)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_fields_requested(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        list_cmdb_audit_log(self.auth, self.config, {})

        fields_param = mock_req.call_args[1]["params"]["sysparm_fields"]
        for field in ("sys_id", "tablename", "fieldname", "oldvalue", "newvalue",
                      "documentkey", "sys_created_on", "sys_created_by"):
            self.assertIn(field, fields_param)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_multiple_entries_formatted(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        entries = [
            dict(FAKE_AUDIT_ENTRY, sys_id="aud001", fieldname="operational_status"),
            dict(FAKE_AUDIT_ENTRY, sys_id="aud002", fieldname="short_description"),
        ]
        mock_resp.json.return_value = {"result": entries}
        mock_req.return_value = mock_resp

        result = list_cmdb_audit_log(self.auth, self.config, {"limit": 5})

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["entries"][0]["sys_id"], "aud001")
        self.assertEqual(result["entries"][1]["sys_id"], "aud002")


class TestListCMDBAuditLogParams(unittest.TestCase):
    def test_defaults(self):
        params = ListCMDBAuditLogParams()
        self.assertEqual(params.ci_table, "cmdb_ci")
        self.assertEqual(params.limit, 20)
        self.assertEqual(params.offset, 0)
        self.assertIsNone(params.ci_sys_id)
        self.assertIsNone(params.field_name)
        self.assertIsNone(params.changed_by)
        self.assertIsNone(params.changed_after)
        self.assertIsNone(params.changed_before)

    def test_valid_params(self):
        params = ListCMDBAuditLogParams(
            ci_table="cmdb_ci_server",
            ci_sys_id="abc123",
            field_name="ip_address",
            changed_by="john.doe",
            changed_after="2026-01-01",
            changed_before="2026-12-31",
            limit=50,
            offset=10,
        )
        self.assertEqual(params.ci_table, "cmdb_ci_server")
        self.assertEqual(params.ci_sys_id, "abc123")
        self.assertEqual(params.field_name, "ip_address")
        self.assertEqual(params.changed_by, "john.doe")
        self.assertEqual(params.limit, 50)
        self.assertEqual(params.offset, 10)

    def test_invalid_changed_after_raises(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ListCMDBAuditLogParams(changed_after="not-a-valid-date")

    def test_invalid_changed_before_raises(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ListCMDBAuditLogParams(changed_before="tomorrow")


if __name__ == "__main__":
    unittest.main()
