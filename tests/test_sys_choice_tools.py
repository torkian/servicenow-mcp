"""Tests for sys_choice tools (list_field_choices, create_field_choice)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from servicenow_mcp.tools.sys_choice_tools import (
    _format_choice,
    create_field_choice,
    list_field_choices,
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


def _make_choice_record(overrides=None):
    base = {
        "sys_id": "abc123",
        "name": "incident",
        "element": "state",
        "value": "1",
        "label": "New",
        "sequence": "100",
        "language": "en",
        "inactive": "false",
        "hint": "",
        "dependent_value": "",
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
# _format_choice tests
# ---------------------------------------------------------------------------


def test_format_choice_basic():
    record = _make_choice_record()
    result = _format_choice(record)
    assert result["table_name"] == "incident"
    assert result["field_name"] == "state"
    assert result["value"] == "1"
    assert result["label"] == "New"
    assert result["sequence"] == "100"
    assert result["language"] == "en"
    assert result["inactive"] is False
    assert result["hint"] == ""


def test_format_choice_inactive_true():
    record = _make_choice_record({"inactive": "true"})
    assert _format_choice(record)["inactive"] is True


def test_format_choice_inactive_bool():
    record = _make_choice_record({"inactive": True})
    assert _format_choice(record)["inactive"] is True


def test_format_choice_with_hint():
    record = _make_choice_record({"hint": "Used for new incidents"})
    result = _format_choice(record)
    assert result["hint"] == "Used for new incidents"


def test_format_choice_dependent_value_included():
    record = _make_choice_record({"dependent_value": "hardware"})
    result = _format_choice(record)
    assert result["dependent_value"] == "hardware"


def test_format_choice_no_dependent_value_key_when_empty():
    record = _make_choice_record({"dependent_value": ""})
    result = _format_choice(record)
    assert "dependent_value" not in result


def test_format_choice_dict_values():
    record = _make_choice_record({
        "value": {"value": "2", "display_value": "2"},
        "label": {"value": "In Progress", "display_value": "In Progress"},
    })
    result = _format_choice(record)
    assert result["value"] == "2"
    assert result["label"] == "In Progress"


# ---------------------------------------------------------------------------
# list_field_choices tests
# ---------------------------------------------------------------------------


def test_list_field_choices_success(config, auth_manager):
    records = [
        _make_choice_record(),
        _make_choice_record({"value": "2", "label": "In Progress", "sequence": "200"}),
    ]
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response(records)
        result = list_field_choices(
            {"table_name": "incident", "field_name": "state"},
            config,
            auth_manager,
        )

    assert "choices" in result
    assert len(result["choices"]) == 2
    assert result["table_name"] == "incident"
    assert result["field_name"] == "state"
    assert "has_more" in result


def test_list_field_choices_no_field_name(config, auth_manager):
    """Omitting field_name returns all choice fields for the table."""
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([_make_choice_record()])
        result = list_field_choices({"table_name": "incident"}, config, auth_manager)

    assert "choices" in result
    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "name=incident" in query
    assert "element=" not in query


def test_list_field_choices_field_name_in_query(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_field_choices(
            {"table_name": "incident", "field_name": "priority"},
            config,
            auth_manager,
        )

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "element=priority" in query


def test_list_field_choices_excludes_inactive_by_default(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_field_choices({"table_name": "incident", "field_name": "state"}, config, auth_manager)

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "inactive=false" in query


def test_list_field_choices_include_inactive(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_field_choices(
            {"table_name": "incident", "field_name": "state", "include_inactive": True},
            config,
            auth_manager,
        )

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "inactive=false" not in query


def test_list_field_choices_language_filter(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_field_choices(
            {"table_name": "incident", "field_name": "state", "language": "fr"},
            config,
            auth_manager,
        )

    query = mock_req.call_args[1]["params"].get("sysparm_query", "")
    assert "language=fr" in query


def test_list_field_choices_ordered_by_sequence(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_field_choices({"table_name": "incident", "field_name": "state"}, config, auth_manager)

    params = mock_req.call_args[1]["params"]
    assert params.get("sysparm_orderby") == "sequence"


def test_list_field_choices_pagination(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        list_field_choices(
            {"table_name": "incident", "field_name": "state", "limit": 5, "offset": 10},
            config,
            auth_manager,
        )

    params = mock_req.call_args[1]["params"]
    assert params["sysparm_limit"] == 5
    assert params["sysparm_offset"] == 10


def test_list_field_choices_http_error(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_resp = MagicMock()
        err_resp = MagicMock()
        err_resp.status_code = 403
        err_resp.json.return_value = {}
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=err_resp)
        mock_req.return_value = mock_resp
        result = list_field_choices(
            {"table_name": "incident", "field_name": "state"},
            config,
            auth_manager,
        )

    assert "error" in result


def test_list_field_choices_request_exception(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.side_effect = requests.ConnectionError("timeout")
        result = list_field_choices({"table_name": "incident", "field_name": "state"}, config, auth_manager)

    assert "error" in result


def test_list_field_choices_no_instance_url(auth_manager):
    cfg = ServerConfig(
        instance_url="",
        auth=AuthConfig(type=AuthType.BASIC, username="u", password="p"),
    )
    auth_manager.instance_url = None
    result = list_field_choices({"table_name": "incident"}, cfg, auth_manager)
    assert "error" in result


def test_list_field_choices_no_headers(config):
    mgr = MagicMock()
    mgr.get_headers.return_value = None
    mgr.instance_url = None
    result = list_field_choices({"table_name": "incident"}, config, mgr)
    assert "error" in result


def test_list_field_choices_missing_table_name(config, auth_manager):
    result = list_field_choices({}, config, auth_manager)
    assert "error" in result


def test_list_field_choices_empty_result(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response([])
        result = list_field_choices({"table_name": "nonexistent", "field_name": "state"}, config, auth_manager)

    assert result["choices"] == []
    assert result["has_more"] is False


# ---------------------------------------------------------------------------
# create_field_choice tests
# ---------------------------------------------------------------------------


def test_create_field_choice_success(config, auth_manager):
    created = _make_choice_record({"value": "5", "label": "Pending", "sequence": "500"})
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response(created)
        result = create_field_choice(
            {
                "table_name": "incident",
                "field_name": "state",
                "value": "5",
                "label": "Pending",
            },
            config,
            auth_manager,
        )

    assert result["success"] is True
    assert "choice" in result
    assert result["choice"]["value"] == "5"
    assert result["choice"]["label"] == "Pending"
    assert "Pending" in result["message"]
    assert "incident.state" in result["message"]


def test_create_field_choice_body_fields(config, auth_manager):
    created = _make_choice_record()
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response(created)
        create_field_choice(
            {
                "table_name": "incident",
                "field_name": "state",
                "value": "1",
                "label": "New",
                "sequence": 100,
                "language": "en",
                "hint": "A new incident",
                "inactive": False,
            },
            config,
            auth_manager,
        )

    body = mock_req.call_args[1]["json"]
    assert body["name"] == "incident"
    assert body["element"] == "state"
    assert body["value"] == "1"
    assert body["label"] == "New"
    assert body["sequence"] == "100"
    assert body["language"] == "en"
    assert body["hint"] == "A new incident"
    assert body["inactive"] == "false"


def test_create_field_choice_inactive_true_serialised(config, auth_manager):
    created = _make_choice_record({"inactive": "true"})
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response(created)
        create_field_choice(
            {
                "table_name": "incident",
                "field_name": "state",
                "value": "99",
                "label": "Hidden",
                "inactive": True,
            },
            config,
            auth_manager,
        )

    body = mock_req.call_args[1]["json"]
    assert body["inactive"] == "true"


def test_create_field_choice_dependent_value(config, auth_manager):
    created = _make_choice_record({"dependent_value": "hardware"})
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response(created)
        create_field_choice(
            {
                "table_name": "change_request",
                "field_name": "category",
                "value": "hw",
                "label": "Hardware",
                "dependent_value": "hardware",
            },
            config,
            auth_manager,
        )

    body = mock_req.call_args[1]["json"]
    assert body["dependent_value"] == "hardware"


def test_create_field_choice_no_sequence_omitted(config, auth_manager):
    created = _make_choice_record()
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response(created)
        create_field_choice(
            {"table_name": "incident", "field_name": "state", "value": "1", "label": "New"},
            config,
            auth_manager,
        )

    body = mock_req.call_args[1]["json"]
    assert "sequence" not in body


def test_create_field_choice_default_language_en(config, auth_manager):
    created = _make_choice_record()
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.return_value = _mock_response(created)
        create_field_choice(
            {"table_name": "incident", "field_name": "state", "value": "1", "label": "New"},
            config,
            auth_manager,
        )

    body = mock_req.call_args[1]["json"]
    assert body["language"] == "en"


def test_create_field_choice_http_error(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_resp = MagicMock()
        err_resp = MagicMock()
        err_resp.status_code = 422
        err_resp.json.return_value = {}
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=err_resp)
        mock_req.return_value = mock_resp
        result = create_field_choice(
            {"table_name": "incident", "field_name": "state", "value": "1", "label": "New"},
            config,
            auth_manager,
        )

    assert "error" in result


def test_create_field_choice_request_exception(config, auth_manager):
    with patch("servicenow_mcp.tools.sys_choice_tools._make_request") as mock_req:
        mock_req.side_effect = requests.Timeout("timed out")
        result = create_field_choice(
            {"table_name": "incident", "field_name": "state", "value": "1", "label": "New"},
            config,
            auth_manager,
        )

    assert "error" in result


def test_create_field_choice_no_instance_url(auth_manager):
    cfg = ServerConfig(
        instance_url="",
        auth=AuthConfig(type=AuthType.BASIC, username="u", password="p"),
    )
    auth_manager.instance_url = None
    result = create_field_choice(
        {"table_name": "incident", "field_name": "state", "value": "1", "label": "New"},
        cfg,
        auth_manager,
    )
    assert "error" in result


def test_create_field_choice_no_headers(config):
    mgr = MagicMock()
    mgr.get_headers.return_value = None
    mgr.instance_url = None
    result = create_field_choice(
        {"table_name": "incident", "field_name": "state", "value": "1", "label": "New"},
        config,
        mgr,
    )
    assert "error" in result


def test_create_field_choice_missing_required_fields(config, auth_manager):
    result = create_field_choice(
        {"table_name": "incident", "field_name": "state"},  # missing value and label
        config,
        auth_manager,
    )
    assert "error" in result


def test_create_field_choice_missing_table_name(config, auth_manager):
    result = create_field_choice(
        {"field_name": "state", "value": "1", "label": "New"},
        config,
        auth_manager,
    )
    assert "error" in result
