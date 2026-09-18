"""Tests for company_tools.py (core_company table)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.company_tools import (
    GetCompanyParams,
    ListCompaniesParams,
    _build_company_query,
    _format_company,
    _resolve_company_sys_id,
    get_company,
    list_companies,
)

# ---------------------------------------------------------------------------
# Constants / fixtures
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://instance.service-now.com"
COMPANY_SYS_ID = "c" * 32


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


RAW_COMPANY = {
    "sys_id": COMPANY_SYS_ID,
    "name": "Acme Corporation",
    "short_description": "Global technology vendor",
    "notes": "Key partner",
    "phone": "+1-555-0100",
    "fax": "+1-555-0101",
    "website": "https://acme.example.com",
    "street": "100 Main St",
    "city": "Springfield",
    "state": "IL",
    "zip": "62701",
    "country": "US",
    "stock_price": "99.50",
    "stock_symbol": "ACME",
    "primary": "false",
    "vendor": "true",
    "customer": "false",
    "manufacturer": "false",
    "parent": {"display_value": "Global Holdings", "value": "parent_sys_id"},
    "sys_created_on": "2024-01-01 08:00:00",
    "sys_updated_on": "2025-06-01 10:00:00",
    "sys_created_by": "admin",
}


# ---------------------------------------------------------------------------
# _format_company
# ---------------------------------------------------------------------------


def test_format_company_basic():
    """Scalar fields are passed through and reference fields normalised."""
    result = _format_company(RAW_COMPANY)
    assert result["sys_id"] == COMPANY_SYS_ID
    assert result["name"] == "Acme Corporation"
    assert result["short_description"] == "Global technology vendor"
    assert result["notes"] == "Key partner"
    assert result["phone"] == "+1-555-0100"
    assert result["fax"] == "+1-555-0101"
    assert result["website"] == "https://acme.example.com"
    assert result["street"] == "100 Main St"
    assert result["city"] == "Springfield"
    assert result["state"] == "IL"
    assert result["zip"] == "62701"
    assert result["country"] == "US"
    assert result["stock_price"] == "99.50"
    assert result["stock_symbol"] == "ACME"
    assert result["vendor"] == "true"
    assert result["customer"] == "false"
    assert result["manufacturer"] == "false"
    assert result["parent"] == "Global Holdings"
    assert result["created_on"] == "2024-01-01 08:00:00"
    assert result["updated_on"] == "2025-06-01 10:00:00"
    assert result["created_by"] == "admin"


def test_format_company_missing_fields():
    """Missing fields return None without error."""
    result = _format_company({})
    assert result["sys_id"] is None
    assert result["name"] is None
    assert result["phone"] is None
    assert result["city"] is None
    assert result["parent"] is None


def test_format_company_scalar_references():
    """Scalar (non-dict) reference values are returned as-is."""
    record = {**RAW_COMPANY, "parent": "plain-string"}
    result = _format_company(record)
    assert result["parent"] == "plain-string"


def test_format_company_ref_fallback_to_value():
    """Reference dicts without display_value fall back to value."""
    record = {**RAW_COMPANY, "parent": {"value": "fallback_id"}}
    result = _format_company(record)
    assert result["parent"] == "fallback_id"


def test_format_company_none_reference():
    """None reference fields are returned as None."""
    record = {**RAW_COMPANY, "parent": None}
    result = _format_company(record)
    assert result["parent"] is None


# ---------------------------------------------------------------------------
# _build_company_query
# ---------------------------------------------------------------------------


def test_build_company_query_empty():
    params = ListCompaniesParams()
    assert _build_company_query(params) == ""


def test_build_company_query_name():
    params = ListCompaniesParams(name="Acme")
    assert _build_company_query(params) == "nameLIKEAcme"


def test_build_company_query_city():
    params = ListCompaniesParams(city="Springfield")
    assert _build_company_query(params) == "cityLIKESpringfield"


def test_build_company_query_country():
    params = ListCompaniesParams(country="US")
    assert _build_company_query(params) == "countryLIKEUS"


def test_build_company_query_vendor_true():
    params = ListCompaniesParams(vendor=True)
    assert _build_company_query(params) == "vendor=true"


def test_build_company_query_vendor_false():
    params = ListCompaniesParams(vendor=False)
    assert _build_company_query(params) == "vendor=false"


def test_build_company_query_customer():
    params = ListCompaniesParams(customer=True)
    assert _build_company_query(params) == "customer=true"


def test_build_company_query_manufacturer():
    params = ListCompaniesParams(manufacturer=True)
    assert _build_company_query(params) == "manufacturer=true"


def test_build_company_query_combined():
    params = ListCompaniesParams(name="Acme", city="Spring", vendor=True)
    q = _build_company_query(params)
    assert "nameLIKEAcme" in q
    assert "cityLIKESpring" in q
    assert "vendor=true" in q
    assert q.count("^") == 2


def test_build_company_query_raw():
    params = ListCompaniesParams(query="active=true")
    assert _build_company_query(params) == "active=true"


def test_build_company_query_name_and_raw():
    params = ListCompaniesParams(name="Acme", query="active=true")
    q = _build_company_query(params)
    assert "nameLIKEAcme" in q
    assert "active=true" in q


# ---------------------------------------------------------------------------
# _resolve_company_sys_id
# ---------------------------------------------------------------------------


def test_resolve_company_sys_id_hex_passthrough():
    """32-char hex string is returned directly without any HTTP call."""
    result = _resolve_company_sys_id(INSTANCE_URL, {}, COMPANY_SYS_ID)
    assert result == COMPANY_SYS_ID


def test_resolve_company_sys_id_name_lookup():
    """Name-based lookup hits the API and returns the first sys_id."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"sys_id": COMPANY_SYS_ID}]}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp) as mock_get:
        result = _resolve_company_sys_id(INSTANCE_URL, {}, "Acme Corporation")
    assert result == COMPANY_SYS_ID
    mock_get.assert_called_once()


def test_resolve_company_sys_id_not_found():
    """Returns None when the name lookup returns no results."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp):
        result = _resolve_company_sys_id(INSTANCE_URL, {}, "Unknown Corp")
    assert result is None


def test_resolve_company_sys_id_request_error():
    """Returns None on network error."""
    import requests as req_lib
    with patch(
        "servicenow_mcp.tools.company_tools.requests.get",
        side_effect=req_lib.RequestException("err"),
    ):
        result = _resolve_company_sys_id(INSTANCE_URL, {}, "Acme Corporation")
    assert result is None


# ---------------------------------------------------------------------------
# list_companies
# ---------------------------------------------------------------------------


def test_list_companies_success(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_COMPANY]}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp):
        result = list_companies(config, auth_manager, ListCompaniesParams())
    assert "records" in result
    assert len(result["records"]) == 1
    assert result["records"][0]["name"] == "Acme Corporation"
    assert result["count"] == 1
    assert result["has_more"] is False
    assert result["next_offset"] is None


def test_list_companies_has_more(config, auth_manager):
    """When result count equals limit, has_more=True and next_offset is set."""
    records = [RAW_COMPANY] * 20
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": records}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp):
        result = list_companies(config, auth_manager, ListCompaniesParams(limit=20, offset=0))
    assert result["has_more"] is True
    assert result["next_offset"] == 20


def test_list_companies_next_offset_with_existing_offset(config, auth_manager):
    """next_offset accumulates correctly when offset is non-zero."""
    records = [RAW_COMPANY] * 10
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": records}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp):
        result = list_companies(config, auth_manager, ListCompaniesParams(limit=10, offset=20))
    assert result["has_more"] is True
    assert result["next_offset"] == 30


def test_list_companies_with_name_filter(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_COMPANY]}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp) as mock_get:
        list_companies(config, auth_manager, ListCompaniesParams(name="Acme"))
    call_kwargs = mock_get.call_args
    assert "nameLIKEAcme" in call_kwargs[1]["params"].get("sysparm_query", "")


def test_list_companies_with_city_filter(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp) as mock_get:
        list_companies(config, auth_manager, ListCompaniesParams(city="Springfield"))
    call_kwargs = mock_get.call_args
    assert "cityLIKESpringfield" in call_kwargs[1]["params"].get("sysparm_query", "")


def test_list_companies_with_vendor_filter(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp) as mock_get:
        list_companies(config, auth_manager, ListCompaniesParams(vendor=True))
    call_kwargs = mock_get.call_args
    assert "vendor=true" in call_kwargs[1]["params"].get("sysparm_query", "")


def test_list_companies_with_customer_filter(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp) as mock_get:
        list_companies(config, auth_manager, ListCompaniesParams(customer=False))
    call_kwargs = mock_get.call_args
    assert "customer=false" in call_kwargs[1]["params"].get("sysparm_query", "")


def test_list_companies_no_query_when_no_filters(config, auth_manager):
    """No sysparm_query parameter when no filters are set."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp) as mock_get:
        list_companies(config, auth_manager, ListCompaniesParams())
    call_kwargs = mock_get.call_args
    assert "sysparm_query" not in call_kwargs[1]["params"]


def test_list_companies_http_error(config, auth_manager):
    import requests as req_lib
    err_resp = MagicMock()
    err_resp.status_code = 500
    exc = req_lib.HTTPError(response=err_resp)
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = exc
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp):
        result = list_companies(config, auth_manager, ListCompaniesParams())
    assert "error" in result
    assert "500" in result["error"]


def test_list_companies_request_exception(config, auth_manager):
    import requests as req_lib
    with patch(
        "servicenow_mcp.tools.company_tools.requests.get",
        side_effect=req_lib.RequestException("connection refused"),
    ):
        result = list_companies(config, auth_manager, ListCompaniesParams())
    assert "error" in result
    assert "Request failed" in result["error"]


def test_list_companies_empty(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp):
        result = list_companies(config, auth_manager, ListCompaniesParams())
    assert result["records"] == []
    assert result["count"] == 0
    assert result["has_more"] is False


# ---------------------------------------------------------------------------
# get_company
# ---------------------------------------------------------------------------


def test_get_company_by_sys_id_success(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_COMPANY}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=mock_resp):
        result = get_company(config, auth_manager, GetCompanyParams(company_id=COMPANY_SYS_ID))
    assert "company" in result
    assert result["company"]["name"] == "Acme Corporation"


def test_get_company_by_name_success(config, auth_manager):
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": COMPANY_SYS_ID}]}
    resolve_resp.raise_for_status = MagicMock()

    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json.return_value = {"result": RAW_COMPANY}
    get_resp.raise_for_status = MagicMock()

    with patch(
        "servicenow_mcp.tools.company_tools.requests.get",
        side_effect=[resolve_resp, get_resp],
    ):
        result = get_company(config, auth_manager, GetCompanyParams(company_id="Acme Corporation"))
    assert "company" in result
    assert result["company"]["sys_id"] == COMPANY_SYS_ID


def test_get_company_not_found_resolve(config, auth_manager):
    """Returns error when name cannot be resolved."""
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": []}
    resolve_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=resolve_resp):
        result = get_company(config, auth_manager, GetCompanyParams(company_id="Unknown Corp"))
    assert "error" in result
    assert "Unknown Corp" in result["error"]


def test_get_company_404(config, auth_manager):
    """404 from the detail endpoint returns an error dict."""
    not_found_resp = MagicMock()
    not_found_resp.status_code = 404
    not_found_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=not_found_resp):
        result = get_company(config, auth_manager, GetCompanyParams(company_id=COMPANY_SYS_ID))
    assert "error" in result


def test_get_company_empty_result(config, auth_manager):
    """Empty result body returns an error dict."""
    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.json.return_value = {"result": None}
    ok_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=ok_resp):
        result = get_company(config, auth_manager, GetCompanyParams(company_id=COMPANY_SYS_ID))
    assert "error" in result


def test_get_company_http_error(config, auth_manager):
    import requests as req_lib
    err_resp = MagicMock()
    err_resp.status_code = 403
    exc = req_lib.HTTPError(response=err_resp)
    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.raise_for_status.side_effect = exc
    with patch("servicenow_mcp.tools.company_tools.requests.get", return_value=ok_resp):
        result = get_company(config, auth_manager, GetCompanyParams(company_id=COMPANY_SYS_ID))
    assert "error" in result
    assert "403" in result["error"]


def test_get_company_request_exception(config, auth_manager):
    import requests as req_lib
    with patch(
        "servicenow_mcp.tools.company_tools.requests.get",
        side_effect=req_lib.RequestException("timeout"),
    ):
        result = get_company(config, auth_manager, GetCompanyParams(company_id=COMPANY_SYS_ID))
    assert "error" in result
    assert "Request failed" in result["error"]
