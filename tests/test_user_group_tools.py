"""Tests for user_group_tools.py."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from servicenow_mcp.tools.user_group_tools import (
    AddUserToGroupParams,
    GetUserGroupParams,
    ListGroupMembersParams,
    ListUserGroupsParams,
    RemoveUserFromGroupParams,
    _format_group_member,
    _format_user_group,
    _resolve_group_sys_id,
    _resolve_user_sys_id,
    add_user_to_group,
    get_user_group,
    list_group_members,
    list_user_groups,
    remove_user_from_group,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GROUP_SYS_ID = "a" * 32
USER_SYS_ID = "b" * 32
MEMBER_SYS_ID = "c" * 32


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


RAW_GROUP = {
    "sys_id": GROUP_SYS_ID,
    "name": "Network Ops",
    "description": "Network operations team",
    "manager": {"display_value": "Alice", "value": USER_SYS_ID},
    "parent": {"display_value": "IT", "value": "d" * 32},
    "type": "itil",
    "email": "netops@example.com",
    "active": "true",
    "sys_created_on": "2024-01-01 00:00:00",
    "sys_updated_on": "2024-06-01 00:00:00",
}

RAW_MEMBER = {
    "sys_id": MEMBER_SYS_ID,
    "group": {"display_value": "Network Ops", "value": GROUP_SYS_ID},
    "user": {"display_value": "Bob", "value": USER_SYS_ID},
    "sys_created_on": "2024-01-15 00:00:00",
}


def _mock_response(data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# _format_user_group
# ---------------------------------------------------------------------------

class TestFormatUserGroup:
    def test_dict_reference_fields(self):
        out = _format_user_group(RAW_GROUP)
        assert out["manager"] == "Alice"
        assert out["parent"] == "IT"

    def test_string_reference_fields(self):
        rec = dict(RAW_GROUP, manager="Charlie", parent="")
        out = _format_user_group(rec)
        assert out["manager"] == "Charlie"
        assert out["parent"] == ""

    def test_missing_fields(self):
        out = _format_user_group({"sys_id": GROUP_SYS_ID})
        assert out["name"] is None
        assert out["manager"] is None

    def test_all_expected_keys(self):
        out = _format_user_group(RAW_GROUP)
        for key in ("sys_id", "name", "description", "manager", "parent", "type", "email", "active", "created_on", "updated_on"):
            assert key in out


# ---------------------------------------------------------------------------
# _format_group_member
# ---------------------------------------------------------------------------

class TestFormatGroupMember:
    def test_dict_reference_fields(self):
        out = _format_group_member(RAW_MEMBER)
        assert out["group"] == "Network Ops"
        assert out["user"] == "Bob"
        assert out["user_sys_id"] == USER_SYS_ID

    def test_string_user_field(self):
        rec = dict(RAW_MEMBER, user="carol")
        out = _format_group_member(rec)
        assert out["user"] == "carol"
        assert out["user_sys_id"] == "carol"

    def test_all_expected_keys(self):
        out = _format_group_member(RAW_MEMBER)
        for key in ("sys_id", "group", "user", "user_sys_id", "created_on"):
            assert key in out


# ---------------------------------------------------------------------------
# _resolve_group_sys_id
# ---------------------------------------------------------------------------

class TestResolveGroupSysId:
    def test_passes_through_sys_id(self):
        result = _resolve_group_sys_id(GROUP_SYS_ID, "https://x", {})
        assert result == {"success": True, "sys_id": GROUP_SYS_ID}

    @patch("servicenow_mcp.tools.user_group_tools._make_request")
    def test_name_lookup_success(self, mock_req):
        mock_req.return_value = _mock_response({"result": [{"sys_id": GROUP_SYS_ID}]})
        result = _resolve_group_sys_id("Network Ops", "https://x", {})
        assert result == {"success": True, "sys_id": GROUP_SYS_ID}

    @patch("servicenow_mcp.tools.user_group_tools._make_request")
    def test_name_lookup_not_found(self, mock_req):
        mock_req.return_value = _mock_response({"result": []})
        result = _resolve_group_sys_id("Unknown", "https://x", {})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.user_group_tools._make_request")
    def test_name_lookup_request_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        result = _resolve_group_sys_id("Network Ops", "https://x", {})
        assert result["success"] is False
        assert "Error looking up group" in result["message"]


# ---------------------------------------------------------------------------
# _resolve_user_sys_id
# ---------------------------------------------------------------------------

class TestResolveUserSysId:
    def test_passes_through_sys_id(self):
        result = _resolve_user_sys_id(USER_SYS_ID, "https://x", {})
        assert result == {"success": True, "sys_id": USER_SYS_ID}

    @patch("servicenow_mcp.tools.user_group_tools._make_request")
    def test_username_lookup_success(self, mock_req):
        mock_req.return_value = _mock_response({"result": [{"sys_id": USER_SYS_ID}]})
        result = _resolve_user_sys_id("alice", "https://x", {})
        assert result == {"success": True, "sys_id": USER_SYS_ID}

    @patch("servicenow_mcp.tools.user_group_tools._make_request")
    def test_username_lookup_not_found(self, mock_req):
        mock_req.return_value = _mock_response({"result": []})
        result = _resolve_user_sys_id("nobody", "https://x", {})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.user_group_tools._make_request")
    def test_username_lookup_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.Timeout()
        result = _resolve_user_sys_id("alice", "https://x", {})
        assert result["success"] is False
        assert "Error looking up user" in result["message"]


# ---------------------------------------------------------------------------
# list_user_groups
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.user_group_tools._make_request")
@patch("servicenow_mcp.tools.user_group_tools._get_headers")
@patch("servicenow_mcp.tools.user_group_tools._get_instance_url")
class TestListUserGroups:
    def test_success_default_params(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": [RAW_GROUP]})

        result = list_user_groups(auth_manager, server_config, {})
        assert result["success"] is True
        assert len(result["groups"]) == 1
        assert result["groups"][0]["name"] == "Network Ops"
        assert "has_more" in result

    def test_filters_applied(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": []})

        list_user_groups(auth_manager, server_config, {"name": "Net", "active": True, "manager": "Alice"})
        call_params = mock_req.call_args[1]["params"]
        assert "nameLIKENet" in call_params.get("sysparm_query", "")
        assert "active=true" in call_params.get("sysparm_query", "")

    def test_query_filter(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": []})

        list_user_groups(auth_manager, server_config, {"query": "ops"})
        call_params = mock_req.call_args[1]["params"]
        assert "nameLIKEops" in call_params.get("sysparm_query", "")

    def test_pagination(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": [RAW_GROUP] * 5})

        result = list_user_groups(auth_manager, server_config, {"limit": 5, "offset": 10})
        assert result["offset"] == 10

    def test_no_instance_url(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = None
        result = list_user_groups(auth_manager, server_config, {})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = None
        result = list_user_groups(auth_manager, server_config, {})
        assert result["success"] is False

    def test_request_error(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.side_effect = requests.exceptions.ConnectionError("down")

        result = list_user_groups(auth_manager, server_config, {})
        assert result["success"] is False
        assert "Error listing user groups" in result["message"]

    def test_empty_results(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": []})

        result = list_user_groups(auth_manager, server_config, {})
        assert result["success"] is True
        assert result["groups"] == []
        assert result["has_more"] is False


# ---------------------------------------------------------------------------
# get_user_group
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.user_group_tools._make_request")
@patch("servicenow_mcp.tools.user_group_tools._get_headers")
@patch("servicenow_mcp.tools.user_group_tools._get_instance_url")
class TestGetUserGroup:
    def test_by_sys_id_success(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": RAW_GROUP})

        result = get_user_group(auth_manager, server_config, {"group_id": GROUP_SYS_ID})
        assert result["success"] is True
        assert result["group"]["name"] == "Network Ops"

    def test_by_sys_id_404(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        resp = _mock_response({}, status_code=404)
        mock_req.return_value = resp

        result = get_user_group(auth_manager, server_config, {"group_id": GROUP_SYS_ID})
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_by_sys_id_empty_result(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": {}})

        result = get_user_group(auth_manager, server_config, {"group_id": GROUP_SYS_ID})
        assert result["success"] is False

    def test_by_name_success(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": [RAW_GROUP]})

        result = get_user_group(auth_manager, server_config, {"group_id": "Network Ops"})
        assert result["success"] is True
        assert result["group"]["sys_id"] == GROUP_SYS_ID

    def test_by_name_not_found(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": []})

        result = get_user_group(auth_manager, server_config, {"group_id": "Unknown"})
        assert result["success"] is False

    def test_missing_group_id(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}

        result = get_user_group(auth_manager, server_config, {})
        assert result["success"] is False

    def test_request_error_by_name(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.side_effect = requests.exceptions.Timeout()

        result = get_user_group(auth_manager, server_config, {"group_id": "Network Ops"})
        assert result["success"] is False
        assert "Error retrieving" in result["message"]

    def test_request_error_by_sys_id(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.side_effect = requests.exceptions.ConnectionError()

        result = get_user_group(auth_manager, server_config, {"group_id": GROUP_SYS_ID})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# add_user_to_group
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.user_group_tools._make_request")
@patch("servicenow_mcp.tools.user_group_tools._get_headers")
@patch("servicenow_mcp.tools.user_group_tools._get_instance_url")
class TestAddUserToGroup:
    def test_success_with_sys_ids(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": {"sys_id": MEMBER_SYS_ID}})

        result = add_user_to_group(
            auth_manager, server_config,
            {"group_id": GROUP_SYS_ID, "user_id": USER_SYS_ID},
        )
        assert result["success"] is True
        assert result["member_sys_id"] == MEMBER_SYS_ID

    def test_success_with_names(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        # First call resolves group name, second resolves username, third is POST
        mock_req.side_effect = [
            _mock_response({"result": [{"sys_id": GROUP_SYS_ID}]}),
            _mock_response({"result": [{"sys_id": USER_SYS_ID}]}),
            _mock_response({"result": {"sys_id": MEMBER_SYS_ID}}),
        ]

        result = add_user_to_group(
            auth_manager, server_config,
            {"group_id": "Network Ops", "user_id": "alice"},
        )
        assert result["success"] is True

    def test_group_not_found(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": []})

        result = add_user_to_group(
            auth_manager, server_config,
            {"group_id": "Bad Group", "user_id": USER_SYS_ID},
        )
        assert result["success"] is False
        assert "Group not found" in result["message"]

    def test_user_not_found(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        # First call returns a group, second returns no user
        mock_req.side_effect = [
            _mock_response({"result": [{"sys_id": GROUP_SYS_ID}]}),
            _mock_response({"result": []}),
        ]

        result = add_user_to_group(
            auth_manager, server_config,
            {"group_id": "Network Ops", "user_id": "nobody"},
        )
        assert result["success"] is False
        assert "User not found" in result["message"]

    def test_post_error(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.side_effect = [
            # resolve group
            type('R', (), {'status_code': 200, 'json': lambda self: {"result": [{"sys_id": GROUP_SYS_ID}]}, 'raise_for_status': lambda self: None})(),
            # resolve user
            type('R', (), {'status_code': 200, 'json': lambda self: {"result": [{"sys_id": USER_SYS_ID}]}, 'raise_for_status': lambda self: None})(),
            # POST fails
            requests.exceptions.ConnectionError("down"),
        ]

        result = add_user_to_group(
            auth_manager, server_config,
            {"group_id": "Network Ops", "user_id": "alice"},
        )
        assert result["success"] is False
        assert "Error adding user to group" in result["message"]

    def test_missing_required_fields(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}

        result = add_user_to_group(auth_manager, server_config, {"group_id": GROUP_SYS_ID})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# remove_user_from_group
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.user_group_tools._make_request")
@patch("servicenow_mcp.tools.user_group_tools._get_headers")
@patch("servicenow_mcp.tools.user_group_tools._get_instance_url")
class TestRemoveUserFromGroup:
    def test_success_204(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({}, status_code=204)

        result = remove_user_from_group(
            auth_manager, server_config, {"member_sys_id": MEMBER_SYS_ID}
        )
        assert result["success"] is True
        assert "removed" in result["message"]

    def test_success_200(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({}, status_code=200)

        result = remove_user_from_group(
            auth_manager, server_config, {"member_sys_id": MEMBER_SYS_ID}
        )
        assert result["success"] is True

    def test_404(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({}, status_code=404)

        result = remove_user_from_group(
            auth_manager, server_config, {"member_sys_id": MEMBER_SYS_ID}
        )
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_missing_member_sys_id(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}

        result = remove_user_from_group(auth_manager, server_config, {})
        assert result["success"] is False

    def test_request_error(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.side_effect = requests.exceptions.Timeout()

        result = remove_user_from_group(
            auth_manager, server_config, {"member_sys_id": MEMBER_SYS_ID}
        )
        assert result["success"] is False
        assert "Error removing user from group" in result["message"]

    def test_no_instance_url(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = None

        result = remove_user_from_group(
            auth_manager, server_config, {"member_sys_id": MEMBER_SYS_ID}
        )
        assert result["success"] is False


# ---------------------------------------------------------------------------
# list_group_members
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.user_group_tools._make_request")
@patch("servicenow_mcp.tools.user_group_tools._get_headers")
@patch("servicenow_mcp.tools.user_group_tools._get_instance_url")
class TestListGroupMembers:
    def test_success_by_sys_id(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": [RAW_MEMBER]})

        result = list_group_members(
            auth_manager, server_config, {"group_id": GROUP_SYS_ID}
        )
        assert result["success"] is True
        assert len(result["members"]) == 1
        assert result["members"][0]["user"] == "Bob"

    def test_success_by_name(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.side_effect = [
            _mock_response({"result": [{"sys_id": GROUP_SYS_ID}]}),
            _mock_response({"result": [RAW_MEMBER]}),
        ]

        result = list_group_members(
            auth_manager, server_config, {"group_id": "Network Ops"}
        )
        assert result["success"] is True
        assert len(result["members"]) == 1

    def test_group_not_found(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": []})

        result = list_group_members(
            auth_manager, server_config, {"group_id": "Unknown Group"}
        )
        assert result["success"] is False

    def test_missing_group_id(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}

        result = list_group_members(auth_manager, server_config, {})
        assert result["success"] is False

    def test_pagination_params(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": []})

        result = list_group_members(
            auth_manager, server_config, {"group_id": GROUP_SYS_ID, "limit": 5, "offset": 20}
        )
        assert result["offset"] == 20

    def test_empty_members(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.return_value = _mock_response({"result": []})

        result = list_group_members(
            auth_manager, server_config, {"group_id": GROUP_SYS_ID}
        )
        assert result["success"] is True
        assert result["members"] == []
        assert result["has_more"] is False

    def test_request_error(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = {"Authorization": "Bearer test"}
        mock_req.side_effect = requests.exceptions.ConnectionError("down")

        result = list_group_members(
            auth_manager, server_config, {"group_id": GROUP_SYS_ID}
        )
        assert result["success"] is False
        assert "Error listing group members" in result["message"]

    def test_no_headers(self, mock_url, mock_hdrs, mock_req, auth_manager, server_config):
        mock_url.return_value = "https://test.service-now.com"
        mock_hdrs.return_value = None

        result = list_group_members(
            auth_manager, server_config, {"group_id": GROUP_SYS_ID}
        )
        assert result["success"] is False


# ---------------------------------------------------------------------------
# Param model validation
# ---------------------------------------------------------------------------

class TestParamModels:
    def test_list_user_groups_defaults(self):
        p = ListUserGroupsParams()
        assert p.limit == 20
        assert p.offset == 0
        assert p.name is None
        assert p.active is None

    def test_get_user_group_requires_group_id(self):
        with pytest.raises(Exception):
            GetUserGroupParams()

    def test_add_user_to_group_requires_fields(self):
        with pytest.raises(Exception):
            AddUserToGroupParams(group_id=GROUP_SYS_ID)

    def test_remove_user_from_group_requires_member_sys_id(self):
        with pytest.raises(Exception):
            RemoveUserFromGroupParams()

    def test_list_group_members_requires_group_id(self):
        with pytest.raises(Exception):
            ListGroupMembersParams()
