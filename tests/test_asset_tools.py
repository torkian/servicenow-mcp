"""Tests for asset_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.tools.asset_tools import (
    GetAssetParams,
    ListAssetsParams,
    UpdateAssetParams,
    _format_asset,
    get_asset,
    list_assets,
    update_asset,
)
from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


FAKE_ASSET = {
    "sys_id": "asset001",
    "asset_tag": "P1000123",
    "display_name": "Dell Laptop 001",
    "serial_number": "SN9876",
    "model": {"display_value": "Dell Latitude 5520", "value": "model001"},
    "model_category": {"display_value": "Computer", "value": "cat001"},
    "assigned_to": {"display_value": "John Doe", "value": "user001"},
    "assigned": "true",
    "install_status": "1",
    "substatus": "active",
    "cost": "1200.00",
    "cost_currency": "USD",
    "purchase_date": "2025-01-15",
    "warranty_expiration": "2028-01-15",
    "lease_id": "",
    "vendor": {"display_value": "Dell Inc.", "value": "vendor001"},
    "acquisition_method": "purchase",
    "owned_by": {"display_value": "IT Dept", "value": "user002"},
    "managed_by": {"display_value": "IT Manager", "value": "user003"},
    "location": {"display_value": "HQ", "value": "loc001"},
    "company": {"display_value": "Acme Corp", "value": "comp001"},
    "department": {"display_value": "Engineering", "value": "dept001"},
    "sys_created_on": "2025-01-15 10:00:00",
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


class TestFormatAsset(unittest.TestCase):
    def test_all_fields_mapped(self):
        result = _format_asset(FAKE_ASSET)
        self.assertEqual(result["sys_id"], "asset001")
        self.assertEqual(result["asset_tag"], "P1000123")
        self.assertEqual(result["display_name"], "Dell Laptop 001")
        self.assertEqual(result["serial_number"], "SN9876")
        self.assertEqual(result["model"], "Dell Latitude 5520")
        self.assertEqual(result["model_category"], "Computer")
        self.assertEqual(result["assigned_to"], "John Doe")
        self.assertEqual(result["assigned"], "true")
        self.assertEqual(result["install_status"], "1")
        self.assertEqual(result["substatus"], "active")
        self.assertEqual(result["cost"], "1200.00")
        self.assertEqual(result["cost_currency"], "USD")
        self.assertEqual(result["purchase_date"], "2025-01-15")
        self.assertEqual(result["warranty_expiration"], "2028-01-15")
        self.assertEqual(result["vendor"], "Dell Inc.")
        self.assertEqual(result["acquisition_method"], "purchase")
        self.assertEqual(result["owned_by"], "IT Dept")
        self.assertEqual(result["managed_by"], "IT Manager")
        self.assertEqual(result["location"], "HQ")
        self.assertEqual(result["company"], "Acme Corp")
        self.assertEqual(result["department"], "Engineering")
        self.assertEqual(result["created_on"], "2025-01-15 10:00:00")
        self.assertEqual(result["updated_on"], "2026-01-01 00:00:00")

    def test_missing_fields_return_none(self):
        result = _format_asset({})
        for key in (
            "sys_id", "asset_tag", "display_name", "serial_number", "model",
            "model_category", "assigned_to", "assigned", "install_status", "substatus",
            "cost", "cost_currency", "purchase_date", "warranty_expiration", "lease_id",
            "vendor", "acquisition_method", "owned_by", "managed_by", "location",
            "company", "department", "created_on", "updated_on",
        ):
            self.assertIsNone(result[key])

    def test_plain_string_reference_fields(self):
        record = dict(FAKE_ASSET)
        record["model"] = "plain-model-string"
        result = _format_asset(record)
        self.assertEqual(result["model"], "plain-model-string")

    def test_reference_with_only_value_key(self):
        record = dict(FAKE_ASSET)
        record["vendor"] = {"value": "vendor002"}
        result = _format_asset(record)
        self.assertEqual(result["vendor"], "vendor002")


class TestListAssets(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("requests.get")
    def test_list_returns_assets(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_ASSET]}
        mock_get.return_value = mock_response

        result = list_assets(self.auth_manager, self.config, {"limit": 10, "offset": 0})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["asset_tag"], "P1000123")

    @patch("requests.get")
    def test_list_with_asset_tag_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_ASSET]}
        mock_get.return_value = mock_response

        result = list_assets(
            self.auth_manager, self.config, {"asset_tag": "P1000123"}
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        params_used = call_kwargs[1].get("params") or call_kwargs[0][1]
        self.assertIn("asset_tag=P1000123", params_used.get("sysparm_query", ""))

    @patch("requests.get")
    def test_list_with_display_name_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_ASSET]}
        mock_get.return_value = mock_response

        result = list_assets(
            self.auth_manager, self.config, {"display_name": "Dell"}
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        params_used = call_kwargs[1].get("params") or call_kwargs[0][1]
        self.assertIn("display_nameLIKEDell", params_used.get("sysparm_query", ""))

    @patch("requests.get")
    def test_list_with_install_status_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_ASSET]}
        mock_get.return_value = mock_response

        result = list_assets(
            self.auth_manager, self.config, {"install_status": "1"}
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        params_used = call_kwargs[1].get("params") or call_kwargs[0][1]
        self.assertIn("install_status=1", params_used.get("sysparm_query", ""))

    @patch("requests.get")
    def test_list_with_assigned_to_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_ASSET]}
        mock_get.return_value = mock_response

        result = list_assets(
            self.auth_manager, self.config, {"assigned_to": "John"}
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        params_used = call_kwargs[1].get("params") or call_kwargs[0][1]
        self.assertIn("assigned_to.nameLIKEJohn", params_used.get("sysparm_query", ""))

    @patch("requests.get")
    def test_list_with_model_category_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_ASSET]}
        mock_get.return_value = mock_response

        result = list_assets(
            self.auth_manager, self.config, {"model_category": "Computer"}
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        params_used = call_kwargs[1].get("params") or call_kwargs[0][1]
        self.assertIn("model_category.nameLIKEComputer", params_used.get("sysparm_query", ""))

    @patch("requests.get")
    def test_list_with_raw_query(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_ASSET]}
        mock_get.return_value = mock_response

        result = list_assets(
            self.auth_manager, self.config, {"query": "company=comp001"}
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        params_used = call_kwargs[1].get("params") or call_kwargs[0][1]
        self.assertIn("company=comp001", params_used.get("sysparm_query", ""))

    @patch("requests.get")
    def test_list_pagination(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_ASSET] * 20}
        mock_get.return_value = mock_response

        result = list_assets(
            self.auth_manager, self.config, {"limit": 20, "offset": 0}
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["has_more"])

    @patch("requests.get")
    def test_list_http_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("connection refused")
        result = list_assets(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])

    def test_list_missing_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer x"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = list_assets(auth, config, {})
        self.assertFalse(result["success"])

    def test_list_missing_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev.service-now.com"
        result = list_assets(auth, config, {})
        self.assertFalse(result["success"])


class TestGetAsset(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("requests.get")
    def test_get_by_sys_id_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": FAKE_ASSET}
        mock_get.return_value = mock_response

        result = get_asset(self.auth_manager, self.config, {"sys_id": "asset001"})
        self.assertTrue(result["success"])
        self.assertEqual(result["asset"]["sys_id"], "asset001")

    @patch("requests.get")
    def test_get_by_asset_tag_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_ASSET]}
        mock_get.return_value = mock_response

        result = get_asset(self.auth_manager, self.config, {"asset_tag": "P1000123"})
        self.assertTrue(result["success"])
        self.assertEqual(result["asset"]["asset_tag"], "P1000123")

    @patch("requests.get")
    def test_get_by_asset_tag_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = get_asset(self.auth_manager, self.config, {"asset_tag": "MISSING"})
        self.assertFalse(result["success"])
        self.assertIn("MISSING", result["message"])

    @patch("requests.get")
    def test_get_by_sys_id_404(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        result = get_asset(self.auth_manager, self.config, {"sys_id": "badid"})
        self.assertFalse(result["success"])
        self.assertIn("badid", result["message"])

    @patch("requests.get")
    def test_get_by_sys_id_empty_result(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {}}
        mock_get.return_value = mock_response

        result = get_asset(self.auth_manager, self.config, {"sys_id": "ghost"})
        self.assertFalse(result["success"])

    def test_get_requires_sys_id_or_asset_tag(self):
        result = get_asset(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("sys_id or asset_tag", result["message"])

    @patch("requests.get")
    def test_get_http_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("timeout")
        result = get_asset(self.auth_manager, self.config, {"sys_id": "asset001"})
        self.assertFalse(result["success"])

    def test_get_missing_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer x"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = get_asset(auth, config, {"sys_id": "x"})
        self.assertFalse(result["success"])

    def test_get_missing_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev.service-now.com"
        result = get_asset(auth, config, {"sys_id": "x"})
        self.assertFalse(result["success"])


class TestUpdateAsset(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("requests.patch")
    def test_update_success(self, mock_patch):
        updated = dict(FAKE_ASSET)
        updated["install_status"] = "3"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": updated}
        mock_patch.return_value = mock_response

        result = update_asset(
            self.auth_manager, self.config,
            {"sys_id": "asset001", "install_status": "3"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["asset"]["install_status"], "3")

    @patch("requests.patch")
    def test_update_404(self, mock_patch):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {}
        mock_patch.return_value = mock_response

        result = update_asset(
            self.auth_manager, self.config,
            {"sys_id": "badid", "display_name": "New Name"}
        )
        self.assertFalse(result["success"])
        self.assertIn("badid", result["message"])

    def test_update_no_fields(self):
        result = update_asset(self.auth_manager, self.config, {"sys_id": "asset001"})
        self.assertFalse(result["success"])
        self.assertIn("No fields", result["message"])

    def test_update_missing_sys_id(self):
        result = update_asset(self.auth_manager, self.config, {"display_name": "X"})
        self.assertFalse(result["success"])

    @patch("requests.patch")
    def test_update_http_error(self, mock_patch):
        mock_patch.side_effect = requests.exceptions.ConnectionError("network error")
        result = update_asset(
            self.auth_manager, self.config,
            {"sys_id": "asset001", "display_name": "New"}
        )
        self.assertFalse(result["success"])

    @patch("requests.patch")
    def test_update_all_optional_fields(self, mock_patch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": FAKE_ASSET}
        mock_patch.return_value = mock_response

        result = update_asset(
            self.auth_manager, self.config,
            {
                "sys_id": "asset001",
                "display_name": "Updated",
                "asset_tag": "P999",
                "serial_number": "SN-NEW",
                "install_status": "4",
                "substatus": "pending_install",
                "cost": "999.00",
                "cost_currency": "EUR",
                "purchase_date": "2026-01-01",
                "warranty_expiration": "2029-01-01",
                "lease_id": "LEASE-001",
                "vendor": "vendor002",
                "acquisition_method": "lease",
                "assigned_to": "user005",
                "owned_by": "user006",
                "managed_by": "user007",
                "location": "loc002",
                "company": "comp002",
                "department": "dept002",
            }
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_patch.call_args
        body = call_kwargs[1].get("json") or call_kwargs[0][1]
        self.assertEqual(body["display_name"], "Updated")
        self.assertEqual(body["install_status"], "4")
        self.assertEqual(body["acquisition_method"], "lease")

    def test_update_missing_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer x"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = update_asset(auth, config, {"sys_id": "x", "display_name": "Y"})
        self.assertFalse(result["success"])

    def test_update_missing_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev.service-now.com"
        result = update_asset(auth, config, {"sys_id": "x", "display_name": "Y"})
        self.assertFalse(result["success"])


class TestParamModels(unittest.TestCase):
    def test_list_assets_defaults(self):
        p = ListAssetsParams()
        self.assertEqual(p.limit, 20)
        self.assertEqual(p.offset, 0)
        self.assertIsNone(p.asset_tag)

    def test_get_asset_both_none(self):
        p = GetAssetParams()
        self.assertIsNone(p.sys_id)
        self.assertIsNone(p.asset_tag)

    def test_update_asset_requires_sys_id(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            UpdateAssetParams()


if __name__ == "__main__":
    unittest.main()
