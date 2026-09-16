"""Tests for location_tools.py (cmn_location table)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.location_tools import (
    CreateLocationParams,
    DeleteLocationParams,
    GetLocationParams,
    ListLocationsParams,
    UpdateLocationParams,
    _build_location_query,
    _format_location,
    _resolve_location_sys_id,
    create_location,
    delete_location,
    get_location,
    list_locations,
    update_location,
)

# ---------------------------------------------------------------------------
# Constants / fixtures
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://instance.service-now.com"
LOCATION_SYS_ID = "a" * 32


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


RAW_LOCATION = {
    "sys_id": LOCATION_SYS_ID,
    "name": "New York Office",
    "full_name": "New York Office",
    "street": "123 Main St",
    "city": "New York",
    "state": "NY",
    "country": "US",
    "zip": "10001",
    "phone": "+1-212-555-0100",
    "fax": "+1-212-555-0101",
    "latitude": "40.7128",
    "longitude": "-74.0060",
    "parent": {"display_value": "North America", "value": "parent_sys_id"},
    "company": {"display_value": "Acme Corp", "value": "company_sys_id"},
    "contact": {"display_value": "Jane Doe", "value": "contact_sys_id"},
    "time_zone": "America/New_York",
    "sys_created_on": "2025-01-01 09:00:00",
    "sys_updated_on": "2025-06-15 12:00:00",
    "sys_created_by": "admin",
}


# ---------------------------------------------------------------------------
# _format_location
# ---------------------------------------------------------------------------


def test_format_location_basic():
    """Scalar fields are passed through and reference fields normalised."""
    result = _format_location(RAW_LOCATION)
    assert result["sys_id"] == LOCATION_SYS_ID
    assert result["name"] == "New York Office"
    assert result["street"] == "123 Main St"
    assert result["city"] == "New York"
    assert result["state"] == "NY"
    assert result["country"] == "US"
    assert result["zip"] == "10001"
    assert result["phone"] == "+1-212-555-0100"
    assert result["fax"] == "+1-212-555-0101"
    assert result["latitude"] == "40.7128"
    assert result["longitude"] == "-74.0060"
    assert result["time_zone"] == "America/New_York"
    assert result["parent"] == "North America"
    assert result["company"] == "Acme Corp"
    assert result["contact"] == "Jane Doe"
    assert result["created_on"] == "2025-01-01 09:00:00"
    assert result["updated_on"] == "2025-06-15 12:00:00"
    assert result["created_by"] == "admin"


def test_format_location_missing_fields():
    """Missing fields return None without error."""
    result = _format_location({})
    assert result["sys_id"] is None
    assert result["name"] is None
    assert result["city"] is None
    assert result["parent"] is None


def test_format_location_scalar_ref():
    """Plain string reference fields are passed through unchanged."""
    record = dict(RAW_LOCATION)
    record["parent"] = "plain_parent"
    result = _format_location(record)
    assert result["parent"] == "plain_parent"


def test_format_location_value_fallback():
    """When display_value is absent, the value key is used."""
    record = dict(RAW_LOCATION)
    record["company"] = {"value": "co_sys_id"}
    result = _format_location(record)
    assert result["company"] == "co_sys_id"


# ---------------------------------------------------------------------------
# _build_location_query
# ---------------------------------------------------------------------------


def test_build_query_empty():
    params = ListLocationsParams()
    assert _build_location_query(params) == ""


def test_build_query_name():
    params = ListLocationsParams(name="York")
    assert _build_location_query(params) == "nameLIKEYork"


def test_build_query_city():
    params = ListLocationsParams(city="London")
    assert _build_location_query(params) == "cityLIKELondon"


def test_build_query_country():
    params = ListLocationsParams(country="US")
    assert _build_location_query(params) == "countryLIKEUS"


def test_build_query_company():
    params = ListLocationsParams(company="Acme")
    assert _build_location_query(params) == "companyLIKEAcme"


def test_build_query_combined():
    params = ListLocationsParams(name="Office", city="New York", country="US")
    result = _build_location_query(params)
    assert "nameLIKEOffice" in result
    assert "cityLIKENew York" in result
    assert "countryLIKEUS" in result


def test_build_query_raw():
    params = ListLocationsParams(query="active=true")
    assert _build_location_query(params) == "active=true"


# ---------------------------------------------------------------------------
# _resolve_location_sys_id
# ---------------------------------------------------------------------------


def test_resolve_sys_id_passthrough():
    """A 32-char hex string is returned as-is without an HTTP call."""
    headers = {}
    result = _resolve_location_sys_id(INSTANCE_URL, headers, LOCATION_SYS_ID)
    assert result == LOCATION_SYS_ID


def test_resolve_name_lookup_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"sys_id": LOCATION_SYS_ID}]}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=mock_resp):
        result = _resolve_location_sys_id(INSTANCE_URL, {}, "New York Office")
    assert result == LOCATION_SYS_ID


def test_resolve_name_lookup_not_found():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=mock_resp):
        result = _resolve_location_sys_id(INSTANCE_URL, {}, "Nonexistent Location")
    assert result is None


def test_resolve_request_exception():
    import requests as req_mod
    with patch("servicenow_mcp.tools.location_tools.requests.get", side_effect=req_mod.RequestException("err")):
        result = _resolve_location_sys_id(INSTANCE_URL, {}, "Some Name")
    assert result is None


# ---------------------------------------------------------------------------
# list_locations
# ---------------------------------------------------------------------------


def test_list_locations_success(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_LOCATION]}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=mock_resp):
        result = list_locations(config, auth_manager, ListLocationsParams())
    assert result["count"] == 1
    assert result["records"][0]["name"] == "New York Office"
    assert result["has_more"] is False
    assert result["next_offset"] is None


def test_list_locations_pagination(config, auth_manager):
    records = [RAW_LOCATION] * 20
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": records}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=mock_resp):
        result = list_locations(config, auth_manager, ListLocationsParams(limit=20, offset=0))
    assert result["has_more"] is True
    assert result["next_offset"] == 20


def test_list_locations_with_filters(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=mock_resp) as mock_get:
        list_locations(config, auth_manager, ListLocationsParams(name="Office", city="NY"))
    call_params = mock_get.call_args.kwargs.get("params", mock_get.call_args[1].get("params", {}))
    assert "sysparm_query" in call_params
    assert "nameLIKEOffice" in call_params["sysparm_query"]


def test_list_locations_http_error(config, auth_manager):
    import requests as req_mod
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    http_err = req_mod.HTTPError(response=mock_resp)
    mock_resp.raise_for_status.side_effect = http_err
    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=mock_resp):
        result = list_locations(config, auth_manager, ListLocationsParams())
    assert "error" in result


def test_list_locations_request_exception(config, auth_manager):
    import requests as req_mod
    with patch("servicenow_mcp.tools.location_tools.requests.get", side_effect=req_mod.RequestException("timeout")):
        result = list_locations(config, auth_manager, ListLocationsParams())
    assert "error" in result
    assert "Request failed" in result["error"]


# ---------------------------------------------------------------------------
# get_location
# ---------------------------------------------------------------------------


def test_get_location_by_sys_id(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_LOCATION}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=mock_resp):
        result = get_location(config, auth_manager, GetLocationParams(location_id=LOCATION_SYS_ID))
    assert "location" in result
    assert result["location"]["sys_id"] == LOCATION_SYS_ID


def test_get_location_by_name(config, auth_manager):
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": LOCATION_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    detail_resp = MagicMock()
    detail_resp.status_code = 200
    detail_resp.json.return_value = {"result": RAW_LOCATION}
    detail_resp.raise_for_status.return_value = None

    with patch("servicenow_mcp.tools.location_tools.requests.get", side_effect=[resolve_resp, detail_resp]):
        result = get_location(config, auth_manager, GetLocationParams(location_id="New York Office"))
    assert "location" in result
    assert result["location"]["name"] == "New York Office"


def test_get_location_not_found_by_name(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=mock_resp):
        result = get_location(config, auth_manager, GetLocationParams(location_id="Unknown"))
    assert "error" in result
    assert "not found" in result["error"]


def test_get_location_404(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=mock_resp):
        result = get_location(config, auth_manager, GetLocationParams(location_id=LOCATION_SYS_ID))
    assert "error" in result
    assert "not found" in result["error"]


def test_get_location_empty_result(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": None}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=mock_resp):
        result = get_location(config, auth_manager, GetLocationParams(location_id=LOCATION_SYS_ID))
    assert "error" in result


def test_get_location_http_error(config, auth_manager):
    import requests as req_mod
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    http_err = req_mod.HTTPError(response=mock_resp)
    mock_resp.raise_for_status.side_effect = http_err

    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": LOCATION_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    with patch("servicenow_mcp.tools.location_tools.requests.get", side_effect=[resolve_resp, mock_resp]):
        result = get_location(config, auth_manager, GetLocationParams(location_id="Any Name"))
    assert "error" in result


def test_get_location_request_exception(config, auth_manager):
    import requests as req_mod

    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": LOCATION_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    with patch(
        "servicenow_mcp.tools.location_tools.requests.get",
        side_effect=[resolve_resp, req_mod.RequestException("conn err")],
    ):
        result = get_location(config, auth_manager, GetLocationParams(location_id="Any Name"))
    assert "error" in result
    assert "Request failed" in result["error"]


# ---------------------------------------------------------------------------
# create_location
# ---------------------------------------------------------------------------


def test_create_location_minimal(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": {**RAW_LOCATION, "sys_id": LOCATION_SYS_ID}}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.post", return_value=mock_resp):
        result = create_location(config, auth_manager, CreateLocationParams(name="New York Office"))
    assert "location" in result
    assert result["location"]["name"] == "New York Office"


def test_create_location_all_fields(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": RAW_LOCATION}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.post", return_value=mock_resp) as mock_post:
        create_location(
            config,
            auth_manager,
            CreateLocationParams(
                name="Boston Office",
                street="1 Main St",
                city="Boston",
                state="MA",
                country="US",
                zip="02101",
                phone="617-555-0100",
                fax="617-555-0101",
                latitude="42.36",
                longitude="-71.06",
                time_zone="America/New_York",
                parent="parent_sys_id",
                company="company_sys_id",
                contact="contact_sys_id",
            ),
        )
    body = mock_post.call_args.kwargs.get("json", mock_post.call_args[1].get("json", {}))
    assert body["name"] == "Boston Office"
    assert body["city"] == "Boston"
    assert body["time_zone"] == "America/New_York"
    assert body["parent"] == "parent_sys_id"


def test_create_location_http_error(config, auth_manager):
    import requests as req_mod
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    http_err = req_mod.HTTPError(response=mock_resp)
    mock_resp.raise_for_status.side_effect = http_err
    with patch("servicenow_mcp.tools.location_tools.requests.post", return_value=mock_resp):
        result = create_location(config, auth_manager, CreateLocationParams(name="Bad Location"))
    assert "error" in result


def test_create_location_request_exception(config, auth_manager):
    import requests as req_mod
    with patch(
        "servicenow_mcp.tools.location_tools.requests.post",
        side_effect=req_mod.RequestException("timeout"),
    ):
        result = create_location(config, auth_manager, CreateLocationParams(name="Timeout Location"))
    assert "error" in result
    assert "Request failed" in result["error"]


# ---------------------------------------------------------------------------
# update_location
# ---------------------------------------------------------------------------


def test_update_location_success(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": {**RAW_LOCATION, "city": "Newark"}}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.patch", return_value=mock_resp):
        result = update_location(
            config,
            auth_manager,
            UpdateLocationParams(location_id=LOCATION_SYS_ID, city="Newark"),
        )
    assert "location" in result
    assert result["location"]["city"] == "Newark"


def test_update_location_all_optional_fields(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_LOCATION}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.patch", return_value=mock_resp) as mock_patch:
        update_location(
            config,
            auth_manager,
            UpdateLocationParams(
                location_id=LOCATION_SYS_ID,
                name="Updated HQ",
                street="2 Main St",
                city="Boston",
                state="MA",
                country="US",
                zip="02102",
                phone="617-555-9999",
                fax="617-555-8888",
                latitude="42.37",
                longitude="-71.07",
                time_zone="America/Chicago",
                parent="new_parent",
                company="new_company",
                contact="new_contact",
            ),
        )
    body = mock_patch.call_args.kwargs.get("json", mock_patch.call_args[1].get("json", {}))
    assert body["name"] == "Updated HQ"
    assert body["time_zone"] == "America/Chicago"
    assert body["contact"] == "new_contact"


def test_update_location_no_fields(config, auth_manager):
    result = update_location(
        config, auth_manager, UpdateLocationParams(location_id=LOCATION_SYS_ID)
    )
    assert "error" in result
    assert "No fields" in result["error"]


def test_update_location_not_found_by_name(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=mock_resp):
        result = update_location(
            config, auth_manager, UpdateLocationParams(location_id="Ghost Location", city="X")
        )
    assert "error" in result
    assert "not found" in result["error"]


def test_update_location_404_on_patch(config, auth_manager):
    import requests as req_mod
    patch_resp = MagicMock()
    patch_resp.status_code = 404
    patch_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.patch", return_value=patch_resp):
        result = update_location(
            config,
            auth_manager,
            UpdateLocationParams(location_id=LOCATION_SYS_ID, city="Anywhere"),
        )
    assert "error" in result
    assert "not found" in result["error"]


def test_update_location_http_error(config, auth_manager):
    import requests as req_mod
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    http_err = req_mod.HTTPError(response=mock_resp)
    mock_resp.raise_for_status.side_effect = http_err
    with patch("servicenow_mcp.tools.location_tools.requests.patch", return_value=mock_resp):
        result = update_location(
            config, auth_manager, UpdateLocationParams(location_id=LOCATION_SYS_ID, city="X")
        )
    assert "error" in result


def test_update_location_request_exception(config, auth_manager):
    import requests as req_mod
    with patch(
        "servicenow_mcp.tools.location_tools.requests.patch",
        side_effect=req_mod.RequestException("conn err"),
    ):
        result = update_location(
            config, auth_manager, UpdateLocationParams(location_id=LOCATION_SYS_ID, city="X")
        )
    assert "error" in result
    assert "Request failed" in result["error"]


# ---------------------------------------------------------------------------
# delete_location
# ---------------------------------------------------------------------------


def test_delete_location_success(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.delete", return_value=mock_resp):
        result = delete_location(
            config, auth_manager, DeleteLocationParams(location_id=LOCATION_SYS_ID)
        )
    assert result.get("success") is True
    assert LOCATION_SYS_ID in result["message"]


def test_delete_location_by_name(config, auth_manager):
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": LOCATION_SYS_ID}]}
    resolve_resp.raise_for_status.return_value = None

    del_resp = MagicMock()
    del_resp.status_code = 204
    del_resp.raise_for_status.return_value = None

    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=resolve_resp), \
         patch("servicenow_mcp.tools.location_tools.requests.delete", return_value=del_resp):
        result = delete_location(
            config, auth_manager, DeleteLocationParams(location_id="New York Office")
        )
    assert result.get("success") is True


def test_delete_location_not_found_by_name(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.get", return_value=mock_resp):
        result = delete_location(
            config, auth_manager, DeleteLocationParams(location_id="Ghost Location")
        )
    assert "error" in result
    assert "not found" in result["error"]


def test_delete_location_404_on_delete(config, auth_manager):
    del_resp = MagicMock()
    del_resp.status_code = 404
    del_resp.raise_for_status.return_value = None
    with patch("servicenow_mcp.tools.location_tools.requests.delete", return_value=del_resp):
        result = delete_location(
            config, auth_manager, DeleteLocationParams(location_id=LOCATION_SYS_ID)
        )
    assert "error" in result
    assert "not found" in result["error"]


def test_delete_location_http_error(config, auth_manager):
    import requests as req_mod
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    http_err = req_mod.HTTPError(response=mock_resp)
    mock_resp.raise_for_status.side_effect = http_err
    with patch("servicenow_mcp.tools.location_tools.requests.delete", return_value=mock_resp):
        result = delete_location(
            config, auth_manager, DeleteLocationParams(location_id=LOCATION_SYS_ID)
        )
    assert "error" in result


def test_delete_location_request_exception(config, auth_manager):
    import requests as req_mod
    with patch(
        "servicenow_mcp.tools.location_tools.requests.delete",
        side_effect=req_mod.RequestException("network err"),
    ):
        result = delete_location(
            config, auth_manager, DeleteLocationParams(location_id=LOCATION_SYS_ID)
        )
    assert "error" in result
    assert "Request failed" in result["error"]
