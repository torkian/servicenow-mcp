"""Tests for on_call_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.on_call_tools import (
    _format_on_call_rotation,
    _format_on_call_rotation_member,
    _resolve_on_call_rotation_sys_id,
    create_on_call_rotation,
    get_on_call_rotation,
    list_on_call_rotation_members,
    list_on_call_rotations,
    update_on_call_rotation,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
FAKE_GROUP_SYS_ID = "b" * 32
FAKE_MANAGER_SYS_ID = "c" * 32
FAKE_SCHEDULE_SYS_ID = "d" * 32

FAKE_ROTATION = {
    "sys_id": FAKE_SYS_ID,
    "name": "Network Team On-call",
    "active": "true",
    "description": "Primary on-call rotation for the network ops team",
    "group": {"display_value": "Network Operations", "value": FAKE_GROUP_SYS_ID},
    "manager": {"display_value": "Jane Doe", "value": FAKE_MANAGER_SYS_ID},
    "schedule": {"display_value": "Business Hours", "value": FAKE_SCHEDULE_SYS_ID},
    "escalation": {"display_value": "Escalation Policy A", "value": "e" * 32},
    "type": "primary",
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-06-01 00:00:00",
    "sys_created_by": "admin",
}


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev99999.service-now.com", auth=auth_config)


def _make_auth_manager():
    auth_manager = MagicMock(spec=AuthManager)
    auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    auth_manager.instance_url = "https://dev99999.service-now.com"
    return auth_manager


def _make_response(status_code, json_data):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=resp
        )
    return resp


# ---------------------------------------------------------------------------
# _format_on_call_rotation
# ---------------------------------------------------------------------------

class TestFormatOnCallRotation(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_on_call_rotation(FAKE_ROTATION)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["name"], "Network Team On-call")
        self.assertEqual(result["active"], "true")
        self.assertEqual(result["description"], "Primary on-call rotation for the network ops team")
        self.assertEqual(result["type"], "primary")
        self.assertEqual(result["created_on"], "2026-01-01 00:00:00")
        self.assertEqual(result["updated_on"], "2026-06-01 00:00:00")
        self.assertEqual(result["created_by"], "admin")

    def test_normalises_group_reference(self):
        result = _format_on_call_rotation(FAKE_ROTATION)
        self.assertEqual(result["group"], "Network Operations")

    def test_normalises_manager_reference(self):
        result = _format_on_call_rotation(FAKE_ROTATION)
        self.assertEqual(result["manager"], "Jane Doe")

    def test_normalises_schedule_reference(self):
        result = _format_on_call_rotation(FAKE_ROTATION)
        self.assertEqual(result["schedule"], "Business Hours")

    def test_normalises_escalation_reference(self):
        result = _format_on_call_rotation(FAKE_ROTATION)
        self.assertEqual(result["escalation"], "Escalation Policy A")

    def test_handles_string_fields(self):
        rotation = {**FAKE_ROTATION, "group": "plain_group", "manager": "plain_manager"}
        result = _format_on_call_rotation(rotation)
        self.assertEqual(result["group"], "plain_group")
        self.assertEqual(result["manager"], "plain_manager")

    def test_handles_value_fallback(self):
        rotation = {**FAKE_ROTATION, "group": {"value": FAKE_GROUP_SYS_ID}}
        result = _format_on_call_rotation(rotation)
        self.assertEqual(result["group"], FAKE_GROUP_SYS_ID)

    def test_handles_missing_fields(self):
        result = _format_on_call_rotation({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["name"])
        self.assertIsNone(result["active"])
        self.assertIsNone(result["group"])
        self.assertIsNone(result["manager"])
        self.assertIsNone(result["schedule"])
        self.assertIsNone(result["escalation"])


# ---------------------------------------------------------------------------
# list_on_call_rotations
# ---------------------------------------------------------------------------

class TestListOnCallRotations(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_returns_rotations_on_success(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_ROTATION]})
        result = list_on_call_rotations(self.auth, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["rotations"]), 1)
        self.assertEqual(result["rotations"][0]["name"], "Network Team On-call")
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_empty_result_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_on_call_rotations(self.auth, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(result["rotations"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_filter_by_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_ROTATION]})
        list_on_call_rotations(self.auth, self.config, {"name": "Network"})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("nameLIKENetwork", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_filter_active_true(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {"active": True})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=true", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_filter_active_false(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {"active": False})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=false", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_filter_by_group_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {"group": "Network Ops"})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("group.nameLIKENetwork Ops", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_filter_by_group_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {"group": FAKE_GROUP_SYS_ID})
        call_params = mock_req.call_args[1]["params"]
        self.assertIn(f"group={FAKE_GROUP_SYS_ID}", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_pagination_params(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {"limit": 5, "offset": 10})
        call_params = mock_req.call_args[1]["params"]
        self.assertEqual(call_params["sysparm_limit"], 5)
        self.assertEqual(call_params["sysparm_offset"], 10)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_has_more_when_full_page(self, mock_req):
        rotations = [dict(FAKE_ROTATION, sys_id=str(i) * 32) for i in range(20)]
        mock_req.return_value = _make_response(200, {"result": rotations})
        result = list_on_call_rotations(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 20)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = list_on_call_rotations(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing on-call rotations", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_on_call_rotations(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing on-call rotations", result["message"])

    def test_invalid_params_returns_failure(self):
        result = list_on_call_rotations(self.auth, self.config, {"limit": "not-an-int"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.on_call_tools._get_instance_url")
    def test_missing_instance_url_returns_failure(self, mock_url):
        mock_url.return_value = None
        result = list_on_call_rotations(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._get_headers")
    def test_missing_headers_returns_failure(self, mock_headers):
        mock_headers.return_value = None
        result = list_on_call_rotations(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_multiple_filters_combined(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(
            self.auth, self.config,
            {"name": "Primary", "active": True, "group": "NOC"},
        )
        call_params = mock_req.call_args[1]["params"]
        query = call_params.get("sysparm_query", "")
        self.assertIn("nameLIKEPrimary", query)
        self.assertIn("active=true", query)
        self.assertIn("group.nameLIKENOC", query)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_default_order_by_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {})
        call_params = mock_req.call_args[1]["params"]
        self.assertEqual(call_params.get("sysparm_orderby"), "name")

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_url_targets_cmn_rota(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_on_call_rotations(self.auth, self.config, {})
        url = mock_req.call_args[0][1]
        self.assertIn("cmn_rota", url)


# ---------------------------------------------------------------------------
# _resolve_on_call_rotation_sys_id
# ---------------------------------------------------------------------------

class TestResolveOnCallRotationSysId(unittest.TestCase):
    def test_passthrough_for_valid_sys_id(self):
        result = _resolve_on_call_rotation_sys_id("https://dev.service-now.com", {}, FAKE_SYS_ID)
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_name_lookup_returns_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        result = _resolve_on_call_rotation_sys_id(
            "https://dev.service-now.com", {}, "Network Team On-call"
        )
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_name_not_found_returns_none(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = _resolve_on_call_rotation_sys_id(
            "https://dev.service-now.com", {}, "Unknown Rotation"
        )
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_request_error_returns_none(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = _resolve_on_call_rotation_sys_id("https://dev.service-now.com", {}, "Any Name")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# get_on_call_rotation
# ---------------------------------------------------------------------------

class TestGetOnCallRotation(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_success_by_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ROTATION})
        result = get_on_call_rotation(self.auth, self.config, {"rotation_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertIn("rotation", result)
        self.assertEqual(result["rotation"]["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["rotation"]["name"], "Network Team On-call")

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_success_by_name(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        get_resp = _make_response(200, {"result": FAKE_ROTATION})
        mock_req.side_effect = [resolve_resp, get_resp]
        result = get_on_call_rotation(
            self.auth, self.config, {"rotation_id": "Network Team On-call"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["rotation"]["name"], "Network Team On-call")

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_not_found_by_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = get_on_call_rotation(self.auth, self.config, {"rotation_id": "Unknown Rotation"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_404_returns_failure(self, mock_req):
        get_resp = _make_response(404, {})
        get_resp.raise_for_status = MagicMock()
        mock_req.return_value = get_resp
        result = get_on_call_rotation(self.auth, self.config, {"rotation_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_empty_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_on_call_rotation(self.auth, self.config, {"rotation_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = get_on_call_rotation(self.auth, self.config, {"rotation_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving on-call rotation", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = get_on_call_rotation(self.auth, self.config, {"rotation_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving on-call rotation", result["message"])

    def test_missing_rotation_id_returns_failure(self):
        result = get_on_call_rotation(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.on_call_tools._get_instance_url")
    def test_missing_instance_url_returns_failure(self, mock_url):
        mock_url.return_value = None
        result = get_on_call_rotation(self.auth, self.config, {"rotation_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._get_headers")
    @patch("servicenow_mcp.tools.on_call_tools._get_instance_url")
    def test_missing_headers_returns_failure(self, mock_url, mock_headers):
        mock_url.return_value = "https://dev.service-now.com"
        mock_headers.return_value = None
        result = get_on_call_rotation(self.auth, self.config, {"rotation_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_url_includes_sys_id(self, mock_req):
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]}),
            _make_response(200, {"result": FAKE_ROTATION}),
        ]
        get_on_call_rotation(self.auth, self.config, {"rotation_id": "Network Team On-call"})
        get_call_url = mock_req.call_args_list[1][0][1]
        self.assertIn(FAKE_SYS_ID, get_call_url)
        self.assertIn("cmn_rota", get_call_url)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_display_value_requested(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ROTATION})
        get_on_call_rotation(self.auth, self.config, {"rotation_id": FAKE_SYS_ID})
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params.get("sysparm_display_value"), "true")

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_normalises_reference_fields(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ROTATION})
        result = get_on_call_rotation(self.auth, self.config, {"rotation_id": FAKE_SYS_ID})
        self.assertEqual(result["rotation"]["group"], "Network Operations")
        self.assertEqual(result["rotation"]["manager"], "Jane Doe")


FAKE_MEMBER_SYS_ID = "f" * 32
FAKE_USER_SYS_ID = "9" * 32

FAKE_ROTA_MEMBER = {
    "sys_id": FAKE_MEMBER_SYS_ID,
    "rota": {"display_value": "Network Team On-call", "value": FAKE_SYS_ID},
    "member": {"display_value": "Alice Smith", "value": FAKE_USER_SYS_ID},
    "order": "1",
    "active": "true",
    "skills": {"display_value": "Network Admin", "value": "0" * 32},
    "override_on_call_rota": "false",
    "catch_all": "false",
    "sys_created_on": "2026-01-10 09:00:00",
    "sys_updated_on": "2026-06-10 12:00:00",
    "sys_created_by": "admin",
}


# ---------------------------------------------------------------------------
# _format_on_call_rotation_member
# ---------------------------------------------------------------------------

class TestFormatOnCallRotationMember(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_on_call_rotation_member(FAKE_ROTA_MEMBER)
        self.assertEqual(result["sys_id"], FAKE_MEMBER_SYS_ID)
        self.assertEqual(result["order"], "1")
        self.assertEqual(result["active"], "true")
        self.assertEqual(result["override_on_call_rota"], "false")
        self.assertEqual(result["catch_all"], "false")
        self.assertEqual(result["created_on"], "2026-01-10 09:00:00")
        self.assertEqual(result["updated_on"], "2026-06-10 12:00:00")
        self.assertEqual(result["created_by"], "admin")

    def test_normalises_rota_reference(self):
        result = _format_on_call_rotation_member(FAKE_ROTA_MEMBER)
        self.assertEqual(result["rota"], "Network Team On-call")

    def test_normalises_member_reference(self):
        result = _format_on_call_rotation_member(FAKE_ROTA_MEMBER)
        self.assertEqual(result["member"], "Alice Smith")

    def test_normalises_skills_reference(self):
        result = _format_on_call_rotation_member(FAKE_ROTA_MEMBER)
        self.assertEqual(result["skills"], "Network Admin")

    def test_handles_string_fields(self):
        record = {**FAKE_ROTA_MEMBER, "member": "plain_user", "rota": "plain_rota"}
        result = _format_on_call_rotation_member(record)
        self.assertEqual(result["member"], "plain_user")
        self.assertEqual(result["rota"], "plain_rota")

    def test_value_fallback_when_no_display_value(self):
        record = {**FAKE_ROTA_MEMBER, "member": {"value": FAKE_USER_SYS_ID}}
        result = _format_on_call_rotation_member(record)
        self.assertEqual(result["member"], FAKE_USER_SYS_ID)

    def test_handles_missing_fields(self):
        result = _format_on_call_rotation_member({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["rota"])
        self.assertIsNone(result["member"])
        self.assertIsNone(result["order"])
        self.assertIsNone(result["skills"])


# ---------------------------------------------------------------------------
# list_on_call_rotation_members
# ---------------------------------------------------------------------------

class TestListOnCallRotationMembers(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    def _patched_call(self, mock_req, members=None, rotation_result=None):
        """Helper: first call resolves the rotation, second lists members."""
        resolve_resp = _make_response(
            200,
            {"result": rotation_result if rotation_result is not None else [{"sys_id": FAKE_SYS_ID}]},
        )
        member_resp = _make_response(200, {"result": members if members is not None else []})
        mock_req.side_effect = [resolve_resp, member_resp]

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_success_by_sys_id_skips_resolve(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_ROTA_MEMBER]})
        result = list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": FAKE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["members"]), 1)
        self.assertEqual(result["members"][0]["member"], "Alice Smith")
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_success_by_rotation_name(self, mock_req):
        self._patched_call(mock_req, members=[FAKE_ROTA_MEMBER])
        result = list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": "Network Team On-call"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["members"]), 1)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_rotation_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": "Unknown Rotation"}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_filter_active_true(self, mock_req):
        self._patched_call(mock_req, members=[])
        list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": "Network Team On-call", "active": True}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=true", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_filter_active_false(self, mock_req):
        self._patched_call(mock_req, members=[])
        list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": "Network Team On-call", "active": False}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=false", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_rotation_sys_id_in_query(self, mock_req):
        self._patched_call(mock_req, members=[])
        list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": "Network Team On-call"}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn(f"rota={FAKE_SYS_ID}", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_url_targets_cmn_rota_member(self, mock_req):
        self._patched_call(mock_req, members=[])
        list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": "Network Team On-call"}
        )
        url = mock_req.call_args[0][1]
        self.assertIn("cmn_rota_member", url)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_order_by_order_field(self, mock_req):
        self._patched_call(mock_req, members=[])
        list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": "Network Team On-call"}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertEqual(call_params.get("sysparm_orderby"), "order")

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_pagination_params_forwarded(self, mock_req):
        self._patched_call(mock_req, members=[])
        list_on_call_rotation_members(
            self.auth, self.config,
            {"rotation_id": "Network Team On-call", "limit": 5, "offset": 10},
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertEqual(call_params["sysparm_limit"], 5)
        self.assertEqual(call_params["sysparm_offset"], 10)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_has_more_when_full_page(self, mock_req):
        members = [dict(FAKE_ROTA_MEMBER, sys_id=str(i) * 32) for i in range(20)]
        self._patched_call(mock_req, members=members)
        result = list_on_call_rotation_members(
            self.auth, self.config,
            {"rotation_id": "Network Team On-call", "limit": 20, "offset": 0},
        )
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 20)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_empty_member_list(self, mock_req):
        self._patched_call(mock_req, members=[])
        result = list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": "Network Team On-call"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["members"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        error_resp = _make_response(500, {})
        mock_req.side_effect = [resolve_resp, error_resp]
        result = list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": "Network Team On-call"}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error listing on-call rotation members", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        mock_req.side_effect = [resolve_resp, requests.exceptions.ConnectionError("timeout")]
        result = list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": "Network Team On-call"}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error listing on-call rotation members", result["message"])

    def test_missing_rotation_id_returns_failure(self):
        result = list_on_call_rotation_members(self.auth, self.config, {})
        self.assertFalse(result["success"])

    def test_invalid_params_returns_failure(self):
        result = list_on_call_rotation_members(
            self.auth, self.config,
            {"rotation_id": FAKE_SYS_ID, "limit": "not-an-int"},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.on_call_tools._get_instance_url")
    def test_missing_instance_url_returns_failure(self, mock_url):
        mock_url.return_value = None
        result = list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._get_headers")
    def test_missing_headers_returns_failure(self, mock_headers):
        mock_headers.return_value = None
        result = list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_normalises_member_reference_fields(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_ROTA_MEMBER]})
        result = list_on_call_rotation_members(
            self.auth, self.config, {"rotation_id": FAKE_SYS_ID}
        )
        self.assertEqual(result["members"][0]["member"], "Alice Smith")
        self.assertEqual(result["members"][0]["rota"], "Network Team On-call")
        self.assertEqual(result["members"][0]["skills"], "Network Admin")


# ---------------------------------------------------------------------------
# create_on_call_rotation
# ---------------------------------------------------------------------------

FAKE_CREATED_ROTATION = {
    **FAKE_ROTATION,
    "sys_id": "f" * 32,
    "name": "New Primary On-call",
}


class TestCreateOnCallRotation(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_creates_rotation_minimal(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_ROTATION})
        result = create_on_call_rotation(
            self.auth, self.config, {"name": "New Primary On-call"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "f" * 32)
        self.assertIn("rotation", result)
        self.assertEqual(result["rotation"]["name"], "New Primary On-call")

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_creates_rotation_all_fields(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_ROTATION})
        result = create_on_call_rotation(
            self.auth,
            self.config,
            {
                "name": "New Primary On-call",
                "group": "Network Operations",
                "active": True,
                "description": "Primary coverage",
                "manager": "Jane Doe",
                "schedule": "Business Hours",
                "escalation": "Escalation Policy A",
                "type": "primary",
            },
        )
        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["name"], "New Primary On-call")
        self.assertEqual(body["group"], "Network Operations")
        self.assertEqual(body["active"], "true")
        self.assertEqual(body["description"], "Primary coverage")
        self.assertEqual(body["manager"], "Jane Doe")
        self.assertEqual(body["schedule"], "Business Hours")
        self.assertEqual(body["escalation"], "Escalation Policy A")
        self.assertEqual(body["type"], "primary")

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_active_false_serialised_as_string(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_ROTATION})
        create_on_call_rotation(
            self.auth, self.config, {"name": "Inactive Rota", "active": False}
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["active"], "false")

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_posts_to_cmn_rota_table(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_ROTATION})
        create_on_call_rotation(self.auth, self.config, {"name": "Test"})
        method, url = mock_req.call_args[0]
        self.assertEqual(method, "POST")
        self.assertIn("cmn_rota", url)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_optional_fields_omitted_when_none(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_ROTATION})
        create_on_call_rotation(self.auth, self.config, {"name": "Minimal"})
        body = mock_req.call_args[1]["json"]
        self.assertNotIn("description", body)
        self.assertNotIn("manager", body)
        self.assertNotIn("schedule", body)
        self.assertNotIn("escalation", body)
        self.assertNotIn("type", body)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = create_on_call_rotation(self.auth, self.config, {"name": "Test"})
        self.assertFalse(result["success"])
        self.assertIn("Error creating on-call rotation", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("unreachable")
        result = create_on_call_rotation(self.auth, self.config, {"name": "Test"})
        self.assertFalse(result["success"])
        self.assertIn("Error creating on-call rotation", result["message"])

    def test_missing_name_returns_failure(self):
        result = create_on_call_rotation(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.on_call_tools._get_instance_url")
    def test_missing_instance_url_returns_failure(self, mock_url):
        mock_url.return_value = None
        result = create_on_call_rotation(self.auth, self.config, {"name": "Test"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._get_headers")
    def test_missing_headers_returns_failure(self, mock_headers):
        mock_headers.return_value = None
        result = create_on_call_rotation(self.auth, self.config, {"name": "Test"})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_success_message_present(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_ROTATION})
        result = create_on_call_rotation(self.auth, self.config, {"name": "Test"})
        self.assertIn("created successfully", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_group_as_sys_id(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_CREATED_ROTATION})
        create_on_call_rotation(
            self.auth, self.config, {"name": "Test", "group": FAKE_GROUP_SYS_ID}
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["group"], FAKE_GROUP_SYS_ID)


# ---------------------------------------------------------------------------
# update_on_call_rotation
# ---------------------------------------------------------------------------

class TestUpdateOnCallRotation(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    def _resolve_then(self, mock_req, patch_resp):
        """First call resolves by name, second is the PATCH."""
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        mock_req.side_effect = [resolve_resp, patch_resp]

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_updates_by_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ROTATION})
        result = update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": FAKE_SYS_ID, "name": "Updated Name"},
        )
        self.assertTrue(result["success"])
        self.assertIn("rotation", result)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_updates_by_name(self, mock_req):
        self._resolve_then(mock_req, _make_response(200, {"result": FAKE_ROTATION}))
        result = update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": "Network Team On-call", "description": "Updated desc"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_patches_cmn_rota_table(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ROTATION})
        update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": FAKE_SYS_ID, "name": "X"},
        )
        method, url = mock_req.call_args[0]
        self.assertEqual(method, "PATCH")
        self.assertIn("cmn_rota", url)
        self.assertIn(FAKE_SYS_ID, url)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_only_provided_fields_in_body(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ROTATION})
        update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": FAKE_SYS_ID, "name": "New Name"},
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body, {"name": "New Name"})
        self.assertNotIn("group", body)
        self.assertNotIn("active", body)
        self.assertNotIn("description", body)

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_all_fields_in_body(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ROTATION})
        update_on_call_rotation(
            self.auth, self.config,
            {
                "rotation_id": FAKE_SYS_ID,
                "name": "Updated",
                "group": "NOC",
                "active": True,
                "description": "desc",
                "manager": "Jane",
                "schedule": "24x7",
                "escalation": "Policy A",
                "type": "secondary",
            },
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["name"], "Updated")
        self.assertEqual(body["group"], "NOC")
        self.assertEqual(body["active"], "true")
        self.assertEqual(body["description"], "desc")
        self.assertEqual(body["manager"], "Jane")
        self.assertEqual(body["schedule"], "24x7")
        self.assertEqual(body["escalation"], "Policy A")
        self.assertEqual(body["type"], "secondary")

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_active_false_serialised_as_string(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ROTATION})
        update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": FAKE_SYS_ID, "active": False},
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["active"], "false")

    def test_empty_body_returns_failure(self):
        result = update_on_call_rotation(
            self.auth, self.config, {"rotation_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("No fields provided", result["message"])

    def test_missing_rotation_id_returns_failure(self):
        result = update_on_call_rotation(self.auth, self.config, {"name": "X"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_rotation_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": "Unknown Rotation", "name": "X"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_404_returns_failure(self, mock_req):
        patch_resp = _make_response(404, {})
        patch_resp.raise_for_status = MagicMock()
        mock_req.return_value = patch_resp
        result = update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": FAKE_SYS_ID, "name": "X"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": FAKE_SYS_ID, "name": "X"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating on-call rotation", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": FAKE_SYS_ID, "name": "X"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating on-call rotation", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._get_instance_url")
    def test_missing_instance_url_returns_failure(self, mock_url):
        mock_url.return_value = None
        result = update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": FAKE_SYS_ID, "name": "X"},
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._get_headers")
    def test_missing_headers_returns_failure(self, mock_headers):
        mock_headers.return_value = None
        result = update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": FAKE_SYS_ID, "name": "X"},
        )
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_success_message_present(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ROTATION})
        result = update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": FAKE_SYS_ID, "name": "X"},
        )
        self.assertIn("updated successfully", result["message"])

    @patch("servicenow_mcp.tools.on_call_tools._make_request")
    def test_normalises_reference_fields_in_response(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ROTATION})
        result = update_on_call_rotation(
            self.auth, self.config,
            {"rotation_id": FAKE_SYS_ID, "name": "X"},
        )
        self.assertEqual(result["rotation"]["group"], "Network Operations")
        self.assertEqual(result["rotation"]["manager"], "Jane Doe")


if __name__ == "__main__":
    unittest.main()
