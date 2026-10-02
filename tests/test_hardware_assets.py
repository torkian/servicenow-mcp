"""Tests for list_hardware_assets in asset_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.asset_tools import (
    ListHardwareAssetsParams,
    list_hardware_assets,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_HW_ASSET = {
    "sys_id": "hw001",
    "asset_tag": "HW-001",
    "display_name": "Dell PowerEdge R740",
    "serial_number": "SN12345",
    "model": {"display_value": "PowerEdge R740", "value": "model_hw1"},
    "model_category": {"display_value": "Computer", "value": "cat_hw1"},
    "assigned_to": {"display_value": "Jane Smith", "value": "user_hw1"},
    "assigned": "true",
    "install_status": "1",
    "substatus": "",
    "cost": "5000",
    "cost_currency": "USD",
    "purchase_date": "2023-01-15",
    "warranty_expiration": "2026-01-15",
    "lease_id": "",
    "vendor": {"display_value": "Dell", "value": "vendor_hw1"},
    "acquisition_method": "purchase",
    "owned_by": {"display_value": "IT Dept", "value": "owner_hw1"},
    "managed_by": {"display_value": "IT Dept", "value": "mgr_hw1"},
    "location": {"display_value": "Data Center 1", "value": "loc_hw1"},
    "company": {"display_value": "Acme Corp", "value": "company_hw1"},
    "department": {"display_value": "IT", "value": "dept_hw1"},
    "sys_created_on": "2023-01-15 10:00:00",
    "sys_updated_on": "2024-03-01 08:00:00",
    "cpu_count": "2",
    "cpu_core_count": "16",
    "cpu_manufacturer": "Intel",
    "cpu_name": "Xeon Gold 6226R",
    "cpu_speed": "2900",
    "disk_space": "2048",
    "ram": "65536",
    "os": "RHEL 8",
    "os_version": "8.6",
    "os_service_pack": "",
    "os_domain": "corp.acme.com",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "ip_address": "10.0.1.50",
}


def _make_auth_and_config():
    auth_manager = MagicMock(spec=AuthManager)
    auth_manager.get_headers.return_value = {"Authorization": "Bearer token"}
    auth_manager.instance_url = "https://test.service-now.com"
    auth_cfg = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="user", password="pass"),
    )
    config = ServerConfig(instance_url="https://test.service-now.com", auth=auth_cfg)
    return auth_manager, config


class TestListHardwareAssetsSuccess(unittest.TestCase):
    def setUp(self):
        self.auth_manager, self.config = _make_auth_and_config()

    @patch("requests.get")
    def test_returns_assets_on_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_HW_ASSET]}
        mock_get.return_value = mock_response

        result = list_hardware_assets(self.auth_manager, self.config, {})

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        asset = result["assets"][0]
        self.assertEqual(asset["sys_id"], "hw001")
        self.assertEqual(asset["display_name"], "Dell PowerEdge R740")

    @patch("requests.get")
    def test_hardware_fields_included_in_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_HW_ASSET]}
        mock_get.return_value = mock_response

        result = list_hardware_assets(self.auth_manager, self.config, {})
        asset = result["assets"][0]

        self.assertEqual(asset["cpu_count"], "2")
        self.assertEqual(asset["ram"], "65536")
        self.assertEqual(asset["os"], "RHEL 8")
        self.assertEqual(asset["ip_address"], "10.0.1.50")
        self.assertEqual(asset["mac_address"], "AA:BB:CC:DD:EE:FF")

    @patch("requests.get")
    def test_queries_alm_hardware_table(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_hardware_assets(self.auth_manager, self.config, {})

        call_args = mock_get.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        self.assertIn("alm_hardware", url)

    @patch("requests.get")
    def test_filter_by_display_name(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_hardware_assets(self.auth_manager, self.config, {"display_name": "PowerEdge"})

        params = mock_get.call_args[1]["params"]
        self.assertIn("display_nameLIKEPowerEdge", params["sysparm_query"])

    @patch("requests.get")
    def test_filter_by_asset_tag(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_hardware_assets(self.auth_manager, self.config, {"asset_tag": "HW-001"})

        params = mock_get.call_args[1]["params"]
        self.assertIn("asset_tag=HW-001", params["sysparm_query"])

    @patch("requests.get")
    def test_filter_by_install_status(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_hardware_assets(self.auth_manager, self.config, {"install_status": "1"})

        params = mock_get.call_args[1]["params"]
        self.assertIn("install_status=1", params["sysparm_query"])

    @patch("requests.get")
    def test_filter_by_assigned_to(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_hardware_assets(self.auth_manager, self.config, {"assigned_to": "Jane"})

        params = mock_get.call_args[1]["params"]
        self.assertIn("assigned_to.nameLIKEJane", params["sysparm_query"])

    @patch("requests.get")
    def test_filter_by_os(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_hardware_assets(self.auth_manager, self.config, {"os": "RHEL"})

        params = mock_get.call_args[1]["params"]
        self.assertIn("osLIKERHEL", params["sysparm_query"])

    @patch("requests.get")
    def test_filter_by_ip_address(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_hardware_assets(self.auth_manager, self.config, {"ip_address": "10.0.1"})

        params = mock_get.call_args[1]["params"]
        self.assertIn("ip_addressLIKE10.0.1", params["sysparm_query"])

    @patch("requests.get")
    def test_filter_by_mac_address(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_hardware_assets(self.auth_manager, self.config, {"mac_address": "AA:BB"})

        params = mock_get.call_args[1]["params"]
        self.assertIn("mac_addressLIKEAA:BB", params["sysparm_query"])

    @patch("requests.get")
    def test_raw_query_passthrough(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_hardware_assets(self.auth_manager, self.config, {"query": "location=loc001"})

        params = mock_get.call_args[1]["params"]
        self.assertIn("location=loc001", params["sysparm_query"])

    @patch("requests.get")
    def test_multiple_filters_combined(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_hardware_assets(
            self.auth_manager,
            self.config,
            {"display_name": "PowerEdge", "os": "RHEL", "install_status": "1"},
        )

        params = mock_get.call_args[1]["params"]
        query = params["sysparm_query"]
        self.assertIn("display_nameLIKEPowerEdge", query)
        self.assertIn("osLIKERHEL", query)
        self.assertIn("install_status=1", query)

    @patch("requests.get")
    def test_pagination_fields_set(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_HW_ASSET] * 20}
        mock_get.return_value = mock_response

        result = list_hardware_assets(
            self.auth_manager, self.config, {"limit": 20, "offset": 0}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 20)

    @patch("requests.get")
    def test_empty_result(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = list_hardware_assets(self.auth_manager, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["assets"], [])

    @patch("requests.get")
    def test_http_error_returns_failure(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("connection refused")
        result = list_hardware_assets(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing hardware assets", result["message"])

    def test_no_instance_url_returns_failure(self):
        empty_config = MagicMock()
        empty_config.instance_url = None
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.instance_url = None
        result = list_hardware_assets(auth_manager, empty_config, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers_returns_failure(self):
        self.auth_manager.get_headers.return_value = None
        result = list_hardware_assets(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


class TestListHardwareAssetsParams(unittest.TestCase):
    def test_defaults(self):
        p = ListHardwareAssetsParams()
        self.assertEqual(p.limit, 20)
        self.assertEqual(p.offset, 0)
        self.assertIsNone(p.asset_tag)
        self.assertIsNone(p.display_name)
        self.assertIsNone(p.install_status)
        self.assertIsNone(p.assigned_to)
        self.assertIsNone(p.os)
        self.assertIsNone(p.ip_address)
        self.assertIsNone(p.mac_address)
        self.assertIsNone(p.query)

    def test_custom_values(self):
        p = ListHardwareAssetsParams(
            limit=10,
            offset=5,
            display_name="PowerEdge",
            os="Windows",
            ip_address="192.168.1",
            install_status="1",
        )
        self.assertEqual(p.limit, 10)
        self.assertEqual(p.offset, 5)
        self.assertEqual(p.display_name, "PowerEdge")
        self.assertEqual(p.os, "Windows")
        self.assertEqual(p.ip_address, "192.168.1")
        self.assertEqual(p.install_status, "1")


if __name__ == "__main__":
    unittest.main()
