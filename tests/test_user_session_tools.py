"""Tests for user_session_tools.py (sys_user_session table)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.user_session_tools import (
    _format_user_session,
    _resolve_user_sys_id_for_session,
    get_user_session,
    list_user_sessions,
)

# ---------------------------------------------------------------------------
# Constants / fixtures
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://instance.service-now.com"
SESSION_SYS_ID = "a" * 32
USER_SYS_ID = "b" * 32


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


RAW_SESSION = {
    "sys_id": SESSION_SYS_ID,
    "user": {"display_value": "jdoe", "value": USER_SYS_ID},
    "session_id": "sess_abc123",
    "logged_in": "2026-09-20 08:00:00",
    "last_request": "2026-09-20 09:30:00",
    "ip_address": "10.0.0.1",
    "user_agent": "Mozilla/5.0",
    "browser": "Chrome",
    "os_type": "Windows",
    "screen_size": "1920x1080",
    "sys_created_on": "2026-09-20 08:00:00",
    "sys_updated_on": "2026-09-20 09:30:00",
}


# ---------------------------------------------------------------------------
# _format_user_session
# ---------------------------------------------------------------------------


def test_format_user_session_basic():
    result = _format_user_session(RAW_SESSION)
    assert result["sys_id"] == SESSION_SYS_ID
    assert result["user"] == "jdoe"
    assert result["session_id"] == "sess_abc123"
    assert result["logged_in"] == "2026-09-20 08:00:00"
    assert result["last_request"] == "2026-09-20 09:30:00"
    assert result["ip_address"] == "10.0.0.1"
    assert result["browser"] == "Chrome"
    assert result["os_type"] == "Windows"
    assert result["screen_size"] == "1920x1080"
    assert result["created_on"] == "2026-09-20 08:00:00"
    assert result["updated_on"] == "2026-09-20 09:30:00"


def test_format_user_session_plain_user_string():
    record = dict(RAW_SESSION)
    record["user"] = "jdoe"
    result = _format_user_session(record)
    assert result["user"] == "jdoe"


def test_format_user_session_user_dict_value_fallback():
    record = dict(RAW_SESSION)
    record["user"] = {"display_value": "", "value": USER_SYS_ID}
    result = _format_user_session(record)
    assert result["user"] == USER_SYS_ID


def test_format_user_session_missing_fields():
    result = _format_user_session({})
    assert result["sys_id"] is None
    assert result["user"] is None
    assert result["ip_address"] is None


# ---------------------------------------------------------------------------
# _resolve_user_sys_id_for_session
# ---------------------------------------------------------------------------


def test_resolve_user_sys_id_passthrough_hex():
    resolved = _resolve_user_sys_id_for_session(USER_SYS_ID, INSTANCE_URL, {})
    assert resolved == USER_SYS_ID


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_resolve_user_sys_id_by_username(mock_req):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": [{"sys_id": USER_SYS_ID}]}
    mock_req.return_value = mock_response
    result = _resolve_user_sys_id_for_session("jdoe", INSTANCE_URL, {"Authorization": "Bearer t"})
    assert result == USER_SYS_ID


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_resolve_user_sys_id_not_found(mock_req):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": []}
    mock_req.return_value = mock_response
    result = _resolve_user_sys_id_for_session("unknown_user", INSTANCE_URL, {})
    assert result is None


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_resolve_user_sys_id_request_exception(mock_req):
    import requests
    mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
    result = _resolve_user_sys_id_for_session("jdoe", INSTANCE_URL, {})
    assert result is None


# ---------------------------------------------------------------------------
# list_user_sessions
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_list_user_sessions_no_filters(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": [RAW_SESSION]}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = list_user_sessions(auth_manager, config, {"limit": 20, "offset": 0})
    assert result["success"] is True
    assert len(result["sessions"]) == 1
    assert result["sessions"][0]["sys_id"] == SESSION_SYS_ID
    assert result["count"] == 1


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_list_user_sessions_with_user_id_hex(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": [RAW_SESSION]}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = list_user_sessions(auth_manager, config, {"user_id": USER_SYS_ID})
    assert result["success"] is True
    call_params = mock_req.call_args[1]["params"]
    assert f"user={USER_SYS_ID}" in call_params.get("sysparm_query", "")


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_list_user_sessions_with_username(mock_req, auth_manager, config):
    user_resp = MagicMock()
    user_resp.json.return_value = {"result": [{"sys_id": USER_SYS_ID}]}
    user_resp.raise_for_status.return_value = None

    sessions_resp = MagicMock()
    sessions_resp.json.return_value = {"result": [RAW_SESSION]}
    sessions_resp.raise_for_status.return_value = None

    mock_req.side_effect = [user_resp, sessions_resp]

    result = list_user_sessions(auth_manager, config, {"user_id": "jdoe"})
    assert result["success"] is True
    assert result["count"] == 1


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_list_user_sessions_user_not_found(mock_req, auth_manager, config):
    user_resp = MagicMock()
    user_resp.json.return_value = {"result": []}
    user_resp.raise_for_status.return_value = None
    mock_req.return_value = user_resp

    result = list_user_sessions(auth_manager, config, {"user_id": "ghost_user"})
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_list_user_sessions_with_ip_filter(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": [RAW_SESSION]}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = list_user_sessions(auth_manager, config, {"ip_address": "10.0.0.1"})
    assert result["success"] is True
    call_params = mock_req.call_args[1]["params"]
    assert "ip_address=10.0.0.1" in call_params.get("sysparm_query", "")


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_list_user_sessions_with_logged_in_after(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": []}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = list_user_sessions(auth_manager, config, {"logged_in_after": "2026-09-20"})
    assert result["success"] is True
    call_params = mock_req.call_args[1]["params"]
    assert "logged_in>=2026-09-20" in call_params.get("sysparm_query", "")


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_list_user_sessions_pagination(mock_req, auth_manager, config):
    # When API returns exactly limit items, has_more=True indicating there may be more
    sessions = [dict(RAW_SESSION, sys_id=f"{'a' * 30}{i:02d}") for i in range(20)]
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": sessions}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = list_user_sessions(auth_manager, config, {"limit": 20, "offset": 0})
    assert result["success"] is True
    assert result.get("has_more") is True
    assert result.get("next_offset") == 20


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_list_user_sessions_http_error(mock_req, auth_manager, config):
    import requests
    mock_req.side_effect = requests.exceptions.HTTPError("500 Server Error")

    result = list_user_sessions(auth_manager, config, {})
    assert result["success"] is False
    assert "error" in result["message"].lower()


def test_list_user_sessions_no_instance_url(auth_manager, config):
    config.instance_url = None
    auth_manager.instance_url = None
    result = list_user_sessions(auth_manager, config, {})
    assert result["success"] is False


def test_list_user_sessions_no_headers(auth_manager, config):
    auth_manager.get_headers.return_value = None
    result = list_user_sessions(auth_manager, config, {})
    assert result["success"] is False


# ---------------------------------------------------------------------------
# get_user_session
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_get_user_session_success(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": RAW_SESSION}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = get_user_session(auth_manager, config, {"session_id": SESSION_SYS_ID})
    assert result["success"] is True
    assert result["session"]["sys_id"] == SESSION_SYS_ID
    assert result["session"]["user"] == "jdoe"


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_get_user_session_not_found_404(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_req.return_value = mock_response

    result = get_user_session(auth_manager, config, {"session_id": "nonexistent"})
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_get_user_session_empty_result(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": None}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = get_user_session(auth_manager, config, {"session_id": SESSION_SYS_ID})
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_session_tools._make_request")
def test_get_user_session_http_error(mock_req, auth_manager, config):
    import requests
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
    mock_req.return_value = mock_response

    result = get_user_session(auth_manager, config, {"session_id": SESSION_SYS_ID})
    assert result["success"] is False
    assert "error" in result["message"].lower()


def test_get_user_session_missing_required_field(auth_manager, config):
    result = get_user_session(auth_manager, config, {})
    assert result["success"] is False


def test_get_user_session_no_instance_url(auth_manager, config):
    config.instance_url = None
    auth_manager.instance_url = None
    result = get_user_session(auth_manager, config, {"session_id": SESSION_SYS_ID})
    assert result["success"] is False


def test_get_user_session_no_headers(auth_manager, config):
    auth_manager.get_headers.return_value = None
    result = get_user_session(auth_manager, config, {"session_id": SESSION_SYS_ID})
    assert result["success"] is False
