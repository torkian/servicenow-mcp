"""Coverage tests for user_tools.py — targets uncovered branches."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.user_tools import (
    AddGroupMembersParams,
    CreateGroupParams,
    CreateUserParams,
    GetUserByEmailParams,
    GetUserParams,
    RemoveGroupMembersParams,
    UpdateGroupParams,
    UpdateUserParams,
    add_group_members,
    assign_roles_to_user,
    check_user_has_role,
    create_group,
    create_user,
    get_role_id,
    get_user,
    get_user_by_email,
    remove_group_members,
    update_group,
    update_user,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


def _make_config():
    return ServerConfig(
        instance_url="https://dev99.service-now.com",
        auth=AuthConfig(type=AuthType.BASIC, basic=BasicAuthConfig(username="u", password="p")),
    )


def _make_auth():
    auth = MagicMock(spec=AuthManager)
    auth.get_headers.return_value = {"Authorization": "Basic X"}
    return auth


def _ok_response(body):
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = body
    return r


class TestCreateUserOptionalFields(unittest.TestCase):
    """create_user: optional fields that branch on None."""

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_all_optional_fields_sent(self, mock_req):
        mock_req.return_value = _ok_response({"result": {"sys_id": "u1", "user_name": "bob"}})
        params = CreateUserParams(
            user_name="bob",
            first_name="Bob",
            last_name="Smith",
            email="bob@test.com",
            title="Engineer",
            department="IT",
            manager="admin",
            phone="555-0100",
            mobile_phone="555-0200",
            location="NYC",
            password="secret",
        )
        result = create_user(_make_config(), _make_auth(), params)
        self.assertTrue(result.success)
        _, kwargs = mock_req.call_args
        body = kwargs["json"]
        self.assertEqual(body["title"], "Engineer")
        self.assertEqual(body["mobile_phone"], "555-0200")
        self.assertEqual(body["user_password"], "secret")

    @patch("servicenow_mcp.tools.user_tools.assign_roles_to_user")
    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_roles_trigger_assign(self, mock_req, mock_assign):
        mock_req.return_value = _ok_response({"result": {"sys_id": "u1", "user_name": "bob"}})
        params = CreateUserParams(
            user_name="bob",
            first_name="Bob",
            last_name="Smith",
            email="bob@test.com",
            roles=["itil", "admin"],
        )
        create_user(_make_config(), _make_auth(), params)
        mock_assign.assert_called_once_with(
            _make_config(), unittest.mock.ANY, "u1", ["itil", "admin"]
        )


class TestUpdateUserOptionalFields(unittest.TestCase):
    """update_user: optional fields including phone, mobile_phone, location, password, roles."""

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_all_optional_fields_sent(self, mock_req):
        mock_req.return_value = _ok_response({"result": {"sys_id": "u1", "user_name": "bob"}})
        params = UpdateUserParams(
            user_id="u1",
            user_name="bob2",
            phone="555-9999",
            mobile_phone="555-8888",
            location="LA",
            password="newpass",
        )
        result = update_user(_make_config(), _make_auth(), params)
        self.assertTrue(result.success)
        _, kwargs = mock_req.call_args
        body = kwargs["json"]
        self.assertEqual(body["user_name"], "bob2")
        self.assertEqual(body["phone"], "555-9999")
        self.assertEqual(body["mobile_phone"], "555-8888")
        self.assertEqual(body["location"], "LA")
        self.assertEqual(body["user_password"], "newpass")

    @patch("servicenow_mcp.tools.user_tools.assign_roles_to_user")
    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_roles_trigger_assign(self, mock_req, mock_assign):
        mock_req.return_value = _ok_response({"result": {"sys_id": "u1", "user_name": "bob"}})
        params = UpdateUserParams(user_id="u1", roles=["itil"])
        update_user(_make_config(), _make_auth(), params)
        mock_assign.assert_called_once()


class TestGetUserNoParams(unittest.TestCase):
    """get_user: returns error when no search parameter is given."""

    def test_no_params_returns_error(self):
        params = GetUserParams()
        result = get_user(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("required", result["message"])


class TestAssignRolesToUser(unittest.TestCase):
    """assign_roles_to_user: role not found, already has role, POST failure."""

    @patch("servicenow_mcp.tools.user_tools.check_user_has_role")
    @patch("servicenow_mcp.tools.user_tools.get_role_id")
    def test_role_not_found_skips(self, mock_get_role, mock_check):
        mock_get_role.return_value = None
        result = assign_roles_to_user(_make_config(), _make_auth(), "u1", ["nonexistent_role"])
        self.assertTrue(result)
        mock_check.assert_not_called()

    @patch("servicenow_mcp.tools.user_tools.check_user_has_role")
    @patch("servicenow_mcp.tools.user_tools.get_role_id")
    def test_user_already_has_role_skips_post(self, mock_get_role, mock_check):
        mock_get_role.return_value = "role_sys_id"
        mock_check.return_value = True
        result = assign_roles_to_user(_make_config(), _make_auth(), "u1", ["itil"])
        self.assertTrue(result)

    @patch("servicenow_mcp.tools.user_tools._make_request")
    @patch("servicenow_mcp.tools.user_tools.check_user_has_role")
    @patch("servicenow_mcp.tools.user_tools.get_role_id")
    def test_post_failure_returns_false(self, mock_get_role, mock_check, mock_req):
        mock_get_role.return_value = "role_sys_id"
        mock_check.return_value = False
        mock_req.side_effect = requests.RequestException("network error")
        result = assign_roles_to_user(_make_config(), _make_auth(), "u1", ["itil"])
        self.assertFalse(result)

    @patch("servicenow_mcp.tools.user_tools._make_request")
    @patch("servicenow_mcp.tools.user_tools.check_user_has_role")
    @patch("servicenow_mcp.tools.user_tools.get_role_id")
    def test_post_success_returns_true(self, mock_get_role, mock_check, mock_req):
        mock_get_role.return_value = "role_sys_id"
        mock_check.return_value = False
        mock_req.return_value = _ok_response({"result": {}})
        result = assign_roles_to_user(_make_config(), _make_auth(), "u1", ["itil"])
        self.assertTrue(result)


class TestGetRoleId(unittest.TestCase):
    """get_role_id: empty result and request exception."""

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_empty_result_returns_none(self, mock_req):
        mock_req.return_value = _ok_response({"result": []})
        result = get_role_id(_make_config(), _make_auth(), "nonexistent")
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_exception_returns_none(self, mock_req):
        mock_req.side_effect = requests.RequestException("timeout")
        result = get_role_id(_make_config(), _make_auth(), "itil")
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_found_returns_sys_id(self, mock_req):
        mock_req.return_value = _ok_response({"result": [{"sys_id": "r1", "name": "itil"}]})
        result = get_role_id(_make_config(), _make_auth(), "itil")
        self.assertEqual(result, "r1")


class TestCheckUserHasRole(unittest.TestCase):
    """check_user_has_role: exception path returns False."""

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_exception_returns_false(self, mock_req):
        mock_req.side_effect = requests.RequestException("error")
        result = check_user_has_role(_make_config(), _make_auth(), "u1", "r1")
        self.assertFalse(result)

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_found_returns_true(self, mock_req):
        mock_req.return_value = _ok_response({"result": [{"sys_id": "m1"}]})
        result = check_user_has_role(_make_config(), _make_auth(), "u1", "r1")
        self.assertTrue(result)

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_not_found_returns_false(self, mock_req):
        mock_req.return_value = _ok_response({"result": []})
        result = check_user_has_role(_make_config(), _make_auth(), "u1", "r1")
        self.assertFalse(result)


class TestCreateGroupOptionalFields(unittest.TestCase):
    """create_group: optional fields description, manager, parent, type, email, members."""

    @patch("servicenow_mcp.tools.user_tools.add_group_members")
    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_all_optional_fields_and_members(self, mock_req, mock_add_members):
        mock_req.return_value = _ok_response({"result": {"sys_id": "g1", "name": "SRE"}})
        params = CreateGroupParams(
            name="SRE",
            description="Site Reliability",
            manager="mgr1",
            parent="parent_g",
            type="team",
            email="sre@corp.com",
            members=["alice", "bob"],
        )
        result = create_group(_make_config(), _make_auth(), params)
        self.assertTrue(result.success)
        _, kwargs = mock_req.call_args
        body = kwargs["json"]
        self.assertEqual(body["description"], "Site Reliability")
        self.assertEqual(body["manager"], "mgr1")
        self.assertEqual(body["parent"], "parent_g")
        self.assertEqual(body["type"], "team")
        self.assertEqual(body["email"], "sre@corp.com")
        mock_add_members.assert_called_once()


class TestUpdateGroupOptionalFields(unittest.TestCase):
    """update_group: optional fields description, manager, parent, type, email, active."""

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_all_optional_fields_sent(self, mock_req):
        mock_req.return_value = _ok_response({"result": {"sys_id": "g1", "name": "SRE"}})
        params = UpdateGroupParams(
            group_id="g1",
            description="Updated desc",
            manager="mgr2",
            parent="parent2",
            type="department",
            email="sre2@corp.com",
            active=False,
        )
        result = update_group(_make_config(), _make_auth(), params)
        self.assertTrue(result.success)
        _, kwargs = mock_req.call_args
        body = kwargs["json"]
        self.assertEqual(body["description"], "Updated desc")
        self.assertEqual(body["manager"], "mgr2")
        self.assertEqual(body["parent"], "parent2")
        self.assertEqual(body["type"], "department")
        self.assertEqual(body["email"], "sre2@corp.com")
        self.assertEqual(body["active"], "false")


class TestAddGroupMembersEmailFallback(unittest.TestCase):
    """add_group_members: fallback to email lookup, POST failure branch."""

    @patch("servicenow_mcp.tools.user_tools._make_request")
    @patch("servicenow_mcp.tools.user_tools.get_user")
    def test_username_not_found_tries_email(self, mock_get_user, mock_req):
        # First call (username) fails, second call (email) succeeds
        mock_get_user.side_effect = [
            {"success": False, "message": "not found"},
            {"success": True, "user": {"sys_id": "u1"}},
        ]
        mock_req.return_value = _ok_response({"result": {}})
        params = AddGroupMembersParams(group_id="g1", members=["alice@test.com"])
        result = add_group_members(_make_config(), _make_auth(), params)
        self.assertTrue(result.success)
        self.assertEqual(mock_get_user.call_count, 2)

    @patch("servicenow_mcp.tools.user_tools._make_request")
    @patch("servicenow_mcp.tools.user_tools.get_user")
    def test_post_failure_after_successful_lookup(self, mock_get_user, mock_req):
        mock_get_user.return_value = {"success": True, "user": {"sys_id": "u1"}}
        mock_req.side_effect = requests.RequestException("POST failed")
        params = AddGroupMembersParams(group_id="g1", members=["alice"])
        result = add_group_members(_make_config(), _make_auth(), params)
        self.assertFalse(result.success)
        self.assertIn("alice", result.message)


class TestRemoveGroupMembersEdgePaths(unittest.TestCase):
    """remove_group_members: empty membership lookup and exception path."""

    @patch("servicenow_mcp.tools.user_tools._make_request")
    @patch("servicenow_mcp.tools.user_tools.get_user")
    def test_membership_not_found_fails(self, mock_get_user, mock_req):
        mock_get_user.return_value = {"success": True, "user": {"sys_id": "u1"}}
        mock_req.return_value = _ok_response({"result": []})  # no membership record
        params = RemoveGroupMembersParams(group_id="g1", members=["alice"])
        result = remove_group_members(_make_config(), _make_auth(), params)
        self.assertFalse(result.success)
        self.assertIn("alice", result.message)

    @patch("servicenow_mcp.tools.user_tools._make_request")
    @patch("servicenow_mcp.tools.user_tools.get_user")
    def test_delete_request_exception(self, mock_get_user, mock_req):
        mock_get_user.return_value = {"success": True, "user": {"sys_id": "u1"}}

        get_resp = _ok_response({"result": [{"sys_id": "m1"}]})
        mock_req.side_effect = [get_resp, requests.RequestException("delete failed")]
        params = RemoveGroupMembersParams(group_id="g1", members=["alice"])
        result = remove_group_members(_make_config(), _make_auth(), params)
        self.assertFalse(result.success)


class TestGetUserByEmail(unittest.TestCase):
    """get_user_by_email: success, not found, exception, LIKE mode."""

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_success_exact_match(self, mock_req):
        mock_req.return_value = _ok_response(
            {"result": [{"sys_id": "u1", "email": "alice@test.com", "user_name": "alice"}]}
        )
        params = GetUserByEmailParams(email="alice@test.com")
        result = get_user_by_email(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        self.assertEqual(result["user"]["sys_id"], "u1")

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_like_mode(self, mock_req):
        mock_req.return_value = _ok_response(
            {"result": [{"sys_id": "u2", "email": "bob@test.com", "user_name": "bob"}]}
        )
        params = GetUserByEmailParams(email="test.com", exact=False)
        result = get_user_by_email(_make_config(), _make_auth(), params)
        self.assertTrue(result["success"])
        _, kwargs = mock_req.call_args
        self.assertIn("LIKE", kwargs["params"]["sysparm_query"])

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _ok_response({"result": []})
        params = GetUserByEmailParams(email="ghost@test.com")
        result = get_user_by_email(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("ghost@test.com", result["message"])

    @patch("servicenow_mcp.tools.user_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = requests.RequestException("timeout")
        params = GetUserByEmailParams(email="alice@test.com")
        result = get_user_by_email(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Failed to look up user by email", result["message"])

    def test_empty_email_returns_error(self):
        params = GetUserByEmailParams(email="")
        result = get_user_by_email(_make_config(), _make_auth(), params)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "email is required")


if __name__ == "__main__":
    unittest.main()
