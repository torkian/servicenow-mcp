"""
Tests for the execute_script_include tool.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.script_include_tools import (
    ExecuteScriptIncludeParams,
    execute_script_include,
)
from servicenow_mcp.utils.config import (
    AuthConfig,
    AuthType,
    BasicAuthConfig,
    ServerConfig,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_ACTIVE_SI = {
    "sys_id": "abc123",
    "name": "MyUtils",
    "active": True,
    "client_callable": False,
    "script": "var MyUtils = Class.create(); ...",
}

_INACTIVE_SI = {**_ACTIVE_SI, "active": False, "name": "InactiveUtils"}


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="admin", password="password"),
    )
    return ServerConfig(
        instance_url="https://test.service-now.com",
        auth=auth_config,
    )


def _make_auth_manager():
    mgr = MagicMock(spec=AuthManager)
    mgr.get_headers.return_value = {
        "Authorization": "Bearer tok",
        "Content-Type": "application/json",
    }
    return mgr


# ---------------------------------------------------------------------------
# ExecuteScriptIncludeParams model tests
# ---------------------------------------------------------------------------


class TestExecuteScriptIncludeParams(unittest.TestCase):
    def test_required_fields(self):
        p = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="getRecords",
        )
        self.assertEqual("MyUtils", p.script_include_id)
        self.assertEqual("getRecords", p.method_name)
        self.assertIsNone(p.method_params)

    def test_with_params(self):
        p = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="add",
            method_params=[1, 2],
        )
        self.assertEqual([1, 2], p.method_params)

    def test_complex_params(self):
        p = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="process",
            method_params=[{"key": "val"}, True, None],
        )
        self.assertEqual(3, len(p.method_params))


# ---------------------------------------------------------------------------
# execute_script_include function tests
# ---------------------------------------------------------------------------


class TestExecuteScriptInclude(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth_manager()

    # ------------------------------------------------------------------
    # Happy path — JSON-parseable output
    # ------------------------------------------------------------------

    @patch("servicenow_mcp.tools.script_include_tools.requests.post")
    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_success_json_result(self, mock_get_si, mock_post):
        mock_get_si.return_value = {"success": True, "script_include": _ACTIVE_SI}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {"output": json.dumps({"count": 42})}
        }
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        params = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="getCount",
        )
        result = execute_script_include(self.config, self.auth, params)

        self.assertTrue(result["success"])
        self.assertEqual("MyUtils", result["script_include_name"])
        self.assertEqual("getCount", result["method_name"])
        self.assertEqual({"count": 42}, result["result"])
        self.assertIn("MyUtils.getCount()", result["message"])

    @patch("servicenow_mcp.tools.script_include_tools.requests.post")
    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_success_string_result(self, mock_get_si, mock_post):
        mock_get_si.return_value = {"success": True, "script_include": _ACTIVE_SI}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {"output": '"hello world"'}
        }
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        params = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="greet",
        )
        result = execute_script_include(self.config, self.auth, params)

        self.assertTrue(result["success"])
        self.assertEqual("hello world", result["result"])

    @patch("servicenow_mcp.tools.script_include_tools.requests.post")
    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_success_print_output_list(self, mock_get_si, mock_post):
        """Endpoint may return output via print_output list instead of output."""
        mock_get_si.return_value = {"success": True, "script_include": _ACTIVE_SI}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {"print_output": ["true"]}
        }
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        params = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="isActive",
        )
        result = execute_script_include(self.config, self.auth, params)

        self.assertTrue(result["success"])
        self.assertTrue(result["result"])

    # ------------------------------------------------------------------
    # Method arguments are forwarded correctly
    # ------------------------------------------------------------------

    @patch("servicenow_mcp.tools.script_include_tools.requests.post")
    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_method_params_serialised_in_script(self, mock_get_si, mock_post):
        mock_get_si.return_value = {"success": True, "script_include": _ACTIVE_SI}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"output": "null"}}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        params = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="add",
            method_params=[3, 4],
        )
        execute_script_include(self.config, self.auth, params)

        _, kwargs = mock_post.call_args
        script_body = kwargs["json"]["script"]
        self.assertIn("obj.add(3, 4)", script_body)

    @patch("servicenow_mcp.tools.script_include_tools.requests.post")
    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_no_params_generates_empty_arg_list(self, mock_get_si, mock_post):
        mock_get_si.return_value = {"success": True, "script_include": _ACTIVE_SI}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"output": "null"}}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        params = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="run",
        )
        execute_script_include(self.config, self.auth, params)

        _, kwargs = mock_post.call_args
        script_body = kwargs["json"]["script"]
        self.assertIn("obj.run()", script_body)

    # ------------------------------------------------------------------
    # Script construction
    # ------------------------------------------------------------------

    @patch("servicenow_mcp.tools.script_include_tools.requests.post")
    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_script_instantiates_correct_class(self, mock_get_si, mock_post):
        mock_get_si.return_value = {"success": True, "script_include": _ACTIVE_SI}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"output": "null"}}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        params = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="doThing",
        )
        execute_script_include(self.config, self.auth, params)

        _, kwargs = mock_post.call_args
        script_body = kwargs["json"]["script"]
        self.assertIn("new MyUtils()", script_body)
        self.assertIn("gs.print(JSON.stringify(result))", script_body)

    # ------------------------------------------------------------------
    # Correct endpoint is called
    # ------------------------------------------------------------------

    @patch("servicenow_mcp.tools.script_include_tools.requests.post")
    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_posts_to_scripting_eval_endpoint(self, mock_get_si, mock_post):
        mock_get_si.return_value = {"success": True, "script_include": _ACTIVE_SI}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"output": "null"}}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        params = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="run",
        )
        execute_script_include(self.config, self.auth, params)

        args, _ = mock_post.call_args
        self.assertEqual(
            "https://test.service-now.com/api/now/v1/scripting/eval",
            args[0],
        )

    # ------------------------------------------------------------------
    # Inactive script include
    # ------------------------------------------------------------------

    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_inactive_script_include_returns_failure(self, mock_get_si):
        mock_get_si.return_value = {
            "success": True,
            "script_include": _INACTIVE_SI,
        }

        params = ExecuteScriptIncludeParams(
            script_include_id="InactiveUtils",
            method_name="run",
        )
        result = execute_script_include(self.config, self.auth, params)

        self.assertFalse(result["success"])
        self.assertIn("not active", result["message"])
        self.assertIsNone(result["result"])

    # ------------------------------------------------------------------
    # Script include not found
    # ------------------------------------------------------------------

    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_script_include_not_found(self, mock_get_si):
        mock_get_si.return_value = {
            "success": False,
            "message": "Script include not found: UnknownUtils",
        }

        params = ExecuteScriptIncludeParams(
            script_include_id="UnknownUtils",
            method_name="run",
        )
        result = execute_script_include(self.config, self.auth, params)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertIsNone(result["script_include_name"])

    # ------------------------------------------------------------------
    # HTTP error from eval endpoint
    # ------------------------------------------------------------------

    @patch("servicenow_mcp.tools.script_include_tools.requests.post")
    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_http_403_returns_failure(self, mock_get_si, mock_post):
        mock_get_si.return_value = {"success": True, "script_include": _ACTIVE_SI}

        http_err_resp = MagicMock()
        http_err_resp.status_code = 403
        http_err_resp.json.return_value = {
            "error": {"message": "Insufficient privileges"}
        }
        mock_post.side_effect = requests.HTTPError(response=http_err_resp)

        params = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="run",
        )
        result = execute_script_include(self.config, self.auth, params)

        self.assertFalse(result["success"])
        self.assertIn("403", result["message"])
        self.assertIn("Insufficient privileges", result["message"])

    @patch("servicenow_mcp.tools.script_include_tools.requests.post")
    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_network_error_returns_failure(self, mock_get_si, mock_post):
        mock_get_si.return_value = {"success": True, "script_include": _ACTIVE_SI}
        mock_post.side_effect = requests.ConnectionError("Network unreachable")

        params = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="run",
        )
        result = execute_script_include(self.config, self.auth, params)

        self.assertFalse(result["success"])
        self.assertIn("Error executing script include", result["message"])

    # ------------------------------------------------------------------
    # Non-JSON output is returned as raw string
    # ------------------------------------------------------------------

    @patch("servicenow_mcp.tools.script_include_tools.requests.post")
    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_non_json_output_returned_as_string(self, mock_get_si, mock_post):
        mock_get_si.return_value = {"success": True, "script_include": _ACTIVE_SI}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"output": "plain text output"}}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        params = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="describe",
        )
        result = execute_script_include(self.config, self.auth, params)

        self.assertTrue(result["success"])
        self.assertEqual("plain text output", result["result"])

    # ------------------------------------------------------------------
    # Empty output → result is None
    # ------------------------------------------------------------------

    @patch("servicenow_mcp.tools.script_include_tools.requests.post")
    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_empty_output_result_is_none(self, mock_get_si, mock_post):
        mock_get_si.return_value = {"success": True, "script_include": _ACTIVE_SI}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"output": ""}}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        params = ExecuteScriptIncludeParams(
            script_include_id="MyUtils",
            method_name="noop",
        )
        result = execute_script_include(self.config, self.auth, params)

        self.assertTrue(result["success"])
        self.assertIsNone(result["result"])

    # ------------------------------------------------------------------
    # sys_id prefix forwarded to get_script_include
    # ------------------------------------------------------------------

    @patch("servicenow_mcp.tools.script_include_tools.requests.post")
    @patch("servicenow_mcp.tools.script_include_tools.get_script_include")
    def test_sys_id_prefix_forwarded(self, mock_get_si, mock_post):
        mock_get_si.return_value = {"success": True, "script_include": _ACTIVE_SI}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"output": "null"}}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        params = ExecuteScriptIncludeParams(
            script_include_id="sys_id:abc123",
            method_name="run",
        )
        execute_script_include(self.config, self.auth, params)

        call_args = mock_get_si.call_args
        forwarded_params = call_args[0][2]
        self.assertEqual("sys_id:abc123", forwarded_params.script_include_id)


if __name__ == "__main__":
    unittest.main()
