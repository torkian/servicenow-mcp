"""Tests for list_cmdb_ci_outages in cmdb_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.cmdb_tools import (
    ListCMDBCIOutagesParams,
    _format_ci_outage,
    list_cmdb_ci_outages,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig
from servicenow_mcp.auth.auth_manager import AuthManager


FAKE_OUTAGE = {
    "sys_id": "out001",
    "cmdb_ci": {"value": "ci001", "display_value": "web-server-01"},
    "type": "hardware",
    "begin": "2026-01-10 08:00:00",
    "end": "2026-01-10 12:00:00",
    "duration": "4 Hours",
    "short_description": "Hardware failure on web-server-01",
    "cause_ci": {"value": "ci002", "display_value": "router-01"},
    "resolved": "true",
    "resolution_notes": "Replaced failed disk",
    "sys_created_on": "2026-01-10 08:05:00",
    "sys_updated_on": "2026-01-10 12:30:00",
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


class TestFormatCIOutage(unittest.TestCase):
    def test_all_fields_mapped(self):
        result = _format_ci_outage(FAKE_OUTAGE)
        self.assertEqual(result["sys_id"], "out001")
        self.assertEqual(result["ci_sys_id"], "ci001")
        self.assertEqual(result["type"], "hardware")
        self.assertEqual(result["begin"], "2026-01-10 08:00:00")
        self.assertEqual(result["end"], "2026-01-10 12:00:00")
        self.assertEqual(result["duration"], "4 Hours")
        self.assertEqual(result["short_description"], "Hardware failure on web-server-01")
        self.assertEqual(result["cause_ci"], "ci002")
        self.assertEqual(result["resolved"], "true")
        self.assertEqual(result["resolution_notes"], "Replaced failed disk")
        self.assertEqual(result["created_on"], "2026-01-10 08:05:00")
        self.assertEqual(result["updated_on"], "2026-01-10 12:30:00")

    def test_plain_string_ci_reference(self):
        record = dict(FAKE_OUTAGE)
        record["cmdb_ci"] = "ci-plain"
        record["cause_ci"] = None
        result = _format_ci_outage(record)
        self.assertEqual(result["ci_sys_id"], "ci-plain")
        self.assertIsNone(result["cause_ci"])

    def test_missing_fields_return_none(self):
        result = _format_ci_outage({})
        for key in ("sys_id", "ci_sys_id", "type", "begin", "end", "duration",
                    "short_description", "cause_ci", "resolved", "resolution_notes",
                    "created_on", "updated_on"):
            self.assertIsNone(result[key])


class TestListCMDBCIOutagesParams(unittest.TestCase):
    def test_defaults(self):
        p = ListCMDBCIOutagesParams()
        self.assertEqual(p.limit, 20)
        self.assertEqual(p.offset, 0)
        self.assertIsNone(p.ci_sys_id)
        self.assertIsNone(p.outage_type)
        self.assertIsNone(p.resolved)
        self.assertIsNone(p.begin_after)
        self.assertIsNone(p.begin_before)
        self.assertIsNone(p.query)

    def test_valid_datetime_fields(self):
        p = ListCMDBCIOutagesParams(
            begin_after="2026-01-01 00:00:00",
            begin_before="2026-01-31",
        )
        self.assertEqual(p.begin_after, "2026-01-01 00:00:00")
        self.assertEqual(p.begin_before, "2026-01-31")

    def test_invalid_datetime_raises(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ListCMDBCIOutagesParams(begin_after="not-a-date")


class TestListCMDBCIOutages(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_returns_outages(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_OUTAGE]}
        mock_req.return_value = mock_resp

        result = list_cmdb_ci_outages(self.auth, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["outages"]), 1)
        self.assertEqual(result["outages"][0]["sys_id"], "out001")

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        result = list_cmdb_ci_outages(self.auth, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(result["outages"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_filter_by_ci_sys_id(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_OUTAGE]}
        mock_req.return_value = mock_resp

        result = list_cmdb_ci_outages(self.auth, self.config, {"ci_sys_id": "ci001"})
        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("cmdb_ci=ci001", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_filter_by_outage_type(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        list_cmdb_ci_outages(self.auth, self.config, {"outage_type": "network"})
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("type=network", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_filter_resolved_true(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        list_cmdb_ci_outages(self.auth, self.config, {"resolved": True})
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("resolved=true", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_filter_resolved_false(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        list_cmdb_ci_outages(self.auth, self.config, {"resolved": False})
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("resolved=false", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_filter_begin_after(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        list_cmdb_ci_outages(
            self.auth, self.config,
            {"begin_after": "2026-01-01 00:00:00"},
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("begin>=2026-01-01 00:00:00", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_filter_begin_before(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        list_cmdb_ci_outages(
            self.auth, self.config,
            {"begin_before": "2026-01-31"},
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("begin<=2026-01-31", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_combined_filters(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_OUTAGE]}
        mock_req.return_value = mock_resp

        list_cmdb_ci_outages(
            self.auth, self.config,
            {
                "ci_sys_id": "ci001",
                "outage_type": "hardware",
                "resolved": False,
                "begin_after": "2026-01-01",
            },
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("cmdb_ci=ci001", query)
        self.assertIn("type=hardware", query)
        self.assertIn("resolved=false", query)
        self.assertIn("begin>=2026-01-01", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_raw_query_appended(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        list_cmdb_ci_outages(
            self.auth, self.config,
            {"query": "short_descriptionLIKEfailure"},
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("short_descriptionLIKEfailure", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_pagination_fields(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_OUTAGE] * 5}
        mock_req.return_value = mock_resp

        result = list_cmdb_ci_outages(
            self.auth, self.config,
            {"limit": 5, "offset": 10},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 5)
        self.assertIn("has_more", result)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        import requests as req_lib
        mock_req.side_effect = req_lib.exceptions.ConnectionError("network error")

        result = list_cmdb_ci_outages(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing CI outages", result["message"])

    def test_missing_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None

        config = MagicMock()
        config.instance_url = None

        result = list_cmdb_ci_outages(auth, config, {})
        self.assertFalse(result["success"])

    def test_missing_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev99999.service-now.com"

        result = list_cmdb_ci_outages(auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_uses_correct_table(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        list_cmdb_ci_outages(self.auth, self.config, {})
        call_args = mock_req.call_args
        url = call_args[0][1]
        self.assertIn("cmdb_ci_outage", url)


if __name__ == "__main__":
    unittest.main()
