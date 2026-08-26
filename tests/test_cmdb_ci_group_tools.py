"""Tests for cmdb_ci_group_tools.py (cmdb_ci_group table)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.cmdb_ci_group_tools import (
    GetCMDBCIGroupParams,
    ListCMDBCIGroupsParams,
    _format_ci_group,
    _build_ci_group_query,
    get_cmdb_ci_group,
    list_cmdb_ci_groups,
)

# ---------------------------------------------------------------------------
# Constants / fixtures
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://instance.service-now.com"
GROUP_SYS_ID = "b" * 32


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


RAW_CI_GROUP = {
    "sys_id": GROUP_SYS_ID,
    "name": "Production Web Servers",
    "type": {"display_value": "manual", "value": "manual"},
    "active": "true",
    "description": "All production web server CIs",
    "manager": {"display_value": "John Admin", "value": "admin_sys_id"},
    "sys_class_name": {"display_value": "CI Group", "value": "cmdb_ci_group"},
    "sys_created_on": "2025-01-15 10:00:00",
    "sys_updated_on": "2025-06-01 08:30:00",
    "sys_created_by": "admin",
}


# ---------------------------------------------------------------------------
# _format_ci_group
# ---------------------------------------------------------------------------


def test_format_ci_group_reference_fields():
    """Dict reference fields are reduced to display_value."""
    result = _format_ci_group(RAW_CI_GROUP)
    assert result["sys_id"] == GROUP_SYS_ID
    assert result["name"] == "Production Web Servers"
    assert result["type"] == "manual"
    assert result["active"] == "true"
    assert result["description"] == "All production web server CIs"
    assert result["manager"] == "John Admin"
    assert result["sys_class_name"] == "CI Group"
    assert result["created_on"] == "2025-01-15 10:00:00"
    assert result["updated_on"] == "2025-06-01 08:30:00"
    assert result["created_by"] == "admin"


def test_format_ci_group_scalar_type():
    """Plain string type field is passed through unchanged."""
    record = dict(RAW_CI_GROUP)
    record["type"] = "dynamic"
    result = _format_ci_group(record)
    assert result["type"] == "dynamic"


def test_format_ci_group_missing_fields():
    """Missing fields return None without error."""
    result = _format_ci_group({})
    assert result["sys_id"] is None
    assert result["name"] is None
    assert result["type"] is None
    assert result["manager"] is None


def test_format_ci_group_value_fallback():
    """When display_value is absent the value key is used."""
    record = dict(RAW_CI_GROUP)
    record["manager"] = {"value": "mgr_sys_id"}
    result = _format_ci_group(record)
    assert result["manager"] == "mgr_sys_id"


# ---------------------------------------------------------------------------
# _build_ci_group_query
# ---------------------------------------------------------------------------


def test_build_query_empty():
    """Empty params produce an empty query string."""
    params = ListCMDBCIGroupsParams()
    assert _build_ci_group_query(params) == ""


def test_build_query_name_filter():
    """name filter uses LIKE operator."""
    params = ListCMDBCIGroupsParams(name="Web")
    query = _build_ci_group_query(params)
    assert "nameLIKEWeb" in query


def test_build_query_group_type_filter():
    """group_type appends an exact match condition."""
    params = ListCMDBCIGroupsParams(group_type="manual")
    query = _build_ci_group_query(params)
    assert "type=manual" in query


def test_build_query_active_true():
    """active=True appends 'active=true'."""
    params = ListCMDBCIGroupsParams(active=True)
    query = _build_ci_group_query(params)
    assert "active=true" in query


def test_build_query_active_false():
    """active=False appends 'active=false'."""
    params = ListCMDBCIGroupsParams(active=False)
    query = _build_ci_group_query(params)
    assert "active=false" in query


def test_build_query_raw_query_passthrough():
    """Raw query string is appended unchanged."""
    params = ListCMDBCIGroupsParams(query="manager=admin_sys_id")
    query = _build_ci_group_query(params)
    assert "manager=admin_sys_id" in query


def test_build_query_combined_filters():
    """Multiple filters are joined with '^'."""
    params = ListCMDBCIGroupsParams(name="Prod", group_type="manual", active=True)
    query = _build_ci_group_query(params)
    assert "nameLIKEProd" in query
    assert "type=manual" in query
    assert "active=true" in query
    parts = query.split("^")
    assert len(parts) == 3


# ---------------------------------------------------------------------------
# list_cmdb_ci_groups — success paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_list_ci_groups_success(mock_get, config, auth_manager):
    """Returns formatted records on HTTP 200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": [RAW_CI_GROUP]}
    mock_get.return_value = mock_resp

    params = ListCMDBCIGroupsParams()
    result = list_cmdb_ci_groups(config, auth_manager, params)

    assert "error" not in result
    assert result["count"] == 1
    assert result["records"][0]["name"] == "Production Web Servers"


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_list_ci_groups_empty(mock_get, config, auth_manager):
    """Empty result set is handled gracefully."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    params = ListCMDBCIGroupsParams()
    result = list_cmdb_ci_groups(config, auth_manager, params)

    assert result["count"] == 0
    assert result["records"] == []
    assert result["has_more"] is False
    assert result["next_offset"] is None


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_list_ci_groups_pagination_has_more(mock_get, config, auth_manager):
    """has_more is True when result count equals limit."""
    records = [dict(RAW_CI_GROUP, sys_id=f"{'c' * 31}{i}") for i in range(5)]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": records}
    mock_get.return_value = mock_resp

    params = ListCMDBCIGroupsParams(limit=5, offset=0)
    result = list_cmdb_ci_groups(config, auth_manager, params)

    assert result["has_more"] is True
    assert result["next_offset"] == 5


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_list_ci_groups_with_name_filter(mock_get, config, auth_manager):
    """Name filter is included in the request params."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    params = ListCMDBCIGroupsParams(name="Production")
    list_cmdb_ci_groups(config, auth_manager, params)

    call_kwargs = mock_get.call_args
    req_params = call_kwargs[1]["params"] if "params" in call_kwargs[1] else call_kwargs[0][1]
    assert "nameLIKEProduction" in req_params.get("sysparm_query", "")


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_list_ci_groups_url_contains_table(mock_get, config, auth_manager):
    """Request URL targets the cmdb_ci_group table."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_get.return_value = mock_resp

    params = ListCMDBCIGroupsParams()
    list_cmdb_ci_groups(config, auth_manager, params)

    called_url = mock_get.call_args[0][0]
    assert "cmdb_ci_group" in called_url


# ---------------------------------------------------------------------------
# list_cmdb_ci_groups — error paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_list_ci_groups_http_error(mock_get, config, auth_manager):
    """HTTP errors are caught and returned as error dict."""
    import requests

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
    mock_get.return_value = mock_resp

    params = ListCMDBCIGroupsParams()
    result = list_cmdb_ci_groups(config, auth_manager, params)

    assert "error" in result


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_list_ci_groups_request_exception(mock_get, config, auth_manager):
    """Network errors are caught and returned as error dict."""
    import requests

    mock_get.side_effect = requests.RequestException("timeout")

    params = ListCMDBCIGroupsParams()
    result = list_cmdb_ci_groups(config, auth_manager, params)

    assert "error" in result
    assert "timeout" in result["error"]


# ---------------------------------------------------------------------------
# get_cmdb_ci_group — success paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_get_ci_group_success(mock_get, config, auth_manager):
    """Returns formatted record under 'ci_group' key on HTTP 200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_CI_GROUP}
    mock_get.return_value = mock_resp

    params = GetCMDBCIGroupParams(sys_id=GROUP_SYS_ID)
    result = get_cmdb_ci_group(config, auth_manager, params)

    assert "error" not in result
    assert "ci_group" in result
    assert result["ci_group"]["sys_id"] == GROUP_SYS_ID
    assert result["ci_group"]["name"] == "Production Web Servers"


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_get_ci_group_url_contains_sys_id(mock_get, config, auth_manager):
    """Request URL includes the sys_id path segment."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_CI_GROUP}
    mock_get.return_value = mock_resp

    params = GetCMDBCIGroupParams(sys_id=GROUP_SYS_ID)
    get_cmdb_ci_group(config, auth_manager, params)

    called_url = mock_get.call_args[0][0]
    assert GROUP_SYS_ID in called_url


# ---------------------------------------------------------------------------
# get_cmdb_ci_group — error paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_get_ci_group_404(mock_get, config, auth_manager):
    """Returns structured error when the server returns 404."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = {}
    mock_get.return_value = mock_resp

    params = GetCMDBCIGroupParams(sys_id=GROUP_SYS_ID)
    result = get_cmdb_ci_group(config, auth_manager, params)

    assert "error" in result
    assert GROUP_SYS_ID in result["error"]


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_get_ci_group_empty_result(mock_get, config, auth_manager):
    """Returns structured error when result is empty."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": None}
    mock_get.return_value = mock_resp

    params = GetCMDBCIGroupParams(sys_id=GROUP_SYS_ID)
    result = get_cmdb_ci_group(config, auth_manager, params)

    assert "error" in result


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_get_ci_group_http_error(mock_get, config, auth_manager):
    """HTTP errors are caught and returned as error dict."""
    import requests

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
    mock_get.return_value = mock_resp

    params = GetCMDBCIGroupParams(sys_id=GROUP_SYS_ID)
    result = get_cmdb_ci_group(config, auth_manager, params)

    assert "error" in result


@patch("servicenow_mcp.tools.cmdb_ci_group_tools.requests.get")
def test_get_ci_group_request_exception(mock_get, config, auth_manager):
    """Network errors are caught and returned as error dict."""
    import requests

    mock_get.side_effect = requests.RequestException("connection refused")

    params = GetCMDBCIGroupParams(sys_id=GROUP_SYS_ID)
    result = get_cmdb_ci_group(config, auth_manager, params)

    assert "error" in result
    assert "connection refused" in result["error"]


# ---------------------------------------------------------------------------
# Param model validation
# ---------------------------------------------------------------------------


def test_get_ci_group_params_requires_sys_id():
    """Missing sys_id raises a validation error."""
    with pytest.raises(Exception):
        GetCMDBCIGroupParams()


def test_list_ci_groups_params_defaults():
    """Default values are set correctly."""
    p = ListCMDBCIGroupsParams()
    assert p.limit == 20
    assert p.offset == 0
    assert p.name is None
    assert p.group_type is None
    assert p.active is None
    assert p.query is None
