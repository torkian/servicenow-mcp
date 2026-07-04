"""Tests for get_ci_class_schema in cmdb_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.cmdb_tools import (
    _format_schema_field,
    get_ci_class_schema,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32

FAKE_FIELD_SERVER = {
    "element": "host_name",
    "column_label": "Host Name",
    "internal_type": "string",
    "mandatory": "false",
    "read_only": "false",
    "max_length": "255",
    "default_value": "",
    "reference": "",
    "active": "true",
}

FAKE_FIELD_MANDATORY = {
    "element": "name",
    "column_label": "Name",
    "internal_type": "string",
    "mandatory": "true",
    "read_only": "false",
    "max_length": "255",
    "default_value": "",
    "reference": "",
    "active": "true",
}

FAKE_FIELD_REFERENCE = {
    "element": "location",
    "column_label": "Location",
    "internal_type": "reference",
    "mandatory": "false",
    "read_only": "false",
    "max_length": "32",
    "default_value": "",
    "reference": {"display_value": "cmn_location", "value": FAKE_SYS_ID},
    "active": "true",
}

FAKE_FIELD_REFERENCE_STR = {
    "element": "company",
    "column_label": "Company",
    "internal_type": "reference",
    "mandatory": "false",
    "read_only": "false",
    "max_length": "32",
    "default_value": "",
    "reference": "core_company",
    "active": "true",
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


def _make_response(status_code, json_data):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


class TestFormatSchemaField(unittest.TestCase):
    """Unit tests for _format_schema_field."""

    def test_plain_string_fields(self):
        result = _format_schema_field(FAKE_FIELD_SERVER)
        self.assertEqual(result["field_name"], "host_name")
        self.assertEqual(result["label"], "Host Name")
        self.assertEqual(result["type"], "string")
        self.assertFalse(result["mandatory"])
        self.assertFalse(result["read_only"])
        self.assertEqual(result["max_length"], "255")
        self.assertIsNone(result["reference_table"])
        self.assertIsNone(result["default_value"])

    def test_mandatory_field(self):
        result = _format_schema_field(FAKE_FIELD_MANDATORY)
        self.assertTrue(result["mandatory"])

    def test_reference_field_dict(self):
        result = _format_schema_field(FAKE_FIELD_REFERENCE)
        self.assertEqual(result["reference_table"], "cmn_location")
        self.assertEqual(result["type"], "reference")

    def test_reference_field_string(self):
        result = _format_schema_field(FAKE_FIELD_REFERENCE_STR)
        self.assertEqual(result["reference_table"], "core_company")

    def test_default_value_empty_becomes_none(self):
        result = _format_schema_field(FAKE_FIELD_SERVER)
        self.assertIsNone(result["default_value"])

    def test_default_value_present(self):
        field = dict(FAKE_FIELD_SERVER, default_value="unknown")
        result = _format_schema_field(field)
        self.assertEqual(result["default_value"], "unknown")


class TestGetCIClassSchema(unittest.TestCase):
    """Integration-style tests for get_ci_class_schema."""

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_basic_success(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": [FAKE_FIELD_MANDATORY, FAKE_FIELD_SERVER]}
        )
        result = get_ci_class_schema(
            self.auth, self.config, {"ci_class": "cmdb_ci_server"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["ci_class"], "cmdb_ci_server")
        self.assertEqual(result["field_count"], 2)
        self.assertIsInstance(result["fields"], list)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_mandatory_sorted_first(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": [FAKE_FIELD_SERVER, FAKE_FIELD_MANDATORY]}
        )
        result = get_ci_class_schema(
            self.auth, self.config, {"ci_class": "cmdb_ci_server"}
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["fields"][0]["mandatory"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_mandatory_only_flag_passed_in_query(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_FIELD_MANDATORY]})
        result = get_ci_class_schema(
            self.auth, self.config, {"ci_class": "cmdb_ci_server", "mandatory_only": True}
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["mandatory_only"])
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"]["sysparm_query"]
        self.assertIn("mandatory=true", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_include_inherited_adds_base_class(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": [FAKE_FIELD_MANDATORY, FAKE_FIELD_SERVER]}
        )
        result = get_ci_class_schema(
            self.auth,
            self.config,
            {"ci_class": "cmdb_ci_server", "include_inherited": True},
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["include_inherited"])
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"]["sysparm_query"]
        self.assertIn("cmdb_ci", query)
        self.assertIn("cmdb_ci_server", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_include_inherited_base_class_not_duplicated(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        get_ci_class_schema(
            self.auth,
            self.config,
            {"ci_class": "cmdb_ci", "include_inherited": True},
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"]["sysparm_query"]
        self.assertEqual(query.count("cmdb_ci"), 1)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = get_ci_class_schema(
            self.auth, self.config, {"ci_class": "cmdb_ci_nonexistent"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["field_count"], 0)
        self.assertEqual(result["fields"], [])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_reference_field_normalised(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_FIELD_REFERENCE]})
        result = get_ci_class_schema(
            self.auth, self.config, {"ci_class": "cmdb_ci_server"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["fields"][0]["reference_table"], "cmn_location")

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_fields_without_element_excluded(self, mock_req):
        blank = dict(FAKE_FIELD_SERVER, element="")
        mock_req.return_value = _make_response(
            200, {"result": [blank, FAKE_FIELD_MANDATORY]}
        )
        result = get_ci_class_schema(
            self.auth, self.config, {"ci_class": "cmdb_ci_server"}
        )
        self.assertEqual(result["field_count"], 1)
        self.assertEqual(result["fields"][0]["field_name"], "name")

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_request_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = get_ci_class_schema(
            self.auth, self.config, {"ci_class": "cmdb_ci_server"}
        )
        self.assertFalse(result["success"])
        self.assertIn("message", result)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_http_error(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = get_ci_class_schema(
            self.auth, self.config, {"ci_class": "cmdb_ci_server"}
        )
        self.assertFalse(result["success"])

    def test_missing_ci_class_returns_error(self):
        result = get_ci_class_schema(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_sysparm_query_contains_active_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        get_ci_class_schema(self.auth, self.config, {"ci_class": "cmdb_ci_server"})
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"]["sysparm_query"]
        self.assertIn("active=true", query)
        self.assertIn("elementISNOTEMPTY", query)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_url_targets_sys_dictionary(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        get_ci_class_schema(self.auth, self.config, {"ci_class": "cmdb_ci_server"})
        call_args = mock_req.call_args
        url = call_args[0][1]
        self.assertIn("sys_dictionary", url)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_fields_list_contains_expected_keys(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_FIELD_MANDATORY]})
        result = get_ci_class_schema(self.auth, self.config, {"ci_class": "cmdb_ci_server"})
        field = result["fields"][0]
        for key in ("field_name", "label", "type", "mandatory", "read_only", "max_length"):
            self.assertIn(key, field)

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_no_instance_url(self, mock_req):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = get_ci_class_schema(auth, config, {"ci_class": "cmdb_ci_server"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.cmdb_tools._make_request")
    def test_multiple_fields_returned(self, mock_req):
        mock_req.return_value = _make_response(
            200,
            {
                "result": [
                    FAKE_FIELD_MANDATORY,
                    FAKE_FIELD_SERVER,
                    FAKE_FIELD_REFERENCE,
                    FAKE_FIELD_REFERENCE_STR,
                ]
            },
        )
        result = get_ci_class_schema(self.auth, self.config, {"ci_class": "cmdb_ci_server"})
        self.assertTrue(result["success"])
        self.assertEqual(result["field_count"], 4)


if __name__ == "__main__":
    unittest.main()
