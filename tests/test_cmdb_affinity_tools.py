"""Tests for cmdb_affinity_tools.py (cmdb_ci_affinity table)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.cmdb_affinity_tools import (
    GetCIAffinityParams,
    ListCIAffinitiesParams,
    _format_affinity,
    get_ci_affinity,
    list_ci_affinities,
)

# ---------------------------------------------------------------------------
# Constants / fixtures
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://instance.service-now.com"
AFFINITY_SYS_ID = "a" * 32


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


RAW_AFFINITY = {
    "sys_id": AFFINITY_SYS_ID,
    "name": "Web Tier Affinity",
    "type": {"display_value": "affinity", "value": "affinity"},
    "active": "true",
    "description": "Keep web servers on the same host",
    "scope": {"display_value": "Global", "value": "global_scope_id"},
    "condition": "sys_class_name=cmdb_ci_web_server",
    "sys_created_on": "2025-01-01 00:00:00",
    "sys_updated_on": "2025-06-01 00:00:00",
    "sys_created_by": "admin",
}


# ---------------------------------------------------------------------------
# _format_affinity
# ---------------------------------------------------------------------------


def test_format_affinity_reference_fields():
    """Dict reference fields are reduced to display_value."""
    result = _format_affinity(RAW_AFFINITY)
    assert result["sys_id"] == AFFINITY_SYS_ID
    assert result["name"] == "Web Tier Affinity"
    assert result["type"] == "affinity"
    assert result["active"] == "true"
    assert result["description"] == "Keep web servers on the same host"
    assert result["scope"] == "Global"
    assert result["condition"] == "sys_class_name=cmdb_ci_web_server"
    assert result["created_on"] == "2025-01-01 00:00:00"
    assert result["updated_on"] == "2025-06-01 00:00:00"
    assert result["created_by"] == "admin"


def test_format_affinity_scalar_type():
    """Plain string type field is passed through unchanged."""
    record = dict(RAW_AFFINITY)
    record["type"] = "anti_affinity"
    result = _format_affinity(record)
    assert result["type"] == "anti_affinity"


def test_format_affinity_missing_fields():
    """Missing fields return None without error."""
    result = _format_affinity({})
    assert result["sys_id"] is None
    assert result["name"] is None
    assert result["type"] is None


# ---------------------------------------------------------------------------
# list_ci_affinities — success paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_list_ci_affinities_no_filters(mock_get, config, auth_manager):
    """Returns paginated list with no filters applied."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": [RAW_AFFINITY]}
    mock_get.return_value = mock_resp

    params = ListCIAffinitiesParams()
    result = list_ci_affinities(config, auth_manager, params)

    assert "records" in result
    assert len(result["records"]) == 1
    assert result["records"][0]["name"] == "Web Tier Affinity"
    assert result["has_more"] is False


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_list_ci_affinities_name_filter(mock_get, config, auth_manager):
    """Name filter is appended to the query string."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    params = ListCIAffinitiesParams(name="Web")
    list_ci_affinities(config, auth_manager, params)

    call_kwargs = mock_get.call_args[1]
    assert "nameLIKEWeb" in call_kwargs["params"]["sysparm_query"]


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_list_ci_affinities_affinity_type_filter(mock_get, config, auth_manager):
    """Affinity type filter adds type= condition."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    params = ListCIAffinitiesParams(affinity_type="anti_affinity")
    list_ci_affinities(config, auth_manager, params)

    call_kwargs = mock_get.call_args[1]
    assert "type=anti_affinity" in call_kwargs["params"]["sysparm_query"]


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_list_ci_affinities_ci_sys_id_filter(mock_get, config, auth_manager):
    """ci_sys_id filter appends cmdb_ci= condition."""
    ci_id = "b" * 32
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    params = ListCIAffinitiesParams(ci_sys_id=ci_id)
    list_ci_affinities(config, auth_manager, params)

    call_kwargs = mock_get.call_args[1]
    assert f"cmdb_ci={ci_id}" in call_kwargs["params"]["sysparm_query"]


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_list_ci_affinities_active_true(mock_get, config, auth_manager):
    """active=True appends active=true condition."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    params = ListCIAffinitiesParams(active=True)
    list_ci_affinities(config, auth_manager, params)

    call_kwargs = mock_get.call_args[1]
    assert "active=true" in call_kwargs["params"]["sysparm_query"]


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_list_ci_affinities_active_false(mock_get, config, auth_manager):
    """active=False appends active=false condition."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    params = ListCIAffinitiesParams(active=False)
    list_ci_affinities(config, auth_manager, params)

    call_kwargs = mock_get.call_args[1]
    assert "active=false" in call_kwargs["params"]["sysparm_query"]


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_list_ci_affinities_raw_query(mock_get, config, auth_manager):
    """Raw query string is appended."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    params = ListCIAffinitiesParams(query="active=true^type=affinity")
    list_ci_affinities(config, auth_manager, params)

    call_kwargs = mock_get.call_args[1]
    assert "active=true^type=affinity" in call_kwargs["params"]["sysparm_query"]


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_list_ci_affinities_pagination(mock_get, config, auth_manager):
    """Pagination offset and limit are forwarded correctly."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    params = ListCIAffinitiesParams(limit=5, offset=10)
    list_ci_affinities(config, auth_manager, params)

    call_kwargs = mock_get.call_args[1]
    assert call_kwargs["params"]["sysparm_limit"] == 5
    assert call_kwargs["params"]["sysparm_offset"] == 10


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_list_ci_affinities_has_more_flag(mock_get, config, auth_manager):
    """has_more is True when result count equals limit."""
    records = [dict(RAW_AFFINITY, sys_id=f"{'a' * 31}{i}") for i in range(5)]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": records}
    mock_get.return_value = mock_resp

    params = ListCIAffinitiesParams(limit=5)
    result = list_ci_affinities(config, auth_manager, params)

    assert result["has_more"] is True
    assert result["next_offset"] == 5


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_list_ci_affinities_no_query_when_no_filters(mock_get, config, auth_manager):
    """sysparm_query is absent when no filters are set."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    params = ListCIAffinitiesParams()
    list_ci_affinities(config, auth_manager, params)

    call_kwargs = mock_get.call_args[1]
    assert "sysparm_query" not in call_kwargs["params"]


# ---------------------------------------------------------------------------
# list_ci_affinities — error paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_list_ci_affinities_http_error(mock_get, config, auth_manager):
    """HTTP errors are caught and returned as error dict."""
    import requests

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
    mock_get.return_value = mock_resp

    params = ListCIAffinitiesParams()
    result = list_ci_affinities(config, auth_manager, params)

    assert "error" in result


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_list_ci_affinities_request_exception(mock_get, config, auth_manager):
    """Network errors are caught and returned as error dict."""
    import requests

    mock_get.side_effect = requests.RequestException("timeout")

    params = ListCIAffinitiesParams()
    result = list_ci_affinities(config, auth_manager, params)

    assert "error" in result
    assert "timeout" in result["error"]


# ---------------------------------------------------------------------------
# get_ci_affinity — success paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_get_ci_affinity_success(mock_get, config, auth_manager):
    """Returns normalised affinity record on success."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_AFFINITY}
    mock_get.return_value = mock_resp

    params = GetCIAffinityParams(sys_id=AFFINITY_SYS_ID)
    result = get_ci_affinity(config, auth_manager, params)

    assert "affinity" in result
    assert result["affinity"]["sys_id"] == AFFINITY_SYS_ID
    assert result["affinity"]["name"] == "Web Tier Affinity"


# ---------------------------------------------------------------------------
# get_ci_affinity — error paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_get_ci_affinity_404(mock_get, config, auth_manager):
    """Returns structured error when the server returns 404."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = {}
    mock_get.return_value = mock_resp

    params = GetCIAffinityParams(sys_id=AFFINITY_SYS_ID)
    result = get_ci_affinity(config, auth_manager, params)

    assert "error" in result
    assert AFFINITY_SYS_ID in result["error"]


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_get_ci_affinity_empty_result(mock_get, config, auth_manager):
    """Returns structured error when result is empty."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": None}
    mock_get.return_value = mock_resp

    params = GetCIAffinityParams(sys_id=AFFINITY_SYS_ID)
    result = get_ci_affinity(config, auth_manager, params)

    assert "error" in result


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_get_ci_affinity_http_error(mock_get, config, auth_manager):
    """HTTP errors are caught and returned as error dict."""
    import requests

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
    mock_get.return_value = mock_resp

    params = GetCIAffinityParams(sys_id=AFFINITY_SYS_ID)
    result = get_ci_affinity(config, auth_manager, params)

    assert "error" in result


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.get")
def test_get_ci_affinity_request_exception(mock_get, config, auth_manager):
    """Network errors are caught and returned as error dict."""
    import requests

    mock_get.side_effect = requests.RequestException("connection refused")

    params = GetCIAffinityParams(sys_id=AFFINITY_SYS_ID)
    result = get_ci_affinity(config, auth_manager, params)

    assert "error" in result
    assert "connection refused" in result["error"]


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_get_ci_affinity_params_requires_sys_id():
    """Missing sys_id raises a validation error."""
    with pytest.raises(Exception):
        GetCIAffinityParams()


def test_list_ci_affinities_params_defaults():
    """Default values are set correctly."""
    p = ListCIAffinitiesParams()
    assert p.limit == 20
    assert p.offset == 0
    assert p.name is None
    assert p.affinity_type is None
    assert p.ci_sys_id is None
    assert p.active is None


def test_list_ci_affinities_combined_filters():
    """Multiple filters build the correct query string."""
    from servicenow_mcp.tools.cmdb_affinity_tools import _build_query

    params = ListCIAffinitiesParams(
        name="Web",
        affinity_type="affinity",
        active=True,
    )
    query = _build_query(params)
    assert "nameLIKEWeb" in query
    assert "type=affinity" in query
    assert "active=true" in query
