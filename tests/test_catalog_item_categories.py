"""Tests for list_catalog_item_categories tool (sc_cat_item_category table)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.catalog_tools import (
    ListCatalogItemCategoriesParams,
    _format_item_category_link,
    list_catalog_item_categories,
)

INSTANCE_URL = "https://instance.service-now.com"
ITEM_SYS_ID = "a" * 32
CATEGORY_SYS_ID = "b" * 32
LINK_SYS_ID = "c" * 32


@pytest.fixture
def auth_manager():
    am = MagicMock()
    am.get_headers.return_value = {"Authorization": "Bearer token"}
    am.config = MagicMock()
    am.config.instance_url = INSTANCE_URL
    return am


@pytest.fixture
def config():
    cfg = MagicMock()
    cfg.instance_url = INSTANCE_URL
    return cfg


RAW_LINK = {
    "sys_id": LINK_SYS_ID,
    "sc_cat_item": {"value": ITEM_SYS_ID, "display_value": "Laptop Request"},
    "sc_category": {"value": CATEGORY_SYS_ID, "display_value": "Hardware"},
}


# ---------------------------------------------------------------------------
# _format_item_category_link
# ---------------------------------------------------------------------------

class TestFormatItemCategoryLink:
    def test_standard_record(self):
        result = _format_item_category_link(RAW_LINK)
        assert result["sys_id"] == LINK_SYS_ID
        assert result["catalog_item_id"] == ITEM_SYS_ID
        assert result["catalog_item_name"] == "Laptop Request"
        assert result["category_id"] == CATEGORY_SYS_ID
        assert result["category_name"] == "Hardware"

    def test_plain_string_fields(self):
        record = {
            "sys_id": LINK_SYS_ID,
            "sc_cat_item": ITEM_SYS_ID,
            "sc_category": CATEGORY_SYS_ID,
        }
        result = _format_item_category_link(record)
        assert result["catalog_item_id"] == ITEM_SYS_ID
        assert result["catalog_item_name"] is None
        assert result["category_id"] == CATEGORY_SYS_ID
        assert result["category_name"] is None

    def test_missing_fields(self):
        result = _format_item_category_link({})
        assert result["sys_id"] is None
        assert result["catalog_item_id"] is None
        assert result["category_id"] is None

    def test_dict_with_only_value(self):
        record = {
            "sys_id": LINK_SYS_ID,
            "sc_cat_item": {"value": ITEM_SYS_ID},
            "sc_category": {"value": CATEGORY_SYS_ID},
        }
        result = _format_item_category_link(record)
        assert result["catalog_item_id"] == ITEM_SYS_ID
        assert result["catalog_item_name"] is None
        assert result["category_id"] == CATEGORY_SYS_ID
        assert result["category_name"] is None


# ---------------------------------------------------------------------------
# ListCatalogItemCategoriesParams
# ---------------------------------------------------------------------------

class TestListCatalogItemCategoriesParams:
    def test_defaults(self):
        p = ListCatalogItemCategoriesParams()
        assert p.limit == 20
        assert p.offset == 0
        assert p.catalog_item_id is None
        assert p.category_id is None

    def test_with_filters(self):
        p = ListCatalogItemCategoriesParams(
            catalog_item_id=ITEM_SYS_ID,
            category_id=CATEGORY_SYS_ID,
            limit=5,
            offset=10,
        )
        assert p.catalog_item_id == ITEM_SYS_ID
        assert p.category_id == CATEGORY_SYS_ID
        assert p.limit == 5
        assert p.offset == 10


# ---------------------------------------------------------------------------
# list_catalog_item_categories
# ---------------------------------------------------------------------------

class TestListCatalogItemCategories:
    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_success_no_filters(self, mock_req, auth_manager, config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_LINK]}
        mock_resp.raise_for_status.return_value = None
        mock_req.return_value = mock_resp

        result = list_catalog_item_categories(auth_manager, config, {})

        assert result["success"] is True
        assert len(result["links"]) == 1
        assert result["links"][0]["sys_id"] == LINK_SYS_ID
        assert result["links"][0]["catalog_item_name"] == "Laptop Request"
        assert result["links"][0]["category_name"] == "Hardware"

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_filter_by_catalog_item(self, mock_req, auth_manager, config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_LINK]}
        mock_resp.raise_for_status.return_value = None
        mock_req.return_value = mock_resp

        result = list_catalog_item_categories(
            auth_manager, config, {"catalog_item_id": ITEM_SYS_ID}
        )

        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert f"sc_cat_item={ITEM_SYS_ID}" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_filter_by_category(self, mock_req, auth_manager, config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_LINK]}
        mock_resp.raise_for_status.return_value = None
        mock_req.return_value = mock_resp

        result = list_catalog_item_categories(
            auth_manager, config, {"category_id": CATEGORY_SYS_ID}
        )

        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert f"sc_category={CATEGORY_SYS_ID}" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_filter_both(self, mock_req, auth_manager, config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_LINK]}
        mock_resp.raise_for_status.return_value = None
        mock_req.return_value = mock_resp

        result = list_catalog_item_categories(
            auth_manager,
            config,
            {"catalog_item_id": ITEM_SYS_ID, "category_id": CATEGORY_SYS_ID},
        )

        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        q = call_params.get("sysparm_query", "")
        assert f"sc_cat_item={ITEM_SYS_ID}" in q
        assert f"sc_category={CATEGORY_SYS_ID}" in q

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_empty_result(self, mock_req, auth_manager, config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_resp.raise_for_status.return_value = None
        mock_req.return_value = mock_resp

        result = list_catalog_item_categories(auth_manager, config, {})

        assert result["success"] is True
        assert result["links"] == []
        assert result["count"] == 0

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_pagination(self, mock_req, auth_manager, config):
        links = [
            {**RAW_LINK, "sys_id": f"link_{i}"}
            for i in range(5)
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": links}
        mock_resp.raise_for_status.return_value = None
        mock_req.return_value = mock_resp

        result = list_catalog_item_categories(
            auth_manager, config, {"limit": 5, "offset": 0}
        )

        assert result["success"] is True
        assert result["count"] == 5

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_has_more(self, mock_req, auth_manager, config):
        links = [
            {**RAW_LINK, "sys_id": f"link_{i}"}
            for i in range(3)
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": links}
        mock_resp.raise_for_status.return_value = None
        mock_req.return_value = mock_resp

        result = list_catalog_item_categories(
            auth_manager, config, {"limit": 3, "offset": 0}
        )

        assert result["has_more"] is True
        assert result["next_offset"] == 3

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_http_error(self, mock_req, auth_manager, config):
        import requests as req_lib

        mock_req.side_effect = req_lib.exceptions.HTTPError("404 Not Found")

        result = list_catalog_item_categories(auth_manager, config, {})

        assert result["success"] is False
        assert "Error listing catalog item categories" in result["message"]

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_connection_error(self, mock_req, auth_manager, config):
        import requests as req_lib

        mock_req.side_effect = req_lib.exceptions.ConnectionError("Network unreachable")

        result = list_catalog_item_categories(auth_manager, config, {})

        assert result["success"] is False

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_url_contains_sc_cat_item_category(self, mock_req, auth_manager, config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_resp.raise_for_status.return_value = None
        mock_req.return_value = mock_resp

        list_catalog_item_categories(auth_manager, config, {})

        call_url = mock_req.call_args[0][1]
        assert "sc_cat_item_category" in call_url

    def test_no_instance_url(self, config):
        am = MagicMock()
        am.get_headers.return_value = {"Authorization": "Bearer token"}
        am.config = None
        config.instance_url = None

        result = list_catalog_item_categories(am, config, {})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.catalog_tools._get_headers", return_value=None)
    def test_no_headers(self, mock_get_headers, auth_manager, config):
        result = list_catalog_item_categories(auth_manager, config, {})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_fields_param_set(self, mock_req, auth_manager, config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_resp.raise_for_status.return_value = None
        mock_req.return_value = mock_resp

        list_catalog_item_categories(auth_manager, config, {})

        call_params = mock_req.call_args[1]["params"]
        fields = call_params.get("sysparm_fields", "")
        assert "sys_id" in fields
        assert "sc_cat_item" in fields
        assert "sc_category" in fields
