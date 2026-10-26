"""Tests for sys_dictionary tools (list_table_fields, get_field_definition)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from servicenow_mcp.tools.sys_dictionary_tools import (
    _format_field,
    get_field_definition,
    list_table_fields,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, ServerConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config():
    auth_cfg = AuthConfig(type=AuthType.BASIC, username="admin", password="pass")
    return ServerConfig(instance_url="https://test.service-now.com", auth=auth_cfg)


@pytest.fixture
def auth_manager():
    mgr = MagicMock()
    mgr.get_headers.return_value = {"Authorization": "Basic dGVzdA=="}
    mgr.instance_url = None
    return mgr


def _make_field_record(overrides=None):
    base = {
        "sys_id": "abc123",
        "name": "incident",
        "element": "priority",
        "internal_type": "integer",
        "column_label": "Priority",
        "comments": "",
        "mandatory": "false",
        "read_only": "false",
        "default_value": "3",
        "max_length": "40",
        "reference": "",
        "reference_qual": "",
        "array": "false",
        "choice": "1",
        "active": "true",
        "sys_created_on": "2020-01-01 00:00:00",
        "sys_updated_on": "2020-06-01 00:00:00",
    }
    if overrides:
        base.update(overrides)
    return base


def _mock_response(data, status=200):
    mock = MagicMock()
    mock.status_code = status
    mock.json.return_value = {"result": data}
    mock.raise_for_status = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# _format_field tests
# ---------------------------------------------------------------------------


def test_format_field_basic():
    record = _make_field_record()
    result = _format_field(record)
    assert result["table_name"] == "incident"
    assert result["field_name"] == "priority"
    assert result["field_type"] == "integer"
    assert result["label"] == "Priority"
    assert result["mandatory"] is False
    assert result["read_only"] is False
    assert result["default_value"] == "3"
    assert result["max_length"] == "40"
    assert result["active"] is True
    assert result["choice"] == "1"


def test_format_field_mandatory_true():
    record = _make_field_record({"mandatory": "true"})
    assert _format_field(record)["mandatory"] is True


def test_format_field_read_only_true():
    record = _make_field_record({"read_only": "true"})
    assert _format_field(record)["read_only"] is True


def test_format_field_reference():
    record = _make_field_record({"internal_type": "reference", "reference": "sys_user", "element": "assigned_to"})
    result = _format_field(record)
    assert result["reference_table"] == "sys_user"


def test_format_field_reference_qualifier():
    record = _make_field_record({
        "internal_type": "reference",
        "reference": "sys_user",
        "reference_qual": "active=true",
    })
    result = _format_field(record)
    assert result["reference_qualifier"] == "active=true"


def test_format_field_no_reference_key_when_empty():
    record = _make_field_record({"reference": ""})
    result = _format_field(record)
    assert "reference_table" not in result


def test_format_field_no_choice_when_zero():
    record = _make_field_record({"choice": "0"})
    result = _format_field(record)
    assert "choice" not in result


def test_format_field_dict_values():
    record = _make_field_record({
        "internal_type": {"value": "string", "display_value": "String"},
        "mandatory": {"value": "true", "display_value": "true"},
    })
    result = _format_field(record)
    assert result["field_type"] == "string"
    assert result["mandatory"] is True


def test_format_field_active_false():
    record = _make_field_record({"active": "false"})
    assert _format_field(record)["active"] is False


# ---------------------------------------------------------------------------
# list_table_fields tests
# ---------------------------------------------------------------------------


def test_list_table_fields_success(config, auth_manager):
    records = [_make_field_record(), _make_field_record({"element": "state", "column_label": "State"})]
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response(records)
        result = list_table_fields({"table_name": "incident"}, config, auth_manager)

    assert "fields" in result
    assert len(result["fields"]) == 2
    assert result["table_name"] == "incident"
    assert "has_more" in result


def test_list_table_fields_empty(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        result = list_table_fields({"table_name": "nonexistent_table"}, config, auth_manager)

    assert result["fields"] == []
    assert result["has_more"] is False


def test_list_table_fields_mandatory_only(config, auth_manager):
    records = [_make_field_record({"mandatory": "true"})]
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response(records)
        result = list_table_fields(
            {"table_name": "incident", "mandatory_only": True},
            config,
            auth_manager,
        )

    assert len(result["fields"]) == 1
    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "mandatory=true" in query


def test_list_table_fields_field_type_filter(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_table_fields(
            {"table_name": "incident", "field_type": "reference"},
            config,
            auth_manager,
        )

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "internal_typeLIKEreference" in query


def test_list_table_fields_pagination(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_table_fields(
            {"table_name": "incident", "limit": 10, "offset": 20},
            config,
            auth_manager,
        )

    params = mock_req.call_args[1]["params"]
    assert params["sysparm_limit"] == 10
    assert params["sysparm_offset"] == 20


def test_list_table_fields_http_error(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_resp = MagicMock()
        err_resp = MagicMock()
        err_resp.status_code = 403
        err_resp.json.return_value = {}
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=err_resp)
        mock_req.return_value = mock_resp
        result = list_table_fields({"table_name": "incident"}, config, auth_manager)

    assert "error" in result


def test_list_table_fields_request_exception(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.side_effect = requests.ConnectionError("timeout")
        result = list_table_fields({"table_name": "incident"}, config, auth_manager)

    assert "error" in result


def test_list_table_fields_no_instance_url(auth_manager):
    cfg = ServerConfig(
        instance_url="",
        auth=AuthConfig(type=AuthType.BASIC, username="u", password="p"),
    )
    auth_manager.instance_url = None
    result = list_table_fields({"table_name": "incident"}, cfg, auth_manager)
    assert "error" in result


def test_list_table_fields_no_headers(config):
    mgr = MagicMock()
    mgr.get_headers.return_value = None
    mgr.instance_url = None
    result = list_table_fields({"table_name": "incident"}, config, mgr)
    assert "error" in result


def test_list_table_fields_missing_table_name(config, auth_manager):
    result = list_table_fields({}, config, auth_manager)
    assert "error" in result


def test_list_table_fields_include_inherited_default(config, auth_manager):
    """Table name filter is included in query regardless of include_inherited."""
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_table_fields(
            {"table_name": "incident", "include_inherited": True},
            config,
            auth_manager,
        )

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "name=incident" in query


def test_list_table_fields_query_contains_table_name(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_table_fields({"table_name": "change_request"}, config, auth_manager)

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "name=change_request" in query


def test_list_table_fields_returns_fields_list(config, auth_manager):
    records = [_make_field_record({"element": f"field_{i}"}) for i in range(3)]
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response(records)
        result = list_table_fields({"table_name": "incident", "limit": 3}, config, auth_manager)

    assert result["count"] == 3
    assert len(result["fields"]) == 3


# ---------------------------------------------------------------------------
# get_field_definition tests
# ---------------------------------------------------------------------------


def test_get_field_definition_success(config, auth_manager):
    record = _make_field_record()
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([record])
        result = get_field_definition(
            {"table_name": "incident", "field_name": "priority"},
            config,
            auth_manager,
        )

    assert "field" in result
    assert result["field"]["field_name"] == "priority"
    assert result["field"]["table_name"] == "incident"


def test_get_field_definition_not_found(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        result = get_field_definition(
            {"table_name": "incident", "field_name": "nonexistent_field"},
            config,
            auth_manager,
        )

    assert "error" in result
    assert "nonexistent_field" in result["error"]
    assert "incident" in result["error"]


def test_get_field_definition_query_params(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([_make_field_record()])
        get_field_definition(
            {"table_name": "change_request", "field_name": "state"},
            config,
            auth_manager,
        )

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "name=change_request" in query
    assert "element=state" in query


def test_get_field_definition_reference_field(config, auth_manager):
    record = _make_field_record({
        "element": "assignment_group",
        "internal_type": "reference",
        "reference": "sys_user_group",
    })
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([record])
        result = get_field_definition(
            {"table_name": "incident", "field_name": "assignment_group"},
            config,
            auth_manager,
        )

    assert result["field"]["reference_table"] == "sys_user_group"
    assert result["field"]["field_type"] == "reference"


def test_get_field_definition_http_error(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_resp = MagicMock()
        err_resp = MagicMock()
        err_resp.status_code = 500
        err_resp.json.return_value = {}
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=err_resp)
        mock_req.return_value = mock_resp
        result = get_field_definition(
            {"table_name": "incident", "field_name": "priority"},
            config,
            auth_manager,
        )

    assert "error" in result


def test_get_field_definition_request_exception(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.side_effect = requests.Timeout("timed out")
        result = get_field_definition(
            {"table_name": "incident", "field_name": "priority"},
            config,
            auth_manager,
        )

    assert "error" in result


def test_get_field_definition_no_instance_url(auth_manager):
    cfg = ServerConfig(
        instance_url="",
        auth=AuthConfig(type=AuthType.BASIC, username="u", password="p"),
    )
    auth_manager.instance_url = None
    result = get_field_definition({"table_name": "incident", "field_name": "priority"}, cfg, auth_manager)
    assert "error" in result


def test_get_field_definition_no_headers(config):
    mgr = MagicMock()
    mgr.get_headers.return_value = None
    mgr.instance_url = None
    result = get_field_definition({"table_name": "incident", "field_name": "priority"}, config, mgr)
    assert "error" in result


def test_get_field_definition_missing_field_name(config, auth_manager):
    result = get_field_definition({"table_name": "incident"}, config, auth_manager)
    assert "error" in result


def test_get_field_definition_missing_table_name(config, auth_manager):
    result = get_field_definition({"field_name": "priority"}, config, auth_manager)
    assert "error" in result


def test_get_field_definition_limits_to_one(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_dictionary_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([_make_field_record()])
        get_field_definition(
            {"table_name": "incident", "field_name": "priority"},
            config,
            auth_manager,
        )

    params = mock_req.call_args[1]["params"]
    assert params["sysparm_limit"] == 1
