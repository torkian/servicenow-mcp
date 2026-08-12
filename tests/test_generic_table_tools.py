"""Tests for generic_table_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests as req

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.generic_table_tools import (
    CreateRecordParams,
    DeleteRecordParams,
    GetRecordParams,
    ListRecordsParams,
    UpdateRecordParams,
    create_record,
    delete_record,
    get_record,
    list_records,
    update_record,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_RECORD = {
    "sys_id": "abc123",
    "short_description": "Test ticket",
    "state": "1",
    "priority": "2",
    "sys_created_on": "2026-08-12 10:00:00",
}

CUSTOM_RECORD = {
    "sys_id": "custom001",
    "u_field_one": "value one",
    "u_field_two": "42",
}


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev99999.service-now.com", auth=auth_config)


def _make_auth_manager():
    am = MagicMock(spec=AuthManager)
    am.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    am.instance_url = "https://dev99999.service-now.com"
    return am


def _make_mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Parameter model tests
# ---------------------------------------------------------------------------


class TestListRecordsParams(unittest.TestCase):
    def test_defaults(self):
        p = ListRecordsParams(table="incident")
        self.assertEqual(p.table, "incident")
        self.assertEqual(p.limit, 20)
        self.assertEqual(p.offset, 0)
        self.assertIsNone(p.query)
        self.assertIsNone(p.fields)
        self.assertIsNone(p.order_by)
        self.assertTrue(p.display_value)

    def test_custom_values(self):
        p = ListRecordsParams(
            table="u_custom",
            query="active=true^priority=1",
            fields="sys_id,short_description",
            limit=50,
            offset=10,
            order_by="DESCsys_created_on",
            display_value=False,
        )
        self.assertEqual(p.table, "u_custom")
        self.assertEqual(p.query, "active=true^priority=1")
        self.assertEqual(p.fields, "sys_id,short_description")
        self.assertEqual(p.limit, 50)
        self.assertEqual(p.offset, 10)
        self.assertEqual(p.order_by, "DESCsys_created_on")
        self.assertFalse(p.display_value)


class TestGetRecordParams(unittest.TestCase):
    def test_required_fields(self):
        p = GetRecordParams(table="incident", sys_id="abc123")
        self.assertEqual(p.table, "incident")
        self.assertEqual(p.sys_id, "abc123")

    def test_optional_fields(self):
        p = GetRecordParams(table="u_table", sys_id="xyz", fields="sys_id,u_field", display_value=False)
        self.assertEqual(p.fields, "sys_id,u_field")
        self.assertFalse(p.display_value)


class TestCreateRecordParams(unittest.TestCase):
    def test_required_fields(self):
        p = CreateRecordParams(table="incident", fields={"short_description": "Test"})
        self.assertEqual(p.table, "incident")
        self.assertEqual(p.fields["short_description"], "Test")

    def test_optional_return_fields(self):
        p = CreateRecordParams(table="u_table", fields={"u_key": "v"}, return_fields="sys_id,u_key")
        self.assertEqual(p.return_fields, "sys_id,u_key")


class TestUpdateRecordParams(unittest.TestCase):
    def test_required_fields(self):
        p = UpdateRecordParams(table="incident", sys_id="abc", fields={"state": "2"})
        self.assertEqual(p.table, "incident")
        self.assertEqual(p.sys_id, "abc")
        self.assertEqual(p.fields["state"], "2")


class TestDeleteRecordParams(unittest.TestCase):
    def test_required_fields(self):
        p = DeleteRecordParams(table="incident", sys_id="abc")
        self.assertEqual(p.table, "incident")
        self.assertEqual(p.sys_id, "abc")


# ---------------------------------------------------------------------------
# list_records tests
# ---------------------------------------------------------------------------


class TestListRecords(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_success_returns_records(self, mock_req):
        mock_req.return_value = _make_mock_response(
            200, {"result": [FAKE_RECORD, CUSTOM_RECORD]}
        )
        result = list_records(
            self.auth,
            self.config,
            {"table": "incident", "limit": 20, "offset": 0},
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(result["count"], 2)

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": []})
        result = list_records(self.auth, self.config, {"table": "u_custom"})
        self.assertTrue(result["success"])
        self.assertEqual(result["records"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_with_query_and_fields(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": [FAKE_RECORD]})
        result = list_records(
            self.auth,
            self.config,
            {
                "table": "incident",
                "query": "active=true^priority=1",
                "fields": "sys_id,short_description",
                "limit": 5,
                "offset": 0,
            },
        )
        self.assertTrue(result["success"])
        # Verify request was made with correct URL
        call_args = mock_req.call_args
        self.assertIn("incident", call_args[0][1])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_with_order_by(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": [FAKE_RECORD]})
        result = list_records(
            self.auth,
            self.config,
            {"table": "incident", "order_by": "DESCsys_created_on"},
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_display_value_false(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": [FAKE_RECORD]})
        result = list_records(
            self.auth,
            self.config,
            {"table": "incident", "display_value": False},
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args[1]
        self.assertEqual(call_kwargs["params"]["sysparm_display_value"], "false")

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_display_value_true(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": [FAKE_RECORD]})
        result = list_records(self.auth, self.config, {"table": "incident", "display_value": True})
        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args[1]
        self.assertEqual(call_kwargs["params"]["sysparm_display_value"], "true")

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_has_more_pagination(self, mock_req):
        records = [FAKE_RECORD] * 20
        mock_req.return_value = _make_mock_response(200, {"result": records})
        result = list_records(
            self.auth, self.config, {"table": "incident", "limit": 20, "offset": 0}
        )
        self.assertTrue(result["success"])
        self.assertTrue(result.get("has_more", False))
        self.assertEqual(result["next_offset"], 20)

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_custom_table(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": [CUSTOM_RECORD]})
        result = list_records(self.auth, self.config, {"table": "u_my_custom_table"})
        self.assertTrue(result["success"])
        call_args = mock_req.call_args
        self.assertIn("u_my_custom_table", call_args[0][1])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.ConnectionError("connection refused")
        result = list_records(self.auth, self.config, {"table": "incident"})
        self.assertFalse(result["success"])
        self.assertIn("incident", result["message"])

    def test_missing_table(self):
        result = list_records(self.auth, self.config, {})
        self.assertFalse(result["success"])

    def test_invalid_config_no_instance_url(self):
        am = MagicMock(spec=AuthManager)
        am.get_headers.return_value = {"Authorization": "Bearer X"}
        am.instance_url = None
        result = list_records(am, self.config, {"table": "incident"})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# get_record tests
# ---------------------------------------------------------------------------


class TestGetRecord(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_success(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": FAKE_RECORD})
        result = get_record(self.auth, self.config, {"table": "incident", "sys_id": "abc123"})
        self.assertTrue(result["success"])
        self.assertEqual(result["record"]["sys_id"], "abc123")

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_404_returns_error(self, mock_req):
        r = _make_mock_response(404, {})
        mock_req.return_value = r
        result = get_record(self.auth, self.config, {"table": "incident", "sys_id": "missing"})
        self.assertFalse(result["success"])
        self.assertIn("missing", result["message"])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_empty_result_returns_error(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": {}})
        result = get_record(self.auth, self.config, {"table": "incident", "sys_id": "abc"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_with_fields_param(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": FAKE_RECORD})
        result = get_record(
            self.auth,
            self.config,
            {"table": "incident", "sys_id": "abc123", "fields": "sys_id,short_description"},
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args[1]
        self.assertEqual(call_kwargs["params"]["sysparm_fields"], "sys_id,short_description")

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_display_value_false(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": FAKE_RECORD})
        result = get_record(
            self.auth, self.config, {"table": "incident", "sys_id": "abc", "display_value": False}
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args[1]
        self.assertEqual(call_kwargs["params"]["sysparm_display_value"], "false")

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.Timeout("timed out")
        result = get_record(self.auth, self.config, {"table": "incident", "sys_id": "abc"})
        self.assertFalse(result["success"])

    def test_missing_table(self):
        result = get_record(self.auth, self.config, {"sys_id": "abc"})
        self.assertFalse(result["success"])

    def test_missing_sys_id(self):
        result = get_record(self.auth, self.config, {"table": "incident"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_custom_table(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": CUSTOM_RECORD})
        result = get_record(self.auth, self.config, {"table": "u_my_table", "sys_id": "custom001"})
        self.assertTrue(result["success"])
        self.assertEqual(result["record"]["sys_id"], "custom001")


# ---------------------------------------------------------------------------
# create_record tests
# ---------------------------------------------------------------------------


class TestCreateRecord(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_success(self, mock_req):
        created = dict(FAKE_RECORD, sys_id="new001")
        mock_req.return_value = _make_mock_response(201, {"result": created})
        result = create_record(
            self.auth,
            self.config,
            {"table": "incident", "fields": {"short_description": "Test", "priority": "2"}},
        )
        self.assertTrue(result["success"])
        self.assertIn("new001", result["message"])
        self.assertEqual(result["record"]["sys_id"], "new001")

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_custom_table(self, mock_req):
        mock_req.return_value = _make_mock_response(201, {"result": CUSTOM_RECORD})
        result = create_record(
            self.auth,
            self.config,
            {"table": "u_custom_table", "fields": {"u_field_one": "hello", "u_field_two": "99"}},
        )
        self.assertTrue(result["success"])
        call_args = mock_req.call_args
        self.assertIn("u_custom_table", call_args[0][1])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_with_return_fields(self, mock_req):
        mock_req.return_value = _make_mock_response(201, {"result": FAKE_RECORD})
        result = create_record(
            self.auth,
            self.config,
            {
                "table": "incident",
                "fields": {"short_description": "Test"},
                "return_fields": "sys_id,short_description",
            },
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args[1]
        self.assertEqual(call_kwargs["params"]["sysparm_fields"], "sys_id,short_description")

    def test_empty_fields_rejected(self):
        result = create_record(self.auth, self.config, {"table": "incident", "fields": {}})
        self.assertFalse(result["success"])
        self.assertIn("No fields", result["message"])

    def test_missing_table(self):
        result = create_record(self.auth, self.config, {"fields": {"short_description": "x"}})
        self.assertFalse(result["success"])

    def test_missing_fields(self):
        result = create_record(self.auth, self.config, {"table": "incident"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.ConnectionError("refused")
        result = create_record(
            self.auth, self.config, {"table": "incident", "fields": {"short_description": "fail"}}
        )
        self.assertFalse(result["success"])
        self.assertIn("incident", result["message"])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_body_sent_correctly(self, mock_req):
        mock_req.return_value = _make_mock_response(201, {"result": FAKE_RECORD})
        fields = {"short_description": "Body test", "priority": "1"}
        create_record(self.auth, self.config, {"table": "incident", "fields": fields})
        call_kwargs = mock_req.call_args[1]
        self.assertEqual(call_kwargs["json"]["short_description"], "Body test")
        self.assertEqual(call_kwargs["json"]["priority"], "1")


# ---------------------------------------------------------------------------
# update_record tests
# ---------------------------------------------------------------------------


class TestUpdateRecord(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_success(self, mock_req):
        updated = dict(FAKE_RECORD, state="2")
        mock_req.return_value = _make_mock_response(200, {"result": updated})
        result = update_record(
            self.auth,
            self.config,
            {"table": "incident", "sys_id": "abc123", "fields": {"state": "2"}},
        )
        self.assertTrue(result["success"])
        self.assertIn("abc123", result["message"])
        self.assertEqual(result["record"]["state"], "2")

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_404_returns_error(self, mock_req):
        r = _make_mock_response(404, {})
        mock_req.return_value = r
        result = update_record(
            self.auth, self.config, {"table": "incident", "sys_id": "missing", "fields": {"state": "2"}}
        )
        self.assertFalse(result["success"])
        self.assertIn("missing", result["message"])

    def test_empty_fields_rejected(self):
        result = update_record(
            self.auth, self.config, {"table": "incident", "sys_id": "abc", "fields": {}}
        )
        self.assertFalse(result["success"])
        self.assertIn("No fields", result["message"])

    def test_missing_table(self):
        result = update_record(self.auth, self.config, {"sys_id": "abc", "fields": {"state": "2"}})
        self.assertFalse(result["success"])

    def test_missing_sys_id(self):
        result = update_record(self.auth, self.config, {"table": "incident", "fields": {"state": "2"}})
        self.assertFalse(result["success"])

    def test_missing_fields_param(self):
        result = update_record(self.auth, self.config, {"table": "incident", "sys_id": "abc"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_with_return_fields(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": FAKE_RECORD})
        result = update_record(
            self.auth,
            self.config,
            {
                "table": "incident",
                "sys_id": "abc",
                "fields": {"priority": "1"},
                "return_fields": "sys_id,priority",
            },
        )
        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args[1]
        self.assertEqual(call_kwargs["params"]["sysparm_fields"], "sys_id,priority")

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_patch_method_used(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": FAKE_RECORD})
        update_record(
            self.auth, self.config, {"table": "incident", "sys_id": "abc", "fields": {"state": "3"}}
        )
        call_args = mock_req.call_args
        self.assertEqual(call_args[0][0], "PATCH")

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.Timeout("timed out")
        result = update_record(
            self.auth, self.config, {"table": "incident", "sys_id": "abc", "fields": {"state": "2"}}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_custom_table(self, mock_req):
        mock_req.return_value = _make_mock_response(200, {"result": CUSTOM_RECORD})
        result = update_record(
            self.auth,
            self.config,
            {"table": "u_custom", "sys_id": "custom001", "fields": {"u_field_one": "updated"}},
        )
        self.assertTrue(result["success"])
        call_args = mock_req.call_args
        self.assertIn("u_custom", call_args[0][1])


# ---------------------------------------------------------------------------
# delete_record tests
# ---------------------------------------------------------------------------


class TestDeleteRecord(unittest.TestCase):
    def setUp(self):
        self.auth = _make_auth_manager()
        self.config = _make_config()

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_success_204(self, mock_req):
        r = _make_mock_response(204, {})
        mock_req.return_value = r
        result = delete_record(self.auth, self.config, {"table": "incident", "sys_id": "abc123"})
        self.assertTrue(result["success"])
        self.assertIn("abc123", result["message"])
        self.assertIn("incident", result["message"])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_success_200(self, mock_req):
        r = _make_mock_response(200, {})
        mock_req.return_value = r
        result = delete_record(self.auth, self.config, {"table": "incident", "sys_id": "abc123"})
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_404_returns_error(self, mock_req):
        r = _make_mock_response(404, {})
        mock_req.return_value = r
        result = delete_record(self.auth, self.config, {"table": "incident", "sys_id": "missing"})
        self.assertFalse(result["success"])
        self.assertIn("missing", result["message"])

    def test_missing_table(self):
        result = delete_record(self.auth, self.config, {"sys_id": "abc"})
        self.assertFalse(result["success"])

    def test_missing_sys_id(self):
        result = delete_record(self.auth, self.config, {"table": "incident"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_delete_method_used(self, mock_req):
        r = _make_mock_response(204, {})
        mock_req.return_value = r
        delete_record(self.auth, self.config, {"table": "incident", "sys_id": "abc"})
        call_args = mock_req.call_args
        self.assertEqual(call_args[0][0], "DELETE")

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_request_exception(self, mock_req):
        mock_req.side_effect = req.exceptions.ConnectionError("refused")
        result = delete_record(self.auth, self.config, {"table": "incident", "sys_id": "abc"})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.generic_table_tools._make_request")
    def test_custom_table(self, mock_req):
        r = _make_mock_response(204, {})
        mock_req.return_value = r
        result = delete_record(self.auth, self.config, {"table": "u_custom", "sys_id": "xyz"})
        self.assertTrue(result["success"])
        call_args = mock_req.call_args
        self.assertIn("u_custom", call_args[0][1])
        self.assertIn("xyz", call_args[0][1])


if __name__ == "__main__":
    unittest.main()
