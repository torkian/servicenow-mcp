"""Tests for import_set_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests as req

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.import_set_tools import (
    _format_import_set,
    _resolve_import_set_sys_id,
    cleanup_import_set,
    get_import_set,
    list_import_sets,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "c" * 32
INSTANCE_URL = "https://dev99999.service-now.com"

FAKE_IMPORT_SET = {
    "sys_id": FAKE_SYS_ID,
    "label": "ISET0010001",
    "table_name": "u_import_users",
    "state": "complete",
    "import_count": "50",
    "error_count": "2",
    "skip_count": "0",
    "complete_source": "true",
    "data_source": {"display_value": "User CSV Import", "value": "a" * 32},
    "sys_created_on": "2026-10-20 08:00:00",
    "sys_updated_on": "2026-10-20 08:05:00",
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
# _format_import_set
# ---------------------------------------------------------------------------
class TestFormatImportSet(unittest.TestCase):
    def test_basic_fields(self):
        result = _format_import_set(FAKE_IMPORT_SET)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["label"], "ISET0010001")
        self.assertEqual(result["table_name"], "u_import_users")
        self.assertEqual(result["state"], "complete")
        self.assertEqual(result["import_count"], "50")
        self.assertEqual(result["error_count"], "2")
        self.assertEqual(result["skip_count"], "0")
        self.assertEqual(result["created_by"], "admin")
        self.assertEqual(result["updated_by"], "admin")

    def test_data_source_dict_normalised(self):
        result = _format_import_set(FAKE_IMPORT_SET)
        self.assertEqual(result["data_source"], "User CSV Import")

    def test_data_source_dict_no_display(self):
        rec = dict(FAKE_IMPORT_SET, data_source={"display_value": None, "value": "fallback"})
        result = _format_import_set(rec)
        self.assertEqual(result["data_source"], "fallback")

    def test_complete_source_true_string(self):
        result = _format_import_set(FAKE_IMPORT_SET)
        self.assertTrue(result["complete_source"])

    def test_complete_source_false_string(self):
        rec = dict(FAKE_IMPORT_SET, complete_source="false")
        result = _format_import_set(rec)
        self.assertFalse(result["complete_source"])

    def test_data_source_string_passthrough(self):
        rec = dict(FAKE_IMPORT_SET, data_source="plain string")
        result = _format_import_set(rec)
        self.assertEqual(result["data_source"], "plain string")


# ---------------------------------------------------------------------------
# _resolve_import_set_sys_id
# ---------------------------------------------------------------------------
class TestResolveImportSetSysId(unittest.TestCase):
    def test_returns_sys_id_directly(self):
        result = _resolve_import_set_sys_id(FAKE_SYS_ID, INSTANCE_URL, {})
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    def test_resolves_by_label(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        result = _resolve_import_set_sys_id("ISET0010001", INSTANCE_URL, {})
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    def test_returns_none_when_not_found(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = _resolve_import_set_sys_id("NONEXISTENT", INSTANCE_URL, {})
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    def test_returns_none_on_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.ConnectionError("timeout")
        result = _resolve_import_set_sys_id("ISET0010001", INSTANCE_URL, {})
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# list_import_sets
# ---------------------------------------------------------------------------
class TestListImportSets(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth()
        self.config = _make_config()

    def test_invalid_params(self):
        result = list_import_sets(self.auth, self.config, {"params": {"limit": "bad"}})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=None)
    def test_no_instance_url(self, _):
        result = list_import_sets(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value=None)
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_no_headers(self, _iu, _h):
        result = list_import_sets(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_returns_list(self, _iu, _h, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": [FAKE_IMPORT_SET]})
        result = list_import_sets(self.auth, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["import_sets"]), 1)
        self.assertFalse(result["has_more"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_filter_label(self, _iu, _h, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = list_import_sets(self.auth, self.config, {"params": {"label": "ISET"}})
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("labelLIKEISET", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_filter_table_name(self, _iu, _h, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = list_import_sets(self.auth, self.config, {"params": {"table_name": "u_import_users"}})
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("table_name=u_import_users", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_filter_state(self, _iu, _h, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = list_import_sets(self.auth, self.config, {"params": {"state": "complete"}})
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("state=complete", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_filter_data_source(self, _iu, _h, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = list_import_sets(self.auth, self.config, {"params": {"data_source": "CSV"}})
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("data_source.nameLIKECSV", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_request_exception(self, _iu, _h, mock_req):
        mock_req.side_effect = req.exceptions.ConnectionError("timeout")
        result = list_import_sets(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing import sets", result["message"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_has_more_when_full_page(self, _iu, _h, mock_req):
        records = [dict(FAKE_IMPORT_SET, sys_id=f"{i:032x}") for i in range(20)]
        mock_req.return_value = _mock_resp(200, {"result": records})
        result = list_import_sets(self.auth, self.config, {"params": {"limit": 20}})
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 20)


# ---------------------------------------------------------------------------
# get_import_set
# ---------------------------------------------------------------------------
class TestGetImportSet(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth()
        self.config = _make_config()

    def test_missing_import_set_id(self):
        result = get_import_set(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=None)
    def test_no_instance_url(self, _):
        result = get_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value=None)
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_no_headers(self, _iu, _h):
        result = get_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.import_set_tools._resolve_import_set_sys_id", return_value=None)
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_not_found(self, _iu, _h, _res):
        result = get_import_set(self.auth, self.config, {"params": {"import_set_id": "bad-label"}})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._resolve_import_set_sys_id", return_value=FAKE_SYS_ID)
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_success(self, _iu, _h, _res, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": FAKE_IMPORT_SET})
        result = get_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertTrue(result["success"])
        self.assertEqual(result["import_set"]["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._resolve_import_set_sys_id", return_value=FAKE_SYS_ID)
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_404_response(self, _iu, _h, _res, mock_req):
        mock_req.return_value = _mock_resp(404)
        result = get_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._resolve_import_set_sys_id", return_value=FAKE_SYS_ID)
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_empty_result(self, _iu, _h, _res, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": None})
        result = get_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._resolve_import_set_sys_id", return_value=FAKE_SYS_ID)
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_request_exception(self, _iu, _h, _res, mock_req):
        mock_req.side_effect = req.exceptions.ConnectionError("timeout")
        result = get_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving import set", result["message"])


# ---------------------------------------------------------------------------
# cleanup_import_set
# ---------------------------------------------------------------------------
class TestCleanupImportSet(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth()
        self.config = _make_config()

    def test_missing_import_set_id(self):
        result = cleanup_import_set(self.auth, self.config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=None)
    def test_no_instance_url(self, _):
        result = cleanup_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value=None)
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_no_headers(self, _iu, _h):
        result = cleanup_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.import_set_tools._resolve_import_set_sys_id", return_value=None)
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_not_found(self, _iu, _h, _res):
        result = cleanup_import_set(self.auth, self.config, {"params": {"import_set_id": "ISET0010001"}})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._resolve_import_set_sys_id", return_value=FAKE_SYS_ID)
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_success_204(self, _iu, _h, _res, mock_req):
        mock_req.return_value = _mock_resp(204)
        result = cleanup_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertTrue(result["success"])
        self.assertIn("deleted successfully", result["message"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._resolve_import_set_sys_id", return_value=FAKE_SYS_ID)
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_success_200(self, _iu, _h, _res, mock_req):
        mock_req.return_value = _mock_resp(200)
        result = cleanup_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertTrue(result["success"])
        self.assertIn("deleted successfully", result["message"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._resolve_import_set_sys_id", return_value=FAKE_SYS_ID)
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_404_response(self, _iu, _h, _res, mock_req):
        mock_req.return_value = _mock_resp(404)
        result = cleanup_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._resolve_import_set_sys_id", return_value=FAKE_SYS_ID)
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_request_exception(self, _iu, _h, _res, mock_req):
        mock_req.side_effect = req.exceptions.ConnectionError("timeout")
        result = cleanup_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertFalse(result["success"])
        self.assertIn("Error deleting import set", result["message"])

    @patch("servicenow_mcp.tools.import_set_tools._make_request")
    @patch("servicenow_mcp.tools.import_set_tools._resolve_import_set_sys_id", return_value=FAKE_SYS_ID)
    @patch("servicenow_mcp.tools.import_set_tools._get_headers", return_value={"Authorization": "Bearer FAKE"})
    @patch("servicenow_mcp.tools.import_set_tools._get_instance_url", return_value=INSTANCE_URL)
    def test_unexpected_status_still_succeeds(self, _iu, _h, _res, mock_req):
        resp = MagicMock()
        resp.status_code = 202
        resp.raise_for_status = MagicMock()
        mock_req.return_value = resp
        result = cleanup_import_set(self.auth, self.config, {"params": {"import_set_id": FAKE_SYS_ID}})
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
