"""Tests for list_catalog_items_by_catalog and search_catalog_items tools."""

import unittest
from unittest.mock import MagicMock, patch

import requests
from pydantic import ValidationError

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.catalog_tools import (
    ListCatalogItemsByCatalogParams,
    SearchCatalogItemsParams,
    _resolve_catalog_sys_id,
    list_catalog_items_by_catalog,
    search_catalog_items,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_SYS_ID = "a" * 32  # 32 hex chars — treated as a raw sys_id
FAKE_CATALOG_TITLE = "IT Services"
FAKE_CATALOG_RESULT = {"sys_id": FAKE_SYS_ID, "title": FAKE_CATALOG_TITLE}

ITEM_1 = {
    "sys_id": "item001",
    "name": "Laptop Request",
    "short_description": "Order a new laptop",
    "category": "Hardware",
    "price": "1200",
    "active": "true",
    "order": "100",
    "picture": "",
}
ITEM_2 = {
    "sys_id": "item002",
    "name": "Software License",
    "short_description": "Request a software license",
    "category": "Software",
    "price": "200",
    "active": "true",
    "order": "200",
    "picture": "",
}


def _make_config():
    auth_cfg = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev12345.service-now.com", auth=auth_cfg)


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


# ---------------------------------------------------------------------------
# Params model tests
# ---------------------------------------------------------------------------


class TestListCatalogItemsByCatalogParams(unittest.TestCase):
    def test_defaults(self):
        p = ListCatalogItemsByCatalogParams(catalog_id="cat01")
        self.assertEqual(p.catalog_id, "cat01")
        self.assertEqual(p.limit, 10)
        self.assertEqual(p.offset, 0)
        self.assertTrue(p.active)
        self.assertIsNone(p.category)
        self.assertIsNone(p.query)

    def test_custom_values(self):
        p = ListCatalogItemsByCatalogParams(
            catalog_id="mycat",
            limit=5,
            offset=20,
            category="Hardware",
            active=False,
            query="laptop",
        )
        self.assertEqual(p.limit, 5)
        self.assertEqual(p.offset, 20)
        self.assertEqual(p.category, "Hardware")
        self.assertFalse(p.active)
        self.assertEqual(p.query, "laptop")

    def test_missing_catalog_id_raises(self):
        with self.assertRaises(ValidationError):
            ListCatalogItemsByCatalogParams()


class TestSearchCatalogItemsParams(unittest.TestCase):
    def test_defaults(self):
        p = SearchCatalogItemsParams(query="laptop")
        self.assertEqual(p.query, "laptop")
        self.assertEqual(p.limit, 10)
        self.assertEqual(p.offset, 0)
        self.assertTrue(p.active)

    def test_custom_values(self):
        p = SearchCatalogItemsParams(query="vpn", limit=3, offset=6, active=False)
        self.assertEqual(p.limit, 3)
        self.assertEqual(p.offset, 6)
        self.assertFalse(p.active)

    def test_missing_query_raises(self):
        with self.assertRaises(ValidationError):
            SearchCatalogItemsParams()


# ---------------------------------------------------------------------------
# _resolve_catalog_sys_id tests
# ---------------------------------------------------------------------------


class TestResolveCatalogSysId(unittest.TestCase):
    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_passthrough_when_already_sys_id(self, mock_req):
        """32-hex string should be returned immediately without an HTTP call."""
        result = _resolve_catalog_sys_id(_make_config(), {}, FAKE_SYS_ID)
        self.assertEqual(result, FAKE_SYS_ID)
        mock_req.assert_not_called()

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_name_resolved_to_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_CATALOG_RESULT]})
        result = _resolve_catalog_sys_id(_make_config(), {}, FAKE_CATALOG_TITLE)
        self.assertEqual(result, FAKE_SYS_ID)
        mock_req.assert_called_once()

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_name_not_found_returns_none(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = _resolve_catalog_sys_id(_make_config(), {}, "Nonexistent Catalog")
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_request_error_returns_none(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("network error")
        result = _resolve_catalog_sys_id(_make_config(), {}, "Any Catalog")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# list_catalog_items_by_catalog tests
# ---------------------------------------------------------------------------


class TestListCatalogItemsByCatalog(unittest.TestCase):
    # --- Success paths ---

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_success_with_sys_id(self, mock_req):
        """Passing a 32-hex catalog sys_id should skip the resolver lookup."""
        mock_req.return_value = _make_response(200, {"result": [ITEM_1, ITEM_2]})
        params = ListCatalogItemsByCatalogParams(catalog_id=FAKE_SYS_ID)
        result = list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["name"], "Laptop Request")
        self.assertEqual(result["catalog_sys_id"], FAKE_SYS_ID)
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])
        # Only one HTTP call made (no resolver lookup needed)
        mock_req.assert_called_once()

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_success_with_catalog_title(self, mock_req):
        """Non-hex catalog_id triggers a resolver lookup first."""
        mock_req.side_effect = [
            _make_response(200, {"result": [FAKE_CATALOG_RESULT]}),  # resolver
            _make_response(200, {"result": [ITEM_1]}),               # items
        ]
        params = ListCatalogItemsByCatalogParams(catalog_id=FAKE_CATALOG_TITLE)
        result = list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["catalog_sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = ListCatalogItemsByCatalogParams(catalog_id=FAKE_SYS_ID)
        result = list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertEqual(result["items"], [])
        self.assertEqual(result["total"], 0)
        self.assertFalse(result["has_more"])

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_pagination_has_more(self, mock_req):
        """When limit+1 items come back, has_more should be True."""
        # limit=2 but we get 3 items → has_more=True
        mock_req.return_value = _make_response(200, {"result": [ITEM_1, ITEM_2, ITEM_1]})
        params = ListCatalogItemsByCatalogParams(catalog_id=FAKE_SYS_ID, limit=2)
        result = list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 2)
        self.assertEqual(len(result["items"]), 2)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_active_filter_default_true(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = ListCatalogItemsByCatalogParams(catalog_id=FAKE_SYS_ID)
        list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("active=true", query)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_active_filter_false_not_appended(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = ListCatalogItemsByCatalogParams(catalog_id=FAKE_SYS_ID, active=False)
        list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertNotIn("active=true", query)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_query_filter_applied(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = ListCatalogItemsByCatalogParams(catalog_id=FAKE_SYS_ID, query="laptop")
        list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        _, kwargs = mock_req.call_args
        q = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("nameLIKElaptop", q)
        self.assertIn("short_descriptionLIKElaptop", q)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_category_sys_id_filter(self, mock_req):
        cat_sys_id = "b" * 32
        mock_req.return_value = _make_response(200, {"result": []})
        params = ListCatalogItemsByCatalogParams(catalog_id=FAKE_SYS_ID, category=cat_sys_id)
        list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        _, kwargs = mock_req.call_args
        q = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn(f"category={cat_sys_id}", q)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_category_name_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = ListCatalogItemsByCatalogParams(catalog_id=FAKE_SYS_ID, category="Hardware")
        list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        _, kwargs = mock_req.call_args
        q = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("category.titleLIKEHardware", q)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_catalog_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = ListCatalogItemsByCatalogParams(catalog_id="Unknown Catalog")
        result = list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertEqual(result["items"], [])

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_items_request_network_error(self, mock_req):
        # Resolver succeeds, items call fails
        mock_req.side_effect = [
            _make_response(200, {"result": [FAKE_CATALOG_RESULT]}),
            requests.exceptions.ConnectionError("timeout"),
        ]
        params = ListCatalogItemsByCatalogParams(catalog_id=FAKE_CATALOG_TITLE)
        result = list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Error listing catalog items", result["message"])

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_item_fields_in_response(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [ITEM_1]})
        params = ListCatalogItemsByCatalogParams(catalog_id=FAKE_SYS_ID)
        result = list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        item = result["items"][0]
        for field in ("sys_id", "name", "short_description", "category", "price", "active", "order", "picture"):
            self.assertIn(field, item)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_pagination_metadata_in_response(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [ITEM_1]})
        params = ListCatalogItemsByCatalogParams(catalog_id=FAKE_SYS_ID, limit=5, offset=10)
        result = list_catalog_items_by_catalog(_make_config(), _make_auth(), params)
        self.assertEqual(result["limit"], 5)
        self.assertEqual(result["offset"], 10)
        self.assertIn("has_more", result)
        self.assertIn("next_offset", result)


# ---------------------------------------------------------------------------
# search_catalog_items tests
# ---------------------------------------------------------------------------


class TestSearchCatalogItems(unittest.TestCase):
    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_success_returns_items(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [ITEM_1, ITEM_2]})
        params = SearchCatalogItemsParams(query="request")
        result = search_catalog_items(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["query"], "request")

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = SearchCatalogItemsParams(query="xyzzy")
        result = search_catalog_items(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertEqual(result["items"], [])
        self.assertEqual(result["total"], 0)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_query_sent_as_name_or_description(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = SearchCatalogItemsParams(query="vpn")
        search_catalog_items(_make_config(), _make_auth(), params)
        _, kwargs = mock_req.call_args
        q = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("nameLIKEvpn", q)
        self.assertIn("short_descriptionLIKEvpn", q)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_active_filter_default_true(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = SearchCatalogItemsParams(query="test")
        search_catalog_items(_make_config(), _make_auth(), params)
        _, kwargs = mock_req.call_args
        q = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("active=true", q)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_active_false_not_appended(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = SearchCatalogItemsParams(query="test", active=False)
        search_catalog_items(_make_config(), _make_auth(), params)
        _, kwargs = mock_req.call_args
        q = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertNotIn("active=true", q)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_pagination_has_more(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [ITEM_1, ITEM_2, ITEM_1]})
        params = SearchCatalogItemsParams(query="item", limit=2)
        result = search_catalog_items(_make_config(), _make_auth(), params)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 2)
        self.assertEqual(len(result["items"]), 2)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_pagination_no_more(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [ITEM_1]})
        params = SearchCatalogItemsParams(query="laptop", limit=10)
        result = search_catalog_items(_make_config(), _make_auth(), params)
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_item_fields_in_response(self, mock_req):
        item_with_catalogs = {**ITEM_1, "catalogs": "IT Services", "description": "Full description"}
        mock_req.return_value = _make_response(200, {"result": [item_with_catalogs]})
        params = SearchCatalogItemsParams(query="laptop")
        result = search_catalog_items(_make_config(), _make_auth(), params)
        item = result["items"][0]
        for field in (
            "sys_id", "name", "short_description", "description",
            "category", "catalogs", "price", "active", "order", "picture"
        ):
            self.assertIn(field, item)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_network_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.Timeout("timed out")
        params = SearchCatalogItemsParams(query="laptop")
        result = search_catalog_items(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Error searching catalog items", result["message"])
        self.assertEqual(result["query"], "laptop")
        self.assertEqual(result["items"], [])

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_limit_sent_as_limit_plus_one(self, mock_req):
        """We request limit+1 items to detect has_more."""
        mock_req.return_value = _make_response(200, {"result": []})
        params = SearchCatalogItemsParams(query="test", limit=7)
        search_catalog_items(_make_config(), _make_auth(), params)
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs.get("params", {}).get("sysparm_limit"), 8)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_pagination_metadata_present(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = SearchCatalogItemsParams(query="test", limit=5, offset=15)
        result = search_catalog_items(_make_config(), _make_auth(), params)
        self.assertEqual(result["limit"], 5)
        self.assertEqual(result["offset"], 15)
        self.assertIn("has_more", result)
        self.assertIn("next_offset", result)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        error_resp = _make_response(500)
        error_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_req.return_value = error_resp
        params = SearchCatalogItemsParams(query="fail")
        result = search_catalog_items(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
