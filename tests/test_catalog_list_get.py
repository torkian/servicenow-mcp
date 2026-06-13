"""Tests for list_catalogs and get_catalog tools."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.catalog_tools import (
    GetCatalogParams,
    ListCatalogsParams,
    get_catalog,
    list_catalogs,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig
from pydantic import ValidationError

FAKE_CATALOG = {
    "sys_id": "cat001",
    "title": "Service Catalog",
    "description": "Main service catalog",
    "active": "true",
    "enable_wish_list": "false",
    "managers": "",
    "desktop_image": "",
    "desktop_continue_shopping": "",
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
    return auth


def _make_response(status_code=200, json_body=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.raise_for_status = MagicMock()
    return resp


class TestListCatalogsParams(unittest.TestCase):
    def test_defaults(self):
        p = ListCatalogsParams()
        self.assertEqual(p.limit, 10)
        self.assertEqual(p.offset, 0)
        self.assertTrue(p.active)
        self.assertIsNone(p.query)

    def test_custom_values(self):
        p = ListCatalogsParams(limit=5, offset=10, query="HR", active=False)
        self.assertEqual(p.limit, 5)
        self.assertEqual(p.offset, 10)
        self.assertEqual(p.query, "HR")
        self.assertFalse(p.active)


class TestGetCatalogParams(unittest.TestCase):
    def test_required_field(self):
        p = GetCatalogParams(catalog_id="cat001")
        self.assertEqual(p.catalog_id, "cat001")

    def test_missing_field_raises(self):
        with self.assertRaises(ValidationError):
            GetCatalogParams()


class TestListCatalogs(unittest.TestCase):
    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_success_returns_catalogs(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_CATALOG]})
        result = list_catalogs(_make_config(), _make_auth(), ListCatalogsParams())
        self.assertTrue(result["success"])
        self.assertEqual(len(result["catalogs"]), 1)
        self.assertEqual(result["catalogs"][0]["sys_id"], "cat001")
        self.assertEqual(result["catalogs"][0]["title"], "Service Catalog")
        self.assertIn("total", result)
        self.assertIn("limit", result)
        self.assertIn("offset", result)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_catalogs(_make_config(), _make_auth(), ListCatalogsParams())
        self.assertTrue(result["success"])
        self.assertEqual(result["catalogs"], [])
        self.assertEqual(result["total"], 0)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_active_filter_applied(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_CATALOG]})
        list_catalogs(_make_config(), _make_auth(), ListCatalogsParams(active=True))
        passed_params = mock_req.call_args.kwargs.get("params", mock_req.call_args.args[2] if len(mock_req.call_args.args) > 2 else {})
        self.assertIn("active=true", passed_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_query_filter_applied(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_catalogs(_make_config(), _make_auth(), ListCatalogsParams(active=False, query="HR"))
        passed_params = mock_req.call_args.kwargs.get("params", {})
        self.assertIn("HR", passed_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_network_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_catalogs(_make_config(), _make_auth(), ListCatalogsParams())
        self.assertFalse(result["success"])
        self.assertIn("Error", result["message"])
        self.assertEqual(result["catalogs"], [])

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_multiple_catalogs_returned(self, mock_req):
        second = dict(FAKE_CATALOG, sys_id="cat002", title="HR Catalog")
        mock_req.return_value = _make_response(200, {"result": [FAKE_CATALOG, second]})
        result = list_catalogs(_make_config(), _make_auth(), ListCatalogsParams())
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["catalogs"][1]["title"], "HR Catalog")

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_pagination_params_passed(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_catalogs(_make_config(), _make_auth(), ListCatalogsParams(limit=25, offset=50))
        passed_params = mock_req.call_args.kwargs.get("params", {})
        self.assertEqual(passed_params["sysparm_limit"], 25)
        self.assertEqual(passed_params["sysparm_offset"], 50)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_response_includes_expected_fields(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_CATALOG]})
        result = list_catalogs(_make_config(), _make_auth(), ListCatalogsParams())
        cat = result["catalogs"][0]
        for field in ("sys_id", "title", "description", "active", "enable_wish_list", "managers"):
            self.assertIn(field, cat)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        resp = _make_response(500)
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
        mock_req.return_value = resp
        result = list_catalogs(_make_config(), _make_auth(), ListCatalogsParams())
        self.assertFalse(result["success"])


class TestGetCatalog(unittest.TestCase):
    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_success_returns_catalog(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_CATALOG})
        result = get_catalog(_make_config(), _make_auth(), GetCatalogParams(catalog_id="cat001"))
        self.assertTrue(result.success)
        self.assertEqual(result.data["sys_id"], "cat001")
        self.assertEqual(result.data["title"], "Service Catalog")

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_404_returns_not_found(self, mock_req):
        resp = _make_response(404, {})
        mock_req.return_value = resp
        result = get_catalog(_make_config(), _make_auth(), GetCatalogParams(catalog_id="missing"))
        self.assertFalse(result.success)
        self.assertIn("not found", result.message.lower())
        self.assertIsNone(result.data)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_empty_result_returns_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_catalog(_make_config(), _make_auth(), GetCatalogParams(catalog_id="cat001"))
        self.assertFalse(result.success)
        self.assertIsNone(result.data)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_network_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = get_catalog(_make_config(), _make_auth(), GetCatalogParams(catalog_id="cat001"))
        self.assertFalse(result.success)
        self.assertIn("Error", result.message)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        resp = _make_response(503)
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError("503")
        mock_req.return_value = resp
        result = get_catalog(_make_config(), _make_auth(), GetCatalogParams(catalog_id="cat001"))
        self.assertFalse(result.success)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_response_includes_expected_fields(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_CATALOG})
        result = get_catalog(_make_config(), _make_auth(), GetCatalogParams(catalog_id="cat001"))
        self.assertTrue(result.success)
        for field in ("sys_id", "title", "description", "active",
                      "enable_wish_list", "managers", "desktop_image"):
            self.assertIn(field, result.data)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_correct_url_used(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_CATALOG})
        get_catalog(_make_config(), _make_auth(), GetCatalogParams(catalog_id="cat001"))
        called_url = mock_req.call_args.args[1]
        self.assertIn("sc_catalog/cat001", called_url)


if __name__ == "__main__":
    unittest.main()
