"""Tests for the list_ci_dependency_groups and get_ci_dependency_group tools."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.cmdb_dep_group_tools import (
    GetCIDependencyGroupParams,
    ListCIDependencyGroupsParams,
    get_ci_dependency_group,
    list_ci_dependency_groups,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

_AUTH = AuthConfig(
    type=AuthType.BASIC,
    basic=BasicAuthConfig(username="admin", password="password"),
)


@pytest.fixture
def server_config():
    return ServerConfig(instance_url="https://instance.service-now.com", auth=_AUTH)


@pytest.fixture
def auth_manager():
    mgr = MagicMock(spec=AuthManager)
    mgr.get_headers.return_value = {"Authorization": "Basic dXNlcjpwYXNz"}
    return mgr


def _make_response(status_code: int, json_body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    if status_code >= 400:
        http_err = requests.HTTPError(response=resp)
        resp.raise_for_status.side_effect = http_err
    else:
        resp.raise_for_status = MagicMock()
    return resp


def _make_group_record(sys_id="grp1", name="Group A", group_type="manual", active="true"):
    return {
        "sys_id": sys_id,
        "name": name,
        "type": {"display_value": group_type, "value": group_type},
        "active": active,
        "description": "Test dependency group",
        "manager": {"display_value": "Admin User", "value": "admin_sys_id"},
        "sys_class_name": {"display_value": "CMDB Dependency Group"},
        "sys_created_on": "2024-01-01 00:00:00",
        "sys_updated_on": "2024-06-01 00:00:00",
        "sys_created_by": "admin",
    }


# ---------------------------------------------------------------------------
# list_ci_dependency_groups tests
# ---------------------------------------------------------------------------


class TestListCIDependencyGroups:
    def test_returns_paginated_records(self, server_config, auth_manager):
        records = [_make_group_record(sys_id=f"grp{i}", name=f"Group {i}") for i in range(3)]
        resp = _make_response(200, {"result": records})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp):
            result = list_ci_dependency_groups(
                server_config,
                auth_manager,
                ListCIDependencyGroupsParams(limit=20, offset=0),
            )

        assert result["count"] == 3
        assert result["has_more"] is False
        assert result["next_offset"] is None
        assert result["records"][0]["name"] == "Group 0"

    def test_has_more_when_full_page(self, server_config, auth_manager):
        records = [_make_group_record(sys_id=f"grp{i}") for i in range(5)]
        resp = _make_response(200, {"result": records})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp):
            result = list_ci_dependency_groups(
                server_config,
                auth_manager,
                ListCIDependencyGroupsParams(limit=5, offset=0),
            )

        assert result["has_more"] is True
        assert result["next_offset"] == 5

    def test_filter_by_name(self, server_config, auth_manager):
        resp = _make_response(200, {"result": [_make_group_record(name="Network Core")]})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp) as mock_get:
            list_ci_dependency_groups(
                server_config,
                auth_manager,
                ListCIDependencyGroupsParams(name="Network"),
            )

        call_kwargs = mock_get.call_args
        assert "nameLIKENetwork" in call_kwargs[1]["params"].get("sysparm_query", "")

    def test_filter_by_active_true(self, server_config, auth_manager):
        resp = _make_response(200, {"result": []})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp) as mock_get:
            list_ci_dependency_groups(
                server_config,
                auth_manager,
                ListCIDependencyGroupsParams(active=True),
            )

        call_kwargs = mock_get.call_args
        assert "active=true" in call_kwargs[1]["params"].get("sysparm_query", "")

    def test_filter_by_active_false(self, server_config, auth_manager):
        resp = _make_response(200, {"result": []})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp) as mock_get:
            list_ci_dependency_groups(
                server_config,
                auth_manager,
                ListCIDependencyGroupsParams(active=False),
            )

        call_kwargs = mock_get.call_args
        assert "active=false" in call_kwargs[1]["params"].get("sysparm_query", "")

    def test_filter_by_group_type(self, server_config, auth_manager):
        resp = _make_response(200, {"result": []})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp) as mock_get:
            list_ci_dependency_groups(
                server_config,
                auth_manager,
                ListCIDependencyGroupsParams(group_type="dynamic"),
            )

        call_kwargs = mock_get.call_args
        assert "type=dynamic" in call_kwargs[1]["params"].get("sysparm_query", "")

    def test_raw_query_passthrough(self, server_config, auth_manager):
        resp = _make_response(200, {"result": []})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp) as mock_get:
            list_ci_dependency_groups(
                server_config,
                auth_manager,
                ListCIDependencyGroupsParams(query="manager=sys_id_123"),
            )

        call_kwargs = mock_get.call_args
        assert "manager=sys_id_123" in call_kwargs[1]["params"].get("sysparm_query", "")

    def test_normalises_reference_fields(self, server_config, auth_manager):
        record = _make_group_record()
        resp = _make_response(200, {"result": [record]})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp):
            result = list_ci_dependency_groups(
                server_config,
                auth_manager,
                ListCIDependencyGroupsParams(),
            )

        first = result["records"][0]
        assert first["manager"] == "Admin User"
        assert first["type"] == "manual"

    def test_http_error_returns_error_dict(self, server_config, auth_manager):
        resp = _make_response(500, {})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp):
            result = list_ci_dependency_groups(
                server_config,
                auth_manager,
                ListCIDependencyGroupsParams(),
            )

        assert "error" in result

    def test_request_exception_returns_error_dict(self, server_config, auth_manager):
        with patch(
            "servicenow_mcp.tools.cmdb_dep_group_tools.requests.get",
            side_effect=requests.RequestException("timeout"),
        ):
            result = list_ci_dependency_groups(
                server_config,
                auth_manager,
                ListCIDependencyGroupsParams(),
            )

        assert "error" in result
        assert "timeout" in result["error"]

    def test_empty_result(self, server_config, auth_manager):
        resp = _make_response(200, {"result": []})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp):
            result = list_ci_dependency_groups(
                server_config,
                auth_manager,
                ListCIDependencyGroupsParams(),
            )

        assert result["count"] == 0
        assert result["records"] == []

    def test_pagination_offset(self, server_config, auth_manager):
        resp = _make_response(200, {"result": []})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp) as mock_get:
            list_ci_dependency_groups(
                server_config,
                auth_manager,
                ListCIDependencyGroupsParams(limit=10, offset=20),
            )

        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["sysparm_offset"] == 20
        assert call_kwargs[1]["params"]["sysparm_limit"] == 10


# ---------------------------------------------------------------------------
# get_ci_dependency_group tests
# ---------------------------------------------------------------------------


class TestGetCIDependencyGroup:
    def test_returns_dep_group(self, server_config, auth_manager):
        record = _make_group_record(sys_id="abc123", name="Core Infra")
        resp = _make_response(200, {"result": record})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp):
            result = get_ci_dependency_group(
                server_config,
                auth_manager,
                GetCIDependencyGroupParams(sys_id="abc123"),
            )

        assert "dep_group" in result
        assert result["dep_group"]["sys_id"] == "abc123"
        assert result["dep_group"]["name"] == "Core Infra"

    def test_404_returns_error(self, server_config, auth_manager):
        resp = MagicMock()
        resp.status_code = 404
        resp.raise_for_status = MagicMock()

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp):
            result = get_ci_dependency_group(
                server_config,
                auth_manager,
                GetCIDependencyGroupParams(sys_id="missing_id"),
            )

        assert "error" in result
        assert "missing_id" in result["error"]

    def test_empty_result_returns_error(self, server_config, auth_manager):
        resp = _make_response(200, {"result": None})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp):
            result = get_ci_dependency_group(
                server_config,
                auth_manager,
                GetCIDependencyGroupParams(sys_id="ghost_id"),
            )

        assert "error" in result

    def test_http_error_returns_error_dict(self, server_config, auth_manager):
        resp = _make_response(403, {})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp):
            result = get_ci_dependency_group(
                server_config,
                auth_manager,
                GetCIDependencyGroupParams(sys_id="any"),
            )

        assert "error" in result

    def test_request_exception_returns_error_dict(self, server_config, auth_manager):
        with patch(
            "servicenow_mcp.tools.cmdb_dep_group_tools.requests.get",
            side_effect=requests.RequestException("connection refused"),
        ):
            result = get_ci_dependency_group(
                server_config,
                auth_manager,
                GetCIDependencyGroupParams(sys_id="any"),
            )

        assert "error" in result
        assert "connection refused" in result["error"]

    def test_normalises_reference_fields(self, server_config, auth_manager):
        record = _make_group_record()
        resp = _make_response(200, {"result": record})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp):
            result = get_ci_dependency_group(
                server_config,
                auth_manager,
                GetCIDependencyGroupParams(sys_id="grp1"),
            )

        dep_group = result["dep_group"]
        assert dep_group["manager"] == "Admin User"
        assert dep_group["type"] == "manual"
        assert dep_group["sys_class_name"] == "CMDB Dependency Group"

    def test_string_manager_field(self, server_config, auth_manager):
        record = _make_group_record()
        record["manager"] = "admin_plain"
        resp = _make_response(200, {"result": record})

        with patch("servicenow_mcp.tools.cmdb_dep_group_tools.requests.get", return_value=resp):
            result = get_ci_dependency_group(
                server_config,
                auth_manager,
                GetCIDependencyGroupParams(sys_id="grp1"),
            )

        assert result["dep_group"]["manager"] == "admin_plain"
