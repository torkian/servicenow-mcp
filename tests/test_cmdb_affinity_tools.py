"""Tests for cmdb_affinity_tools.py (cmdb_ci_affinity table)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.cmdb_affinity_tools import (
    CreateCIAffinityParams,
    DeleteCIAffinityParams,
    GetCIAffinityParams,
    ListCIAffinitiesParams,
    UpdateCIAffinityParams,
    _format_affinity,
    create_ci_affinity,
    delete_ci_affinity,
    get_ci_affinity,
    list_ci_affinities,
    update_ci_affinity,
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


# ---------------------------------------------------------------------------
# create_ci_affinity — success paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.post")
def test_create_ci_affinity_minimal(mock_post, config, auth_manager):
    """Creates a record with only the required name field."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"result": dict(RAW_AFFINITY, name="New Rule")}
    mock_post.return_value = mock_resp

    params = CreateCIAffinityParams(name="New Rule")
    result = create_ci_affinity(config, auth_manager, params)

    assert "affinity" in result
    assert result["affinity"]["name"] == "New Rule"
    body = mock_post.call_args[1]["json"]
    assert body["name"] == "New Rule"
    assert "type" not in body


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.post")
def test_create_ci_affinity_all_fields(mock_post, config, auth_manager):
    """All optional fields are included in the POST body when provided."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"result": RAW_AFFINITY}
    mock_post.return_value = mock_resp

    params = CreateCIAffinityParams(
        name="Web Tier Affinity",
        affinity_type="affinity",
        active=True,
        description="Keep web servers together",
        scope="scope_sys_id_123",
        condition="sys_class_name=cmdb_ci_web_server",
    )
    result = create_ci_affinity(config, auth_manager, params)

    assert "affinity" in result
    body = mock_post.call_args[1]["json"]
    assert body["name"] == "Web Tier Affinity"
    assert body["type"] == "affinity"
    assert body["active"] == "true"
    assert body["description"] == "Keep web servers together"
    assert body["scope"] == "scope_sys_id_123"
    assert body["condition"] == "sys_class_name=cmdb_ci_web_server"


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.post")
def test_create_ci_affinity_active_false(mock_post, config, auth_manager):
    """active=False is serialised as the string 'false'."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"result": RAW_AFFINITY}
    mock_post.return_value = mock_resp

    params = CreateCIAffinityParams(name="Inactive Rule", active=False)
    create_ci_affinity(config, auth_manager, params)

    body = mock_post.call_args[1]["json"]
    assert body["active"] == "false"


# ---------------------------------------------------------------------------
# create_ci_affinity — error paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.post")
def test_create_ci_affinity_http_error(mock_post, config, auth_manager):
    """HTTP errors are caught and returned as error dict."""
    import requests

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
    mock_post.return_value = mock_resp

    params = CreateCIAffinityParams(name="Bad Rule")
    result = create_ci_affinity(config, auth_manager, params)

    assert "error" in result


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.post")
def test_create_ci_affinity_request_exception(mock_post, config, auth_manager):
    """Network errors are caught and returned as error dict."""
    import requests

    mock_post.side_effect = requests.RequestException("connection reset")

    params = CreateCIAffinityParams(name="Offline Rule")
    result = create_ci_affinity(config, auth_manager, params)

    assert "error" in result
    assert "connection reset" in result["error"]


# ---------------------------------------------------------------------------
# update_ci_affinity — success paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.patch")
def test_update_ci_affinity_name(mock_patch, config, auth_manager):
    """Updating only the name sends correct PATCH body."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": dict(RAW_AFFINITY, name="Renamed Rule")}
    mock_patch.return_value = mock_resp

    params = UpdateCIAffinityParams(sys_id=AFFINITY_SYS_ID, name="Renamed Rule")
    result = update_ci_affinity(config, auth_manager, params)

    assert "affinity" in result
    body = mock_patch.call_args[1]["json"]
    assert body == {"name": "Renamed Rule"}


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.patch")
def test_update_ci_affinity_all_fields(mock_patch, config, auth_manager):
    """All optional fields are sent when provided."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_AFFINITY}
    mock_patch.return_value = mock_resp

    params = UpdateCIAffinityParams(
        sys_id=AFFINITY_SYS_ID,
        name="Updated Name",
        affinity_type="anti_affinity",
        active=False,
        description="Updated desc",
        scope="new_scope_id",
        condition="sys_class_name=cmdb_ci_db_instance",
    )
    update_ci_affinity(config, auth_manager, params)

    body = mock_patch.call_args[1]["json"]
    assert body["name"] == "Updated Name"
    assert body["type"] == "anti_affinity"
    assert body["active"] == "false"
    assert body["description"] == "Updated desc"
    assert body["scope"] == "new_scope_id"
    assert body["condition"] == "sys_class_name=cmdb_ci_db_instance"


# ---------------------------------------------------------------------------
# update_ci_affinity — error paths
# ---------------------------------------------------------------------------


def test_update_ci_affinity_no_fields(config, auth_manager):
    """Returns error when no updatable fields are supplied."""
    params = UpdateCIAffinityParams(sys_id=AFFINITY_SYS_ID)
    result = update_ci_affinity(config, auth_manager, params)

    assert "error" in result
    assert "No fields" in result["error"]


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.patch")
def test_update_ci_affinity_404(mock_patch, config, auth_manager):
    """Returns structured error when the server returns 404."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_patch.return_value = mock_resp

    params = UpdateCIAffinityParams(sys_id=AFFINITY_SYS_ID, name="Ghost")
    result = update_ci_affinity(config, auth_manager, params)

    assert "error" in result
    assert AFFINITY_SYS_ID in result["error"]


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.patch")
def test_update_ci_affinity_http_error(mock_patch, config, auth_manager):
    """HTTP errors are caught and returned as error dict."""
    import requests

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
    mock_patch.return_value = mock_resp

    params = UpdateCIAffinityParams(sys_id=AFFINITY_SYS_ID, name="Fail")
    result = update_ci_affinity(config, auth_manager, params)

    assert "error" in result


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.patch")
def test_update_ci_affinity_request_exception(mock_patch, config, auth_manager):
    """Network errors are caught and returned as error dict."""
    import requests

    mock_patch.side_effect = requests.RequestException("network down")

    params = UpdateCIAffinityParams(sys_id=AFFINITY_SYS_ID, name="Offline")
    result = update_ci_affinity(config, auth_manager, params)

    assert "error" in result
    assert "network down" in result["error"]


# ---------------------------------------------------------------------------
# delete_ci_affinity — success paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.delete")
def test_delete_ci_affinity_success_204(mock_delete, config, auth_manager):
    """Returns success dict on HTTP 204 No Content."""
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_delete.return_value = mock_resp

    params = DeleteCIAffinityParams(sys_id=AFFINITY_SYS_ID)
    result = delete_ci_affinity(config, auth_manager, params)

    assert result["success"] is True
    assert AFFINITY_SYS_ID in result["message"]


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.delete")
def test_delete_ci_affinity_success_200(mock_delete, config, auth_manager):
    """Returns success dict on HTTP 200 as well."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_delete.return_value = mock_resp

    params = DeleteCIAffinityParams(sys_id=AFFINITY_SYS_ID)
    result = delete_ci_affinity(config, auth_manager, params)

    assert result["success"] is True


# ---------------------------------------------------------------------------
# delete_ci_affinity — error paths
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.delete")
def test_delete_ci_affinity_404(mock_delete, config, auth_manager):
    """Returns structured error when the server returns 404."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_delete.return_value = mock_resp

    params = DeleteCIAffinityParams(sys_id=AFFINITY_SYS_ID)
    result = delete_ci_affinity(config, auth_manager, params)

    assert "error" in result
    assert AFFINITY_SYS_ID in result["error"]


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.delete")
def test_delete_ci_affinity_http_error(mock_delete, config, auth_manager):
    """HTTP errors are caught and returned as error dict."""
    import requests

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
    mock_delete.return_value = mock_resp

    params = DeleteCIAffinityParams(sys_id=AFFINITY_SYS_ID)
    result = delete_ci_affinity(config, auth_manager, params)

    assert "error" in result


@patch("servicenow_mcp.tools.cmdb_affinity_tools.requests.delete")
def test_delete_ci_affinity_request_exception(mock_delete, config, auth_manager):
    """Network errors are caught and returned as error dict."""
    import requests

    mock_delete.side_effect = requests.RequestException("socket error")

    params = DeleteCIAffinityParams(sys_id=AFFINITY_SYS_ID)
    result = delete_ci_affinity(config, auth_manager, params)

    assert "error" in result
    assert "socket error" in result["error"]


# ---------------------------------------------------------------------------
# Param model validation
# ---------------------------------------------------------------------------


def test_create_ci_affinity_params_requires_name():
    """Missing name raises a validation error."""
    with pytest.raises(Exception):
        CreateCIAffinityParams()


def test_update_ci_affinity_params_requires_sys_id():
    """Missing sys_id raises a validation error."""
    with pytest.raises(Exception):
        UpdateCIAffinityParams()


def test_delete_ci_affinity_params_requires_sys_id():
    """Missing sys_id raises a validation error."""
    with pytest.raises(Exception):
        DeleteCIAffinityParams()


def test_create_ci_affinity_params_defaults():
    """Optional fields default to None."""
    p = CreateCIAffinityParams(name="Test")
    assert p.affinity_type is None
    assert p.active is None
    assert p.description is None
    assert p.scope is None
    assert p.condition is None


def test_update_ci_affinity_params_defaults():
    """All optional fields default to None."""
    p = UpdateCIAffinityParams(sys_id=AFFINITY_SYS_ID)
    assert p.name is None
    assert p.affinity_type is None
    assert p.active is None
    assert p.description is None
    assert p.scope is None
    assert p.condition is None
