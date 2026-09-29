"""Tests for the create_kb_category tool."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.knowledge_base import (
    CreateKBCategoryParams,
    create_kb_category,
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
    resp.raise_for_status = MagicMock()
    return resp


def _make_category_result(sys_id="abc123", label="My Category", kb_sys_id="kb1", parent_sys_id=None):
    parent = {"display_value": "Parent Cat", "value": parent_sys_id} if parent_sys_id else ""
    return {
        "sys_id": sys_id,
        "label": {"display_value": label, "value": label},
        "description": {"display_value": "A test category"},
        "kb_knowledge_base": {"display_value": "IT KB", "value": kb_sys_id},
        "parent": parent,
        "active": "true",
    }


class TestCreateKBCategorySuccess:
    def test_creates_category_with_name_resolution(self, server_config, auth_manager):
        kb_resp = _make_response(200, {"result": [{"sys_id": "kb_sys_id_1", "title": "IT KB"}]})
        post_resp = _make_response(201, {"result": _make_category_result(kb_sys_id="kb_sys_id_1")})

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request",
            side_effect=[kb_resp, post_resp],
        ):
            result = create_kb_category(
                server_config,
                auth_manager,
                CreateKBCategoryParams(name="My Category", knowledge_base="IT KB"),
            )

        assert result["success"] is True
        assert "My Category" in result["message"]
        assert result["category"]["sys_id"] == "abc123"
        assert result["category"]["label"] == "My Category"
        assert result["category"]["active"] is True

    def test_creates_category_with_kb_sys_id(self, server_config, auth_manager):
        kb_sys_id = "a" * 32
        post_resp = _make_response(201, {"result": _make_category_result(kb_sys_id=kb_sys_id)})

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request",
            side_effect=[post_resp],
        ):
            result = create_kb_category(
                server_config,
                auth_manager,
                CreateKBCategoryParams(name="My Category", knowledge_base=kb_sys_id),
            )

        assert result["success"] is True

    def test_creates_subcategory_with_parent_name_resolution(self, server_config, auth_manager):
        kb_resp = _make_response(200, {"result": [{"sys_id": "kb1"}]})
        parent_resp = _make_response(200, {"result": [{"sys_id": "parent1", "label": "Root"}]})
        post_resp = _make_response(
            201,
            {"result": _make_category_result(kb_sys_id="kb1", parent_sys_id="parent1")},
        )

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request",
            side_effect=[kb_resp, parent_resp, post_resp],
        ):
            result = create_kb_category(
                server_config,
                auth_manager,
                CreateKBCategoryParams(
                    name="Sub Cat", knowledge_base="IT KB", parent="Root"
                ),
            )

        assert result["success"] is True
        assert result["category"]["parent_category_sys_id"] == "parent1"

    def test_creates_category_with_description(self, server_config, auth_manager):
        kb_resp = _make_response(200, {"result": [{"sys_id": "kb1"}]})
        post_resp = _make_response(201, {"result": _make_category_result()})

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request",
            side_effect=[kb_resp, post_resp],
        ):
            result = create_kb_category(
                server_config,
                auth_manager,
                CreateKBCategoryParams(
                    name="My Category",
                    knowledge_base="IT KB",
                    description="Detailed description",
                ),
            )

        assert result["success"] is True

    def test_creates_inactive_category(self, server_config, auth_manager):
        kb_resp = _make_response(200, {"result": [{"sys_id": "kb1"}]})
        result_data = _make_category_result()
        result_data["active"] = "false"
        post_resp = _make_response(201, {"result": result_data})

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request",
            side_effect=[kb_resp, post_resp],
        ):
            result = create_kb_category(
                server_config,
                auth_manager,
                CreateKBCategoryParams(
                    name="My Category", knowledge_base="IT KB", active=False
                ),
            )

        assert result["success"] is True
        assert result["category"]["active"] is False

    def test_response_normalises_string_fields(self, server_config, auth_manager):
        kb_sys_id = "b" * 32
        result_data = {
            "sys_id": "xyz",
            "label": "Plain Label",
            "description": "Plain desc",
            "kb_knowledge_base": kb_sys_id,
            "parent": "",
            "active": "true",
        }
        post_resp = _make_response(201, {"result": result_data})

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request",
            side_effect=[post_resp],
        ):
            result = create_kb_category(
                server_config,
                auth_manager,
                CreateKBCategoryParams(name="Plain Label", knowledge_base=kb_sys_id),
            )

        assert result["success"] is True
        assert result["category"]["label"] == "Plain Label"
        assert result["category"]["description"] == "Plain desc"
        assert result["category"]["knowledge_base_sys_id"] == kb_sys_id


class TestCreateKBCategoryNotFound:
    def test_kb_not_found_returns_error(self, server_config, auth_manager):
        kb_resp = _make_response(200, {"result": []})

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request",
            side_effect=[kb_resp],
        ):
            result = create_kb_category(
                server_config,
                auth_manager,
                CreateKBCategoryParams(name="Cat", knowledge_base="Unknown KB"),
            )

        assert result["success"] is False
        assert "Unknown KB" in result["message"]

    def test_parent_not_found_returns_error(self, server_config, auth_manager):
        kb_resp = _make_response(200, {"result": [{"sys_id": "kb1"}]})
        parent_resp = _make_response(200, {"result": []})

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request",
            side_effect=[kb_resp, parent_resp],
        ):
            result = create_kb_category(
                server_config,
                auth_manager,
                CreateKBCategoryParams(
                    name="Cat", knowledge_base="IT KB", parent="Missing Parent"
                ),
            )

        assert result["success"] is False
        assert "Missing Parent" in result["message"]


class TestCreateKBCategoryErrors:
    def test_post_http_error_returns_failure(self, server_config, auth_manager):
        kb_sys_id = "c" * 32
        err_resp = MagicMock()
        err_resp.status_code = 403
        err_resp.raise_for_status.side_effect = requests.HTTPError(
            response=err_resp
        )
        err_resp.json.return_value = {
            "error": {"message": "Insufficient privileges", "detail": ""}
        }

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request",
            return_value=err_resp,
        ):
            result = create_kb_category(
                server_config,
                auth_manager,
                CreateKBCategoryParams(name="Cat", knowledge_base=kb_sys_id),
            )

        assert result["success"] is False
        assert "Failed to create KB category" in result["message"]

    def test_request_exception_on_kb_lookup_returns_failure(self, server_config, auth_manager):
        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request",
            side_effect=requests.ConnectionError("timeout"),
        ):
            result = create_kb_category(
                server_config,
                auth_manager,
                CreateKBCategoryParams(name="Cat", knowledge_base="Some KB"),
            )

        assert result["success"] is False
        assert "not found" in result["message"]


class TestCreateKBCategoryParams:
    def test_required_fields(self):
        params = CreateKBCategoryParams(name="Cat", knowledge_base="IT KB")
        assert params.name == "Cat"
        assert params.knowledge_base == "IT KB"
        assert params.active is True
        assert params.parent is None
        assert params.description is None

    def test_all_fields(self):
        params = CreateKBCategoryParams(
            name="Sub Cat",
            knowledge_base="IT KB",
            parent="Root",
            active=False,
            description="Some desc",
        )
        assert params.parent == "Root"
        assert params.active is False
        assert params.description == "Some desc"

    def test_missing_name_raises(self):
        with pytest.raises(Exception):
            CreateKBCategoryParams(knowledge_base="IT KB")

    def test_missing_kb_raises(self):
        with pytest.raises(Exception):
            CreateKBCategoryParams(name="Cat")
