"""Tests for user_preference_tools.py (sys_user_preference table)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.user_preference_tools import (
    DeleteUserPreferenceParams,
    GetUserPreferenceParams,
    ListUserPreferencesParams,
    SetUserPreferenceParams,
    _find_preference_sys_id,
    _format_user_preference,
    _resolve_user_sys_id,
    delete_user_preference,
    get_user_preference,
    list_user_preferences,
    set_user_preference,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://instance.service-now.com"
USER_SYS_ID = "a" * 32  # valid 32-char hex string (skips username lookup)
PREF_SYS_ID = "b" * 32  # valid 32-char hex string


@pytest.fixture
def auth_manager():
    am = MagicMock()
    am.instance_url = INSTANCE_URL
    am.get_headers.return_value = {"Authorization": "Bearer token"}
    return am


@pytest.fixture
def server_config():
    sc = MagicMock()
    sc.instance_url = None
    return sc


RAW_PREF = {
    "sys_id": "b" * 32,
    "user": {"display_value": "jsmith", "value": "a" * 32},
    "name": "rowcount",
    "value": "50",
    "type": "integer",
    "system": "false",
    "description": "Rows per page",
    "sys_created_on": "2024-01-10 08:00:00",
    "sys_updated_on": "2024-06-01 12:00:00",
}


# ---------------------------------------------------------------------------
# _format_user_preference
# ---------------------------------------------------------------------------


def test_format_user_preference_with_dict_user():
    result = _format_user_preference(RAW_PREF)
    assert result["sys_id"] == PREF_SYS_ID
    assert result["user"] == "jsmith"
    assert result["name"] == "rowcount"
    assert result["value"] == "50"
    assert result["system"] == "false"
    assert result["description"] == "Rows per page"
    assert result["created_on"] == "2024-01-10 08:00:00"
    assert result["updated_on"] == "2024-06-01 12:00:00"


def test_format_user_preference_with_string_user():
    raw = dict(RAW_PREF, user="jsmith")
    result = _format_user_preference(raw)
    assert result["user"] == "jsmith"


def test_format_user_preference_user_value_fallback():
    raw = dict(RAW_PREF, user={"display_value": "", "value": USER_SYS_ID})
    result = _format_user_preference(raw)
    assert result["user"] == USER_SYS_ID


# ---------------------------------------------------------------------------
# _resolve_user_sys_id
# ---------------------------------------------------------------------------


def test_resolve_user_sys_id_returns_hex_unchanged():
    hex_id = "a" * 32
    result = _resolve_user_sys_id(hex_id, INSTANCE_URL, {})
    assert result == hex_id


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_resolve_user_sys_id_by_username(mock_req):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"sys_id": USER_SYS_ID}]}
    mock_req.return_value = mock_resp
    result = _resolve_user_sys_id("jsmith", INSTANCE_URL, {"Authorization": "Bearer token"})
    assert result == USER_SYS_ID


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_resolve_user_sys_id_not_found(mock_req):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_req.return_value = mock_resp
    result = _resolve_user_sys_id("nobody", INSTANCE_URL, {})
    assert result is None


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_resolve_user_sys_id_request_error(mock_req):
    import requests
    mock_req.side_effect = requests.exceptions.ConnectionError("fail")
    result = _resolve_user_sys_id("jsmith", INSTANCE_URL, {})
    assert result is None


# ---------------------------------------------------------------------------
# _find_preference_sys_id
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_find_preference_sys_id_found(mock_req):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"sys_id": PREF_SYS_ID}]}
    mock_req.return_value = mock_resp
    result = _find_preference_sys_id(USER_SYS_ID, "rowcount", INSTANCE_URL, {})
    assert result == PREF_SYS_ID


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_find_preference_sys_id_not_found(mock_req):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_req.return_value = mock_resp
    result = _find_preference_sys_id(USER_SYS_ID, "nopref", INSTANCE_URL, {})
    assert result is None


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_find_preference_sys_id_request_error(mock_req):
    import requests
    mock_req.side_effect = requests.exceptions.ConnectionError("fail")
    result = _find_preference_sys_id(USER_SYS_ID, "rowcount", INSTANCE_URL, {})
    assert result is None


# ---------------------------------------------------------------------------
# get_user_preference
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_get_user_preference_success(mock_req, auth_manager, server_config):
    # _resolve_user_sys_id: hex ID passthrough; then list lookup for pref
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": [RAW_PREF]}
    mock_req.return_value = mock_resp

    result = get_user_preference(auth_manager, server_config, {"user_id": USER_SYS_ID, "name": "rowcount"})
    assert result["success"] is True
    assert result["preference"]["name"] == "rowcount"


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_get_user_preference_not_found(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": []}
    mock_req.return_value = mock_resp

    result = get_user_preference(auth_manager, server_config, {"user_id": USER_SYS_ID, "name": "nopref"})
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_get_user_preference_user_not_found(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_req.return_value = mock_resp

    result = get_user_preference(auth_manager, server_config, {"user_id": "nobody", "name": "rowcount"})
    assert result["success"] is False
    assert "user not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_get_user_preference_request_error(mock_req, auth_manager, server_config):
    import requests
    # First call (user lookup – but user_id is hex so no lookup needed)
    mock_req.side_effect = requests.exceptions.ConnectionError("fail")

    result = get_user_preference(auth_manager, server_config, {"user_id": USER_SYS_ID, "name": "rowcount"})
    assert result["success"] is False


def test_get_user_preference_no_instance_url(server_config):
    am = MagicMock()
    am.instance_url = None
    am.get_headers.return_value = None
    server_config.instance_url = None
    result = get_user_preference(am, server_config, {"user_id": USER_SYS_ID, "name": "x"})
    assert result["success"] is False


def test_get_user_preference_missing_required_field(auth_manager, server_config):
    result = get_user_preference(auth_manager, server_config, {"user_id": USER_SYS_ID})
    assert result["success"] is False


# ---------------------------------------------------------------------------
# set_user_preference — create path
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.user_preference_tools._find_preference_sys_id")
@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_set_user_preference_creates(mock_req, mock_find, auth_manager, server_config):
    mock_find.return_value = None  # no existing preference
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"result": RAW_PREF}
    mock_req.return_value = mock_resp

    result = set_user_preference(
        auth_manager, server_config,
        {"user_id": USER_SYS_ID, "name": "rowcount", "value": "50"},
    )
    assert result["success"] is True
    assert result["action"] == "created"
    assert result["preference"]["name"] == "rowcount"


@patch("servicenow_mcp.tools.user_preference_tools._find_preference_sys_id")
@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_set_user_preference_updates(mock_req, mock_find, auth_manager, server_config):
    mock_find.return_value = PREF_SYS_ID  # existing preference found
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_PREF}
    mock_req.return_value = mock_resp

    result = set_user_preference(
        auth_manager, server_config,
        {"user_id": USER_SYS_ID, "name": "rowcount", "value": "100"},
    )
    assert result["success"] is True
    assert result["action"] == "updated"


@patch("servicenow_mcp.tools.user_preference_tools._find_preference_sys_id")
@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_set_user_preference_update_404(mock_req, mock_find, auth_manager, server_config):
    mock_find.return_value = PREF_SYS_ID
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_req.return_value = mock_resp

    result = set_user_preference(
        auth_manager, server_config,
        {"user_id": USER_SYS_ID, "name": "rowcount", "value": "100"},
    )
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_preference_tools._find_preference_sys_id")
@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_set_user_preference_with_optional_fields(mock_req, mock_find, auth_manager, server_config):
    mock_find.return_value = None
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"result": RAW_PREF}
    mock_req.return_value = mock_resp

    result = set_user_preference(
        auth_manager, server_config,
        {
            "user_id": USER_SYS_ID,
            "name": "rowcount",
            "value": "50",
            "description": "Rows per page",
            "system": False,
        },
    )
    assert result["success"] is True
    # Verify system field sent as string
    call_kwargs = mock_req.call_args
    body = call_kwargs[1].get("json", {})
    assert body.get("system") == "false"


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_set_user_preference_user_not_found(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_req.return_value = mock_resp

    result = set_user_preference(
        auth_manager, server_config,
        {"user_id": "nobody", "name": "rowcount", "value": "50"},
    )
    assert result["success"] is False
    assert "user not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_preference_tools._find_preference_sys_id")
@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_set_user_preference_request_error(mock_req, mock_find, auth_manager, server_config):
    import requests
    mock_find.return_value = None
    mock_req.side_effect = requests.exceptions.ConnectionError("fail")

    result = set_user_preference(
        auth_manager, server_config,
        {"user_id": USER_SYS_ID, "name": "rowcount", "value": "50"},
    )
    assert result["success"] is False


def test_set_user_preference_missing_required(auth_manager, server_config):
    result = set_user_preference(auth_manager, server_config, {"user_id": USER_SYS_ID, "name": "x"})
    assert result["success"] is False


# ---------------------------------------------------------------------------
# delete_user_preference
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.user_preference_tools._find_preference_sys_id")
@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_delete_user_preference_success_204(mock_req, mock_find, auth_manager, server_config):
    mock_find.return_value = PREF_SYS_ID
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_req.return_value = mock_resp

    result = delete_user_preference(auth_manager, server_config, {"user_id": USER_SYS_ID, "name": "rowcount"})
    assert result["success"] is True
    assert "deleted" in result["message"].lower()


@patch("servicenow_mcp.tools.user_preference_tools._find_preference_sys_id")
@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_delete_user_preference_success_200(mock_req, mock_find, auth_manager, server_config):
    mock_find.return_value = PREF_SYS_ID
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_req.return_value = mock_resp

    result = delete_user_preference(auth_manager, server_config, {"user_id": USER_SYS_ID, "name": "rowcount"})
    assert result["success"] is True


@patch("servicenow_mcp.tools.user_preference_tools._find_preference_sys_id")
@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_delete_user_preference_404_on_delete(mock_req, mock_find, auth_manager, server_config):
    mock_find.return_value = PREF_SYS_ID
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_req.return_value = mock_resp

    result = delete_user_preference(auth_manager, server_config, {"user_id": USER_SYS_ID, "name": "rowcount"})
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_preference_tools._find_preference_sys_id")
def test_delete_user_preference_pref_not_found(mock_find, auth_manager, server_config):
    mock_find.return_value = None

    result = delete_user_preference(auth_manager, server_config, {"user_id": USER_SYS_ID, "name": "nopref"})
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_delete_user_preference_user_not_found(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_req.return_value = mock_resp

    result = delete_user_preference(auth_manager, server_config, {"user_id": "nobody", "name": "rowcount"})
    assert result["success"] is False
    assert "user not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_preference_tools._find_preference_sys_id")
@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_delete_user_preference_request_error(mock_req, mock_find, auth_manager, server_config):
    import requests
    mock_find.return_value = PREF_SYS_ID
    mock_req.side_effect = requests.exceptions.ConnectionError("fail")

    result = delete_user_preference(auth_manager, server_config, {"user_id": USER_SYS_ID, "name": "rowcount"})
    assert result["success"] is False


def test_delete_user_preference_missing_required(auth_manager, server_config):
    result = delete_user_preference(auth_manager, server_config, {"user_id": USER_SYS_ID})
    assert result["success"] is False


def test_delete_user_preference_no_instance_url(server_config):
    am = MagicMock()
    am.instance_url = None
    am.get_headers.return_value = None
    server_config.instance_url = None
    result = delete_user_preference(am, server_config, {"user_id": USER_SYS_ID, "name": "rowcount"})
    assert result["success"] is False


# ---------------------------------------------------------------------------
# list_user_preferences
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_list_user_preferences_all(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": [RAW_PREF, RAW_PREF]}
    mock_req.return_value = mock_resp

    result = list_user_preferences(auth_manager, server_config, {})
    assert result["success"] is True
    assert result["count"] == 2
    assert len(result["preferences"]) == 2


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_list_user_preferences_filtered_by_user(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": [RAW_PREF]}
    mock_req.return_value = mock_resp

    result = list_user_preferences(auth_manager, server_config, {"user_id": USER_SYS_ID})
    assert result["success"] is True
    assert result["count"] == 1


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_list_user_preferences_filtered_by_name(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": [RAW_PREF]}
    mock_req.return_value = mock_resp

    result = list_user_preferences(auth_manager, server_config, {"name": "row"})
    assert result["success"] is True
    # Verify nameLIKE used in query
    call_kwargs = mock_req.call_args[1]
    assert "nameLIKErow" in call_kwargs.get("params", {}).get("sysparm_query", "")


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_list_user_preferences_user_not_found(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_req.return_value = mock_resp

    result = list_user_preferences(auth_manager, server_config, {"user_id": "nobody"})
    assert result["success"] is False
    assert "user not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_list_user_preferences_request_error(mock_req, auth_manager, server_config):
    import requests
    mock_req.side_effect = requests.exceptions.ConnectionError("fail")

    result = list_user_preferences(auth_manager, server_config, {})
    assert result["success"] is False


@patch("servicenow_mcp.tools.user_preference_tools._make_request")
def test_list_user_preferences_has_more(mock_req, auth_manager, server_config):
    prefs = [RAW_PREF] * 5
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": prefs}
    mock_req.return_value = mock_resp

    result = list_user_preferences(auth_manager, server_config, {"limit": 5, "offset": 0})
    assert result["success"] is True
    assert result.get("has_more") is True


def test_list_user_preferences_no_instance_url(server_config):
    am = MagicMock()
    am.instance_url = None
    am.get_headers.return_value = None
    server_config.instance_url = None
    result = list_user_preferences(am, server_config, {})
    assert result["success"] is False


# ---------------------------------------------------------------------------
# Parameter model validation
# ---------------------------------------------------------------------------


def test_get_user_preference_params_required_fields():
    with pytest.raises(Exception):
        GetUserPreferenceParams()


def test_set_user_preference_params_required_fields():
    with pytest.raises(Exception):
        SetUserPreferenceParams(user_id="x", name="y")  # missing value


def test_delete_user_preference_params_required_fields():
    with pytest.raises(Exception):
        DeleteUserPreferenceParams(user_id="x")  # missing name


def test_list_user_preferences_params_defaults():
    p = ListUserPreferencesParams()
    assert p.limit == 20
    assert p.offset == 0
    assert p.user_id is None
    assert p.name is None
