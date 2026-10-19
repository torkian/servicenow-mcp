"""Tests for event_rule_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests as req

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.event_rule_tools import (
    _format_event_rule,
    _resolve_event_rule_sys_id,
    create_event_rule,
    delete_event_rule,
    get_event_rule,
    list_event_rules,
    update_event_rule,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_RULE = {
    "sys_id": "rule001abc" + "0" * 22,
    "name": "incident.created",
    "description": "Run on new incidents",
    "active": "true",
    "order": "100",
    "condition": "",
    "script": "gs.log('hello');",
    "filter_fields": "parm1,parm2",
    "queue": "default",
    "application": {"display_value": "Global", "value": "global_sys"},
    "sys_created_on": "2026-10-01 10:00:00",
    "sys_updated_on": "2026-10-02 11:00:00",
    "sys_created_by": "admin",
    "sys_updated_by": "admin",
}

INSTANCE_URL = "https://dev99999.service-now.com"


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url=INSTANCE_URL, auth=auth_config)


def _make_auth_manager():
    am = MagicMock(spec=AuthManager)
    am.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    am.instance_url = INSTANCE_URL
    return am


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = req.exceptions.HTTPError(response=resp)
    return resp


# ---------------------------------------------------------------------------
# _format_event_rule
# ---------------------------------------------------------------------------
class TestFormatEventRule(unittest.TestCase):
    def test_all_fields(self):
        result = _format_event_rule(FAKE_RULE)
        self.assertEqual(result["sys_id"], FAKE_RULE["sys_id"])
        self.assertEqual(result["name"], "incident.created")
        self.assertTrue(result["active"])
        self.assertEqual(result["application"], "Global")
        self.assertEqual(result["script"], "gs.log('hello');")

    def test_active_false(self):
        result = _format_event_rule(dict(FAKE_RULE, active="false"))
        self.assertFalse(result["active"])

    def test_active_bool_passthrough(self):
        result = _format_event_rule(dict(FAKE_RULE, active=True))
        self.assertTrue(result["active"])

    def test_application_string(self):
        result = _format_event_rule(dict(FAKE_RULE, application="Global"))
        self.assertEqual(result["application"], "Global")

    def test_application_dict_no_display(self):
        result = _format_event_rule(dict(FAKE_RULE, application={"value": "global_sys"}))
        self.assertEqual(result["application"], "global_sys")

    def test_missing_fields(self):
        result = _format_event_rule({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["name"])


# ---------------------------------------------------------------------------
# _resolve_event_rule_sys_id
# ---------------------------------------------------------------------------
class TestResolveEventRuleSysId(unittest.TestCase):
    def test_hex_sys_id_passthrough(self):
        sys_id = "a" * 32
        result = _resolve_event_rule_sys_id(sys_id, INSTANCE_URL, {})
        self.assertEqual(result, sys_id)

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_name_lookup_found(self, mock_req):
        mock_req.return_value = _mock_response(200, {"result": [{"sys_id": "found_sys_id"}]})
        result = _resolve_event_rule_sys_id("incident.created", INSTANCE_URL, {})
        self.assertEqual(result, "found_sys_id")

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_name_lookup_not_found(self, mock_req):
        mock_req.return_value = _mock_response(200, {"result": []})
        result = _resolve_event_rule_sys_id("no.such.rule", INSTANCE_URL, {})
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_name_lookup_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.ConnectionError("fail")
        result = _resolve_event_rule_sys_id("incident.created", INSTANCE_URL, {})
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# list_event_rules
# ---------------------------------------------------------------------------
class TestListEventRules(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_success_no_filters(self, mock_req):
        mock_req.return_value = _mock_response(200, {"result": [FAKE_RULE]})
        result = list_event_rules(self.auth, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["event_rules"]), 1)
        self.assertEqual(result["event_rules"][0]["name"], "incident.created")

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_success_with_filters(self, mock_req):
        mock_req.return_value = _mock_response(200, {"result": [FAKE_RULE]})
        result = list_event_rules(
            self.auth,
            self.config,
            {"name": "incident", "active": True, "queue": "default", "application": "Global"},
        )
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("incident", call_params.get("sysparm_query", ""))
        self.assertIn("active=true", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_active_false_filter(self, mock_req):
        mock_req.return_value = _mock_response(200, {"result": []})
        result = list_event_rules(self.auth, self.config, {"active": False})
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=false", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_pagination(self, mock_req):
        rules = [dict(FAKE_RULE, sys_id=f"r{i:030d}") for i in range(20)]
        mock_req.return_value = _mock_response(200, {"result": rules})
        result = list_event_rules(self.auth, self.config, {"limit": 20, "offset": 0})
        self.assertTrue(result.get("has_more"))

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {}
        auth.instance_url = None
        config = ServerConfig(instance_url="", auth=_make_config().auth)
        result = list_event_rules(auth, config, {})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = INSTANCE_URL
        result = list_event_rules(auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.ConnectionError("network error")
        result = list_event_rules(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing event rules", result["message"])


# ---------------------------------------------------------------------------
# get_event_rule
# ---------------------------------------------------------------------------
class TestGetEventRule(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    def test_missing_rule_id(self):
        result = get_event_rule(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_success_by_sys_id(self, mock_req):
        sys_id = "a" * 32
        mock_req.return_value = _mock_response(200, {"result": dict(FAKE_RULE, sys_id=sys_id)})
        result = get_event_rule(self.auth, self.config, {"rule_id": sys_id})
        self.assertTrue(result["success"])
        self.assertIn("event_rule", result)

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_success_by_name(self, mock_req):
        # First call resolves name→sys_id, second fetches the record
        mock_req.side_effect = [
            _mock_response(200, {"result": [{"sys_id": "resolved_id"}]}),
            _mock_response(200, {"result": FAKE_RULE}),
        ]
        result = get_event_rule(self.auth, self.config, {"rule_id": "incident.created"})
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_not_found_by_name(self, mock_req):
        mock_req.return_value = _mock_response(200, {"result": []})
        result = get_event_rule(self.auth, self.config, {"rule_id": "no.such.rule"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_404_response(self, mock_req):
        sys_id = "b" * 32
        # _resolve returns the sys_id (passthrough), then GET returns 404
        mock_req.return_value = _mock_response(404)
        result = get_event_rule(self.auth, self.config, {"rule_id": sys_id})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_empty_result(self, mock_req):
        sys_id = "c" * 32
        mock_req.return_value = _mock_response(200, {"result": {}})
        result = get_event_rule(self.auth, self.config, {"rule_id": sys_id})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_request_exception(self, mock_req):
        sys_id = "d" * 32
        mock_req.side_effect = req.exceptions.ConnectionError("fail")
        result = get_event_rule(self.auth, self.config, {"rule_id": sys_id})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {}
        auth.instance_url = None
        config = ServerConfig(instance_url="", auth=_make_config().auth)
        result = get_event_rule(auth, config, {"rule_id": "a" * 32})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = INSTANCE_URL
        result = get_event_rule(auth, self.config, {"rule_id": "a" * 32})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# create_event_rule
# ---------------------------------------------------------------------------
class TestCreateEventRule(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()
        self.base_params = {
            "name": "incident.created",
            "script": "gs.log('new incident');",
        }

    def test_missing_required_fields(self):
        result = create_event_rule(self.auth, self.config, {})
        self.assertFalse(result["success"])

    def test_missing_script(self):
        result = create_event_rule(self.auth, self.config, {"name": "incident.created"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_success_minimal(self, mock_req):
        mock_req.return_value = _mock_response(201, {"result": FAKE_RULE})
        result = create_event_rule(self.auth, self.config, self.base_params)
        self.assertTrue(result["success"])
        self.assertIn("created successfully", result["message"])
        self.assertIn("event_rule", result)

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_success_all_fields(self, mock_req):
        mock_req.return_value = _mock_response(201, {"result": FAKE_RULE})
        params = dict(
            self.base_params,
            description="Handle new incidents",
            active=False,
            order=200,
            condition="event.parm1 != ''",
            filter_fields="parm1",
            queue="high_priority",
        )
        result = create_event_rule(self.auth, self.config, params)
        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["active"], "false")
        self.assertEqual(body["order"], "200")
        self.assertEqual(body["queue"], "high_priority")

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_active_defaults_true(self, mock_req):
        mock_req.return_value = _mock_response(201, {"result": FAKE_RULE})
        create_event_rule(self.auth, self.config, self.base_params)
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["active"], "true")

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.ConnectionError("fail")
        result = create_event_rule(self.auth, self.config, self.base_params)
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {}
        auth.instance_url = None
        config = ServerConfig(instance_url="", auth=_make_config().auth)
        result = create_event_rule(auth, config, self.base_params)
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = INSTANCE_URL
        result = create_event_rule(auth, self.config, self.base_params)
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# update_event_rule
# ---------------------------------------------------------------------------
class TestUpdateEventRule(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()
        self.sys_id = "e" * 32

    def test_missing_rule_id(self):
        result = update_event_rule(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_empty_body_guard(self, mock_req):
        result = update_event_rule(self.auth, self.config, {"rule_id": self.sys_id})
        self.assertFalse(result["success"])
        self.assertIn("No fields", result["message"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_success(self, mock_req):
        mock_req.return_value = _mock_response(200, {"result": FAKE_RULE})
        result = update_event_rule(
            self.auth,
            self.config,
            {"rule_id": self.sys_id, "active": False, "order": 50},
        )
        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["active"], "false")
        self.assertEqual(body["order"], "50")

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_all_optional_fields(self, mock_req):
        mock_req.return_value = _mock_response(200, {"result": FAKE_RULE})
        result = update_event_rule(
            self.auth,
            self.config,
            {
                "rule_id": self.sys_id,
                "name": "new.event",
                "script": "gs.log('updated');",
                "description": "New description",
                "active": True,
                "order": 10,
                "condition": "true",
                "filter_fields": "parm1",
                "queue": "low",
            },
        )
        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["name"], "new.event")
        self.assertEqual(body["queue"], "low")

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_name_resolution_failure(self, mock_req):
        mock_req.return_value = _mock_response(200, {"result": []})
        result = update_event_rule(self.auth, self.config, {"rule_id": "no.such.rule", "active": True})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_404_response(self, mock_req):
        mock_req.return_value = _mock_response(404)
        result = update_event_rule(self.auth, self.config, {"rule_id": self.sys_id, "active": True})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_request_exception(self, mock_req):
        def side_effect(method, *args, **kwargs):
            if method == "PATCH":
                raise req.exceptions.ConnectionError("fail")
            return _mock_response(200, {"result": []})

        mock_req.side_effect = side_effect
        result = update_event_rule(self.auth, self.config, {"rule_id": self.sys_id, "active": True})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {}
        auth.instance_url = None
        config = ServerConfig(instance_url="", auth=_make_config().auth)
        result = update_event_rule(auth, config, {"rule_id": self.sys_id, "active": True})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = INSTANCE_URL
        result = update_event_rule(auth, self.config, {"rule_id": self.sys_id, "active": True})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# delete_event_rule
# ---------------------------------------------------------------------------
class TestDeleteEventRule(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()
        self.sys_id = "f" * 32

    def test_missing_rule_id(self):
        result = delete_event_rule(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_success_204(self, mock_req):
        mock_req.return_value = _mock_response(204)
        result = delete_event_rule(self.auth, self.config, {"rule_id": self.sys_id})
        self.assertTrue(result["success"])
        self.assertIn("deleted successfully", result["message"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_success_200(self, mock_req):
        mock_req.return_value = _mock_response(200, {"result": {}})
        result = delete_event_rule(self.auth, self.config, {"rule_id": self.sys_id})
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_404_response(self, mock_req):
        mock_req.return_value = _mock_response(404)
        result = delete_event_rule(self.auth, self.config, {"rule_id": self.sys_id})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_not_found_by_name(self, mock_req):
        mock_req.return_value = _mock_response(200, {"result": []})
        result = delete_event_rule(self.auth, self.config, {"rule_id": "no.such.rule"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.event_rule_tools._make_request")
    def test_request_exception(self, mock_req):
        def side_effect(method, *args, **kwargs):
            if method == "DELETE":
                raise req.exceptions.ConnectionError("fail")
            return _mock_response(200, {"result": []})

        mock_req.side_effect = side_effect
        result = delete_event_rule(self.auth, self.config, {"rule_id": self.sys_id})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {}
        auth.instance_url = None
        config = ServerConfig(instance_url="", auth=_make_config().auth)
        result = delete_event_rule(auth, config, {"rule_id": self.sys_id})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = INSTANCE_URL
        result = delete_event_rule(auth, self.config, {"rule_id": self.sys_id})
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
