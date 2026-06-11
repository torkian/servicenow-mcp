"""Tests for role_tools.py."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from servicenow_mcp.tools.role_tools import (
    AssignRoleToGroupParams,
    GetGroupRolesParams,
    ListUserRolesParams,
    RemoveRoleFromGroupParams,
    _format_group_role,
    _format_user_role,
    _resolve_group_sys_id,
    _resolve_role_sys_id,
    _resolve_user_sys_id,
    assign_role_to_group,
    get_group_roles,
    list_user_roles,
    remove_role_from_group,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GROUP_SYS_ID = "a" * 32
USER_SYS_ID = "b" * 32
ROLE_SYS_ID = "c" * 32
MEMBER_SYS_ID = "d" * 32


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_manager():
    am = MagicMock()
    am.get_headers.return_value = {"Authorization": "Bearer test"}
    am.instance_url = "https://test.service-now.com"
    return am


@pytest.fixture
def server_config():
    sc = MagicMock()
    sc.instance_url = "https://test.service-now.com"
    return sc


RAW_GROUP_ROLE = {
    "sys_id": MEMBER_SYS_ID,
    "group": {"display_value": "Network Ops", "value": GROUP_SYS_ID},
    "role": {"display_value": "itil", "value": ROLE_SYS_ID},
    "sys_created_on": "2024-01-01 00:00:00",
}

RAW_USER_ROLE = {
    "sys_id": MEMBER_SYS_ID,
    "user": {"display_value": "Alice", "value": USER_SYS_ID},
    "role": {"display_value": "admin", "value": ROLE_SYS_ID},
    "inherited": "false",
    "granted_by": {"display_value": "itil", "value": ROLE_SYS_ID},
    "sys_created_on": "2024-03-01 00:00:00",
}


def _mock_response(data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# _format_group_role
# ---------------------------------------------------------------------------

class TestFormatGroupRole:
    def test_dict_reference_fields(self):
        out = _format_group_role(RAW_GROUP_ROLE)
        assert out["role_name"] == "itil"
        assert out["role_sys_id"] == ROLE_SYS_ID
        assert out["group_name"] == "Network Ops"
        assert out["group_sys_id"] == GROUP_SYS_ID

    def test_string_reference_fields(self):
        rec = dict(RAW_GROUP_ROLE, role="itil", group="Network Ops")
        out = _format_group_role(rec)
        assert out["role_name"] == "itil"
        assert out["group_name"] == "Network Ops"

    def test_missing_fields(self):
        out = _format_group_role({"sys_id": MEMBER_SYS_ID})
        assert out["role_name"] is None
        assert out["group_name"] is None

    def test_all_expected_keys(self):
        out = _format_group_role(RAW_GROUP_ROLE)
        assert set(out.keys()) == {"sys_id", "role_name", "role_sys_id", "group_name", "group_sys_id", "created_on"}


# ---------------------------------------------------------------------------
# _format_user_role
# ---------------------------------------------------------------------------

class TestFormatUserRole:
    def test_dict_reference_fields(self):
        out = _format_user_role(RAW_USER_ROLE)
        assert out["role_name"] == "admin"
        assert out["role_sys_id"] == ROLE_SYS_ID
        assert out["user"] == "Alice"
        assert out["user_sys_id"] == USER_SYS_ID
        assert out["granted_by"] == "itil"

    def test_string_reference_fields(self):
        rec = dict(RAW_USER_ROLE, user="bob", role="itil", granted_by=None)
        out = _format_user_role(rec)
        assert out["user"] == "bob"
        assert out["role_name"] == "itil"

    def test_missing_fields(self):
        out = _format_user_role({"sys_id": MEMBER_SYS_ID})
        assert out["role_name"] is None
        assert out["user"] is None

    def test_all_expected_keys(self):
        out = _format_user_role(RAW_USER_ROLE)
        assert set(out.keys()) == {
            "sys_id", "role_name", "role_sys_id", "user", "user_sys_id",
            "inherited", "granted_by", "created_on",
        }


# ---------------------------------------------------------------------------
# _resolve_group_sys_id
# ---------------------------------------------------------------------------

class TestResolveGroupSysId:
    def test_already_sys_id(self):
        result = _resolve_group_sys_id(GROUP_SYS_ID, "https://test.service-now.com", {})
        assert result == {"success": True, "sys_id": GROUP_SYS_ID}

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_name_lookup_success(self, mock_req):
        mock_req.return_value = _mock_response({"result": [{"sys_id": GROUP_SYS_ID}]})
        result = _resolve_group_sys_id("Network Ops", "https://test.service-now.com", {})
        assert result == {"success": True, "sys_id": GROUP_SYS_ID}

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_name_lookup_not_found(self, mock_req):
        mock_req.return_value = _mock_response({"result": []})
        result = _resolve_group_sys_id("Unknown", "https://test.service-now.com", {})
        assert not result["success"]

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_name_lookup_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError()
        result = _resolve_group_sys_id("Network Ops", "https://test.service-now.com", {})
        assert not result["success"]
        assert "Error looking up group" in result["message"]


# ---------------------------------------------------------------------------
# _resolve_user_sys_id
# ---------------------------------------------------------------------------

class TestResolveUserSysId:
    def test_already_sys_id(self):
        result = _resolve_user_sys_id(USER_SYS_ID, "https://test.service-now.com", {})
        assert result == {"success": True, "sys_id": USER_SYS_ID}

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_username_lookup_success(self, mock_req):
        mock_req.return_value = _mock_response({"result": [{"sys_id": USER_SYS_ID}]})
        result = _resolve_user_sys_id("alice", "https://test.service-now.com", {})
        assert result == {"success": True, "sys_id": USER_SYS_ID}

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_username_not_found(self, mock_req):
        mock_req.return_value = _mock_response({"result": []})
        result = _resolve_user_sys_id("nobody", "https://test.service-now.com", {})
        assert not result["success"]

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_lookup_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError()
        result = _resolve_user_sys_id("alice", "https://test.service-now.com", {})
        assert not result["success"]
        assert "Error looking up user" in result["message"]


# ---------------------------------------------------------------------------
# _resolve_role_sys_id
# ---------------------------------------------------------------------------

class TestResolveRoleSysId:
    def test_already_sys_id(self):
        result = _resolve_role_sys_id(ROLE_SYS_ID, "https://test.service-now.com", {})
        assert result == {"success": True, "sys_id": ROLE_SYS_ID}

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_name_lookup_success(self, mock_req):
        mock_req.return_value = _mock_response({"result": [{"sys_id": ROLE_SYS_ID}]})
        result = _resolve_role_sys_id("itil", "https://test.service-now.com", {})
        assert result == {"success": True, "sys_id": ROLE_SYS_ID}

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_name_not_found(self, mock_req):
        mock_req.return_value = _mock_response({"result": []})
        result = _resolve_role_sys_id("nonexistent_role", "https://test.service-now.com", {})
        assert not result["success"]
        assert "Role not found" in result["message"]

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_lookup_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.Timeout()
        result = _resolve_role_sys_id("itil", "https://test.service-now.com", {})
        assert not result["success"]
        assert "Error looking up role" in result["message"]


# ---------------------------------------------------------------------------
# get_group_roles
# ---------------------------------------------------------------------------

class TestGetGroupRoles:
    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_success_by_sys_id(self, mock_req, auth_manager, server_config):
        mock_req.return_value = _mock_response({"result": [RAW_GROUP_ROLE]})
        result = get_group_roles(auth_manager, server_config, {"group_id": GROUP_SYS_ID})
        assert result["success"]
        assert len(result["roles"]) == 1
        assert result["roles"][0]["role_name"] == "itil"

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_success_by_name(self, mock_req, auth_manager, server_config):
        lookup_resp = _mock_response({"result": [{"sys_id": GROUP_SYS_ID}]})
        list_resp = _mock_response({"result": [RAW_GROUP_ROLE]})
        mock_req.side_effect = [lookup_resp, list_resp]
        result = get_group_roles(auth_manager, server_config, {"group_id": "Network Ops"})
        assert result["success"]
        assert result["roles"][0]["group_sys_id"] == GROUP_SYS_ID

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_empty_list(self, mock_req, auth_manager, server_config):
        mock_req.return_value = _mock_response({"result": []})
        result = get_group_roles(auth_manager, server_config, {"group_id": GROUP_SYS_ID})
        assert result["success"]
        assert result["roles"] == []

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_pagination_full_page(self, mock_req, auth_manager, server_config):
        # exactly limit items returned → has_more=True (there may be more)
        roles = [dict(RAW_GROUP_ROLE, sys_id=f"{'e' * 30}{i:02d}") for i in range(20)]
        mock_req.return_value = _mock_response({"result": roles})
        result = get_group_roles(
            auth_manager, server_config, {"group_id": GROUP_SYS_ID, "limit": 20, "offset": 0}
        )
        assert result["success"]
        assert result["has_more"] is True
        assert result["next_offset"] == 20

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_pagination_partial_page(self, mock_req, auth_manager, server_config):
        # fewer than limit items → has_more=False (end of results)
        roles = [dict(RAW_GROUP_ROLE, sys_id=f"{'e' * 30}{i:02d}") for i in range(5)]
        mock_req.return_value = _mock_response({"result": roles})
        result = get_group_roles(
            auth_manager, server_config, {"group_id": GROUP_SYS_ID, "limit": 20, "offset": 0}
        )
        assert result["success"]
        assert result["has_more"] is False

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_group_not_found(self, mock_req, auth_manager, server_config):
        mock_req.return_value = _mock_response({"result": []})
        result = get_group_roles(auth_manager, server_config, {"group_id": "Unknown Group"})
        assert not result["success"]
        assert "not found" in result["message"]

    def test_missing_group_id(self, auth_manager, server_config):
        result = get_group_roles(auth_manager, server_config, {})
        assert not result["success"]

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_request_error(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = [
            _mock_response({"result": [{"sys_id": GROUP_SYS_ID}]}),
            requests.exceptions.ConnectionError(),
        ]
        result = get_group_roles(auth_manager, server_config, {"group_id": "Network Ops"})
        assert not result["success"]
        assert "Error listing group roles" in result["message"]


# ---------------------------------------------------------------------------
# assign_role_to_group
# ---------------------------------------------------------------------------

class TestAssignRoleToGroup:
    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_success_by_sys_ids(self, mock_req, auth_manager, server_config):
        mock_req.return_value = _mock_response({"result": {"sys_id": MEMBER_SYS_ID}})
        result = assign_role_to_group(
            auth_manager, server_config, {"group_id": GROUP_SYS_ID, "role_id": ROLE_SYS_ID}
        )
        assert result["success"]
        assert result["member_sys_id"] == MEMBER_SYS_ID
        assert result["group_sys_id"] == GROUP_SYS_ID
        assert result["role_sys_id"] == ROLE_SYS_ID

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_success_by_names(self, mock_req, auth_manager, server_config):
        lookup_group = _mock_response({"result": [{"sys_id": GROUP_SYS_ID}]})
        lookup_role = _mock_response({"result": [{"sys_id": ROLE_SYS_ID}]})
        post_resp = _mock_response({"result": {"sys_id": MEMBER_SYS_ID}})
        mock_req.side_effect = [lookup_group, lookup_role, post_resp]
        result = assign_role_to_group(
            auth_manager, server_config, {"group_id": "Help Desk", "role_id": "itil"}
        )
        assert result["success"]
        assert "successfully" in result["message"]

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_group_not_found(self, mock_req, auth_manager, server_config):
        mock_req.return_value = _mock_response({"result": []})
        result = assign_role_to_group(
            auth_manager, server_config, {"group_id": "Ghost Group", "role_id": ROLE_SYS_ID}
        )
        assert not result["success"]

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_role_not_found(self, mock_req, auth_manager, server_config):
        lookup_group = _mock_response({"result": [{"sys_id": GROUP_SYS_ID}]})
        lookup_role = _mock_response({"result": []})
        mock_req.side_effect = [lookup_group, lookup_role]
        result = assign_role_to_group(
            auth_manager, server_config, {"group_id": "Help Desk", "role_id": "ghost_role"}
        )
        assert not result["success"]
        assert "Role not found" in result["message"]

    def test_missing_required_params(self, auth_manager, server_config):
        result = assign_role_to_group(auth_manager, server_config, {"group_id": GROUP_SYS_ID})
        assert not result["success"]

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_post_error(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = [
            _mock_response({"result": [{"sys_id": GROUP_SYS_ID}]}),
            _mock_response({"result": [{"sys_id": ROLE_SYS_ID}]}),
            requests.exceptions.ConnectionError(),
        ]
        result = assign_role_to_group(
            auth_manager, server_config, {"group_id": "Help Desk", "role_id": "itil"}
        )
        assert not result["success"]
        assert "Error assigning role" in result["message"]


# ---------------------------------------------------------------------------
# remove_role_from_group
# ---------------------------------------------------------------------------

class TestRemoveRoleFromGroup:
    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_success_204(self, mock_req, auth_manager, server_config):
        mock_req.return_value = _mock_response({}, status_code=204)
        result = remove_role_from_group(
            auth_manager, server_config, {"member_sys_id": MEMBER_SYS_ID}
        )
        assert result["success"]
        assert "successfully" in result["message"]

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_success_200(self, mock_req, auth_manager, server_config):
        mock_req.return_value = _mock_response({"result": {}}, status_code=200)
        result = remove_role_from_group(
            auth_manager, server_config, {"member_sys_id": MEMBER_SYS_ID}
        )
        assert result["success"]

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_not_found_404(self, mock_req, auth_manager, server_config):
        resp = _mock_response({}, status_code=404)
        mock_req.return_value = resp
        result = remove_role_from_group(
            auth_manager, server_config, {"member_sys_id": MEMBER_SYS_ID}
        )
        assert not result["success"]
        assert "not found" in result["message"]

    def test_missing_member_sys_id(self, auth_manager, server_config):
        result = remove_role_from_group(auth_manager, server_config, {})
        assert not result["success"]

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_request_error(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.Timeout()
        result = remove_role_from_group(
            auth_manager, server_config, {"member_sys_id": MEMBER_SYS_ID}
        )
        assert not result["success"]
        assert "Error removing role" in result["message"]


# ---------------------------------------------------------------------------
# list_user_roles
# ---------------------------------------------------------------------------

class TestListUserRoles:
    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_success_by_sys_id(self, mock_req, auth_manager, server_config):
        mock_req.return_value = _mock_response({"result": [RAW_USER_ROLE]})
        result = list_user_roles(auth_manager, server_config, {"user_id": USER_SYS_ID})
        assert result["success"]
        assert len(result["roles"]) == 1
        assert result["roles"][0]["role_name"] == "admin"

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_success_by_username(self, mock_req, auth_manager, server_config):
        lookup_resp = _mock_response({"result": [{"sys_id": USER_SYS_ID}]})
        list_resp = _mock_response({"result": [RAW_USER_ROLE]})
        mock_req.side_effect = [lookup_resp, list_resp]
        result = list_user_roles(auth_manager, server_config, {"user_id": "alice"})
        assert result["success"]
        assert result["roles"][0]["user_sys_id"] == USER_SYS_ID

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_filter_inherited_true(self, mock_req, auth_manager, server_config):
        mock_req.return_value = _mock_response({"result": []})
        result = list_user_roles(
            auth_manager, server_config,
            {"user_id": USER_SYS_ID, "include_inherited": True},
        )
        assert result["success"]
        call_params = mock_req.call_args[1]["params"]
        assert "inherited=true" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_filter_inherited_false(self, mock_req, auth_manager, server_config):
        mock_req.return_value = _mock_response({"result": []})
        result = list_user_roles(
            auth_manager, server_config,
            {"user_id": USER_SYS_ID, "include_inherited": False},
        )
        assert result["success"]
        call_params = mock_req.call_args[1]["params"]
        assert "inherited=false" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_empty_list(self, mock_req, auth_manager, server_config):
        mock_req.return_value = _mock_response({"result": []})
        result = list_user_roles(auth_manager, server_config, {"user_id": USER_SYS_ID})
        assert result["success"]
        assert result["roles"] == []

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_user_not_found(self, mock_req, auth_manager, server_config):
        mock_req.return_value = _mock_response({"result": []})
        result = list_user_roles(auth_manager, server_config, {"user_id": "nobody"})
        assert not result["success"]
        assert "not found" in result["message"]

    def test_missing_user_id(self, auth_manager, server_config):
        result = list_user_roles(auth_manager, server_config, {})
        assert not result["success"]

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_request_error(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = [
            _mock_response({"result": [{"sys_id": USER_SYS_ID}]}),
            requests.exceptions.ConnectionError(),
        ]
        result = list_user_roles(auth_manager, server_config, {"user_id": "alice"})
        assert not result["success"]
        assert "Error listing user roles" in result["message"]

    @patch("servicenow_mcp.tools.role_tools._make_request")
    def test_pagination_has_more(self, mock_req, auth_manager, server_config):
        # exactly limit items returned → has_more=True (ServiceNow may have more)
        roles = [dict(RAW_USER_ROLE, sys_id=f"{'e' * 30}{i:02d}") for i in range(20)]
        mock_req.return_value = _mock_response({"result": roles})
        result = list_user_roles(
            auth_manager, server_config, {"user_id": USER_SYS_ID, "limit": 20, "offset": 0}
        )
        assert result["success"]
        assert result["has_more"] is True
        assert result["next_offset"] == 20
