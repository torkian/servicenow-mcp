"""Tests for cmdb_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.cmdb_tools import (
    CreateCIParams,
    GetCIParams,
    ListCIsParams,
    UpdateCIParams,
    _format_ci,
    create_ci,
    get_ci,
    list_cis,
    update_ci,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig
from servicenow_mcp.auth.auth_manager import AuthManager


FAKE_CI = {
    "sys_id": "ci001",
    "name": "web-server-01",
    "sys_class_name": "cmdb_ci_server",
    "category": "Compute",
    "operational_status": "1",
    "environment": "production",
    "short_description": "Primary web server",
    "ip_address": "10.0.0.1",
    "serial_number": "SN123456",
    "asset_tag": "AT-001",
    "install_status": "1",
    "managed_by": "user001",
    "owned_by": "user002",
    "location": "loc001",
    "company": "comp001",
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-04-01 00:00:00",
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


class TestFormatCI(unittest.TestCase):
    def test_all_fields_mapped(self):
        result = _format_ci(FAKE_CI)
        self.assertEqual(result["sys_id"], "ci001")
        self.assertEqual(result["name"], "web-server-01")
        self.assertEqual(result["ci_class"], "cmdb_ci_server")
        self.assertEqual(result["category"], "Compute")
        self.assertEqual(result["operational_status"], "1")
        self.assertEqual(result["environment"], "production")
        self.assertEqual(result["short_description"], "Primary web server")
        self.assertEqual(result["ip_address"], "10.0.0.1")
        self.assertEqual(result["serial_number"], "SN123456")
        self.assertEqual(result["asset_tag"], "AT-001")
        self.assertEqual(result["install_status"], "1")
        self.assertEqual(result["managed_by"], "user001")
        self.assertEqual(result["owned_by"], "user002")
        self.assertEqual(result["location"], "loc001")
        self.assertEqual(result["company"], "comp001")
        self.assertEqual(result["created_on"], "2026-01-01 00:00:00")
        self.assertEqual(result["updated_on"], "2026-04-01 00:00:00")

    def test_missing_fields_return_none(self):
        result = _format_ci({})
        for key in ("sys_id", "name", "ci_class", "category", "operational_status",
                    "environment", "short_description", "ip_address", "serial_number",
                    "asset_tag", "install_status", "managed_by", "owned_by",
                    "location", "company", "created_on", "updated_on"):
            self.assertIsNone(result[key])


class TestListCIs(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("requests.get")
    def test_list_returns_cis(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_CI]}
        mock_get.return_value = mock_response

        result = list_cis(self.auth_manager, self.config, {"limit": 10, "offset": 0})

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["cis"][0]["sys_id"], "ci001")

    @patch("requests.get")
    def test_list_empty_result(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = list_cis(self.auth_manager, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["cis"], [])

    @patch("requests.get")
    def test_list_with_name_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_CI]}
        mock_get.return_value = mock_response

        result = list_cis(self.auth_manager, self.config, {"name": "web-server"})

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("nameLIKEweb-server", query)

    @patch("requests.get")
    def test_list_with_operational_status_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = list_cis(self.auth_manager, self.config, {"operational_status": "1"})

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("operational_status=1", query)

    @patch("requests.get")
    def test_list_with_environment_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = list_cis(self.auth_manager, self.config, {"environment": "production"})

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("environment=production", query)

    @patch("requests.get")
    def test_list_with_raw_query(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = list_cis(self.auth_manager, self.config, {"query": "companyLIKEAcme"})

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("companyLIKEAcme", query)

    @patch("requests.get")
    def test_list_uses_ci_class_table(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_cis(self.auth_manager, self.config, {"ci_class": "cmdb_ci_server"})

        call_url = mock_get.call_args[0][0]
        self.assertIn("cmdb_ci_server", call_url)

    @patch("requests.get")
    def test_list_defaults_to_cmdb_ci_table(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        list_cis(self.auth_manager, self.config, {})

        call_url = mock_get.call_args[0][0]
        self.assertIn("/cmdb_ci", call_url)

    @patch("requests.get")
    def test_list_request_exception(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("timeout")

        result = list_cis(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing CIs", result["message"])

    def test_list_missing_instance_url(self):
        auth_manager = MagicMock()
        del auth_manager.instance_url
        server_config = MagicMock()
        del server_config.instance_url

        result = list_cis(auth_manager, server_config, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_list_missing_headers(self):
        auth_manager = MagicMock()
        auth_manager.instance_url = "https://dev99999.service-now.com"
        del auth_manager.get_headers
        server_config = MagicMock()
        del server_config.instance_url
        del server_config.get_headers

        result = list_cis(auth_manager, server_config, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("requests.get")
    def test_list_pagination_meta(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_CI] * 20}
        mock_get.return_value = mock_response

        result = list_cis(self.auth_manager, self.config, {"limit": 20, "offset": 0})
        self.assertIn("has_more", result)
        self.assertIn("next_offset", result)


class TestGetCI(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("requests.get")
    def test_get_ci_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": FAKE_CI}
        mock_get.return_value = mock_response

        result = get_ci(self.auth_manager, self.config, {"sys_id": "ci001"})

        self.assertTrue(result["success"])
        self.assertEqual(result["ci"]["sys_id"], "ci001")
        self.assertEqual(result["ci"]["name"], "web-server-01")

    @patch("requests.get")
    def test_get_ci_not_found_404(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = get_ci(self.auth_manager, self.config, {"sys_id": "missing"})

        self.assertFalse(result["success"])
        self.assertIn("missing", result["message"])

    @patch("requests.get")
    def test_get_ci_empty_result(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {}}
        mock_get.return_value = mock_response

        result = get_ci(self.auth_manager, self.config, {"sys_id": "ci_empty"})

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("requests.get")
    def test_get_ci_uses_ci_class_table(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": FAKE_CI}
        mock_get.return_value = mock_response

        get_ci(self.auth_manager, self.config, {"sys_id": "ci001", "ci_class": "cmdb_ci_server"})

        call_url = mock_get.call_args[0][0]
        self.assertIn("cmdb_ci_server", call_url)

    @patch("requests.get")
    def test_get_ci_request_exception(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("timeout")

        result = get_ci(self.auth_manager, self.config, {"sys_id": "ci001"})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving CI", result["message"])

    def test_get_ci_missing_sys_id(self):
        result = get_ci(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])

    def test_get_ci_missing_instance_url(self):
        auth_manager = MagicMock()
        del auth_manager.instance_url
        server_config = MagicMock()
        del server_config.instance_url

        result = get_ci(auth_manager, server_config, {"sys_id": "ci001"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])


class TestCreateCI(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("requests.post")
    def test_create_ci_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"result": FAKE_CI}
        mock_post.return_value = mock_response

        result = create_ci(
            self.auth_manager,
            self.config,
            {"name": "web-server-01", "ci_class": "cmdb_ci_server"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "ci001")
        self.assertEqual(result["ci"]["name"], "web-server-01")

    @patch("requests.post")
    def test_create_ci_with_optional_fields(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"result": FAKE_CI}
        mock_post.return_value = mock_response

        result = create_ci(
            self.auth_manager,
            self.config,
            {
                "name": "web-server-01",
                "short_description": "Primary web server",
                "environment": "production",
                "operational_status": "1",
                "ip_address": "10.0.0.1",
                "serial_number": "SN123456",
                "asset_tag": "AT-001",
            },
        )

        self.assertTrue(result["success"])
        body_sent = mock_post.call_args[1]["json"]
        self.assertEqual(body_sent["name"], "web-server-01")
        self.assertEqual(body_sent["environment"], "production")
        self.assertEqual(body_sent["ip_address"], "10.0.0.1")

    @patch("requests.post")
    def test_create_ci_uses_ci_class_table(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"result": FAKE_CI}
        mock_post.return_value = mock_response

        create_ci(
            self.auth_manager,
            self.config,
            {"name": "server-x", "ci_class": "cmdb_ci_server"},
        )

        call_url = mock_post.call_args[0][0]
        self.assertIn("cmdb_ci_server", call_url)

    @patch("requests.post")
    def test_create_ci_defaults_to_cmdb_ci(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"result": FAKE_CI}
        mock_post.return_value = mock_response

        create_ci(self.auth_manager, self.config, {"name": "generic-ci"})

        call_url = mock_post.call_args[0][0]
        self.assertTrue(call_url.endswith("/cmdb_ci"))

    @patch("requests.post")
    def test_create_ci_ci_class_not_in_body(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"result": FAKE_CI}
        mock_post.return_value = mock_response

        create_ci(
            self.auth_manager,
            self.config,
            {"name": "server-x", "ci_class": "cmdb_ci_server"},
        )

        body_sent = mock_post.call_args[1]["json"]
        self.assertNotIn("ci_class", body_sent)

    @patch("requests.post")
    def test_create_ci_request_exception(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("timeout")

        result = create_ci(self.auth_manager, self.config, {"name": "server"})
        self.assertFalse(result["success"])
        self.assertIn("Error creating CI", result["message"])

    def test_create_ci_missing_name(self):
        result = create_ci(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])

    def test_create_ci_missing_instance_url(self):
        auth_manager = MagicMock()
        del auth_manager.instance_url
        server_config = MagicMock()
        del server_config.instance_url

        result = create_ci(auth_manager, server_config, {"name": "ci"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_create_ci_missing_headers(self):
        auth_manager = MagicMock()
        auth_manager.instance_url = "https://dev99999.service-now.com"
        del auth_manager.get_headers
        server_config = MagicMock()
        del server_config.instance_url
        del server_config.get_headers

        result = create_ci(auth_manager, server_config, {"name": "ci"})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


class TestUpdateCI(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("requests.patch")
    def test_update_ci_success(self, mock_patch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": FAKE_CI}
        mock_patch.return_value = mock_response

        result = update_ci(
            self.auth_manager,
            self.config,
            {"sys_id": "ci001", "operational_status": "6"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["ci"]["sys_id"], "ci001")

    @patch("requests.patch")
    def test_update_ci_sends_correct_body(self, mock_patch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": FAKE_CI}
        mock_patch.return_value = mock_response

        update_ci(
            self.auth_manager,
            self.config,
            {"sys_id": "ci001", "environment": "staging", "ip_address": "10.0.0.2"},
        )

        body_sent = mock_patch.call_args[1]["json"]
        self.assertEqual(body_sent["environment"], "staging")
        self.assertEqual(body_sent["ip_address"], "10.0.0.2")
        self.assertNotIn("sys_id", body_sent)
        self.assertNotIn("ci_class", body_sent)

    @patch("requests.patch")
    def test_update_ci_not_found_404(self, mock_patch):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_patch.return_value = mock_response

        result = update_ci(
            self.auth_manager,
            self.config,
            {"sys_id": "missing", "name": "new-name"},
        )

        self.assertFalse(result["success"])
        self.assertIn("missing", result["message"])

    @patch("requests.patch")
    def test_update_ci_uses_ci_class_table(self, mock_patch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": FAKE_CI}
        mock_patch.return_value = mock_response

        update_ci(
            self.auth_manager,
            self.config,
            {"sys_id": "ci001", "ci_class": "cmdb_ci_server", "name": "renamed"},
        )

        call_url = mock_patch.call_args[0][0]
        self.assertIn("cmdb_ci_server", call_url)

    def test_update_ci_no_fields_to_update(self):
        result = update_ci(self.auth_manager, self.config, {"sys_id": "ci001"})
        self.assertFalse(result["success"])
        self.assertIn("No fields", result["message"])

    @patch("requests.patch")
    def test_update_ci_request_exception(self, mock_patch):
        import requests as req
        mock_patch.side_effect = req.exceptions.ConnectionError("timeout")

        result = update_ci(
            self.auth_manager, self.config, {"sys_id": "ci001", "name": "x"}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating CI", result["message"])

    def test_update_ci_missing_sys_id(self):
        result = update_ci(self.auth_manager, self.config, {"name": "x"})
        self.assertFalse(result["success"])

    def test_update_ci_missing_instance_url(self):
        auth_manager = MagicMock()
        del auth_manager.instance_url
        server_config = MagicMock()
        del server_config.instance_url

        result = update_ci(auth_manager, server_config, {"sys_id": "ci001", "name": "x"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])


class TestCMDBParams(unittest.TestCase):
    def test_list_params_defaults(self):
        p = ListCIsParams()
        self.assertEqual(p.limit, 20)
        self.assertEqual(p.offset, 0)
        self.assertIsNone(p.ci_class)
        self.assertIsNone(p.name)
        self.assertIsNone(p.operational_status)
        self.assertIsNone(p.environment)
        self.assertIsNone(p.query)

    def test_get_params_requires_sys_id(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            GetCIParams()

    def test_get_params_valid(self):
        p = GetCIParams(sys_id="ci001")
        self.assertEqual(p.sys_id, "ci001")
        self.assertIsNone(p.ci_class)

    def test_create_params_requires_name(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            CreateCIParams()

    def test_create_params_valid(self):
        p = CreateCIParams(name="server-1", ci_class="cmdb_ci_server")
        self.assertEqual(p.name, "server-1")
        self.assertEqual(p.ci_class, "cmdb_ci_server")

    def test_update_params_requires_sys_id(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            UpdateCIParams()

    def test_update_params_valid(self):
        p = UpdateCIParams(sys_id="ci001", name="renamed")
        self.assertEqual(p.sys_id, "ci001")
        self.assertEqual(p.name, "renamed")


if __name__ == "__main__":
    unittest.main()
