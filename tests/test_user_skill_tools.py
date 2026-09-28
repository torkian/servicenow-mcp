"""Tests for user_skill_tools.py (sys_user_has_skill table)."""

import pytest
import requests
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.user_skill_tools import (
    _format_user_skill,
    _resolve_skill_sys_id,
    _resolve_user_sys_id,
    get_user_skill,
    list_user_skills,
)

# ---------------------------------------------------------------------------
# Constants / fixtures
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://instance.service-now.com"
USER_SKILL_SYS_ID = "a" * 32
USER_SYS_ID = "b" * 32
SKILL_SYS_ID = "c" * 32


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


RAW_USER_SKILL = {
    "sys_id": USER_SKILL_SYS_ID,
    "user": {"display_value": "jdoe", "value": USER_SYS_ID},
    "skill": {"display_value": "Python", "value": SKILL_SYS_ID},
    "level": "3",
    "sys_created_on": "2026-09-01 10:00:00",
    "sys_updated_on": "2026-09-15 14:30:00",
}


# ---------------------------------------------------------------------------
# _format_user_skill
# ---------------------------------------------------------------------------


def test_format_user_skill_basic():
    result = _format_user_skill(RAW_USER_SKILL)
    assert result["sys_id"] == USER_SKILL_SYS_ID
    assert result["user"] == "jdoe"
    assert result["skill"] == "Python"
    assert result["skill_sys_id"] == SKILL_SYS_ID
    assert result["level"] == "3"
    assert result["created_on"] == "2026-09-01 10:00:00"
    assert result["updated_on"] == "2026-09-15 14:30:00"


def test_format_user_skill_plain_string_user():
    record = dict(RAW_USER_SKILL)
    record["user"] = "jdoe"
    result = _format_user_skill(record)
    assert result["user"] == "jdoe"


def test_format_user_skill_plain_string_skill():
    record = dict(RAW_USER_SKILL)
    record["skill"] = "Python"
    result = _format_user_skill(record)
    assert result["skill"] == "Python"
    assert result["skill_sys_id"] == "Python"


def test_format_user_skill_missing_fields():
    result = _format_user_skill({})
    assert result["sys_id"] is None
    assert result["user"] is None
    assert result["skill"] is None
    assert result["skill_sys_id"] is None
    assert result["level"] is None


# ---------------------------------------------------------------------------
# _resolve_user_sys_id
# ---------------------------------------------------------------------------


def test_resolve_user_sys_id_passthrough_hex():
    resolved = _resolve_user_sys_id(USER_SYS_ID, INSTANCE_URL, {})
    assert resolved == USER_SYS_ID


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_resolve_user_sys_id_by_username(mock_req):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": [{"sys_id": USER_SYS_ID}]}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response
    result = _resolve_user_sys_id("jdoe", INSTANCE_URL, {"Authorization": "Bearer t"})
    assert result == USER_SYS_ID


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_resolve_user_sys_id_not_found(mock_req):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": []}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response
    result = _resolve_user_sys_id("ghost_user", INSTANCE_URL, {})
    assert result is None


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_resolve_user_sys_id_request_exception(mock_req):
    mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
    result = _resolve_user_sys_id("jdoe", INSTANCE_URL, {})
    assert result is None


# ---------------------------------------------------------------------------
# _resolve_skill_sys_id
# ---------------------------------------------------------------------------


def test_resolve_skill_sys_id_passthrough_hex():
    resolved = _resolve_skill_sys_id(SKILL_SYS_ID, INSTANCE_URL, {})
    assert resolved == SKILL_SYS_ID


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_resolve_skill_sys_id_by_name(mock_req):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": [{"sys_id": SKILL_SYS_ID}]}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response
    result = _resolve_skill_sys_id("Python", INSTANCE_URL, {"Authorization": "Bearer t"})
    assert result == SKILL_SYS_ID


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_resolve_skill_sys_id_not_found(mock_req):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": []}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response
    result = _resolve_skill_sys_id("UnknownSkill", INSTANCE_URL, {})
    assert result is None


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_resolve_skill_sys_id_request_exception(mock_req):
    mock_req.side_effect = requests.exceptions.ConnectionError("network error")
    result = _resolve_skill_sys_id("Python", INSTANCE_URL, {})
    assert result is None


# ---------------------------------------------------------------------------
# list_user_skills
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_list_user_skills_no_filters(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": [RAW_USER_SKILL]}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = list_user_skills(auth_manager, config, {"limit": 20, "offset": 0})
    assert result["success"] is True
    assert len(result["skills"]) == 1
    assert result["skills"][0]["sys_id"] == USER_SKILL_SYS_ID
    assert result["count"] == 1


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_list_user_skills_with_user_id_hex(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": [RAW_USER_SKILL]}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = list_user_skills(auth_manager, config, {"user_id": USER_SYS_ID})
    assert result["success"] is True
    call_params = mock_req.call_args[1]["params"]
    assert f"user={USER_SYS_ID}" in call_params.get("sysparm_query", "")


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_list_user_skills_with_username(mock_req, auth_manager, config):
    user_resp = MagicMock()
    user_resp.json.return_value = {"result": [{"sys_id": USER_SYS_ID}]}
    user_resp.raise_for_status.return_value = None

    skills_resp = MagicMock()
    skills_resp.json.return_value = {"result": [RAW_USER_SKILL]}
    skills_resp.raise_for_status.return_value = None

    mock_req.side_effect = [user_resp, skills_resp]

    result = list_user_skills(auth_manager, config, {"user_id": "jdoe"})
    assert result["success"] is True
    assert result["count"] == 1


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_list_user_skills_user_not_found(mock_req, auth_manager, config):
    user_resp = MagicMock()
    user_resp.json.return_value = {"result": []}
    user_resp.raise_for_status.return_value = None
    mock_req.return_value = user_resp

    result = list_user_skills(auth_manager, config, {"user_id": "ghost_user"})
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_list_user_skills_with_skill_id_hex(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": [RAW_USER_SKILL]}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = list_user_skills(auth_manager, config, {"skill_id": SKILL_SYS_ID})
    assert result["success"] is True
    call_params = mock_req.call_args[1]["params"]
    assert f"skill={SKILL_SYS_ID}" in call_params.get("sysparm_query", "")


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_list_user_skills_with_skill_name(mock_req, auth_manager, config):
    skill_resp = MagicMock()
    skill_resp.json.return_value = {"result": [{"sys_id": SKILL_SYS_ID}]}
    skill_resp.raise_for_status.return_value = None

    skills_resp = MagicMock()
    skills_resp.json.return_value = {"result": [RAW_USER_SKILL]}
    skills_resp.raise_for_status.return_value = None

    mock_req.side_effect = [skill_resp, skills_resp]

    result = list_user_skills(auth_manager, config, {"skill_id": "Python"})
    assert result["success"] is True
    assert result["count"] == 1


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_list_user_skills_skill_not_found(mock_req, auth_manager, config):
    skill_resp = MagicMock()
    skill_resp.json.return_value = {"result": []}
    skill_resp.raise_for_status.return_value = None
    mock_req.return_value = skill_resp

    result = list_user_skills(auth_manager, config, {"skill_id": "NonexistentSkill"})
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_list_user_skills_with_level_filter(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": [RAW_USER_SKILL]}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = list_user_skills(auth_manager, config, {"level": "3"})
    assert result["success"] is True
    call_params = mock_req.call_args[1]["params"]
    assert "level=3" in call_params.get("sysparm_query", "")


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_list_user_skills_pagination(mock_req, auth_manager, config):
    skills = [dict(RAW_USER_SKILL, sys_id=f"{'a' * 30}{i:02d}") for i in range(20)]
    mock_response = MagicMock()
    mock_response.json.return_value = {"result": skills}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = list_user_skills(auth_manager, config, {"limit": 20, "offset": 0})
    assert result["success"] is True
    assert result.get("has_more") is True
    assert result.get("next_offset") == 20


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_list_user_skills_http_error(mock_req, auth_manager, config):
    mock_req.side_effect = requests.exceptions.HTTPError("500 Server Error")

    result = list_user_skills(auth_manager, config, {})
    assert result["success"] is False
    assert "error" in result["message"].lower()


def test_list_user_skills_no_instance_url(auth_manager, config):
    config.instance_url = None
    auth_manager.instance_url = None
    result = list_user_skills(auth_manager, config, {})
    assert result["success"] is False


def test_list_user_skills_no_headers(auth_manager, config):
    auth_manager.get_headers.return_value = None
    result = list_user_skills(auth_manager, config, {})
    assert result["success"] is False


# ---------------------------------------------------------------------------
# get_user_skill
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_get_user_skill_success(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": RAW_USER_SKILL}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = get_user_skill(auth_manager, config, {"user_skill_id": USER_SKILL_SYS_ID})
    assert result["success"] is True
    assert result["skill"]["sys_id"] == USER_SKILL_SYS_ID
    assert result["skill"]["user"] == "jdoe"
    assert result["skill"]["skill"] == "Python"
    assert result["skill"]["level"] == "3"


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_get_user_skill_not_found_404(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_req.return_value = mock_response

    result = get_user_skill(auth_manager, config, {"user_skill_id": "nonexistent"})
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_get_user_skill_empty_result(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": None}
    mock_response.raise_for_status.return_value = None
    mock_req.return_value = mock_response

    result = get_user_skill(auth_manager, config, {"user_skill_id": USER_SKILL_SYS_ID})
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@patch("servicenow_mcp.tools.user_skill_tools._make_request")
def test_get_user_skill_http_error(mock_req, auth_manager, config):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
    mock_req.return_value = mock_response

    result = get_user_skill(auth_manager, config, {"user_skill_id": USER_SKILL_SYS_ID})
    assert result["success"] is False
    assert "error" in result["message"].lower()


def test_get_user_skill_missing_required_field(auth_manager, config):
    result = get_user_skill(auth_manager, config, {})
    assert result["success"] is False


def test_get_user_skill_no_instance_url(auth_manager, config):
    config.instance_url = None
    auth_manager.instance_url = None
    result = get_user_skill(auth_manager, config, {"user_skill_id": USER_SKILL_SYS_ID})
    assert result["success"] is False


def test_get_user_skill_no_headers(auth_manager, config):
    auth_manager.get_headers.return_value = None
    result = get_user_skill(auth_manager, config, {"user_skill_id": USER_SKILL_SYS_ID})
    assert result["success"] is False
