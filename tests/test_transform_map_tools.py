"""Tests for transform_map_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests as req

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.transform_map_tools import (
    _format_transform_map,
    _resolve_transform_map_sys_id,
    create_transform_map,
    delete_transform_map,
    get_transform_map,
    list_transform_maps,
    run_transform,
    update_transform_map,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
INSTANCE_URL = "https://dev99999.service-now.com"

FAKE_MAP = {
    "sys_id": FAKE_SYS_ID,
    "name": "User Import Map",
    "source_table": "u_import_users",
    "target_table": "sys_user",
    "active": "true",
    "run_business_rules": "true",
    "enforce_mandatory_fields": "true",
    "copy_empty_fields": "false",
    "order": "100",
    "sys_created_on": "2026-10-20 08:00:00",
    "sys_updated_on": "2026-10-20 09:00:00",
    "sys_created_by": "admin",
    "sys_updated_by": "admin",
}


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url=INSTANCE_URL, auth=auth_config)


def _make_auth():
    am = MagicMock(spec=AuthManager)
    am.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    am.instance_url = INSTANCE_URL
    return am


def _mock_resp(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = req.exceptions.HTTPError(response=resp)
    return resp


# ---------------------------------------------------------------------------
# _format_transform_map
# ---------------------------------------------------------------------------
class TestFormatTransformMap(unittest.TestCase):
    def test_string_booleans_true(self):
        result = _format_transform_map(FAKE_MAP)
        self.assertTrue(result["active"])
        self.assertTrue(result["run_business_rules"])
        self.assertTrue(result["enforce_mandatory_fields"])
        self.assertFalse(result["copy_empty_fields"])

    def test_string_booleans_false(self):
        result = _format_transform_map(dict(FAKE_MAP, active="false", run_business_rules="false"))
        self.assertFalse(result["active"])
        self.assertFalse(result["run_business_rules"])

    def test_source_table_dict(self):
        result = _format_transform_map(dict(FAKE_MAP, source_table={"display_value": "Import Users", "value": "u_import_users"}))
        self.assertEqual(result["source_table"], "Import Users")

    def test_target_table_dict(self):
        result = _format_transform_map(dict(FAKE_MAP, target_table={"display_value": "User", "value": "sys_user"}))
        self.assertEqual(result["target_table"], "User")

    def test_target_table_dict_no_display(self):
        result = _format_transform_map(dict(FAKE_MAP, target_table={"display_value": None, "value": "sys_user"}))
        self.assertEqual(result["target_table"], "sys_user")

    def test_basic_fields(self):
        result = _format_transform_map(FAKE_MAP)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["name"], "User Import Map")
        self.assertEqual(result["order"], "100")
        self.assertEqual(result["created_by"], "admin")
        self.assertEqual(result["updated_by"], "admin")


# ---------------------------------------------------------------------------
# _resolve_transform_map_sys_id
# ---------------------------------------------------------------------------
class TestResolveTransformMapSysId(unittest.TestCase):
    def test_hex_sys_id_returned_directly(self):
        result = _resolve_transform_map_sys_id(FAKE_SYS_ID, INSTANCE_URL, {})
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_name_resolved(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        result = _resolve_transform_map_sys_id("User Import Map", INSTANCE_URL, {})
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_name_not_found(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = _resolve_transform_map_sys_id("Unknown Map", INSTANCE_URL, {})
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.RequestException("timeout")
        result = _resolve_transform_map_sys_id("User Import Map", INSTANCE_URL, {})
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# list_transform_maps
# ---------------------------------------------------------------------------
class TestListTransformMaps(unittest.TestCase):
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_success_no_filters(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": [FAKE_MAP]})
        result = list_transform_maps(_make_auth(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["transform_maps"]), 1)
        self.assertEqual(result["transform_maps"][0]["name"], "User Import Map")

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_success_with_all_filters(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": [FAKE_MAP]})
        result = list_transform_maps(_make_auth(), _make_config(), {
            "name": "User",
            "source_table": "u_import",
            "target_table": "sys_user",
            "active": True,
        })
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("nameLIKEUser", call_params.get("sysparm_query", ""))
        self.assertIn("active=true", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_active_false_filter(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = list_transform_maps(_make_auth(), _make_config(), {"active": False})
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=false", call_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_http_error(self, mock_req):
        mock_req.return_value = _mock_resp(500)
        result = list_transform_maps(_make_auth(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.RequestException("network error")
        result = list_transform_maps(_make_auth(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        auth = _make_auth()
        auth.instance_url = None
        config = _make_config()
        config.instance_url = None
        result = list_transform_maps(auth, config, {})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = _make_auth()
        auth.get_headers.return_value = None
        config = _make_config()
        config.instance_url = None
        result = list_transform_maps(auth, config, {})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# get_transform_map
# ---------------------------------------------------------------------------
class TestGetTransformMap(unittest.TestCase):
    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_success(self, mock_req, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        mock_req.return_value = _mock_resp(200, {"result": FAKE_MAP})
        result = get_transform_map(_make_auth(), _make_config(), {"map_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["transform_map"]["name"], "User Import Map")

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    def test_map_not_found_resolver(self, mock_resolve):
        mock_resolve.return_value = None
        result = get_transform_map(_make_auth(), _make_config(), {"map_id": "Unknown"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_404_response(self, mock_req, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        mock_req.return_value = _mock_resp(404)
        result = get_transform_map(_make_auth(), _make_config(), {"map_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_empty_result(self, mock_req, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        mock_req.return_value = _mock_resp(200, {"result": {}})
        result = get_transform_map(_make_auth(), _make_config(), {"map_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])

    def test_missing_required_param(self):
        result = get_transform_map(_make_auth(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_request_exception(self, mock_req, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        mock_req.side_effect = req.exceptions.RequestException("timeout")
        result = get_transform_map(_make_auth(), _make_config(), {"map_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# create_transform_map
# ---------------------------------------------------------------------------
class TestCreateTransformMap(unittest.TestCase):
    def _params(self, **overrides):
        base = {
            "name": "User Import Map",
            "source_table": "u_import_users",
            "target_table": "sys_user",
        }
        base.update(overrides)
        return base

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_success_minimal(self, mock_req):
        mock_req.return_value = _mock_resp(201, {"result": FAKE_MAP})
        result = create_transform_map(_make_auth(), _make_config(), self._params())
        self.assertTrue(result["success"])
        self.assertIn("created", result["message"])
        self.assertIn("transform_map", result)

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_success_all_optional_fields(self, mock_req):
        mock_req.return_value = _mock_resp(201, {"result": FAKE_MAP})
        result = create_transform_map(_make_auth(), _make_config(), self._params(
            active=False,
            run_business_rules=False,
            enforce_mandatory_fields=False,
            copy_empty_fields=True,
            order=200,
        ))
        self.assertTrue(result["success"])
        body_sent = mock_req.call_args[1]["json"]
        self.assertEqual(body_sent["active"], "false")
        self.assertEqual(body_sent["copy_empty_fields"], "true")
        self.assertEqual(body_sent["order"], "200")

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_http_error(self, mock_req):
        mock_req.return_value = _mock_resp(400)
        result = create_transform_map(_make_auth(), _make_config(), self._params())
        self.assertFalse(result["success"])

    def test_missing_required_fields(self):
        result = create_transform_map(_make_auth(), _make_config(), {"name": "Only Name"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.RequestException("error")
        result = create_transform_map(_make_auth(), _make_config(), self._params())
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# update_transform_map
# ---------------------------------------------------------------------------
class TestUpdateTransformMap(unittest.TestCase):
    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_success(self, mock_req, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        mock_req.return_value = _mock_resp(200, {"result": FAKE_MAP})
        result = update_transform_map(_make_auth(), _make_config(), {
            "map_id": FAKE_SYS_ID,
            "active": False,
        })
        self.assertTrue(result["success"])
        self.assertIn("updated", result["message"])

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    def test_map_not_found(self, mock_resolve):
        mock_resolve.return_value = None
        result = update_transform_map(_make_auth(), _make_config(), {"map_id": "nope", "name": "x"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    def test_empty_body_guard(self, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        result = update_transform_map(_make_auth(), _make_config(), {"map_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("No fields", result["message"])

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_404_response(self, mock_req, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        mock_req.return_value = _mock_resp(404)
        result = update_transform_map(_make_auth(), _make_config(), {
            "map_id": FAKE_SYS_ID,
            "name": "New Name",
        })
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_all_optional_fields(self, mock_req, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        mock_req.return_value = _mock_resp(200, {"result": FAKE_MAP})
        result = update_transform_map(_make_auth(), _make_config(), {
            "map_id": FAKE_SYS_ID,
            "name": "New Name",
            "source_table": "u_import_new",
            "target_table": "cmdb_ci",
            "active": True,
            "run_business_rules": False,
            "enforce_mandatory_fields": False,
            "copy_empty_fields": True,
            "order": 50,
        })
        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["name"], "New Name")
        self.assertEqual(body["run_business_rules"], "false")
        self.assertEqual(body["order"], "50")

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_request_exception(self, mock_req, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        mock_req.side_effect = req.exceptions.RequestException("err")
        result = update_transform_map(_make_auth(), _make_config(), {
            "map_id": FAKE_SYS_ID, "name": "x"
        })
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# delete_transform_map
# ---------------------------------------------------------------------------
class TestDeleteTransformMap(unittest.TestCase):
    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_success_204(self, mock_req, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        mock_req.return_value = _mock_resp(204)
        result = delete_transform_map(_make_auth(), _make_config(), {"map_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertIn("deleted", result["message"])

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_success_200(self, mock_req, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        mock_req.return_value = _mock_resp(200)
        result = delete_transform_map(_make_auth(), _make_config(), {"map_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    def test_not_found_resolver(self, mock_resolve):
        mock_resolve.return_value = None
        result = delete_transform_map(_make_auth(), _make_config(), {"map_id": "Unknown"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_404_response(self, mock_req, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        mock_req.return_value = _mock_resp(404)
        result = delete_transform_map(_make_auth(), _make_config(), {"map_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])

    def test_missing_required_param(self):
        result = delete_transform_map(_make_auth(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.transform_map_tools._resolve_transform_map_sys_id")
    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_request_exception(self, mock_req, mock_resolve):
        mock_resolve.return_value = FAKE_SYS_ID
        mock_req.side_effect = req.exceptions.RequestException("err")
        result = delete_transform_map(_make_auth(), _make_config(), {"map_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# run_transform
# ---------------------------------------------------------------------------
class TestRunTransform(unittest.TestCase):
    def _params(self, **overrides):
        base = {
            "staging_table": "u_import_users",
            "data": {"u_first_name": "John", "u_last_name": "Doe"},
        }
        base.update(overrides)
        return base

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_success_list_result(self, mock_req):
        mock_req.return_value = _mock_resp(200, {
            "result": [
                {
                    "import_set": "ISET0001234",
                    "staging_table": "u_import_users",
                    "display_value": "ISET0001234",
                    "status": "inserted",
                },
                {
                    "transform_map": "User Import Map",
                    "status": "inserted",
                    "table": "sys_user",
                    "sys_id": FAKE_SYS_ID,
                    "display_value": "John Doe",
                },
            ]
        })
        result = run_transform(_make_auth(), _make_config(), self._params())
        self.assertTrue(result["success"])
        self.assertIn("Transform triggered", result["message"])
        self.assertIsNotNone(result["import_set"])
        self.assertEqual(len(result["transform_results"]), 1)
        self.assertEqual(result["transform_results"][0]["transform_map"], "User Import Map")

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_success_dict_result(self, mock_req):
        mock_req.return_value = _mock_resp(200, {
            "result": {
                "import_set": "ISET0001235",
                "staging_table": "u_import_users",
                "status": "inserted",
            }
        })
        result = run_transform(_make_auth(), _make_config(), self._params())
        self.assertTrue(result["success"])
        self.assertEqual(result["import_set"]["sys_id"], "ISET0001235")
        self.assertEqual(result["transform_results"], [])

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_http_error(self, mock_req):
        mock_req.return_value = _mock_resp(400)
        result = run_transform(_make_auth(), _make_config(), self._params())
        self.assertFalse(result["success"])

    def test_missing_required_fields(self):
        result = run_transform(_make_auth(), _make_config(), {"staging_table": "u_import_users"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.transform_map_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.RequestException("network error")
        result = run_transform(_make_auth(), _make_config(), self._params())
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        auth = _make_auth()
        auth.instance_url = None
        config = _make_config()
        config.instance_url = None
        result = run_transform(auth, config, self._params())
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = _make_auth()
        auth.get_headers.return_value = None
        config = _make_config()
        config.instance_url = None
        result = run_transform(auth, config, self._params())
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
