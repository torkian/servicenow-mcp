"""Tests for workflow_activity_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.workflow_activity_tools import (
    _format_action_type,
    _resolve_action_type_sys_id,
    _resolve_flow_scope,
    get_workflow_activity,
    list_workflow_activities,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
FAKE_SCOPE_SYS_ID = "b" * 32
FAKE_FLOW_SYS_ID = "c" * 32

FAKE_ACTION_TYPE = {
    "sys_id": FAKE_SYS_ID,
    "name": "create_record",
    "label": "Create Record",
    "description": "Creates a new record in a table",
    "category": "ServiceNow Core",
    "active": "true",
    "sys_scope": {"display_value": "global", "value": FAKE_SCOPE_SYS_ID},
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-06-01 00:00:00",
    "sys_created_by": "admin",
}

FAKE_FLOW = {
    "sys_id": FAKE_FLOW_SYS_ID,
    "sys_scope": {"value": FAKE_SCOPE_SYS_ID, "display_value": "global"},
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
# _format_action_type
# ---------------------------------------------------------------------------

class TestFormatActionType(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_action_type(FAKE_ACTION_TYPE)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["name"], "create_record")
        self.assertEqual(result["label"], "Create Record")
        self.assertEqual(result["description"], "Creates a new record in a table")
        self.assertEqual(result["category"], "ServiceNow Core")
        self.assertEqual(result["active"], "true")
        self.assertEqual(result["created_on"], "2026-01-01 00:00:00")
        self.assertEqual(result["updated_on"], "2026-06-01 00:00:00")
        self.assertEqual(result["created_by"], "admin")

    def test_normalises_scope_reference_dict(self):
        result = _format_action_type(FAKE_ACTION_TYPE)
        self.assertEqual(result["scope"], "global")

    def test_normalises_scope_value_fallback(self):
        rec = {**FAKE_ACTION_TYPE, "sys_scope": {"value": FAKE_SCOPE_SYS_ID}}
        result = _format_action_type(rec)
        self.assertEqual(result["scope"], FAKE_SCOPE_SYS_ID)

    def test_handles_string_scope(self):
        rec = {**FAKE_ACTION_TYPE, "sys_scope": "global"}
        result = _format_action_type(rec)
        self.assertEqual(result["scope"], "global")

    def test_handles_missing_fields(self):
        result = _format_action_type({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["name"])
        self.assertIsNone(result["label"])
        self.assertIsNone(result["scope"])


# ---------------------------------------------------------------------------
# _resolve_flow_scope
# ---------------------------------------------------------------------------

class TestResolveFlowScope(unittest.TestCase):
    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_resolves_by_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_FLOW]})
        scope = _resolve_flow_scope(
            "https://dev99999.service-now.com",
            {},
            FAKE_FLOW_SYS_ID,
        )
        self.assertEqual(scope, FAKE_SCOPE_SYS_ID)
        call_params = mock_req.call_args[1]["params"]
        self.assertIn(f"sys_id={FAKE_FLOW_SYS_ID}", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_resolves_by_name_substring(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_FLOW]})
        scope = _resolve_flow_scope(
            "https://dev99999.service-now.com",
            {},
            "My Approval Flow",
        )
        self.assertEqual(scope, FAKE_SCOPE_SYS_ID)
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("nameLIKE", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_returns_none_when_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        scope = _resolve_flow_scope("https://dev99999.service-now.com", {}, "missing")
        self.assertIsNone(scope)

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_returns_none_on_network_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        scope = _resolve_flow_scope("https://dev99999.service-now.com", {}, "any")
        self.assertIsNone(scope)

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_handles_string_scope_in_response(self, mock_req):
        flow = {"sys_id": FAKE_FLOW_SYS_ID, "sys_scope": FAKE_SCOPE_SYS_ID}
        mock_req.return_value = _make_response(200, {"result": [flow]})
        scope = _resolve_flow_scope(
            "https://dev99999.service-now.com", {}, FAKE_FLOW_SYS_ID
        )
        self.assertEqual(scope, FAKE_SCOPE_SYS_ID)


# ---------------------------------------------------------------------------
# list_workflow_activities — no scope filter
# ---------------------------------------------------------------------------

class TestListWorkflowActivitiesNoScope(unittest.TestCase):
    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_success_returns_activities(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_ACTION_TYPE]})
        result = list_workflow_activities(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["activities"]), 1)
        self.assertEqual(result["activities"][0]["name"], "create_record")

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_workflow_activities(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(result["activities"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_name_filter_applied(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_workflow_activities(
            _make_auth_manager(), _make_config(), {"name": "record"}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("nameLIKErecord", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_active_filter_true(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_workflow_activities(
            _make_auth_manager(), _make_config(), {"active": True}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=true", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_active_filter_false(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_workflow_activities(
            _make_auth_manager(), _make_config(), {"active": False}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=false", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_category_filter_applied(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_workflow_activities(
            _make_auth_manager(), _make_config(), {"category": "ServiceNow Core"}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("category=ServiceNow Core", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_pagination_fields_included(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_workflow_activities(
            _make_auth_manager(), _make_config(), {"limit": 5, "offset": 10}
        )
        call_params = mock_req.call_args[1]["params"]
        self.assertEqual(call_params["sysparm_limit"], 5)
        self.assertEqual(call_params["sysparm_offset"], 10)

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_has_more_set_when_full_page(self, mock_req):
        records = [FAKE_ACTION_TYPE] * 3
        mock_req.return_value = _make_response(200, {"result": records})
        result = list_workflow_activities(
            _make_auth_manager(), _make_config(), {"limit": 3, "offset": 0}
        )
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 3)

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_has_more_false_when_partial_page(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_ACTION_TYPE]})
        result = list_workflow_activities(
            _make_auth_manager(), _make_config(), {"limit": 5, "offset": 0}
        )
        self.assertFalse(result["has_more"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_network_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        result = list_workflow_activities(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("message", result)

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = list_workflow_activities(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# list_workflow_activities — with flow_id scope
# ---------------------------------------------------------------------------

class TestListWorkflowActivitiesWithScope(unittest.TestCase):
    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_scoped_by_flow_sys_id(self, mock_req):
        flow_resp = _make_response(200, {"result": [FAKE_FLOW]})
        activities_resp = _make_response(200, {"result": [FAKE_ACTION_TYPE]})
        mock_req.side_effect = [flow_resp, activities_resp]

        result = list_workflow_activities(
            _make_auth_manager(), _make_config(), {"flow_id": FAKE_FLOW_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["activities"]), 1)
        # Second call (activities) should include scope filter
        second_call_params = mock_req.call_args_list[1][1]["params"]
        self.assertIn(f"sys_scope={FAKE_SCOPE_SYS_ID}", second_call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_scoped_by_flow_name(self, mock_req):
        flow_resp = _make_response(200, {"result": [FAKE_FLOW]})
        activities_resp = _make_response(200, {"result": []})
        mock_req.side_effect = [flow_resp, activities_resp]

        result = list_workflow_activities(
            _make_auth_manager(), _make_config(), {"flow_id": "My Flow"}
        )
        self.assertTrue(result["success"])
        # First call resolves flow
        first_call_params = mock_req.call_args_list[0][1]["params"]
        self.assertIn("nameLIKEMy Flow", first_call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_flow_not_found_returns_error(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_workflow_activities(
            _make_auth_manager(), _make_config(), {"flow_id": "nonexistent"}
        )
        self.assertFalse(result["success"])
        self.assertIn("Flow not found", result["message"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_combined_filters_with_scope(self, mock_req):
        flow_resp = _make_response(200, {"result": [FAKE_FLOW]})
        activities_resp = _make_response(200, {"result": [FAKE_ACTION_TYPE]})
        mock_req.side_effect = [flow_resp, activities_resp]

        list_workflow_activities(
            _make_auth_manager(),
            _make_config(),
            {"flow_id": FAKE_FLOW_SYS_ID, "name": "create", "active": True},
        )
        second_call_params = mock_req.call_args_list[1][1]["params"]
        query = second_call_params["sysparm_query"]
        self.assertIn(f"sys_scope={FAKE_SCOPE_SYS_ID}", query)
        self.assertIn("nameLIKEcreate", query)
        self.assertIn("active=true", query)


# ---------------------------------------------------------------------------
# list_workflow_activities — instance_url / headers failures
# ---------------------------------------------------------------------------

class TestListWorkflowActivitiesConfigFailures(unittest.TestCase):
    def test_missing_instance_url(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = {}
        auth_manager.instance_url = None

        config = MagicMock()
        config.instance_url = None

        result = list_workflow_activities(auth_manager, config, {})
        self.assertFalse(result["success"])

    def test_missing_headers(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = "https://dev99999.service-now.com"

        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"

        result = list_workflow_activities(auth_manager, config, {})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# _resolve_action_type_sys_id
# ---------------------------------------------------------------------------

class TestResolveActionTypeSysId(unittest.TestCase):
    def test_passthrough_for_sys_id(self):
        result = _resolve_action_type_sys_id("https://dev.service-now.com", {}, FAKE_SYS_ID)
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_resolves_by_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        result = _resolve_action_type_sys_id(
            "https://dev.service-now.com", {}, "create_record"
        )
        self.assertEqual(result, FAKE_SYS_ID)
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("name=create_record", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_returns_none_when_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = _resolve_action_type_sys_id(
            "https://dev.service-now.com", {}, "nonexistent"
        )
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_returns_none_on_network_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        result = _resolve_action_type_sys_id(
            "https://dev.service-now.com", {}, "any_name"
        )
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# get_workflow_activity
# ---------------------------------------------------------------------------

class TestGetWorkflowActivitySuccess(unittest.TestCase):
    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_get_by_sys_id_returns_activity(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ACTION_TYPE})
        result = get_workflow_activity(
            _make_auth_manager(), _make_config(), {"activity_id": FAKE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertIn("activity", result)
        self.assertEqual(result["activity"]["name"], "create_record")

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_get_by_name_resolves_then_fetches(self, mock_req):
        lookup_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        get_resp = _make_response(200, {"result": FAKE_ACTION_TYPE})
        mock_req.side_effect = [lookup_resp, get_resp]
        result = get_workflow_activity(
            _make_auth_manager(), _make_config(), {"activity_id": "create_record"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["activity"]["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_formats_scope_as_display_value(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ACTION_TYPE})
        result = get_workflow_activity(
            _make_auth_manager(), _make_config(), {"activity_id": FAKE_SYS_ID}
        )
        self.assertEqual(result["activity"]["scope"], "global")


class TestGetWorkflowActivityNotFound(unittest.TestCase):
    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_name_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = get_workflow_activity(
            _make_auth_manager(), _make_config(), {"activity_id": "missing_action"}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_404_response_returns_failure(self, mock_req):
        # First call: sys_id passthrough, second call: 404
        resp_404 = _make_response(404, {})
        resp_404.raise_for_status = MagicMock()  # don't raise, let status_code check handle
        mock_req.return_value = resp_404
        result = get_workflow_activity(
            _make_auth_manager(), _make_config(), {"activity_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_empty_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_workflow_activity(
            _make_auth_manager(), _make_config(), {"activity_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = get_workflow_activity(
            _make_auth_manager(), _make_config(), {"activity_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.workflow_activity_tools._make_request")
    def test_network_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("refused")
        result = get_workflow_activity(
            _make_auth_manager(), _make_config(), {"activity_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("message", result)


class TestGetWorkflowActivityValidation(unittest.TestCase):
    def test_missing_activity_id_returns_failure(self):
        result = get_workflow_activity(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_missing_instance_url(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = {}
        auth_manager.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = get_workflow_activity(
            auth_manager, config, {"activity_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])

    def test_missing_headers(self):
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.get_headers.return_value = None
        auth_manager.instance_url = "https://dev99999.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev99999.service-now.com"
        result = get_workflow_activity(
            auth_manager, config, {"activity_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
