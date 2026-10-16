"""Tests for portal_tools.py (sp_portal, sc_portal, sp_page tables)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.portal_tools import (
    GetCatalogPortalParams,
    GetPortalPageParams,
    GetServicePortalParams,
    ListCatalogPortalsParams,
    ListPortalPagesParams,
    ListServicePortalsParams,
    _format_sc_portal,
    _format_sp_page,
    _format_sp_portal,
    _resolve_portal_sys_id,
    get_catalog_portal,
    get_portal_page,
    get_service_portal,
    list_catalog_portals,
    list_portal_pages,
    list_service_portals,
)

# ---------------------------------------------------------------------------
# Constants / fixtures
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://instance.service-now.com"
PORTAL_SYS_ID = "a" * 32
PAGE_SYS_ID = "b" * 32


@pytest.fixture
def auth_manager():
    am = MagicMock()
    am.get_headers.return_value = {"Authorization": "Bearer token"}
    return am


@pytest.fixture
def config():
    cfg = MagicMock()
    cfg.instance_url = INSTANCE_URL
    return cfg


RAW_SP_PORTAL = {
    "sys_id": PORTAL_SYS_ID,
    "title": "IT Portal",
    "url_suffix": "it_portal",
    "logo": "logo.png",
    "homepage": {"display_value": "Home Page", "value": PAGE_SYS_ID},
    "login_page": {"display_value": "Login", "value": "c" * 32},
    "theme": {"display_value": "Dark Theme", "value": "d" * 32},
    "css_variables": "--color-primary: #0057a8;",
    "sys_created_on": "2025-01-01 09:00:00",
    "sys_updated_on": "2025-06-15 12:00:00",
    "sys_created_by": "admin",
}

RAW_SC_PORTAL = {
    "sys_id": PORTAL_SYS_ID,
    "title": "Classic Catalog",
    "url_suffix": "classic",
    "logo": "classic_logo.png",
    "catalog": {"display_value": "Service Catalog", "value": "e" * 32},
    "homepage": {"display_value": "Catalog Home", "value": PAGE_SYS_ID},
    "sys_created_on": "2025-02-01 10:00:00",
    "sys_updated_on": "2025-07-01 08:00:00",
    "sys_created_by": "admin",
}

RAW_SP_PAGE = {
    "sys_id": PAGE_SYS_ID,
    "title": "Home Page",
    "id": "index",
    "portal": {"display_value": "IT Portal", "value": PORTAL_SYS_ID},
    "template": {"display_value": "Two Column", "value": "f" * 32},
    "internal": "false",
    "draft": "false",
    "sys_created_on": "2025-01-05 11:00:00",
    "sys_updated_on": "2025-06-20 15:00:00",
    "sys_created_by": "admin",
}


# ---------------------------------------------------------------------------
# _format_sp_portal
# ---------------------------------------------------------------------------


def test_format_sp_portal_basic():
    result = _format_sp_portal(RAW_SP_PORTAL)
    assert result["sys_id"] == PORTAL_SYS_ID
    assert result["title"] == "IT Portal"
    assert result["url_suffix"] == "it_portal"
    assert result["homepage"] == "Home Page"
    assert result["login_page"] == "Login"
    assert result["theme"] == "Dark Theme"
    assert result["css_variables"] == "--color-primary: #0057a8;"
    assert result["created_by"] == "admin"


def test_format_sp_portal_missing_fields():
    result = _format_sp_portal({})
    assert result["sys_id"] is None
    assert result["homepage"] is None
    assert result["theme"] is None


# ---------------------------------------------------------------------------
# _format_sc_portal
# ---------------------------------------------------------------------------


def test_format_sc_portal_basic():
    result = _format_sc_portal(RAW_SC_PORTAL)
    assert result["sys_id"] == PORTAL_SYS_ID
    assert result["title"] == "Classic Catalog"
    assert result["catalog"] == "Service Catalog"
    assert result["homepage"] == "Catalog Home"
    assert result["created_on"] == "2025-02-01 10:00:00"


def test_format_sc_portal_scalar_reference():
    raw = dict(RAW_SC_PORTAL)
    raw["catalog"] = "raw_catalog_id"
    result = _format_sc_portal(raw)
    assert result["catalog"] == "raw_catalog_id"


# ---------------------------------------------------------------------------
# _format_sp_page
# ---------------------------------------------------------------------------


def test_format_sp_page_basic():
    result = _format_sp_page(RAW_SP_PAGE)
    assert result["sys_id"] == PAGE_SYS_ID
    assert result["title"] == "Home Page"
    assert result["page_id"] == "index"
    assert result["portal"] == "IT Portal"
    assert result["template"] == "Two Column"
    assert result["draft"] == "false"


def test_format_sp_page_missing_fields():
    result = _format_sp_page({})
    assert result["sys_id"] is None
    assert result["page_id"] is None
    assert result["portal"] is None


# ---------------------------------------------------------------------------
# _resolve_portal_sys_id
# ---------------------------------------------------------------------------


def test_resolve_portal_sys_id_passthrough():
    """32-char hex string bypasses the HTTP lookup."""
    result = _resolve_portal_sys_id(INSTANCE_URL, {}, "sp_portal", PORTAL_SYS_ID)
    assert result == PORTAL_SYS_ID


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_resolve_portal_sys_id_by_title(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"sys_id": PORTAL_SYS_ID}]}
    mock_get.return_value = mock_resp
    result = _resolve_portal_sys_id(INSTANCE_URL, {}, "sp_portal", "IT Portal")
    assert result == PORTAL_SYS_ID


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_resolve_portal_sys_id_not_found(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp
    result = _resolve_portal_sys_id(INSTANCE_URL, {}, "sp_portal", "Nonexistent")
    assert result is None


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_resolve_portal_sys_id_request_exception(mock_get):
    import requests as req_lib
    mock_get.side_effect = req_lib.RequestException("connection error")
    result = _resolve_portal_sys_id(INSTANCE_URL, {}, "sp_portal", "IT Portal")
    assert result is None


# ---------------------------------------------------------------------------
# list_service_portals
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_service_portals_success(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_SP_PORTAL]}
    mock_get.return_value = mock_resp

    result = list_service_portals(config, auth_manager, ListServicePortalsParams())
    assert result["count"] == 1
    assert result["records"][0]["title"] == "IT Portal"
    assert "error" not in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_service_portals_with_title_filter(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_SP_PORTAL]}
    mock_get.return_value = mock_resp

    result = list_service_portals(
        config, auth_manager, ListServicePortalsParams(title="IT", url_suffix="it_portal")
    )
    assert result["count"] == 1
    call_params = mock_get.call_args[1]["params"]
    assert "titleLIKEIT" in call_params["sysparm_query"]
    assert "url_suffix=it_portal" in call_params["sysparm_query"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_service_portals_raw_query(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    result = list_service_portals(
        config, auth_manager, ListServicePortalsParams(query="active=true")
    )
    assert result["count"] == 0
    call_params = mock_get.call_args[1]["params"]
    assert "active=true" in call_params["sysparm_query"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_service_portals_has_more(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_SP_PORTAL] * 20}
    mock_get.return_value = mock_resp

    result = list_service_portals(
        config, auth_manager, ListServicePortalsParams(limit=20, offset=0)
    )
    assert result["has_more"] is True
    assert result["next_offset"] == 20


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_service_portals_http_error(mock_get, config, auth_manager):
    import requests as req_lib
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_get.return_value = mock_resp
    mock_resp.raise_for_status.side_effect = req_lib.HTTPError(response=mock_resp)

    result = list_service_portals(config, auth_manager, ListServicePortalsParams())
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_service_portals_request_exception(mock_get, config, auth_manager):
    import requests as req_lib
    mock_get.side_effect = req_lib.RequestException("timeout")

    result = list_service_portals(config, auth_manager, ListServicePortalsParams())
    assert "error" in result
    assert "timeout" in result["error"]


# ---------------------------------------------------------------------------
# get_service_portal
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_service_portal_by_sys_id(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_SP_PORTAL}
    mock_get.return_value = mock_resp

    result = get_service_portal(config, auth_manager, GetServicePortalParams(portal_id=PORTAL_SYS_ID))
    assert "portal" in result
    assert result["portal"]["title"] == "IT Portal"


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_service_portal_not_found_resolve(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    result = get_service_portal(config, auth_manager, GetServicePortalParams(portal_id="Missing"))
    assert "error" in result
    assert "not found" in result["error"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_service_portal_404(mock_get, config, auth_manager):
    # First call resolves sys_id (resolve returns PORTAL_SYS_ID)
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": PORTAL_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    # Second call is the actual GET which returns 404
    get_resp = MagicMock()
    get_resp.status_code = 404
    get_resp.raise_for_status.return_value = None

    mock_get.side_effect = [resolve_resp, get_resp]

    result = get_service_portal(config, auth_manager, GetServicePortalParams(portal_id="IT Portal"))
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_service_portal_empty_result(mock_get, config, auth_manager):
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": PORTAL_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json.return_value = {"result": None}
    get_resp.raise_for_status.return_value = None

    mock_get.side_effect = [resolve_resp, get_resp]

    result = get_service_portal(config, auth_manager, GetServicePortalParams(portal_id="IT Portal"))
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_service_portal_request_exception(mock_get, config, auth_manager):
    import requests as req_lib
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": PORTAL_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    mock_get.side_effect = [resolve_resp, req_lib.RequestException("timeout")]

    result = get_service_portal(config, auth_manager, GetServicePortalParams(portal_id="IT Portal"))
    assert "error" in result


# ---------------------------------------------------------------------------
# list_catalog_portals
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_catalog_portals_success(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_SC_PORTAL]}
    mock_get.return_value = mock_resp

    result = list_catalog_portals(config, auth_manager, ListCatalogPortalsParams())
    assert result["count"] == 1
    assert result["records"][0]["catalog"] == "Service Catalog"


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_catalog_portals_filters(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    result = list_catalog_portals(
        config, auth_manager, ListCatalogPortalsParams(title="Classic", url_suffix="classic")
    )
    assert result["count"] == 0
    call_params = mock_get.call_args[1]["params"]
    assert "titleLIKEClassic" in call_params["sysparm_query"]
    assert "url_suffix=classic" in call_params["sysparm_query"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_catalog_portals_raw_query(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    result = list_catalog_portals(
        config, auth_manager, ListCatalogPortalsParams(query="active=true")
    )
    assert result["count"] == 0
    call_params = mock_get.call_args[1]["params"]
    assert "active=true" in call_params["sysparm_query"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_catalog_portals_http_error(mock_get, config, auth_manager):
    import requests as req_lib
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_get.return_value = mock_resp
    mock_resp.raise_for_status.side_effect = req_lib.HTTPError(response=mock_resp)

    result = list_catalog_portals(config, auth_manager, ListCatalogPortalsParams())
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_catalog_portals_request_exception(mock_get, config, auth_manager):
    import requests as req_lib
    mock_get.side_effect = req_lib.RequestException("timeout")

    result = list_catalog_portals(config, auth_manager, ListCatalogPortalsParams())
    assert "error" in result


# ---------------------------------------------------------------------------
# get_catalog_portal
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_catalog_portal_by_sys_id(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_SC_PORTAL}
    mock_get.return_value = mock_resp

    result = get_catalog_portal(config, auth_manager, GetCatalogPortalParams(portal_id=PORTAL_SYS_ID))
    assert "portal" in result
    assert result["portal"]["catalog"] == "Service Catalog"


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_catalog_portal_not_found(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    result = get_catalog_portal(config, auth_manager, GetCatalogPortalParams(portal_id="Missing"))
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_catalog_portal_404(mock_get, config, auth_manager):
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": PORTAL_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    get_resp = MagicMock()
    get_resp.status_code = 404
    get_resp.raise_for_status.return_value = None

    mock_get.side_effect = [resolve_resp, get_resp]

    result = get_catalog_portal(config, auth_manager, GetCatalogPortalParams(portal_id="Classic Catalog"))
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_catalog_portal_empty_result(mock_get, config, auth_manager):
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": PORTAL_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json.return_value = {"result": None}
    get_resp.raise_for_status.return_value = None

    mock_get.side_effect = [resolve_resp, get_resp]

    result = get_catalog_portal(config, auth_manager, GetCatalogPortalParams(portal_id="Classic Catalog"))
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_catalog_portal_request_exception(mock_get, config, auth_manager):
    import requests as req_lib
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": PORTAL_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    mock_get.side_effect = [resolve_resp, req_lib.RequestException("timeout")]

    result = get_catalog_portal(config, auth_manager, GetCatalogPortalParams(portal_id="Classic Catalog"))
    assert "error" in result


# ---------------------------------------------------------------------------
# list_portal_pages
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_portal_pages_success(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_SP_PAGE]}
    mock_get.return_value = mock_resp

    result = list_portal_pages(config, auth_manager, ListPortalPagesParams())
    assert result["count"] == 1
    assert result["records"][0]["page_id"] == "index"


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_portal_pages_with_portal_id(mock_get, config, auth_manager):
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": PORTAL_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    list_resp = MagicMock()
    list_resp.json.return_value = {"result": [RAW_SP_PAGE]}
    list_resp.raise_for_status.return_value = None

    mock_get.side_effect = [resolve_resp, list_resp]

    result = list_portal_pages(
        config, auth_manager, ListPortalPagesParams(portal_id="IT Portal")
    )
    assert result["count"] == 1
    call_params = mock_get.call_args[1]["params"]
    assert f"portal={PORTAL_SYS_ID}" in call_params["sysparm_query"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_portal_pages_portal_not_found(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    result = list_portal_pages(
        config, auth_manager, ListPortalPagesParams(portal_id="Missing Portal")
    )
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_portal_pages_include_drafts(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    list_portal_pages(
        config, auth_manager, ListPortalPagesParams(include_drafts=True)
    )
    call_params = mock_get.call_args[1]["params"]
    # When include_drafts=True, draft=false filter should NOT be in the query
    assert "draft=false" not in call_params.get("sysparm_query", "")


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_portal_pages_exclude_drafts_default(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    list_portal_pages(config, auth_manager, ListPortalPagesParams())
    call_params = mock_get.call_args[1]["params"]
    assert "draft=false" in call_params["sysparm_query"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_portal_pages_raw_query(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    list_portal_pages(
        config, auth_manager, ListPortalPagesParams(query="template.nameLIKETwo")
    )
    call_params = mock_get.call_args[1]["params"]
    assert "template.nameLIKETwo" in call_params["sysparm_query"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_portal_pages_title_and_page_id_filter(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    list_portal_pages(
        config, auth_manager, ListPortalPagesParams(title="Home", page_id="index")
    )
    call_params = mock_get.call_args[1]["params"]
    assert "titleLIKEHome" in call_params["sysparm_query"]
    assert "id=index" in call_params["sysparm_query"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_portal_pages_http_error(mock_get, config, auth_manager):
    import requests as req_lib
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_get.return_value = mock_resp
    mock_resp.raise_for_status.side_effect = req_lib.HTTPError(response=mock_resp)

    result = list_portal_pages(config, auth_manager, ListPortalPagesParams())
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_portal_pages_request_exception(mock_get, config, auth_manager):
    import requests as req_lib
    mock_get.side_effect = req_lib.RequestException("timeout")

    result = list_portal_pages(config, auth_manager, ListPortalPagesParams())
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_list_portal_pages_has_more(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_SP_PAGE] * 20}
    mock_get.return_value = mock_resp

    result = list_portal_pages(
        config, auth_manager, ListPortalPagesParams(limit=20, offset=0)
    )
    assert result["has_more"] is True
    assert result["next_offset"] == 20


# ---------------------------------------------------------------------------
# get_portal_page
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_portal_page_by_sys_id(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_SP_PAGE}
    mock_get.return_value = mock_resp

    result = get_portal_page(config, auth_manager, GetPortalPageParams(page_id=PAGE_SYS_ID))
    assert "page" in result
    assert result["page"]["page_id"] == "index"


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_portal_page_by_sys_id_404(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    result = get_portal_page(config, auth_manager, GetPortalPageParams(page_id=PAGE_SYS_ID))
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_portal_page_by_sys_id_empty_result(mock_get, config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": None}
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    result = get_portal_page(config, auth_manager, GetPortalPageParams(page_id=PAGE_SYS_ID))
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_portal_page_by_url_id(mock_get, config, auth_manager):
    # Lookup by URL id (not a sys_id) — falls back to table query
    list_resp = MagicMock()
    list_resp.json.return_value = {"result": [RAW_SP_PAGE]}
    list_resp.raise_for_status.return_value = None
    mock_get.return_value = list_resp

    result = get_portal_page(config, auth_manager, GetPortalPageParams(page_id="index"))
    assert "page" in result
    assert result["page"]["page_id"] == "index"
    # The first call should query by id=index
    first_call_params = mock_get.call_args_list[0][1]["params"]
    assert "id=index" in first_call_params["sysparm_query"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_portal_page_by_title_fallback(mock_get, config, auth_manager):
    # First query (by id) returns empty; second (by titleLIKE) returns result
    empty_resp = MagicMock()
    empty_resp.json.return_value = {"result": []}
    empty_resp.raise_for_status.return_value = None

    found_resp = MagicMock()
    found_resp.json.return_value = {"result": [RAW_SP_PAGE]}
    found_resp.raise_for_status.return_value = None

    mock_get.side_effect = [empty_resp, found_resp]

    result = get_portal_page(config, auth_manager, GetPortalPageParams(page_id="Home Page"))
    assert "page" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_portal_page_not_found(mock_get, config, auth_manager):
    empty_resp = MagicMock()
    empty_resp.json.return_value = {"result": []}
    empty_resp.raise_for_status.return_value = None
    mock_get.return_value = empty_resp

    result = get_portal_page(config, auth_manager, GetPortalPageParams(page_id="nonexistent"))
    assert "error" in result
    assert "not found" in result["error"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_portal_page_with_portal_id(mock_get, config, auth_manager):
    # With portal_id: first resolves portal, then queries pages
    portal_resolve = MagicMock()
    portal_resolve.json.return_value = {"result": [{"sys_id": PORTAL_SYS_ID}]}
    portal_resolve.raise_for_status.return_value = None

    page_resp = MagicMock()
    page_resp.json.return_value = {"result": [RAW_SP_PAGE]}
    page_resp.raise_for_status.return_value = None

    mock_get.side_effect = [portal_resolve, page_resp]

    result = get_portal_page(
        config, auth_manager, GetPortalPageParams(page_id="index", portal_id="IT Portal")
    )
    assert "page" in result
    # Verify portal was added to query
    second_call_params = mock_get.call_args_list[1][1]["params"]
    assert f"portal={PORTAL_SYS_ID}" in second_call_params["sysparm_query"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_portal_page_portal_not_found(mock_get, config, auth_manager):
    portal_resolve = MagicMock()
    portal_resolve.json.return_value = {"result": []}
    mock_get.return_value = portal_resolve

    result = get_portal_page(
        config, auth_manager, GetPortalPageParams(page_id="index", portal_id="Missing Portal")
    )
    assert "error" in result
    assert "not found" in result["error"]


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_portal_page_http_error_on_sys_id_lookup(mock_get, config, auth_manager):
    import requests as req_lib
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = req_lib.HTTPError(response=mock_resp)
    mock_get.return_value = mock_resp

    result = get_portal_page(config, auth_manager, GetPortalPageParams(page_id=PAGE_SYS_ID))
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_portal_page_request_exception_on_sys_id(mock_get, config, auth_manager):
    import requests as req_lib
    mock_get.side_effect = req_lib.RequestException("timeout")

    result = get_portal_page(config, auth_manager, GetPortalPageParams(page_id=PAGE_SYS_ID))
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_service_portal_http_error_on_get(mock_get, config, auth_manager):
    import requests as req_lib
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": PORTAL_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    error_resp = MagicMock()
    error_resp.status_code = 500
    error_resp.raise_for_status.side_effect = req_lib.HTTPError(response=error_resp)
    mock_get.side_effect = [resolve_resp, error_resp]

    result = get_service_portal(config, auth_manager, GetServicePortalParams(portal_id="IT Portal"))
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_catalog_portal_http_error_on_get(mock_get, config, auth_manager):
    import requests as req_lib
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": PORTAL_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    error_resp = MagicMock()
    error_resp.status_code = 500
    error_resp.raise_for_status.side_effect = req_lib.HTTPError(response=error_resp)
    mock_get.side_effect = [resolve_resp, error_resp]

    result = get_catalog_portal(config, auth_manager, GetCatalogPortalParams(portal_id="Classic Catalog"))
    assert "error" in result


@patch("servicenow_mcp.tools.portal_tools.requests.get")
def test_get_portal_page_request_exception_in_fallback_loop(mock_get, config, auth_manager):
    import requests as req_lib
    # Non-sys_id page_id falls into fallback loop; both calls raise RequestException
    mock_get.side_effect = req_lib.RequestException("network error")

    result = get_portal_page(config, auth_manager, GetPortalPageParams(page_id="some-page"))
    assert "error" in result
    assert "not found" in result["error"]
