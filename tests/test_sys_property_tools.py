"""Tests for sys_property_tools.py (sys_properties table)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.sys_property_tools import (
    DeletePropertyParams,
    GetPropertyParams,
    ListPropertiesParams,
    SetPropertyParams,
    _format_property,
    _resolve_property_sys_id,
    delete_property,
    get_property,
    list_properties,
    set_property,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://instance.service-now.com"
PROP_SYS_ID = "a" * 32


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


RAW_PROP = {
    "sys_id": PROP_SYS_ID,
    "name": "glide.email.smtp.host",
    "value": "smtp.example.com",
    "type": "string",
    "description": "SMTP server hostname",
    "suffix": None,
    "category": "email",
    "choices": None,
    "read_roles": "admin",
    "write_roles": "admin",
    "private": "false",
    "ignore_cache": "false",
    "encrypt": "false",
    "sys_created_on": "2024-01-10 08:00:00",
    "sys_updated_on": "2024-06-01 12:00:00",
}


# ---------------------------------------------------------------------------
# _format_property
# ---------------------------------------------------------------------------


def test_format_property_basic():
    result = _format_property(RAW_PROP)
    assert result["sys_id"] == PROP_SYS_ID
    assert result["name"] == "glide.email.smtp.host"
    assert result["value"] == "smtp.example.com"
    assert result["type"] == "string"
    assert result["description"] == "SMTP server hostname"
    assert result["category"] == "email"
    assert result["read_roles"] == "admin"
    assert result["write_roles"] == "admin"
    assert result["private"] == "false"
    assert result["encrypt"] == "false"
    assert result["created_on"] == "2024-01-10 08:00:00"
    assert result["updated_on"] == "2024-06-01 12:00:00"


def test_format_property_missing_fields():
    result = _format_property({})
    assert result["sys_id"] is None
    assert result["name"] is None
    assert result["value"] is None


# ---------------------------------------------------------------------------
# _resolve_property_sys_id
# ---------------------------------------------------------------------------


def test_resolve_property_sys_id_is_hex():
    """A 32-char hex string is returned as-is without an HTTP call."""
    result = _resolve_property_sys_id(PROP_SYS_ID, INSTANCE_URL, {})
    assert result == PROP_SYS_ID


def test_resolve_property_sys_id_by_name_found():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"sys_id": PROP_SYS_ID}]}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=mock_resp):
        result = _resolve_property_sys_id("glide.email.smtp.host", INSTANCE_URL, {})
    assert result == PROP_SYS_ID


def test_resolve_property_sys_id_by_name_not_found():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=mock_resp):
        result = _resolve_property_sys_id("nonexistent.prop", INSTANCE_URL, {})
    assert result is None


def test_resolve_property_sys_id_request_exception():
    import requests
    with patch(
        "servicenow_mcp.tools.sys_property_tools._make_request",
        side_effect=requests.exceptions.RequestException("timeout"),
    ):
        result = _resolve_property_sys_id("some.prop", INSTANCE_URL, {})
    assert result is None


# ---------------------------------------------------------------------------
# list_properties
# ---------------------------------------------------------------------------


def test_list_properties_success(auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_PROP]}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=mock_resp):
        result = list_properties(auth_manager, server_config, {})
    assert result["success"] is True
    assert len(result["properties"]) == 1
    assert result["properties"][0]["name"] == "glide.email.smtp.host"


def test_list_properties_with_filters(auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_PROP]}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=mock_resp) as mock_req:
        result = list_properties(
            auth_manager,
            server_config,
            {"name": "glide.email", "category": "email", "type": "string"},
        )
    assert result["success"] is True
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "") or call_kwargs[0][2].get("sysparm_query", "")
    assert "nameLIKEglide.email" in query
    assert "category=email" in query
    assert "type=string" in query


def test_list_properties_empty(auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=mock_resp):
        result = list_properties(auth_manager, server_config, {})
    assert result["success"] is True
    assert result["properties"] == []


def test_list_properties_no_instance_url(server_config):
    am = MagicMock()
    am.instance_url = None
    am.get_headers.return_value = {}
    server_config.instance_url = None
    result = list_properties(am, server_config, {})
    assert result["success"] is False
    assert "instance_url" in result["message"]


def test_list_properties_no_headers(server_config):
    am = MagicMock()
    am.instance_url = INSTANCE_URL
    am.get_headers.return_value = None
    result = list_properties(am, server_config, {})
    assert result["success"] is False
    assert "get_headers" in result["message"]


def test_list_properties_request_exception(auth_manager, server_config):
    import requests
    with patch(
        "servicenow_mcp.tools.sys_property_tools._make_request",
        side_effect=requests.exceptions.RequestException("conn error"),
    ):
        result = list_properties(auth_manager, server_config, {})
    assert result["success"] is False
    assert "Error" in result["message"]


# ---------------------------------------------------------------------------
# get_property
# ---------------------------------------------------------------------------


def test_get_property_by_sys_id(auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_PROP}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=mock_resp):
        result = get_property(auth_manager, server_config, {"property_id": PROP_SYS_ID})
    assert result["success"] is True
    assert result["property"]["name"] == "glide.email.smtp.host"


def test_get_property_by_name(auth_manager, server_config):
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": PROP_SYS_ID}]}
    resolve_resp.raise_for_status = MagicMock()

    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json.return_value = {"result": RAW_PROP}
    get_resp.raise_for_status = MagicMock()

    with patch(
        "servicenow_mcp.tools.sys_property_tools._make_request",
        side_effect=[resolve_resp, get_resp],
    ):
        result = get_property(
            auth_manager, server_config, {"property_id": "glide.email.smtp.host"}
        )
    assert result["success"] is True
    assert result["property"]["value"] == "smtp.example.com"


def test_get_property_not_found(auth_manager, server_config):
    with patch(
        "servicenow_mcp.tools.sys_property_tools._resolve_property_sys_id",
        return_value=None,
    ):
        result = get_property(
            auth_manager, server_config, {"property_id": "missing.prop"}
        )
    assert result["success"] is False
    assert "not found" in result["message"]


def test_get_property_404(auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=mock_resp):
        result = get_property(auth_manager, server_config, {"property_id": PROP_SYS_ID})
    assert result["success"] is False
    assert "not found" in result["message"]


def test_get_property_empty_result(auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": None}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=mock_resp):
        result = get_property(auth_manager, server_config, {"property_id": PROP_SYS_ID})
    assert result["success"] is False
    assert "not found" in result["message"]


def test_get_property_no_instance_url(server_config):
    am = MagicMock()
    am.instance_url = None
    am.get_headers.return_value = {}
    server_config.instance_url = None
    result = get_property(am, server_config, {"property_id": PROP_SYS_ID})
    assert result["success"] is False


def test_get_property_no_headers(server_config):
    am = MagicMock()
    am.instance_url = INSTANCE_URL
    am.get_headers.return_value = None
    result = get_property(am, server_config, {"property_id": PROP_SYS_ID})
    assert result["success"] is False


def test_get_property_request_exception(auth_manager, server_config):
    import requests
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": PROP_SYS_ID}]}
    resolve_resp.raise_for_status = MagicMock()

    with patch(
        "servicenow_mcp.tools.sys_property_tools._make_request",
        side_effect=[resolve_resp, requests.exceptions.RequestException("err")],
    ):
        result = get_property(
            auth_manager, server_config, {"property_id": "some.prop"}
        )
    assert result["success"] is False


# ---------------------------------------------------------------------------
# set_property — create path
# ---------------------------------------------------------------------------


def test_set_property_create(auth_manager, server_config):
    """When no existing property is found, a new one is POSTed."""
    post_resp = MagicMock()
    post_resp.status_code = 201
    post_resp.json.return_value = {"result": RAW_PROP}
    post_resp.raise_for_status = MagicMock()

    with patch(
        "servicenow_mcp.tools.sys_property_tools._resolve_property_sys_id",
        return_value=None,
    ):
        with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=post_resp):
            result = set_property(
                auth_manager,
                server_config,
                {"name": "glide.email.smtp.host", "value": "smtp.example.com"},
            )
    assert result["success"] is True
    assert result["action"] == "created"
    assert result["property"]["name"] == "glide.email.smtp.host"


def test_set_property_update(auth_manager, server_config):
    """When an existing property is found, it is PATCHed."""
    patch_resp = MagicMock()
    patch_resp.status_code = 200
    patch_resp.json.return_value = {"result": RAW_PROP}
    patch_resp.raise_for_status = MagicMock()

    with patch(
        "servicenow_mcp.tools.sys_property_tools._resolve_property_sys_id",
        return_value=PROP_SYS_ID,
    ):
        with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=patch_resp):
            result = set_property(
                auth_manager,
                server_config,
                {"name": "glide.email.smtp.host", "value": "smtp2.example.com"},
            )
    assert result["success"] is True
    assert result["action"] == "updated"


def test_set_property_update_404(auth_manager, server_config):
    patch_resp = MagicMock()
    patch_resp.status_code = 404

    with patch(
        "servicenow_mcp.tools.sys_property_tools._resolve_property_sys_id",
        return_value=PROP_SYS_ID,
    ):
        with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=patch_resp):
            result = set_property(
                auth_manager,
                server_config,
                {"name": "glide.email.smtp.host", "value": "x"},
            )
    assert result["success"] is False
    assert "not found" in result["message"]


def test_set_property_with_all_optional_fields(auth_manager, server_config):
    """Optional fields (type, category, private, encrypt, roles) are included in body."""
    post_resp = MagicMock()
    post_resp.status_code = 201
    post_resp.json.return_value = {"result": RAW_PROP}
    post_resp.raise_for_status = MagicMock()

    with patch(
        "servicenow_mcp.tools.sys_property_tools._resolve_property_sys_id",
        return_value=None,
    ):
        with patch(
            "servicenow_mcp.tools.sys_property_tools._make_request", return_value=post_resp
        ) as mock_req:
            result = set_property(
                auth_manager,
                server_config,
                {
                    "name": "my.prop",
                    "value": "val",
                    "description": "Test",
                    "type": "true_false",
                    "category": "test",
                    "private": True,
                    "encrypt": False,
                    "read_roles": "admin",
                    "write_roles": "admin",
                },
            )
    assert result["success"] is True
    body = mock_req.call_args[1]["json"]
    assert body["type"] == "true_false"
    assert body["category"] == "test"
    assert body["private"] == "true"
    assert body["encrypt"] == "false"
    assert body["read_roles"] == "admin"
    assert body["description"] == "Test"


def test_set_property_no_instance_url(server_config):
    am = MagicMock()
    am.instance_url = None
    am.get_headers.return_value = {}
    server_config.instance_url = None
    result = set_property(am, server_config, {"name": "x", "value": "y"})
    assert result["success"] is False


def test_set_property_no_headers(server_config):
    am = MagicMock()
    am.instance_url = INSTANCE_URL
    am.get_headers.return_value = None
    result = set_property(am, server_config, {"name": "x", "value": "y"})
    assert result["success"] is False


def test_set_property_request_exception(auth_manager, server_config):
    import requests
    with patch(
        "servicenow_mcp.tools.sys_property_tools._resolve_property_sys_id",
        return_value=None,
    ):
        with patch(
            "servicenow_mcp.tools.sys_property_tools._make_request",
            side_effect=requests.exceptions.RequestException("net err"),
        ):
            result = set_property(auth_manager, server_config, {"name": "x", "value": "y"})
    assert result["success"] is False


# ---------------------------------------------------------------------------
# delete_property
# ---------------------------------------------------------------------------


def test_delete_property_success(auth_manager, server_config):
    del_resp = MagicMock()
    del_resp.status_code = 204
    del_resp.raise_for_status = MagicMock()

    with patch(
        "servicenow_mcp.tools.sys_property_tools._resolve_property_sys_id",
        return_value=PROP_SYS_ID,
    ):
        with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=del_resp):
            result = delete_property(
                auth_manager, server_config, {"property_id": PROP_SYS_ID}
            )
    assert result["success"] is True
    assert "deleted" in result["message"]


def test_delete_property_200(auth_manager, server_config):
    del_resp = MagicMock()
    del_resp.status_code = 200
    del_resp.raise_for_status = MagicMock()

    with patch(
        "servicenow_mcp.tools.sys_property_tools._resolve_property_sys_id",
        return_value=PROP_SYS_ID,
    ):
        with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=del_resp):
            result = delete_property(
                auth_manager, server_config, {"property_id": PROP_SYS_ID}
            )
    assert result["success"] is True


def test_delete_property_404(auth_manager, server_config):
    del_resp = MagicMock()
    del_resp.status_code = 404

    with patch(
        "servicenow_mcp.tools.sys_property_tools._resolve_property_sys_id",
        return_value=PROP_SYS_ID,
    ):
        with patch("servicenow_mcp.tools.sys_property_tools._make_request", return_value=del_resp):
            result = delete_property(
                auth_manager, server_config, {"property_id": PROP_SYS_ID}
            )
    assert result["success"] is False
    assert "not found" in result["message"]


def test_delete_property_not_found_resolve(auth_manager, server_config):
    with patch(
        "servicenow_mcp.tools.sys_property_tools._resolve_property_sys_id",
        return_value=None,
    ):
        result = delete_property(
            auth_manager, server_config, {"property_id": "missing.prop"}
        )
    assert result["success"] is False
    assert "not found" in result["message"]


def test_delete_property_no_instance_url(server_config):
    am = MagicMock()
    am.instance_url = None
    am.get_headers.return_value = {}
    server_config.instance_url = None
    result = delete_property(am, server_config, {"property_id": "x"})
    assert result["success"] is False


def test_delete_property_no_headers(server_config):
    am = MagicMock()
    am.instance_url = INSTANCE_URL
    am.get_headers.return_value = None
    result = delete_property(am, server_config, {"property_id": "x"})
    assert result["success"] is False


def test_delete_property_request_exception(auth_manager, server_config):
    import requests
    with patch(
        "servicenow_mcp.tools.sys_property_tools._resolve_property_sys_id",
        return_value=PROP_SYS_ID,
    ):
        with patch(
            "servicenow_mcp.tools.sys_property_tools._make_request",
            side_effect=requests.exceptions.RequestException("err"),
        ):
            result = delete_property(
                auth_manager, server_config, {"property_id": PROP_SYS_ID}
            )
    assert result["success"] is False


# ---------------------------------------------------------------------------
# Param model validation
# ---------------------------------------------------------------------------


def test_list_properties_params_defaults():
    p = ListPropertiesParams()
    assert p.limit == 20
    assert p.offset == 0
    assert p.name is None
    assert p.category is None
    assert p.type is None


def test_get_property_params_required():
    with pytest.raises(Exception):
        GetPropertyParams()


def test_set_property_params_required():
    with pytest.raises(Exception):
        SetPropertyParams()


def test_delete_property_params_required():
    with pytest.raises(Exception):
        DeletePropertyParams()


def test_set_property_params_optional_defaults():
    p = SetPropertyParams(name="my.prop", value="val")
    assert p.type is None
    assert p.category is None
    assert p.private is None
    assert p.encrypt is None
