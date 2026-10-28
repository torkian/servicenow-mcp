"""Tests for sys_db_object tools (list_tables, get_table_definition)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from servicenow_mcp.tools.sys_db_object_tools import (
    _format_table,
    get_table_definition,
    list_tables,
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


def _make_table_record(overrides=None):
    base = {
        "sys_id": "abc123def456abc7890abc123def456a",
        "name": "incident",
        "label": "Incident",
        "super_class": "task",
        "scope": "global",
        "is_extendable": "false",
        "create_access": "true",
        "read_access": "true",
        "write_access": "true",
        "delete_access": "false",
        "number_ref": "",
        "sys_created_on": "2020-01-01 00:00:00",
        "sys_updated_on": "2024-01-01 00:00:00",
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
# _format_table tests
# ---------------------------------------------------------------------------


def test_format_table_basic():
    record = _make_table_record()
    result = _format_table(record)
    assert result["name"] == "incident"
    assert result["label"] == "Incident"
    assert result["super_class"] == "task"
    assert result["scope"] == "global"
    assert result["is_extendable"] is False
    assert result["create_access"] is True
    assert result["read_access"] is True
    assert result["write_access"] is True
    assert result["delete_access"] is False


def test_format_table_is_extendable_true():
    record = _make_table_record({"is_extendable": "true"})
    assert _format_table(record)["is_extendable"] is True


def test_format_table_dict_values():
    record = _make_table_record({
        "label": {"value": "Incident", "display_value": "Incident"},
        "scope": {"value": "global", "display_value": "Global"},
    })
    result = _format_table(record)
    assert result["label"] == "Incident"
    assert result["scope"] == "Global"


def test_format_table_no_super_class_when_empty():
    record = _make_table_record({"super_class": ""})
    result = _format_table(record)
    assert "super_class" not in result


def test_format_table_no_scope_when_empty():
    record = _make_table_record({"scope": ""})
    result = _format_table(record)
    assert "scope" not in result


def test_format_table_no_number_ref_when_empty():
    record = _make_table_record({"number_ref": ""})
    result = _format_table(record)
    assert "number_ref" not in result


def test_format_table_number_ref_included():
    record = _make_table_record({"number_ref": "INC"})
    result = _format_table(record)
    assert result["number_ref"] == "INC"


def test_format_table_all_access_false():
    record = _make_table_record({
        "create_access": "false",
        "read_access": "false",
        "write_access": "false",
        "delete_access": "false",
    })
    result = _format_table(record)
    assert result["create_access"] is False
    assert result["read_access"] is False
    assert result["write_access"] is False
    assert result["delete_access"] is False


def test_format_table_bool_integers():
    record = _make_table_record({
        "is_extendable": 1,
        "create_access": True,
        "delete_access": 0,
    })
    result = _format_table(record)
    assert result["is_extendable"] is True
    assert result["create_access"] is True
    assert result["delete_access"] is False


# ---------------------------------------------------------------------------
# list_tables tests
# ---------------------------------------------------------------------------


def test_list_tables_success(config, auth_manager):
    records = [_make_table_record(), _make_table_record({"name": "incident_task", "label": "Incident Task"})]
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response(records)
        result = list_tables({}, config, auth_manager)

    assert "tables" in result
    assert len(result["tables"]) == 2
    assert "has_more" in result


def test_list_tables_empty(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        result = list_tables({}, config, auth_manager)

    assert result["tables"] == []
    assert result["has_more"] is False


def test_list_tables_name_query_filter(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_tables({"name_query": "incident"}, config, auth_manager)

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "nameLIKEincident" in query


def test_list_tables_label_query_filter(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_tables({"label_query": "Change"}, config, auth_manager)

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "labelLIKEChange" in query


def test_list_tables_scope_filter(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_tables({"scope": "global"}, config, auth_manager)

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "scope.name=global" in query


def test_list_tables_is_extendable_true_filter(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_tables({"is_extendable": True}, config, auth_manager)

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "is_extendable=true" in query


def test_list_tables_is_extendable_false_filter(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_tables({"is_extendable": False}, config, auth_manager)

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "is_extendable=false" in query


def test_list_tables_no_query_when_no_filters(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_tables({}, config, auth_manager)

    params = mock_req.call_args[1]["params"]
    assert params.get("sysparm_query", "") in ("", None)


def test_list_tables_pagination(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_tables({"limit": 10, "offset": 20}, config, auth_manager)

    params = mock_req.call_args[1]["params"]
    assert params["sysparm_limit"] == 10
    assert params["sysparm_offset"] == 20


def test_list_tables_count(config, auth_manager):
    records = [_make_table_record({"name": f"table_{i}"}) for i in range(5)]
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response(records)
        result = list_tables({"limit": 5}, config, auth_manager)

    assert result["count"] == 5


def test_list_tables_http_error(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_resp = MagicMock()
        err_resp = MagicMock()
        err_resp.status_code = 403
        err_resp.json.return_value = {}
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=err_resp)
        mock_req.return_value = mock_resp
        result = list_tables({}, config, auth_manager)

    assert "error" in result


def test_list_tables_request_exception(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.side_effect = requests.ConnectionError("timeout")
        result = list_tables({}, config, auth_manager)

    assert "error" in result


def test_list_tables_no_instance_url(auth_manager):
    cfg = ServerConfig(
        instance_url="",
        auth=AuthConfig(type=AuthType.BASIC, username="u", password="p"),
    )
    auth_manager.instance_url = None
    result = list_tables({}, cfg, auth_manager)
    assert "error" in result


def test_list_tables_no_headers(config):
    mgr = MagicMock()
    mgr.get_headers.return_value = None
    mgr.instance_url = None
    result = list_tables({}, config, mgr)
    assert "error" in result


def test_list_tables_combined_filters(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_tables({"name_query": "cmdb", "scope": "global", "is_extendable": True}, config, auth_manager)

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "nameLIKEcmdb" in query
    assert "scope.name=global" in query
    assert "is_extendable=true" in query


# ---------------------------------------------------------------------------
# get_table_definition tests
# ---------------------------------------------------------------------------


def test_get_table_definition_success(config, auth_manager):
    record = _make_table_record()
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([record])
        result = get_table_definition({"table_name": "incident"}, config, auth_manager)

    assert "table" in result
    assert result["table"]["name"] == "incident"
    assert result["table"]["label"] == "Incident"


def test_get_table_definition_not_found(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        result = get_table_definition({"table_name": "nonexistent_table_xyz"}, config, auth_manager)

    assert "error" in result
    assert "nonexistent_table_xyz" in result["error"]


def test_get_table_definition_by_name_uses_name_query(config, auth_manager):
    record = _make_table_record()
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([record])
        get_table_definition({"table_name": "incident"}, config, auth_manager)

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "name=incident" in query


def test_get_table_definition_by_sys_id_uses_sys_id_query(config, auth_manager):
    record = _make_table_record()
    sys_id = "abc123def456abc7890abc123def456a"
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([record])
        get_table_definition({"table_name": sys_id}, config, auth_manager)

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert f"sys_id={sys_id}" in query


def test_get_table_definition_limits_to_one(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([_make_table_record()])
        get_table_definition({"table_name": "incident"}, config, auth_manager)

    params = mock_req.call_args[1]["params"]
    assert params["sysparm_limit"] == 1


def test_get_table_definition_missing_table_name(config, auth_manager):
    result = get_table_definition({}, config, auth_manager)
    assert "error" in result


def test_get_table_definition_http_error(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_resp = MagicMock()
        err_resp = MagicMock()
        err_resp.status_code = 500
        err_resp.json.return_value = {}
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=err_resp)
        mock_req.return_value = mock_resp
        result = get_table_definition({"table_name": "incident"}, config, auth_manager)

    assert "error" in result


def test_get_table_definition_request_exception(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.side_effect = requests.Timeout("timed out")
        result = get_table_definition({"table_name": "incident"}, config, auth_manager)

    assert "error" in result


def test_get_table_definition_no_instance_url(auth_manager):
    cfg = ServerConfig(
        instance_url="",
        auth=AuthConfig(type=AuthType.BASIC, username="u", password="p"),
    )
    auth_manager.instance_url = None
    result = get_table_definition({"table_name": "incident"}, cfg, auth_manager)
    assert "error" in result


def test_get_table_definition_no_headers(config):
    mgr = MagicMock()
    mgr.get_headers.return_value = None
    mgr.instance_url = None
    result = get_table_definition({"table_name": "incident"}, config, mgr)
    assert "error" in result


def test_get_table_definition_super_class_normalised(config, auth_manager):
    record = _make_table_record({"super_class": {"value": "task", "display_value": "Task"}})
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([record])
        result = get_table_definition({"table_name": "incident"}, config, auth_manager)

    assert result["table"]["super_class"] == "Task"


def test_get_table_definition_extendable_true(config, auth_manager):
    record = _make_table_record({"is_extendable": "true", "name": "task"})
    with patch("servicenow_mcp.tools.sys_db_object_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([record])
        result = get_table_definition({"table_name": "task"}, config, auth_manager)

    assert result["table"]["is_extendable"] is True
