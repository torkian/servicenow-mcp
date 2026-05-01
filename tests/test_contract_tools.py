"""Tests for contract_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.tools.contract_tools import (
    _format_contract,
    get_asset_contract,
    list_asset_contracts,
)
from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


FAKE_CONTRACT = {
    "sys_id": "con001",
    "number": "CON0001234",
    "short_description": "Annual hardware maintenance",
    "vendor": {"display_value": "Dell Inc.", "value": "vendor001"},
    "state": "active",
    "contract_type": {"display_value": "Maintenance", "value": "maint001"},
    "category": {"display_value": "Hardware", "value": "cat001"},
    "start_date": "2025-01-01",
    "end_date": "2026-01-01",
    "value": "50000.00",
    "currency": "USD",
    "assigned_to": {"display_value": "Jane Smith", "value": "user001"},
    "department": {"display_value": "IT", "value": "dept001"},
    "company": {"display_value": "Acme Corp", "value": "comp001"},
    "location": {"display_value": "HQ", "value": "loc001"},
    "sys_created_on": "2025-01-01 09:00:00",
    "sys_updated_on": "2026-01-01 00:00:00",
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


class TestFormatContract(unittest.TestCase):
    def test_all_fields_mapped(self):
        result = _format_contract(FAKE_CONTRACT)
        self.assertEqual(result["sys_id"], "con001")
        self.assertEqual(result["number"], "CON0001234")
        self.assertEqual(result["short_description"], "Annual hardware maintenance")
        self.assertEqual(result["vendor"], "Dell Inc.")
        self.assertEqual(result["state"], "active")
        self.assertEqual(result["contract_type"], "Maintenance")
        self.assertEqual(result["category"], "Hardware")
        self.assertEqual(result["start_date"], "2025-01-01")
        self.assertEqual(result["end_date"], "2026-01-01")
        self.assertEqual(result["value"], "50000.00")
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(result["assigned_to"], "Jane Smith")
        self.assertEqual(result["department"], "IT")
        self.assertEqual(result["company"], "Acme Corp")
        self.assertEqual(result["location"], "HQ")
        self.assertEqual(result["created_on"], "2025-01-01 09:00:00")
        self.assertEqual(result["updated_on"], "2026-01-01 00:00:00")

    def test_missing_fields_return_none(self):
        result = _format_contract({})
        for key in ("sys_id", "number", "short_description", "vendor", "state",
                    "contract_type", "category", "start_date", "end_date",
                    "value", "currency", "assigned_to", "department", "company",
                    "location", "created_on", "updated_on"):
            self.assertIsNone(result[key], f"{key} should be None for empty record")

    def test_plain_string_ref_fields(self):
        record = dict(FAKE_CONTRACT)
        record["vendor"] = "Some Vendor"
        record["assigned_to"] = "plain_user"
        result = _format_contract(record)
        self.assertEqual(result["vendor"], "Some Vendor")
        self.assertEqual(result["assigned_to"], "plain_user")

    def test_ref_field_falls_back_to_value(self):
        record = dict(FAKE_CONTRACT)
        record["vendor"] = {"display_value": "", "value": "raw_vendor_id"}
        result = _format_contract(record)
        self.assertEqual(result["vendor"], "raw_vendor_id")


class TestListAssetContracts(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    def _mock_response(self, data, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = {"result": data}
        resp.raise_for_status.return_value = None
        return resp

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_returns_contracts(self, mock_req):
        mock_req.return_value = self._mock_response([FAKE_CONTRACT])
        result = list_asset_contracts(self.auth, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["contracts"]), 1)
        self.assertEqual(result["contracts"][0]["number"], "CON0001234")

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_empty_result(self, mock_req):
        mock_req.return_value = self._mock_response([])
        result = list_asset_contracts(self.auth, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(result["contracts"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_vendor_filter_applied(self, mock_req):
        mock_req.return_value = self._mock_response([FAKE_CONTRACT])
        list_asset_contracts(self.auth, self.config, {"vendor": "Dell"})
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("vendor.nameLIKEDell", query)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_state_filter_applied(self, mock_req):
        mock_req.return_value = self._mock_response([FAKE_CONTRACT])
        list_asset_contracts(self.auth, self.config, {"state": "active"})
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("state=active", query)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_contract_type_filter(self, mock_req):
        mock_req.return_value = self._mock_response([FAKE_CONTRACT])
        list_asset_contracts(self.auth, self.config, {"contract_type": "Maintenance"})
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("contract_type.nameLIKEMaintenance", query)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_short_description_filter(self, mock_req):
        mock_req.return_value = self._mock_response([FAKE_CONTRACT])
        list_asset_contracts(self.auth, self.config, {"short_description": "hardware"})
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("short_descriptionLIKEhardware", query)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_start_date_from_filter(self, mock_req):
        mock_req.return_value = self._mock_response([FAKE_CONTRACT])
        list_asset_contracts(self.auth, self.config, {"start_date_from": "2025-01-01"})
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("start_date>=2025-01-01", query)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_end_date_before_filter(self, mock_req):
        mock_req.return_value = self._mock_response([FAKE_CONTRACT])
        list_asset_contracts(self.auth, self.config, {"end_date_before": "2026-12-31"})
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("end_date<=2026-12-31", query)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_raw_query_filter(self, mock_req):
        mock_req.return_value = self._mock_response([FAKE_CONTRACT])
        list_asset_contracts(self.auth, self.config, {"query": "active=true"})
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("active=true", query)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_pagination_params(self, mock_req):
        mock_req.return_value = self._mock_response([FAKE_CONTRACT])
        list_asset_contracts(self.auth, self.config, {"limit": 5, "offset": 10})
        call_kwargs = mock_req.call_args
        qp = call_kwargs[1]["params"]
        self.assertEqual(qp["sysparm_limit"], 5)
        self.assertEqual(qp["sysparm_offset"], 10)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_http_error(self, mock_req):
        mock_req.return_value = self._mock_response([], 500)
        mock_req.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Server Error"
        )
        result = list_asset_contracts(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing asset contracts", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_connection_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_asset_contracts(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing asset contracts", result["message"])

    def test_list_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_instance_url = MagicMock(return_value=None)
        auth.instance_url = None
        config = MagicMock(spec=ServerConfig)
        config.instance_url = None
        result = list_asset_contracts(auth, config, {})
        self.assertFalse(result["success"])

    def test_list_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_instance_url = MagicMock(return_value="https://dev.service-now.com")
        auth.instance_url = "https://dev.service-now.com"
        auth.get_headers = MagicMock(return_value=None)
        config = MagicMock(spec=ServerConfig)
        config.instance_url = "https://dev.service-now.com"
        result = list_asset_contracts(auth, config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_has_more_pagination(self, mock_req):
        contracts = [dict(FAKE_CONTRACT)] * 5
        mock_req.return_value = self._mock_response(contracts)
        result = list_asset_contracts(self.auth, self.config, {"limit": 5, "offset": 0})
        self.assertTrue(result["success"])
        self.assertIn("has_more", result)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_list_multiple_filters_combined(self, mock_req):
        mock_req.return_value = self._mock_response([FAKE_CONTRACT])
        list_asset_contracts(
            self.auth,
            self.config,
            {"vendor": "Dell", "state": "active", "start_date_from": "2025-01-01"},
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("vendor.nameLIKEDell", query)
        self.assertIn("state=active", query)
        self.assertIn("start_date>=2025-01-01", query)


class TestGetAssetContract(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    def _mock_response(self, data, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = {"result": data}
        resp.raise_for_status.return_value = None
        return resp

    def test_no_identifier_returns_error(self):
        result = get_asset_contract(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("required", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_get_by_sys_id_success(self, mock_req):
        mock_req.return_value = self._mock_response(FAKE_CONTRACT)
        result = get_asset_contract(self.auth, self.config, {"sys_id": "con001"})
        self.assertTrue(result["success"])
        self.assertEqual(result["contract"]["number"], "CON0001234")

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_get_by_sys_id_404(self, mock_req):
        resp = MagicMock()
        resp.status_code = 404
        mock_req.return_value = resp
        result = get_asset_contract(self.auth, self.config, {"sys_id": "missing001"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_get_by_sys_id_empty_result(self, mock_req):
        mock_req.return_value = self._mock_response({})
        result = get_asset_contract(self.auth, self.config, {"sys_id": "con001"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_get_by_number_success(self, mock_req):
        mock_req.return_value = self._mock_response([FAKE_CONTRACT])
        result = get_asset_contract(self.auth, self.config, {"number": "CON0001234"})
        self.assertTrue(result["success"])
        self.assertEqual(result["contract"]["number"], "CON0001234")

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_get_by_number_not_found(self, mock_req):
        mock_req.return_value = self._mock_response([])
        result = get_asset_contract(self.auth, self.config, {"number": "CON9999"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_get_by_number_query_includes_number(self, mock_req):
        mock_req.return_value = self._mock_response([FAKE_CONTRACT])
        get_asset_contract(self.auth, self.config, {"number": "CON0001234"})
        call_kwargs = mock_req.call_args
        qp = call_kwargs[1]["params"]
        self.assertIn("number=CON0001234", qp.get("sysparm_query", ""))
        self.assertEqual(qp.get("sysparm_limit"), "1")

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_get_http_error(self, mock_req):
        mock_req.return_value = self._mock_response({}, 500)
        mock_req.return_value.status_code = 500
        mock_req.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Server Error"
        )
        result = get_asset_contract(self.auth, self.config, {"sys_id": "con001"})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving asset contract", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_get_connection_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = get_asset_contract(self.auth, self.config, {"sys_id": "con001"})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving asset contract", result["message"])

    def test_get_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_instance_url = MagicMock(return_value=None)
        auth.instance_url = None
        config = MagicMock(spec=ServerConfig)
        config.instance_url = None
        result = get_asset_contract(auth, config, {"sys_id": "con001"})
        self.assertFalse(result["success"])

    def test_get_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_instance_url = MagicMock(return_value="https://dev.service-now.com")
        auth.instance_url = "https://dev.service-now.com"
        auth.get_headers = MagicMock(return_value=None)
        config = MagicMock(spec=ServerConfig)
        config.instance_url = "https://dev.service-now.com"
        result = get_asset_contract(auth, config, {"sys_id": "con001"})
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
