"""Tests for get_catalog_category tool."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.catalog_tools import (
    GetCatalogCategoryParams,
    get_catalog_category,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig
from pydantic import ValidationError

FAKE_CATEGORY = {
    "sys_id": "cat_001",
    "title": "Hardware",
    "description": "Hardware requests",
    "parent": "",
    "icon": "",
    "active": "true",
    "order": "100",
    "full_description": "",
    "header_icon": "",
    "homepage_renderer": "",
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


class TestGetCatalogCategoryParams(unittest.TestCase):
    def test_required_field(self):
        p = GetCatalogCategoryParams(category_id="cat_001")
        self.assertEqual(p.category_id, "cat_001")

    def test_missing_field_raises(self):
        with self.assertRaises(ValidationError):
            GetCatalogCategoryParams()


class TestGetCatalogCategory(unittest.TestCase):
    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_success_returns_category(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_CATEGORY})
        result = get_catalog_category(
            _make_config(), _make_auth(), GetCatalogCategoryParams(category_id="cat_001")
        )
        self.assertTrue(result.success)
        self.assertIn("Hardware", result.message)
        self.assertEqual(result.data["sys_id"], "cat_001")
        self.assertEqual(result.data["title"], "Hardware")
        self.assertEqual(result.data["active"], "true")

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_404_returns_not_found(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        result = get_catalog_category(
            _make_config(), _make_auth(), GetCatalogCategoryParams(category_id="missing")
        )
        self.assertFalse(result.success)
        self.assertIn("missing", result.message)
        self.assertIsNone(result.data)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_empty_result_returns_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_catalog_category(
            _make_config(), _make_auth(), GetCatalogCategoryParams(category_id="cat_001")
        )
        self.assertFalse(result.success)
        self.assertIn("cat_001", result.message)
        self.assertIsNone(result.data)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_network_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = get_catalog_category(
            _make_config(), _make_auth(), GetCatalogCategoryParams(category_id="cat_001")
        )
        self.assertFalse(result.success)
        self.assertIn("Error getting catalog category", result.message)
        self.assertIsNone(result.data)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_includes_extra_fields(self, mock_req):
        category = dict(FAKE_CATEGORY)
        category["full_description"] = "Extended desc"
        category["header_icon"] = "icon.png"
        category["homepage_renderer"] = "renderer_001"
        mock_req.return_value = _make_response(200, {"result": category})
        result = get_catalog_category(
            _make_config(), _make_auth(), GetCatalogCategoryParams(category_id="cat_001")
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data["full_description"], "Extended desc")
        self.assertEqual(result.data["header_icon"], "icon.png")
        self.assertEqual(result.data["homepage_renderer"], "renderer_001")

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_correct_url_called(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_CATEGORY})
        get_catalog_category(
            _make_config(), _make_auth(), GetCatalogCategoryParams(category_id="cat_001")
        )
        call_args = mock_req.call_args
        self.assertIn("sc_category/cat_001", call_args[0][1])

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_display_value_params_sent(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_CATEGORY})
        get_catalog_category(
            _make_config(), _make_auth(), GetCatalogCategoryParams(category_id="cat_001")
        )
        call_kwargs = mock_req.call_args[1]
        self.assertEqual(call_kwargs["params"]["sysparm_display_value"], "true")
        self.assertEqual(call_kwargs["params"]["sysparm_exclude_reference_link"], "true")

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        http_err = requests.exceptions.HTTPError("500 Server Error")
        resp = _make_response(500)
        resp.raise_for_status.side_effect = http_err
        mock_req.return_value = resp
        result = get_catalog_category(
            _make_config(), _make_auth(), GetCatalogCategoryParams(category_id="cat_001")
        )
        self.assertFalse(result.success)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_inactive_category_returned(self, mock_req):
        category = dict(FAKE_CATEGORY)
        category["active"] = "false"
        mock_req.return_value = _make_response(200, {"result": category})
        result = get_catalog_category(
            _make_config(), _make_auth(), GetCatalogCategoryParams(category_id="cat_001")
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data["active"], "false")

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_parent_field_included(self, mock_req):
        category = dict(FAKE_CATEGORY)
        category["parent"] = "parent_cat_001"
        mock_req.return_value = _make_response(200, {"result": category})
        result = get_catalog_category(
            _make_config(), _make_auth(), GetCatalogCategoryParams(category_id="cat_001")
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data["parent"], "parent_cat_001")


if __name__ == "__main__":
    unittest.main()
