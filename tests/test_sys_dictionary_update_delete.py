"""Tests for update_field_definition and delete_field_definition tools."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from servicenow_mcp.tools.sys_dictionary_tools import (
    _resolve_field_sys_id,
    delete_field_definition,
    update_field_definition,
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


def _mock_http_error(status=404):
    resp = MagicMock()
    resp.status_code = status
    resp.text = '{"error":{"message":"Not found","detail":"Record not found"}}'
    exc = requests.HTTPError(response=resp)
    return exc


# ---------------------------------------------------------------------------
# _resolve_field_sys_id tests
# ---------------------------------------------------------------------------


def test_resolve_with_sys_id_directly():
    result = _resolve_field_sys_id("abc123", None, None, "https://x", {})
    assert result == {"sys_id": "abc123"}


def test_resolve_missing_both():
    result = _resolve_field_sys_id(None, None, None, "https://x", {})
    assert "error" in result


def test_resolve_missing_field_name():
    result = _resolve_field_sys_id(None, "incident", None, "https://x", {})
    assert "error" in result


def test_resolve_missing_table_name():
    result = _resolve_field_sys_id(None, None, "priority", "https://x", {})
    assert "error" in result


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_resolve_by_table_and_field(mock_req):
    mock_req.return_value = _mock_response([{"sys_id": "xyz789"}])
    result = _resolve_field_sys_id(None, "incident", "priority", "https://x", {})
    assert result == {"sys_id": "xyz789"}


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_resolve_by_table_and_field_not_found(mock_req):
    mock_req.return_value = _mock_response([])
    result = _resolve_field_sys_id(None, "incident", "priority", "https://x", {})
    assert "error" in result
    assert "priority" in result["error"]


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_resolve_by_table_http_error(mock_req):
    mock_req.return_value = MagicMock(
        **{"raise_for_status.side_effect": _mock_http_error(500), "status_code": 500}
    )
    result = _resolve_field_sys_id(None, "incident", "priority", "https://x", {})
    assert "error" in result


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_resolve_by_table_request_exception(mock_req):
    mock_req.side_effect = requests.RequestException("connection refused")
    result = _resolve_field_sys_id(None, "incident", "priority", "https://x", {})
    assert "error" in result


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_resolve_sys_id_dict_value(mock_req):
    mock_req.return_value = _mock_response([{"sys_id": {"value": "dict_id"}}])
    result = _resolve_field_sys_id(None, "incident", "priority", "https://x", {})
    assert result == {"sys_id": "dict_id"}


# ---------------------------------------------------------------------------
# update_field_definition tests
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_update_by_sys_id_column_label(mock_req, config, auth_manager):
    updated = _make_field_record({"column_label": "New Priority Label"})
    mock_req.return_value = _mock_response(updated)
    result = update_field_definition(
        {"sys_id": "abc123", "column_label": "New Priority Label"},
        config,
        auth_manager,
    )
    assert result["success"] is True
    assert result["field"]["label"] == "New Priority Label"
    assert "updated successfully" in result["message"]


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_update_by_table_and_field(mock_req, config, auth_manager):
    lookup_resp = _mock_response([{"sys_id": "abc123"}])
    updated_resp = _mock_response(_make_field_record({"mandatory": "true"}))
    mock_req.side_effect = [lookup_resp, updated_resp]
    result = update_field_definition(
        {"table_name": "incident", "field_name": "priority", "mandatory": True},
        config,
        auth_manager,
    )
    assert result["success"] is True
    assert result["field"]["mandatory"] is True


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_update_read_only_field(mock_req, config, auth_manager):
    mock_req.return_value = _mock_response(_make_field_record({"read_only": "true"}))
    result = update_field_definition(
        {"sys_id": "abc123", "read_only": True},
        config,
        auth_manager,
    )
    assert result["success"] is True
    assert result["field"]["read_only"] is True


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_update_all_optional_fields(mock_req, config, auth_manager):
    mock_req.return_value = _mock_response(_make_field_record())
    result = update_field_definition(
        {
            "sys_id": "abc123",
            "column_label": "Lbl",
            "mandatory": False,
            "read_only": False,
            "default_value": "1",
            "max_length": 255,
            "comments": "A comment",
            "active": True,
            "reference_qual": "active=true",
        },
        config,
        auth_manager,
    )
    assert result["success"] is True
    _, kwargs = mock_req.call_args
    body = kwargs.get("json", {})
    assert body["column_label"] == "Lbl"
    assert body["mandatory"] == "false"
    assert body["read_only"] == "false"
    assert body["default_value"] == "1"
    assert body["max_length"] == "255"
    assert body["comments"] == "A comment"
    assert body["active"] == "true"
    assert body["reference_qual"] == "active=true"


def test_update_no_fields_to_update(config, auth_manager):
    result = update_field_definition({"sys_id": "abc123"}, config, auth_manager)
    assert "error" in result
    assert "No fields to update" in result["error"]


def test_update_invalid_params(config, auth_manager):
    result = update_field_definition({}, config, auth_manager)
    # No sys_id, no table_name+field_name → resolve error or no-fields error
    assert "error" in result


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_update_404_error(mock_req, config, auth_manager):
    err = _mock_http_error(404)
    resp = MagicMock()
    resp.status_code = 404
    resp.raise_for_status.side_effect = err
    mock_req.return_value = resp
    result = update_field_definition(
        {"sys_id": "abc123", "column_label": "X"},
        config,
        auth_manager,
    )
    assert "error" in result
    assert "not found" in result["error"].lower()


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_update_http_error_non_404(mock_req, config, auth_manager):
    err = _mock_http_error(500)
    resp = MagicMock()
    resp.status_code = 500
    resp.raise_for_status.side_effect = err
    mock_req.return_value = resp
    result = update_field_definition(
        {"sys_id": "abc123", "column_label": "X"},
        config,
        auth_manager,
    )
    assert "error" in result


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_update_request_exception(mock_req, config, auth_manager):
    mock_req.side_effect = requests.RequestException("timeout")
    result = update_field_definition(
        {"sys_id": "abc123", "column_label": "X"},
        config,
        auth_manager,
    )
    assert "error" in result


def test_update_no_instance_url(config, auth_manager):
    auth_manager.get_headers.return_value = {}
    result = update_field_definition(
        {"sys_id": "abc123", "column_label": "X"},
        config,
        auth_manager,
    )
    # Will fail at headers check
    assert "error" in result


def test_update_no_instance_url_config(auth_manager):
    cfg = ServerConfig(instance_url="", auth=AuthConfig(type=AuthType.BASIC, username="a", password="b"))
    result = update_field_definition(
        {"sys_id": "abc123", "column_label": "X"},
        cfg,
        auth_manager,
    )
    assert "error" in result


# ---------------------------------------------------------------------------
# delete_field_definition tests
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_delete_by_sys_id(mock_req, config, auth_manager):
    resp = MagicMock()
    resp.status_code = 204
    resp.raise_for_status = MagicMock()
    mock_req.return_value = resp
    result = delete_field_definition({"sys_id": "abc123"}, config, auth_manager)
    assert result["success"] is True
    assert result["sys_id"] == "abc123"
    assert "deleted successfully" in result["message"]


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_delete_200_response(mock_req, config, auth_manager):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    mock_req.return_value = resp
    result = delete_field_definition({"sys_id": "abc123"}, config, auth_manager)
    assert result["success"] is True


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_delete_by_table_and_field(mock_req, config, auth_manager):
    lookup_resp = _mock_response([{"sys_id": "abc123"}])
    delete_resp = MagicMock()
    delete_resp.status_code = 204
    delete_resp.raise_for_status = MagicMock()
    mock_req.side_effect = [lookup_resp, delete_resp]
    result = delete_field_definition(
        {"table_name": "incident", "field_name": "priority"},
        config,
        auth_manager,
    )
    assert result["success"] is True
    assert result["sys_id"] == "abc123"


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_delete_404_response(mock_req, config, auth_manager):
    resp = MagicMock()
    resp.status_code = 404
    resp.raise_for_status = MagicMock()
    mock_req.return_value = resp
    result = delete_field_definition({"sys_id": "abc123"}, config, auth_manager)
    assert "error" in result
    assert "not found" in result["error"].lower()


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_delete_http_error(mock_req, config, auth_manager):
    err = _mock_http_error(500)
    resp = MagicMock()
    resp.status_code = 500
    resp.raise_for_status.side_effect = err
    mock_req.return_value = resp
    result = delete_field_definition({"sys_id": "abc123"}, config, auth_manager)
    assert "error" in result


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_delete_request_exception(mock_req, config, auth_manager):
    mock_req.side_effect = requests.RequestException("network error")
    result = delete_field_definition({"sys_id": "abc123"}, config, auth_manager)
    assert "error" in result


def test_delete_no_identifier(config, auth_manager):
    result = delete_field_definition({}, config, auth_manager)
    assert "error" in result


@patch("servicenow_mcp.tools.sys_dictionary_tools._make_request")
def test_delete_lookup_not_found(mock_req, config, auth_manager):
    mock_req.return_value = _mock_response([])
    result = delete_field_definition(
        {"table_name": "incident", "field_name": "no_such_field"},
        config,
        auth_manager,
    )
    assert "error" in result


def test_delete_no_instance_url(config, auth_manager):
    auth_manager.get_headers.return_value = {}
    result = delete_field_definition({"sys_id": "abc123"}, config, auth_manager)
    assert "error" in result


def test_delete_no_instance_url_config(auth_manager):
    cfg = ServerConfig(instance_url="", auth=AuthConfig(type=AuthType.BASIC, username="a", password="b"))
    result = delete_field_definition({"sys_id": "abc123"}, cfg, auth_manager)
    assert "error" in result
