"""Tests for transform_entry_tools.py."""

from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.transform_entry_tools import (
    create_transform_entry,
    get_transform_entry,
    list_transform_entries,
    update_transform_entry,
)


ENTRY_SYS_ID = "a" * 32
MAP_SYS_ID = "b" * 32

SAMPLE_ENTRY = {
    "sys_id": ENTRY_SYS_ID,
    "name": "user_name -> name",
    "map": {"display_value": "User Import Map", "value": MAP_SYS_ID},
    "source_field": "user_name",
    "target_field": "name",
    "coalesce": "false",
    "coalesce_empty_fields": "false",
    "active": "true",
    "default_value": "",
    "type": "field",
    "value": "",
    "script": "",
    "order": "100",
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-01-02 00:00:00",
    "sys_created_by": "admin",
    "sys_updated_by": "admin",
}


def _make_mocks(json_result):
    auth_manager = MagicMock()
    server_config = MagicMock()
    auth_manager.get_instance_url.return_value = "https://instance.service-now.com"
    auth_manager.get_headers.return_value = {"Authorization": "Bearer token"}
    server_config.instance_url = "https://instance.service-now.com"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = json_result
    mock_resp.raise_for_status = MagicMock()
    return auth_manager, server_config, mock_resp


# ---------------------------------------------------------------------------
# _format_transform_entry
# ---------------------------------------------------------------------------

def test_format_entry_string_booleans():
    from servicenow_mcp.tools.transform_entry_tools import _format_transform_entry
    rec = dict(SAMPLE_ENTRY)
    result = _format_transform_entry(rec)
    assert result["coalesce"] is False
    assert result["coalesce_empty_fields"] is False
    assert result["active"] is True
    assert result["map"] == "User Import Map"


def test_format_entry_already_bool():
    from servicenow_mcp.tools.transform_entry_tools import _format_transform_entry
    rec = dict(SAMPLE_ENTRY)
    rec["coalesce"] = True
    rec["active"] = False
    rec["map"] = "Direct string"
    result = _format_transform_entry(rec)
    assert result["coalesce"] is True
    assert result["active"] is False
    assert result["map"] == "Direct string"


def test_format_entry_map_dict_value_fallback():
    from servicenow_mcp.tools.transform_entry_tools import _format_transform_entry
    rec = dict(SAMPLE_ENTRY)
    rec["map"] = {"display_value": "", "value": "fallback_map_id"}
    result = _format_transform_entry(rec)
    assert result["map"] == "fallback_map_id"


# ---------------------------------------------------------------------------
# list_transform_entries
# ---------------------------------------------------------------------------

def test_list_transform_entries_no_instance_url():
    auth_manager = MagicMock()
    server_config = MagicMock()
    auth_manager.get_instance_url.return_value = None
    server_config.instance_url = None
    result = list_transform_entries(auth_manager, server_config, {})
    assert not result["success"]
    assert "instance_url" in result["message"]


def test_list_transform_entries_no_headers():
    auth_manager = MagicMock()
    server_config = MagicMock()
    auth_manager.get_instance_url.return_value = "https://instance.service-now.com"
    server_config.instance_url = "https://instance.service-now.com"
    auth_manager.get_headers.return_value = None
    server_config.get_headers = None
    result = list_transform_entries(auth_manager, server_config, {})
    assert not result["success"]
    assert "get_headers" in result["message"]


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_list_transform_entries_basic(mock_req):
    auth_manager, server_config, mock_resp = _make_mocks({"result": [SAMPLE_ENTRY]})
    mock_req.return_value = mock_resp
    result = list_transform_entries(auth_manager, server_config, {"limit": 10, "offset": 0})
    assert result["success"]
    assert len(result["transform_entries"]) == 1
    assert result["transform_entries"][0]["source_field"] == "user_name"


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_list_transform_entries_with_map_id(mock_req):
    auth_manager, server_config, mock_resp = _make_mocks({"result": [SAMPLE_ENTRY]})
    mock_req.return_value = mock_resp
    # map_id is a hex sys_id so resolve will pass through; first call returns map lookup, second returns list
    result = list_transform_entries(
        auth_manager, server_config, {"map_id": MAP_SYS_ID, "limit": 10, "offset": 0}
    )
    assert result["success"]


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_list_transform_entries_map_not_found(mock_req):
    auth_manager = MagicMock()
    server_config = MagicMock()
    auth_manager.get_instance_url.return_value = "https://instance.service-now.com"
    server_config.instance_url = "https://instance.service-now.com"
    auth_manager.get_headers.return_value = {"Authorization": "Bearer token"}

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = list_transform_entries(
        auth_manager, server_config, {"map_id": "NonExistentMap", "limit": 10, "offset": 0}
    )
    assert not result["success"]
    assert "not found" in result["message"]


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_list_transform_entries_filters(mock_req):
    auth_manager, server_config, mock_resp = _make_mocks({"result": []})
    mock_req.return_value = mock_resp
    result = list_transform_entries(
        auth_manager,
        server_config,
        {
            "source_field": "user",
            "target_field": "name",
            "active": True,
            "coalesce": False,
            "limit": 5,
            "offset": 0,
        },
    )
    assert result["success"]
    call_kwargs = mock_req.call_args
    params = call_kwargs[1]["params"]
    assert "source_fieldLIKEuser" in params.get("sysparm_query", "")
    assert "target_fieldLIKEname" in params.get("sysparm_query", "")


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_list_transform_entries_request_exception(mock_req):
    import requests
    auth_manager, server_config, _ = _make_mocks({})
    mock_req.side_effect = requests.exceptions.RequestException("network error")
    result = list_transform_entries(auth_manager, server_config, {})
    assert not result["success"]
    assert "Error listing" in result["message"]


# ---------------------------------------------------------------------------
# get_transform_entry
# ---------------------------------------------------------------------------

def test_get_transform_entry_missing_entry_id():
    auth_manager, server_config, _ = _make_mocks({})
    result = get_transform_entry(auth_manager, server_config, {})
    assert not result["success"]


def test_get_transform_entry_no_instance_url():
    auth_manager = MagicMock()
    server_config = MagicMock()
    auth_manager.get_instance_url.return_value = None
    server_config.instance_url = None
    result = get_transform_entry(auth_manager, server_config, {"entry_id": ENTRY_SYS_ID})
    assert not result["success"]


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_get_transform_entry_success(mock_req):
    auth_manager, server_config, mock_resp = _make_mocks({"result": SAMPLE_ENTRY})
    mock_req.return_value = mock_resp
    result = get_transform_entry(auth_manager, server_config, {"entry_id": ENTRY_SYS_ID})
    assert result["success"]
    assert result["transform_entry"]["sys_id"] == ENTRY_SYS_ID


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_get_transform_entry_404(mock_req):
    auth_manager, server_config, mock_resp = _make_mocks({})
    mock_resp.status_code = 404
    mock_req.return_value = mock_resp
    result = get_transform_entry(auth_manager, server_config, {"entry_id": ENTRY_SYS_ID})
    assert not result["success"]
    assert "not found" in result["message"]


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_get_transform_entry_empty_result(mock_req):
    auth_manager, server_config, mock_resp = _make_mocks({"result": {}})
    mock_resp.status_code = 200
    mock_req.return_value = mock_resp
    result = get_transform_entry(auth_manager, server_config, {"entry_id": ENTRY_SYS_ID})
    assert not result["success"]
    assert "not found" in result["message"]


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_get_transform_entry_request_exception(mock_req):
    import requests
    auth_manager, server_config, _ = _make_mocks({})
    mock_req.side_effect = requests.exceptions.RequestException("timeout")
    result = get_transform_entry(auth_manager, server_config, {"entry_id": ENTRY_SYS_ID})
    assert not result["success"]
    assert "Error retrieving" in result["message"]


# ---------------------------------------------------------------------------
# create_transform_entry
# ---------------------------------------------------------------------------

def test_create_transform_entry_missing_required():
    auth_manager, server_config, _ = _make_mocks({})
    result = create_transform_entry(auth_manager, server_config, {"map_id": MAP_SYS_ID})
    assert not result["success"]


def test_create_transform_entry_no_instance_url():
    auth_manager = MagicMock()
    server_config = MagicMock()
    auth_manager.get_instance_url.return_value = None
    server_config.instance_url = None
    result = create_transform_entry(
        auth_manager,
        server_config,
        {"map_id": MAP_SYS_ID, "source_field": "u_name", "target_field": "name"},
    )
    assert not result["success"]


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_create_transform_entry_map_not_found(mock_req):
    auth_manager = MagicMock()
    server_config = MagicMock()
    auth_manager.get_instance_url.return_value = "https://instance.service-now.com"
    server_config.instance_url = "https://instance.service-now.com"
    auth_manager.get_headers.return_value = {"Authorization": "Bearer token"}

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = create_transform_entry(
        auth_manager,
        server_config,
        {"map_id": "NonExistentMap", "source_field": "u_name", "target_field": "name"},
    )
    assert not result["success"]
    assert "not found" in result["message"]


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_create_transform_entry_success(mock_req):
    auth_manager, server_config, mock_resp = _make_mocks({"result": SAMPLE_ENTRY})
    mock_req.return_value = mock_resp
    result = create_transform_entry(
        auth_manager,
        server_config,
        {
            "map_id": MAP_SYS_ID,
            "source_field": "user_name",
            "target_field": "name",
            "active": True,
            "coalesce": False,
            "coalesce_empty_fields": False,
            "default_value": "unknown",
            "type": "field",
            "order": 100,
        },
    )
    assert result["success"]
    assert result["transform_entry"]["source_field"] == "user_name"


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_create_transform_entry_with_script(mock_req):
    auth_manager, server_config, mock_resp = _make_mocks({"result": SAMPLE_ENTRY})
    mock_req.return_value = mock_resp
    result = create_transform_entry(
        auth_manager,
        server_config,
        {
            "map_id": MAP_SYS_ID,
            "source_field": "u_raw",
            "target_field": "processed",
            "type": "script",
            "script": "answer = source.u_raw.toUpperCase();",
        },
    )
    assert result["success"]
    # Verify script was in body
    call_kwargs = mock_req.call_args_list[-1]
    body = call_kwargs[1]["json"]
    assert body["script"] == "answer = source.u_raw.toUpperCase();"


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_create_transform_entry_request_exception(mock_req):
    import requests

    auth_manager = MagicMock()
    server_config = MagicMock()
    auth_manager.get_instance_url.return_value = "https://instance.service-now.com"
    server_config.instance_url = "https://instance.service-now.com"
    auth_manager.get_headers.return_value = {"Authorization": "Bearer token"}

    # First call (resolve map) succeeds, second call (POST) raises
    mock_resolve = MagicMock()
    mock_resolve.status_code = 200
    mock_resolve.json.return_value = {"result": [{"sys_id": MAP_SYS_ID}]}
    mock_resolve.raise_for_status = MagicMock()

    mock_req.side_effect = [mock_resolve, requests.exceptions.RequestException("connection error")]

    result = create_transform_entry(
        auth_manager,
        server_config,
        {"map_id": "User Import Map", "source_field": "u_name", "target_field": "name"},
    )
    assert not result["success"]
    assert "Error creating" in result["message"]


# ---------------------------------------------------------------------------
# update_transform_entry
# ---------------------------------------------------------------------------

def test_update_transform_entry_missing_entry_id():
    auth_manager, server_config, _ = _make_mocks({})
    result = update_transform_entry(auth_manager, server_config, {"active": True})
    assert not result["success"]


def test_update_transform_entry_no_fields():
    auth_manager, server_config, mock_resp = _make_mocks({"result": SAMPLE_ENTRY})
    with patch("servicenow_mcp.tools.transform_entry_tools._make_request") as mock_req:
        mock_req.return_value = mock_resp
        result = update_transform_entry(
            auth_manager, server_config, {"entry_id": ENTRY_SYS_ID}
        )
    assert not result["success"]
    assert "No fields" in result["message"]


def test_update_transform_entry_no_instance_url():
    auth_manager = MagicMock()
    server_config = MagicMock()
    auth_manager.get_instance_url.return_value = None
    server_config.instance_url = None
    result = update_transform_entry(
        auth_manager, server_config, {"entry_id": ENTRY_SYS_ID, "active": False}
    )
    assert not result["success"]


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_update_transform_entry_success(mock_req):
    auth_manager, server_config, mock_resp = _make_mocks({"result": SAMPLE_ENTRY})
    mock_req.return_value = mock_resp
    result = update_transform_entry(
        auth_manager,
        server_config,
        {
            "entry_id": ENTRY_SYS_ID,
            "active": False,
            "coalesce": True,
            "target_field": "first_name",
            "order": 200,
        },
    )
    assert result["success"]
    call_body = mock_req.call_args[1]["json"]
    assert call_body["active"] == "false"
    assert call_body["coalesce"] == "true"
    assert call_body["target_field"] == "first_name"
    assert call_body["order"] == "200"


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_update_transform_entry_404(mock_req):
    auth_manager, server_config, mock_resp = _make_mocks({})
    mock_resp.status_code = 404
    mock_req.return_value = mock_resp
    result = update_transform_entry(
        auth_manager, server_config, {"entry_id": ENTRY_SYS_ID, "active": True}
    )
    assert not result["success"]
    assert "not found" in result["message"]


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_update_transform_entry_request_exception(mock_req):
    import requests
    auth_manager, server_config, _ = _make_mocks({})
    mock_req.side_effect = requests.exceptions.RequestException("timeout")
    result = update_transform_entry(
        auth_manager, server_config, {"entry_id": ENTRY_SYS_ID, "source_field": "new_field"}
    )
    assert not result["success"]
    assert "Error updating" in result["message"]


@patch("servicenow_mcp.tools.transform_entry_tools._make_request")
def test_update_transform_entry_all_fields(mock_req):
    auth_manager, server_config, mock_resp = _make_mocks({"result": SAMPLE_ENTRY})
    mock_req.return_value = mock_resp
    result = update_transform_entry(
        auth_manager,
        server_config,
        {
            "entry_id": ENTRY_SYS_ID,
            "source_field": "u_email",
            "target_field": "email",
            "active": True,
            "coalesce": True,
            "coalesce_empty_fields": True,
            "default_value": "noreply@example.com",
            "type": "script",
            "value": "",
            "script": "answer = source.u_email.toLowerCase();",
            "order": 50,
        },
    )
    assert result["success"]
    body = mock_req.call_args[1]["json"]
    assert body["coalesce_empty_fields"] == "true"
    assert body["script"] == "answer = source.u_email.toLowerCase();"
