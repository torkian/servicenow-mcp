"""Tests for data_source_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests as req

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.data_source_tools import (
    _format_data_source,
    _resolve_data_source_sys_id,
    create_data_source,
    delete_data_source,
    get_data_source,
    list_data_sources,
    load_data_source,
    update_data_source,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "b" * 32
INSTANCE_URL = "https://dev99999.service-now.com"

FAKE_SOURCE = {
    "sys_id": FAKE_SYS_ID,
    "name": "User CSV Import",
    "import_set_table_name": "u_import_users",
    "format": "csv",
    "file_retrieval_method": "http",
    "source": "https://example.com/users.csv",
    "header_row": "true",
    "comma_separated": "true",
    "csv_separator": "",
    "active": "true",
    "last_import_set": "ISET0010001",
    "last_run": "2026-10-20 08:00:00",
    "sys_created_on": "2026-10-01 09:00:00",
    "sys_updated_on": "2026-10-20 08:00:00",
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
# _format_data_source
# ---------------------------------------------------------------------------
class TestFormatDataSource(unittest.TestCase):
    def test_string_booleans_true(self):
        result = _format_data_source(FAKE_SOURCE)
        self.assertTrue(result["active"])
        self.assertTrue(result["header_row"])
        self.assertTrue(result["comma_separated"])

    def test_string_booleans_false(self):
        result = _format_data_source(dict(FAKE_SOURCE, active="false", header_row="false", comma_separated="false"))
        self.assertFalse(result["active"])
        self.assertFalse(result["header_row"])
        self.assertFalse(result["comma_separated"])

    def test_last_import_set_dict(self):
        result = _format_data_source(dict(FAKE_SOURCE, last_import_set={"display_value": "ISET001", "value": "abc123"}))
        self.assertEqual(result["last_import_set"], "ISET001")

    def test_last_import_set_dict_no_display(self):
        result = _format_data_source(dict(FAKE_SOURCE, last_import_set={"display_value": None, "value": "abc123"}))
        self.assertEqual(result["last_import_set"], "abc123")

    def test_basic_fields(self):
        result = _format_data_source(FAKE_SOURCE)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["name"], "User CSV Import")
        self.assertEqual(result["import_set_table_name"], "u_import_users")
        self.assertEqual(result["format"], "csv")
        self.assertEqual(result["file_retrieval_method"], "http")
        self.assertEqual(result["source"], "https://example.com/users.csv")
        self.assertEqual(result["created_by"], "admin")
        self.assertEqual(result["updated_by"], "admin")


# ---------------------------------------------------------------------------
# _resolve_data_source_sys_id
# ---------------------------------------------------------------------------
class TestResolveDataSourceSysId(unittest.TestCase):
    def test_returns_sys_id_directly(self):
        result = _resolve_data_source_sys_id(FAKE_SYS_ID, INSTANCE_URL, {})
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_resolves_by_name(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        result = _resolve_data_source_sys_id("User CSV Import", INSTANCE_URL, {})
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_returns_none_when_not_found(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = _resolve_data_source_sys_id("Nonexistent", INSTANCE_URL, {})
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_returns_none_on_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.ConnectionError("err")
        result = _resolve_data_source_sys_id("Any Name", INSTANCE_URL, {})
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# list_data_sources
# ---------------------------------------------------------------------------
class TestListDataSources(unittest.TestCase):
    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_success(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": [FAKE_SOURCE]})
        result = list_data_sources(_make_auth(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["data_sources"]), 1)
        self.assertEqual(result["data_sources"][0]["name"], "User CSV Import")

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_filters_applied(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = list_data_sources(
            _make_auth(),
            _make_config(),
            {"name": "User", "format": "csv", "file_retrieval_method": "http", "active": True},
        )
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("nameLIKEUser", call_params["sysparm_query"])
        self.assertIn("format=csv", call_params["sysparm_query"])
        self.assertIn("file_retrieval_method=http", call_params["sysparm_query"])
        self.assertIn("active=true", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_active_false_filter(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = list_data_sources(_make_auth(), _make_config(), {"active": False})
        self.assertTrue(result["success"])
        call_params = mock_req.call_args[1]["params"]
        self.assertIn("active=false", call_params["sysparm_query"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_http_error(self, mock_req):
        mock_req.return_value = _mock_resp(500)
        result = list_data_sources(_make_auth(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        am = MagicMock(spec=AuthManager)
        am.instance_url = None
        am.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        cfg = MagicMock()
        cfg.instance_url = None
        result = list_data_sources(am, cfg, {})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        am = MagicMock(spec=AuthManager)
        am.instance_url = INSTANCE_URL
        am.get_headers.return_value = {}
        cfg = MagicMock()
        cfg.instance_url = INSTANCE_URL
        result = list_data_sources(am, cfg, {})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# get_data_source
# ---------------------------------------------------------------------------
class TestGetDataSource(unittest.TestCase):
    def test_missing_source_id(self):
        result = get_data_source(_make_auth(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_success(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": FAKE_SOURCE})
        result = get_data_source(_make_auth(), _make_config(), {"source_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["data_source"]["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_not_found_404(self, mock_req):
        mock_req.return_value = _mock_resp(404)
        result = get_data_source(_make_auth(), _make_config(), {"source_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": {}})
        result = get_data_source(_make_auth(), _make_config(), {"source_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_name_not_found(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = get_data_source(_make_auth(), _make_config(), {"source_id": "Nonexistent Source"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_request_exception(self, mock_req):
        def side_effect(*args, **kwargs):
            if args[0] == "GET" and "/sys_data_source/" in args[1]:
                raise req.exceptions.ConnectionError("err")
            return _mock_resp(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        mock_req.side_effect = side_effect
        result = get_data_source(_make_auth(), _make_config(), {"source_id": "User CSV Import"})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# create_data_source
# ---------------------------------------------------------------------------
class TestCreateDataSource(unittest.TestCase):
    def test_missing_required(self):
        result = create_data_source(_make_auth(), _make_config(), {"name": "Test"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_success_minimal(self, mock_req):
        mock_req.return_value = _mock_resp(201, {"result": FAKE_SOURCE})
        result = create_data_source(
            _make_auth(),
            _make_config(),
            {"name": "User CSV Import", "import_set_table_name": "u_import_users"},
        )
        self.assertTrue(result["success"])
        self.assertIn("created", result["message"])
        self.assertEqual(result["data_source"]["name"], "User CSV Import")

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_success_all_fields(self, mock_req):
        mock_req.return_value = _mock_resp(201, {"result": FAKE_SOURCE})
        result = create_data_source(
            _make_auth(),
            _make_config(),
            {
                "name": "User CSV Import",
                "import_set_table_name": "u_import_users",
                "format": "csv",
                "file_retrieval_method": "http",
                "source": "https://example.com/users.csv",
                "header_row": True,
                "comma_separated": True,
                "csv_separator": ",",
                "active": True,
            },
        )
        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["format"], "csv")
        self.assertEqual(body["file_retrieval_method"], "http")
        self.assertEqual(body["source"], "https://example.com/users.csv")
        self.assertEqual(body["header_row"], "true")
        self.assertEqual(body["comma_separated"], "true")
        self.assertEqual(body["csv_separator"], ",")
        self.assertEqual(body["active"], "true")

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_inactive_data_source(self, mock_req):
        mock_req.return_value = _mock_resp(201, {"result": FAKE_SOURCE})
        result = create_data_source(
            _make_auth(),
            _make_config(),
            {"name": "Test DS", "import_set_table_name": "u_import_test", "active": False},
        )
        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["active"], "false")

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_http_error(self, mock_req):
        mock_req.return_value = _mock_resp(400)
        result = create_data_source(
            _make_auth(),
            _make_config(),
            {"name": "Test DS", "import_set_table_name": "u_import_test"},
        )
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# update_data_source
# ---------------------------------------------------------------------------
class TestUpdateDataSource(unittest.TestCase):
    def test_missing_source_id(self):
        result = update_data_source(_make_auth(), _make_config(), {"name": "New Name"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_empty_body(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        result = update_data_source(_make_auth(), _make_config(), {"source_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("No fields", result["message"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_success(self, mock_req):
        updated = dict(FAKE_SOURCE, name="Updated DS")
        mock_req.return_value = _mock_resp(200, {"result": updated})
        result = update_data_source(
            _make_auth(),
            _make_config(),
            {"source_id": FAKE_SYS_ID, "name": "Updated DS"},
        )
        self.assertTrue(result["success"])
        self.assertIn("updated", result["message"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_404(self, mock_req):
        # FAKE_SYS_ID is 32-char hex so resolver returns it directly;
        # the PATCH itself returns 404.
        mock_req.return_value = _mock_resp(404)
        result = update_data_source(
            _make_auth(),
            _make_config(),
            {"source_id": FAKE_SYS_ID, "name": "New Name"},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_not_found_resolver(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = update_data_source(
            _make_auth(),
            _make_config(),
            {"source_id": "Nonexistent", "active": True},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_all_optional_fields(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": FAKE_SOURCE})
        result = update_data_source(
            _make_auth(),
            _make_config(),
            {
                "source_id": FAKE_SYS_ID,
                "name": "New Name",
                "import_set_table_name": "u_new_table",
                "format": "xml",
                "file_retrieval_method": "ftp",
                "source": "ftp://example.com/data.xml",
                "header_row": False,
                "comma_separated": False,
                "csv_separator": ";",
                "active": False,
            },
        )
        self.assertTrue(result["success"])
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["format"], "xml")
        self.assertEqual(body["header_row"], "false")
        self.assertEqual(body["comma_separated"], "false")
        self.assertEqual(body["csv_separator"], ";")
        self.assertEqual(body["active"], "false")


# ---------------------------------------------------------------------------
# delete_data_source
# ---------------------------------------------------------------------------
class TestDeleteDataSource(unittest.TestCase):
    def test_missing_source_id(self):
        result = delete_data_source(_make_auth(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_success_204(self, mock_req):
        mock_req.return_value = _mock_resp(204)
        result = delete_data_source(_make_auth(), _make_config(), {"source_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertIn("deleted", result["message"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_success_200(self, mock_req):
        mock_req.return_value = _mock_resp(200)
        result = delete_data_source(_make_auth(), _make_config(), {"source_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_404(self, mock_req):
        mock_req.return_value = _mock_resp(404)
        result = delete_data_source(_make_auth(), _make_config(), {"source_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_not_found_resolver(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = delete_data_source(_make_auth(), _make_config(), {"source_id": "Nonexistent"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_request_exception(self, mock_req):
        def side_effect(*args, **kwargs):
            if args[0] == "DELETE":
                raise req.exceptions.ConnectionError("err")
            return _mock_resp(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        mock_req.side_effect = side_effect
        result = delete_data_source(_make_auth(), _make_config(), {"source_id": "User CSV Import"})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# load_data_source
# ---------------------------------------------------------------------------
class TestLoadDataSource(unittest.TestCase):
    def test_missing_source_id(self):
        result = load_data_source(_make_auth(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_not_found(self, mock_req):
        mock_req.return_value = _mock_resp(200, {"result": []})
        result = load_data_source(_make_auth(), _make_config(), {"source_id": "Nonexistent"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_success(self, mock_req):
        run_record = {
            "sys_id": "c" * 32,
            "import_set": "ISET0010001",
            "state": "complete",
            "data_source": FAKE_SYS_ID,
        }
        resolve_resp = _mock_resp(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        load_resp = _mock_resp(201, {"result": run_record})
        mock_req.side_effect = [resolve_resp, load_resp]
        result = load_data_source(_make_auth(), _make_config(), {"source_id": "User CSV Import"})
        self.assertTrue(result["success"])
        self.assertIn("triggered", result["message"])
        self.assertEqual(result["import_set"]["state"], "complete")

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_success_sys_id_direct(self, mock_req):
        run_record = {
            "sys_id": "c" * 32,
            "import_set": {"display_value": "ISET0010001", "value": "abc123"},
            "state": "loading",
            "data_source": FAKE_SYS_ID,
        }
        mock_req.return_value = _mock_resp(201, {"result": run_record})
        result = load_data_source(_make_auth(), _make_config(), {"source_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["import_set"]["import_set"], "ISET0010001")

    @patch("servicenow_mcp.tools.data_source_tools._make_request")
    def test_http_error(self, mock_req):
        def side_effect(*args, **kwargs):
            if args[0] == "POST":
                return _mock_resp(500)
            return _mock_resp(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        mock_req.side_effect = side_effect
        result = load_data_source(_make_auth(), _make_config(), {"source_id": "User CSV Import"})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        am = MagicMock(spec=AuthManager)
        am.instance_url = None
        am.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        cfg = MagicMock()
        cfg.instance_url = None
        result = load_data_source(am, cfg, {"source_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
