"""Tests for contract_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.tools.contract_tools import (
    _format_contract,
    _format_contract_asset,
    create_asset_contract,
    expire_asset_contract,
    get_asset_contract,
    list_asset_contracts,
    list_contract_assets,
    update_asset_contract,
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


class TestCreateAssetContract(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    def _mock_response(self, data, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = {"result": data}
        resp.raise_for_status.return_value = None
        return resp

    def test_missing_short_description_returns_error(self):
        result = create_asset_contract(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_create_success_returns_sys_id_and_contract(self, mock_req):
        mock_req.return_value = self._mock_response(FAKE_CONTRACT)
        result = create_asset_contract(
            self.auth, self.config, {"short_description": "Annual maintenance"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "con001")
        self.assertIn("contract", result)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_create_posts_to_contract_table(self, mock_req):
        mock_req.return_value = self._mock_response(FAKE_CONTRACT)
        create_asset_contract(
            self.auth, self.config, {"short_description": "Test contract"}
        )
        call_args = mock_req.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertIn("alm_contract", call_args[0][1])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_create_includes_optional_fields_in_body(self, mock_req):
        mock_req.return_value = self._mock_response(FAKE_CONTRACT)
        create_asset_contract(
            self.auth,
            self.config,
            {
                "short_description": "Test",
                "vendor": "vendor001",
                "start_date": "2026-01-01",
                "end_date": "2027-01-01",
                "value": "99000",
                "currency": "USD",
                "state": "draft",
            },
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["vendor"], "vendor001")
        self.assertEqual(body["start_date"], "2026-01-01")
        self.assertEqual(body["end_date"], "2027-01-01")
        self.assertEqual(body["value"], "99000")
        self.assertEqual(body["currency"], "USD")
        self.assertEqual(body["state"], "draft")

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_create_omits_none_fields_from_body(self, mock_req):
        mock_req.return_value = self._mock_response(FAKE_CONTRACT)
        create_asset_contract(
            self.auth, self.config, {"short_description": "Minimal contract"}
        )
        body = mock_req.call_args[1]["json"]
        self.assertNotIn("vendor", body)
        self.assertNotIn("start_date", body)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_create_http_error(self, mock_req):
        mock_req.return_value = self._mock_response({}, 400)
        mock_req.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Bad Request"
        )
        result = create_asset_contract(
            self.auth, self.config, {"short_description": "Test"}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error creating asset contract", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_create_connection_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = create_asset_contract(
            self.auth, self.config, {"short_description": "Test"}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error creating asset contract", result["message"])

    def test_create_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.instance_url = None
        config = MagicMock(spec=ServerConfig)
        config.instance_url = None
        result = create_asset_contract(auth, config, {"short_description": "Test"})
        self.assertFalse(result["success"])

    def test_create_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.instance_url = "https://dev.service-now.com"
        auth.get_headers = MagicMock(return_value=None)
        config = MagicMock(spec=ServerConfig)
        config.instance_url = "https://dev.service-now.com"
        result = create_asset_contract(auth, config, {"short_description": "Test"})
        self.assertFalse(result["success"])


class TestUpdateAssetContract(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    def _mock_response(self, data, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = {"result": data}
        resp.raise_for_status.return_value = None
        return resp

    def test_missing_sys_id_returns_error(self):
        result = update_asset_contract(
            self.auth, self.config, {"short_description": "Updated"}
        )
        self.assertFalse(result["success"])

    def test_no_update_fields_returns_error(self):
        result = update_asset_contract(self.auth, self.config, {"sys_id": "con001"})
        self.assertFalse(result["success"])
        self.assertIn("No fields", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_update_success(self, mock_req):
        mock_req.return_value = self._mock_response(FAKE_CONTRACT)
        result = update_asset_contract(
            self.auth, self.config, {"sys_id": "con001", "state": "active"}
        )
        self.assertTrue(result["success"])
        self.assertIn("contract", result)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_update_patches_correct_url(self, mock_req):
        mock_req.return_value = self._mock_response(FAKE_CONTRACT)
        update_asset_contract(
            self.auth, self.config, {"sys_id": "con001", "value": "12000"}
        )
        call_args = mock_req.call_args
        self.assertEqual(call_args[0][0], "PATCH")
        self.assertIn("con001", call_args[0][1])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_update_sends_only_provided_fields(self, mock_req):
        mock_req.return_value = self._mock_response(FAKE_CONTRACT)
        update_asset_contract(
            self.auth,
            self.config,
            {"sys_id": "con001", "short_description": "Revised", "currency": "EUR"},
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["short_description"], "Revised")
        self.assertEqual(body["currency"], "EUR")
        self.assertNotIn("vendor", body)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_update_404_returns_not_found(self, mock_req):
        resp = MagicMock()
        resp.status_code = 404
        mock_req.return_value = resp
        result = update_asset_contract(
            self.auth, self.config, {"sys_id": "missing001", "state": "expired"}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_update_http_error(self, mock_req):
        resp = MagicMock()
        resp.status_code = 500
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")
        mock_req.return_value = resp
        result = update_asset_contract(
            self.auth, self.config, {"sys_id": "con001", "state": "active"}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating asset contract", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_update_connection_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = update_asset_contract(
            self.auth, self.config, {"sys_id": "con001", "state": "active"}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating asset contract", result["message"])

    def test_update_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.instance_url = None
        config = MagicMock(spec=ServerConfig)
        config.instance_url = None
        result = update_asset_contract(
            auth, config, {"sys_id": "con001", "state": "active"}
        )
        self.assertFalse(result["success"])

    def test_update_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.instance_url = "https://dev.service-now.com"
        auth.get_headers = MagicMock(return_value=None)
        config = MagicMock(spec=ServerConfig)
        config.instance_url = "https://dev.service-now.com"
        result = update_asset_contract(
            auth, config, {"sys_id": "con001", "state": "active"}
        )
        self.assertFalse(result["success"])


FAKE_CONTRACT_ASSET = {
    "sys_id": "asset001",
    "asset_tag": "P000123",
    "display_name": "Dell Laptop",
    "serial_number": "SN12345",
    "model": {"display_value": "Dell XPS 15", "value": "model001"},
    "model_category": {"display_value": "Computer", "value": "cat001"},
    "assigned_to": {"display_value": "Alice Brown", "value": "user001"},
    "install_status": "1",
    "substatus": "",
    "cost": "1500.00",
    "cost_currency": "USD",
    "purchase_date": "2024-01-15",
    "warranty_expiration": "2027-01-15",
    "vendor": {"display_value": "Dell Inc.", "value": "vendor001"},
    "location": {"display_value": "HQ", "value": "loc001"},
    "company": {"display_value": "Acme Corp", "value": "comp001"},
    "department": {"display_value": "IT", "value": "dept001"},
    "maintenance_contract": {"display_value": "CON0001234", "value": "con001"},
    "sys_created_on": "2024-01-15 09:00:00",
    "sys_updated_on": "2025-01-01 00:00:00",
}


class TestFormatContractAsset(unittest.TestCase):
    def test_all_fields_mapped(self):
        result = _format_contract_asset(FAKE_CONTRACT_ASSET)
        self.assertEqual(result["sys_id"], "asset001")
        self.assertEqual(result["asset_tag"], "P000123")
        self.assertEqual(result["display_name"], "Dell Laptop")
        self.assertEqual(result["serial_number"], "SN12345")
        self.assertEqual(result["model"], "Dell XPS 15")
        self.assertEqual(result["model_category"], "Computer")
        self.assertEqual(result["assigned_to"], "Alice Brown")
        self.assertEqual(result["install_status"], "1")
        self.assertEqual(result["cost"], "1500.00")
        self.assertEqual(result["cost_currency"], "USD")
        self.assertEqual(result["purchase_date"], "2024-01-15")
        self.assertEqual(result["warranty_expiration"], "2027-01-15")
        self.assertEqual(result["vendor"], "Dell Inc.")
        self.assertEqual(result["location"], "HQ")
        self.assertEqual(result["company"], "Acme Corp")
        self.assertEqual(result["department"], "IT")
        self.assertEqual(result["maintenance_contract"], "CON0001234")
        self.assertEqual(result["created_on"], "2024-01-15 09:00:00")
        self.assertEqual(result["updated_on"], "2025-01-01 00:00:00")

    def test_missing_fields_return_none(self):
        result = _format_contract_asset({})
        for key in ("sys_id", "asset_tag", "display_name", "model", "vendor"):
            self.assertIsNone(result[key])

    def test_scalar_reference_fields(self):
        record = dict(FAKE_CONTRACT_ASSET)
        record["vendor"] = "Flat Vendor"
        result = _format_contract_asset(record)
        self.assertEqual(result["vendor"], "Flat Vendor")


class TestListContractAssets(unittest.TestCase):
    def _make_auth_and_config(self):
        return _make_auth_manager(), _make_config()

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_success_returns_assets(self, mock_req):
        auth, config = self._make_auth_and_config()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_CONTRACT_ASSET]}
        mock_req.return_value = mock_resp

        result = list_contract_assets(auth, config, {"contract_sys_id": "con001"})

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["assets"][0]["sys_id"], "asset001")
        self.assertEqual(result["assets"][0]["display_name"], "Dell Laptop")

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_filter_by_install_status(self, mock_req):
        auth, config = self._make_auth_and_config()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_CONTRACT_ASSET]}
        mock_req.return_value = mock_resp

        result = list_contract_assets(
            auth, config, {"contract_sys_id": "con001", "install_status": "1"}
        )

        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("install_status=1", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_filter_by_display_name(self, mock_req):
        auth, config = self._make_auth_and_config()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_CONTRACT_ASSET]}
        mock_req.return_value = mock_resp

        result = list_contract_assets(
            auth, config, {"contract_sys_id": "con001", "display_name": "Laptop"}
        )

        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("display_nameLIKELaptop", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_contract_sys_id_in_query(self, mock_req):
        auth, config = self._make_auth_and_config()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        list_contract_assets(auth, config, {"contract_sys_id": "con999"})

        call_params = mock_req.call_args[1]["params"]
        self.assertIn("maintenance_contract=con999", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_empty_result(self, mock_req):
        auth, config = self._make_auth_and_config()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        result = list_contract_assets(auth, config, {"contract_sys_id": "con001"})

        self.assertTrue(result["success"])
        self.assertEqual(result["assets"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_http_error(self, mock_req):
        auth, config = self._make_auth_and_config()
        mock_req.side_effect = requests.exceptions.RequestException("server error")

        result = list_contract_assets(auth, config, {"contract_sys_id": "con001"})

        self.assertFalse(result["success"])
        self.assertIn("Error listing contract assets", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_pagination_fields_present(self, mock_req):
        auth, config = self._make_auth_and_config()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_CONTRACT_ASSET] * 20}
        mock_req.return_value = mock_resp

        result = list_contract_assets(
            auth, config, {"contract_sys_id": "con001", "limit": 20, "offset": 0}
        )

        self.assertIn("has_more", result)
        self.assertIn("next_offset", result)

    def test_missing_contract_sys_id(self):
        auth, config = self._make_auth_and_config()
        result = list_contract_assets(auth, config, {})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.instance_url = None
        config = MagicMock(spec=ServerConfig)
        config.instance_url = None
        result = list_contract_assets(auth, config, {"contract_sys_id": "con001"})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.instance_url = "https://dev.service-now.com"
        auth.get_headers = MagicMock(return_value=None)
        config = MagicMock(spec=ServerConfig)
        config.instance_url = "https://dev.service-now.com"
        result = list_contract_assets(auth, config, {"contract_sys_id": "con001"})
        self.assertFalse(result["success"])


class TestExpireAssetContract(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    def _mock_response(self, data, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = {"result": data}
        resp.raise_for_status.return_value = None
        return resp

    def test_missing_sys_id_returns_error(self):
        result = expire_asset_contract(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_expire_success_returns_contract(self, mock_req):
        expired = dict(FAKE_CONTRACT)
        expired["state"] = "expired"
        mock_req.return_value = self._mock_response(expired)
        result = expire_asset_contract(self.auth, self.config, {"sys_id": "con001"})
        self.assertTrue(result["success"])
        self.assertIn("contract", result)
        self.assertEqual(result["contract"]["state"], "expired")

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_expire_sends_patch_with_expired_state(self, mock_req):
        mock_req.return_value = self._mock_response(FAKE_CONTRACT)
        expire_asset_contract(self.auth, self.config, {"sys_id": "con001"})
        call_args = mock_req.call_args
        self.assertEqual(call_args[0][0], "PATCH")
        self.assertIn("con001", call_args[0][1])
        self.assertEqual(call_args[1]["json"]["state"], "expired")

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_expire_with_notes_includes_notes_in_body(self, mock_req):
        mock_req.return_value = self._mock_response(FAKE_CONTRACT)
        expire_asset_contract(
            self.auth, self.config, {"sys_id": "con001", "notes": "End of term"}
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["notes"], "End of term")
        self.assertEqual(body["state"], "expired")

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_expire_without_notes_omits_notes_from_body(self, mock_req):
        mock_req.return_value = self._mock_response(FAKE_CONTRACT)
        expire_asset_contract(self.auth, self.config, {"sys_id": "con001"})
        body = mock_req.call_args[1]["json"]
        self.assertNotIn("notes", body)

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_expire_404_returns_not_found_message(self, mock_req):
        mock_req.return_value = self._mock_response({}, status_code=404)
        result = expire_asset_contract(self.auth, self.config, {"sys_id": "bad001"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertIn("bad001", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_expire_http_error_returns_error_message(self, mock_req):
        mock_req.return_value = self._mock_response({}, 500)
        mock_req.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Server Error"
        )
        result = expire_asset_contract(self.auth, self.config, {"sys_id": "con001"})
        self.assertFalse(result["success"])
        self.assertIn("Error expiring asset contract", result["message"])

    @patch("servicenow_mcp.tools.contract_tools._make_request")
    def test_expire_connection_error_returns_error_message(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = expire_asset_contract(self.auth, self.config, {"sys_id": "con001"})
        self.assertFalse(result["success"])
        self.assertIn("Error expiring asset contract", result["message"])

    def test_expire_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.instance_url = None
        config = MagicMock(spec=ServerConfig)
        config.instance_url = None
        result = expire_asset_contract(auth, config, {"sys_id": "con001"})
        self.assertFalse(result["success"])

    def test_expire_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.instance_url = "https://dev.service-now.com"
        auth.get_headers = MagicMock(return_value=None)
        config = MagicMock(spec=ServerConfig)
        config.instance_url = "https://dev.service-now.com"
        result = expire_asset_contract(auth, config, {"sys_id": "con001"})
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
