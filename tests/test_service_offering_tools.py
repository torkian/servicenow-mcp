"""Tests for service_offering_tools.py (service_offering table)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.service_offering_tools import (
    GetServiceOfferingParams,
    ListServiceOfferingsParams,
    _build_service_offering_query,
    _format_service_offering,
    _resolve_service_offering_sys_id,
    get_service_offering,
    list_service_offerings,
)

# ---------------------------------------------------------------------------
# Constants / fixtures
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://instance.service-now.com"
OFFERING_SYS_ID = "a" * 32


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


RAW_OFFERING = {
    "sys_id": OFFERING_SYS_ID,
    "name": "Email Service",
    "short_description": "Corporate email hosting",
    "description": "Full-featured email for employees",
    "state": "operational",
    "price": "0",
    "currency": "USD",
    "availability": "99.9%",
    "business_contact": {"display_value": "Jane Doe", "value": "bc_sys_id"},
    "it_contact": {"display_value": "John Smith", "value": "itc_sys_id"},
    "owned_by": {"display_value": "IT Dept", "value": "owner_sys_id"},
    "managed_by": {"display_value": "Ops Team", "value": "mgr_sys_id"},
    "business_criticality": "3",
    "service_classification": "Business Service",
    "parent": {"display_value": "Communications", "value": "parent_sys_id"},
    "portfolio": {"display_value": "IT Portfolio", "value": "port_sys_id"},
    "version": "2.1",
    "start_date": "2023-01-01",
    "end_date": "",
    "active": "true",
    "sys_created_on": "2023-01-01 08:00:00",
    "sys_updated_on": "2025-09-01 09:00:00",
    "sys_created_by": "admin",
}


# ---------------------------------------------------------------------------
# _format_service_offering
# ---------------------------------------------------------------------------


def test_format_service_offering_basic():
    result = _format_service_offering(RAW_OFFERING)
    assert result["sys_id"] == OFFERING_SYS_ID
    assert result["name"] == "Email Service"
    assert result["short_description"] == "Corporate email hosting"
    assert result["description"] == "Full-featured email for employees"
    assert result["state"] == "operational"
    assert result["price"] == "0"
    assert result["currency"] == "USD"
    assert result["availability"] == "99.9%"
    assert result["version"] == "2.1"
    assert result["active"] == "true"


def test_format_service_offering_reference_fields():
    result = _format_service_offering(RAW_OFFERING)
    assert result["business_contact"] == "Jane Doe"
    assert result["it_contact"] == "John Smith"
    assert result["owned_by"] == "IT Dept"
    assert result["managed_by"] == "Ops Team"
    assert result["parent"] == "Communications"
    assert result["portfolio"] == "IT Portfolio"


def test_format_service_offering_reference_as_string():
    record = {**RAW_OFFERING, "owned_by": "plain_string"}
    result = _format_service_offering(record)
    assert result["owned_by"] == "plain_string"


def test_format_service_offering_missing_fields():
    result = _format_service_offering({})
    assert result["sys_id"] is None
    assert result["name"] is None
    assert result["business_contact"] is None


def test_format_service_offering_ref_value_fallback():
    record = {**RAW_OFFERING, "parent": {"display_value": "", "value": "fallback_id"}}
    result = _format_service_offering(record)
    assert result["parent"] == "fallback_id"


# ---------------------------------------------------------------------------
# _build_service_offering_query
# ---------------------------------------------------------------------------


def test_build_query_empty():
    params = ListServiceOfferingsParams()
    assert _build_service_offering_query(params) == ""


def test_build_query_name():
    params = ListServiceOfferingsParams(name="Email")
    assert "nameLIKEEmail" in _build_service_offering_query(params)


def test_build_query_state():
    params = ListServiceOfferingsParams(state="operational")
    assert "state=operational" in _build_service_offering_query(params)


def test_build_query_active_true():
    params = ListServiceOfferingsParams(active=True)
    assert "active=true" in _build_service_offering_query(params)


def test_build_query_active_false():
    params = ListServiceOfferingsParams(active=False)
    assert "active=false" in _build_service_offering_query(params)


def test_build_query_service_classification():
    params = ListServiceOfferingsParams(service_classification="Business")
    assert "service_classificationLIKEBusiness" in _build_service_offering_query(params)


def test_build_query_raw():
    params = ListServiceOfferingsParams(query="business_criticality=1")
    assert "business_criticality=1" in _build_service_offering_query(params)


def test_build_query_combined():
    params = ListServiceOfferingsParams(name="Mail", state="operational", active=True)
    q = _build_service_offering_query(params)
    assert "nameLIKEMail" in q
    assert "state=operational" in q
    assert "active=true" in q


# ---------------------------------------------------------------------------
# _resolve_service_offering_sys_id
# ---------------------------------------------------------------------------


def test_resolve_passthrough_sys_id():
    result = _resolve_service_offering_sys_id(INSTANCE_URL, {}, OFFERING_SYS_ID)
    assert result == OFFERING_SYS_ID


def test_resolve_by_name_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"sys_id": OFFERING_SYS_ID}]}
    with patch("servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp):
        result = _resolve_service_offering_sys_id(INSTANCE_URL, {}, "Email Service")
    assert result == OFFERING_SYS_ID


def test_resolve_by_name_not_found():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    with patch("servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp):
        result = _resolve_service_offering_sys_id(INSTANCE_URL, {}, "Unknown Offering")
    assert result is None


def test_resolve_request_exception():
    import requests as req_lib
    with patch(
        "servicenow_mcp.tools.service_offering_tools.requests.get",
        side_effect=req_lib.RequestException("network error"),
    ):
        result = _resolve_service_offering_sys_id(INSTANCE_URL, {}, "Some Service")
    assert result is None


# ---------------------------------------------------------------------------
# list_service_offerings
# ---------------------------------------------------------------------------


def test_list_service_offerings_success(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_OFFERING]}
    with patch("servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp):
        result = list_service_offerings(config, auth_manager, ListServiceOfferingsParams())
    assert "records" in result
    assert result["count"] == 1
    assert result["records"][0]["name"] == "Email Service"
    assert result["has_more"] is False
    assert result["next_offset"] is None


def test_list_service_offerings_empty(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    with patch("servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp):
        result = list_service_offerings(config, auth_manager, ListServiceOfferingsParams())
    assert result["count"] == 0
    assert result["has_more"] is False


def test_list_service_offerings_has_more(config, auth_manager):
    records = [RAW_OFFERING] * 20
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": records}
    with patch("servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp):
        result = list_service_offerings(config, auth_manager, ListServiceOfferingsParams(limit=20))
    assert result["has_more"] is True
    assert result["next_offset"] == 20


def test_list_service_offerings_with_offset(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_OFFERING]}
    with patch("servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp):
        result = list_service_offerings(
            config, auth_manager, ListServiceOfferingsParams(limit=20, offset=20)
        )
    assert result["has_more"] is False
    assert result["next_offset"] is None


def test_list_service_offerings_http_error(config, auth_manager):
    import requests as req_lib

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    err = req_lib.HTTPError(response=mock_resp)
    mock_resp.raise_for_status.side_effect = err
    with patch("servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp):
        result = list_service_offerings(config, auth_manager, ListServiceOfferingsParams())
    assert "error" in result
    assert "403" in result["error"]


def test_list_service_offerings_request_exception(config, auth_manager):
    import requests as req_lib

    with patch(
        "servicenow_mcp.tools.service_offering_tools.requests.get",
        side_effect=req_lib.RequestException("timeout"),
    ):
        result = list_service_offerings(config, auth_manager, ListServiceOfferingsParams())
    assert "error" in result
    assert "timeout" in result["error"]


def test_list_service_offerings_name_filter(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_OFFERING]}
    with patch(
        "servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp
    ) as mock_get:
        list_service_offerings(
            config, auth_manager, ListServiceOfferingsParams(name="Email")
        )
    call_params = mock_get.call_args[1]["params"]
    assert "nameLIKEEmail" in call_params.get("sysparm_query", "")


def test_list_service_offerings_state_filter(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    with patch(
        "servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp
    ) as mock_get:
        list_service_offerings(
            config, auth_manager, ListServiceOfferingsParams(state="retired")
        )
    call_params = mock_get.call_args[1]["params"]
    assert "state=retired" in call_params.get("sysparm_query", "")


def test_list_service_offerings_active_filter(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    with patch(
        "servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp
    ) as mock_get:
        list_service_offerings(
            config, auth_manager, ListServiceOfferingsParams(active=False)
        )
    call_params = mock_get.call_args[1]["params"]
    assert "active=false" in call_params.get("sysparm_query", "")


# ---------------------------------------------------------------------------
# get_service_offering
# ---------------------------------------------------------------------------


def test_get_service_offering_by_sys_id(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_OFFERING}
    with patch("servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp):
        result = get_service_offering(
            config, auth_manager, GetServiceOfferingParams(offering_id=OFFERING_SYS_ID)
        )
    assert "service_offering" in result
    assert result["service_offering"]["name"] == "Email Service"


def test_get_service_offering_by_name(config, auth_manager):
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": OFFERING_SYS_ID}]}

    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json.return_value = {"result": RAW_OFFERING}

    with patch(
        "servicenow_mcp.tools.service_offering_tools.requests.get",
        side_effect=[resolve_resp, get_resp],
    ):
        result = get_service_offering(
            config, auth_manager, GetServiceOfferingParams(offering_id="Email Service")
        )
    assert "service_offering" in result


def test_get_service_offering_not_found_resolve(config, auth_manager):
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": []}
    with patch("servicenow_mcp.tools.service_offering_tools.requests.get", return_value=resolve_resp):
        result = get_service_offering(
            config, auth_manager, GetServiceOfferingParams(offering_id="Nonexistent")
        )
    assert "error" in result
    assert "not found" in result["error"]


def test_get_service_offering_404(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp):
        result = get_service_offering(
            config, auth_manager, GetServiceOfferingParams(offering_id=OFFERING_SYS_ID)
        )
    assert "error" in result
    assert "not found" in result["error"]


def test_get_service_offering_empty_result(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": None}
    with patch("servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp):
        result = get_service_offering(
            config, auth_manager, GetServiceOfferingParams(offering_id=OFFERING_SYS_ID)
        )
    assert "error" in result


def test_get_service_offering_http_error(config, auth_manager):
    import requests as req_lib

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    err = req_lib.HTTPError(response=mock_resp)
    mock_resp.raise_for_status.side_effect = err
    with patch("servicenow_mcp.tools.service_offering_tools.requests.get", return_value=mock_resp):
        result = get_service_offering(
            config, auth_manager, GetServiceOfferingParams(offering_id=OFFERING_SYS_ID)
        )
    assert "error" in result
    assert "500" in result["error"]


def test_get_service_offering_request_exception(config, auth_manager):
    import requests as req_lib

    with patch(
        "servicenow_mcp.tools.service_offering_tools.requests.get",
        side_effect=req_lib.RequestException("connection refused"),
    ):
        result = get_service_offering(
            config, auth_manager, GetServiceOfferingParams(offering_id=OFFERING_SYS_ID)
        )
    assert "error" in result
    assert "connection refused" in result["error"]
