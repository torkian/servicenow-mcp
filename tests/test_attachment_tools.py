"""Tests for attachment_tools.py."""

import base64
import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.tools.attachment_tools import (
    _format_attachment,
    delete_attachment,
    get_attachment,
    list_attachments,
    upload_attachment,
)
from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


FAKE_ATTACHMENT = {
    "sys_id": "att001",
    "file_name": "screenshot.png",
    "content_type": "image/png",
    "size_bytes": "204800",
    "size_compressed": "102400",
    "table_name": "incident",
    "table_sys_id": "inc001",
    "sys_created_on": "2026-01-01 10:00:00",
    "sys_created_by": "admin",
    "sys_updated_on": "2026-01-01 10:00:00",
    "download_link": "https://dev99999.service-now.com/api/now/attachment/att001/file",
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


def _make_response(status_code=200, json_body=None):
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.json.return_value = json_body or {}
    response.raise_for_status = MagicMock()
    return response


class TestFormatAttachment(unittest.TestCase):
    def test_all_fields_mapped(self):
        result = _format_attachment(FAKE_ATTACHMENT)
        self.assertEqual(result["sys_id"], "att001")
        self.assertEqual(result["file_name"], "screenshot.png")
        self.assertEqual(result["content_type"], "image/png")
        self.assertEqual(result["size_bytes"], "204800")
        self.assertEqual(result["size_compressed"], "102400")
        self.assertEqual(result["table_name"], "incident")
        self.assertEqual(result["table_sys_id"], "inc001")
        self.assertEqual(result["created_on"], "2026-01-01 10:00:00")
        self.assertEqual(result["created_by"], "admin")
        self.assertEqual(result["updated_on"], "2026-01-01 10:00:00")
        self.assertIn("download_link", result)

    def test_empty_record_returns_nones(self):
        result = _format_attachment({})
        for key in (
            "sys_id",
            "file_name",
            "content_type",
            "size_bytes",
            "table_name",
            "table_sys_id",
            "created_on",
            "created_by",
            "updated_on",
            "download_link",
        ):
            self.assertIsNone(result[key], f"{key} should be None for empty record")


class TestListAttachments(unittest.TestCase):
    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_success_returns_attachments(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_ATTACHMENT]})
        result = list_attachments(
            _make_auth_manager(),
            _make_config(),
            {"table_name": "incident", "table_sys_id": "inc001"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["attachments"]), 1)
        self.assertEqual(result["attachments"][0]["sys_id"], "att001")
        self.assertIn("count", result)

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_attachments(
            _make_auth_manager(),
            _make_config(),
            {"table_name": "change_request", "table_sys_id": "chg001"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["attachments"], [])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_file_name_filter_passed_in_query(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_attachments(
            _make_auth_manager(),
            _make_config(),
            {"table_name": "incident", "table_sys_id": "inc001", "file_name": "log"},
        )
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("file_nameLIKElog", query)

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_content_type_filter_passed_in_query(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_attachments(
            _make_auth_manager(),
            _make_config(),
            {"table_name": "incident", "table_sys_id": "inc001", "content_type": "application/pdf"},
        )
        _, kwargs = mock_req.call_args
        query = kwargs.get("params", {}).get("sysparm_query", "")
        self.assertIn("content_type=application/pdf", query)

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_pagination_params_forwarded(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_attachments(
            _make_auth_manager(),
            _make_config(),
            {"table_name": "incident", "table_sys_id": "inc001", "limit": 5, "offset": 10},
        )
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        self.assertEqual(params.get("sysparm_limit"), 5)
        self.assertEqual(params.get("sysparm_offset"), 10)

    def test_missing_required_table_name(self):
        result = list_attachments(
            _make_auth_manager(),
            _make_config(),
            {"table_sys_id": "inc001"},
        )
        self.assertFalse(result["success"])

    def test_missing_required_table_sys_id(self):
        result = list_attachments(
            _make_auth_manager(),
            _make_config(),
            {"table_name": "incident"},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_request_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_attachments(
            _make_auth_manager(),
            _make_config(),
            {"table_name": "incident", "table_sys_id": "inc001"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error listing attachments", result["message"])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_has_more_flag(self, mock_req):
        records = [dict(FAKE_ATTACHMENT, sys_id=f"att{i:03d}") for i in range(5)]
        mock_req.return_value = _make_response(200, {"result": records})
        result = list_attachments(
            _make_auth_manager(),
            _make_config(),
            {"table_name": "incident", "table_sys_id": "inc001", "limit": 5, "offset": 0},
        )
        self.assertTrue(result["success"])
        self.assertIn("has_more", result)


class TestGetAttachment(unittest.TestCase):
    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_success(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_ATTACHMENT})
        result = get_attachment(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": "att001"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["attachment"]["sys_id"], "att001")
        self.assertEqual(result["attachment"]["file_name"], "screenshot.png")

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_404_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(404, {})
        result = get_attachment(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": "no_such_id"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_empty_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_attachment(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": "att001"},
        )
        self.assertFalse(result["success"])

    def test_missing_sys_id(self):
        result = get_attachment(
            _make_auth_manager(),
            _make_config(),
            {},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_request_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.Timeout("timeout")
        result = get_attachment(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": "att001"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving attachment", result["message"])


class TestDeleteAttachment(unittest.TestCase):
    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_success_204(self, mock_req):
        mock_req.return_value = _make_response(204)
        result = delete_attachment(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": "att001"},
        )
        self.assertTrue(result["success"])
        self.assertIn("deleted successfully", result["message"])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_success_200(self, mock_req):
        mock_req.return_value = _make_response(200)
        result = delete_attachment(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": "att001"},
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_404_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(404)
        result = delete_attachment(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": "no_such_id"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    def test_missing_sys_id(self):
        result = delete_attachment(
            _make_auth_manager(),
            _make_config(),
            {},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_request_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("conn refused")
        result = delete_attachment(
            _make_auth_manager(),
            _make_config(),
            {"sys_id": "att001"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error deleting attachment", result["message"])


_SAMPLE_CONTENT = b"Hello, ServiceNow!"
_SAMPLE_B64 = base64.b64encode(_SAMPLE_CONTENT).decode()


class TestUploadAttachment(unittest.TestCase):
    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_success_returns_attachment_metadata(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        result = upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_name": "screenshot.png",
                "file_content_base64": _SAMPLE_B64,
                "content_type": "image/png",
            },
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["attachment"]["sys_id"], "att001")
        self.assertEqual(result["attachment"]["file_name"], "screenshot.png")

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_correct_url_and_method(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_name": "file.txt",
                "file_content_base64": _SAMPLE_B64,
            },
        )
        args, _ = mock_req.call_args
        self.assertEqual(args[0], "POST")
        self.assertIn("/api/now/attachment/file", args[1])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_query_params_forwarded(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_name": "notes.txt",
                "file_content_base64": _SAMPLE_B64,
            },
        )
        _, kwargs = mock_req.call_args
        p = kwargs.get("params", {})
        self.assertEqual(p["table_name"], "incident")
        self.assertEqual(p["table_sys_id"], "inc001")
        self.assertEqual(p["file_name"], "notes.txt")

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_encryption_context_forwarded_when_provided(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_name": "secure.pdf",
                "file_content_base64": _SAMPLE_B64,
                "encryption_context": "enc_ctx_001",
            },
        )
        _, kwargs = mock_req.call_args
        p = kwargs.get("params", {})
        self.assertEqual(p["encryption_context"], "enc_ctx_001")

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_encryption_context_absent_when_not_provided(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_name": "plain.txt",
                "file_content_base64": _SAMPLE_B64,
            },
        )
        _, kwargs = mock_req.call_args
        p = kwargs.get("params", {})
        self.assertNotIn("encryption_context", p)

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_content_type_set_in_headers(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_name": "doc.pdf",
                "file_content_base64": _SAMPLE_B64,
                "content_type": "application/pdf",
            },
        )
        _, kwargs = mock_req.call_args
        headers = kwargs.get("headers", {})
        self.assertEqual(headers.get("Content-Type"), "application/pdf")

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_default_content_type_octet_stream(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_name": "blob.bin",
                "file_content_base64": _SAMPLE_B64,
            },
        )
        _, kwargs = mock_req.call_args
        headers = kwargs.get("headers", {})
        self.assertEqual(headers.get("Content-Type"), "application/octet-stream")

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_raw_bytes_sent_as_body(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_name": "data.bin",
                "file_content_base64": _SAMPLE_B64,
            },
        )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs.get("data"), _SAMPLE_CONTENT)

    def test_invalid_base64_returns_failure(self):
        result = upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_name": "bad.txt",
                "file_content_base64": "!!!not_valid_base64!!!",
            },
        )
        self.assertFalse(result["success"])
        self.assertIn("Invalid base64", result["message"])

    def test_missing_table_name_returns_failure(self):
        result = upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_sys_id": "inc001",
                "file_name": "x.txt",
                "file_content_base64": _SAMPLE_B64,
            },
        )
        self.assertFalse(result["success"])

    def test_missing_table_sys_id_returns_failure(self):
        result = upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "file_name": "x.txt",
                "file_content_base64": _SAMPLE_B64,
            },
        )
        self.assertFalse(result["success"])

    def test_missing_file_name_returns_failure(self):
        result = upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_content_base64": _SAMPLE_B64,
            },
        )
        self.assertFalse(result["success"])

    def test_missing_file_content_returns_failure(self):
        result = upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_name": "x.txt",
            },
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_request_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.Timeout("timeout")
        result = upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_name": "x.txt",
                "file_content_base64": _SAMPLE_B64,
            },
        )
        self.assertFalse(result["success"])
        self.assertIn("Error uploading attachment", result["message"])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        bad_response = _make_response(403, {})
        bad_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Forbidden")
        mock_req.return_value = bad_response
        result = upload_attachment(
            _make_auth_manager(),
            _make_config(),
            {
                "table_name": "incident",
                "table_sys_id": "inc001",
                "file_name": "x.txt",
                "file_content_base64": _SAMPLE_B64,
            },
        )
        self.assertFalse(result["success"])
        self.assertIn("Error uploading attachment", result["message"])


if __name__ == "__main__":
    unittest.main()
