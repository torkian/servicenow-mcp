"""Tests for bulk_upload_attachments in attachment_tools.py."""

import base64
import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.attachment_tools import bulk_upload_attachments
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_ATTACHMENT = {
    "sys_id": "att001",
    "file_name": "report.pdf",
    "content_type": "application/pdf",
    "size_bytes": "1024",
    "size_compressed": "512",
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


_VALID_BASE64 = base64.b64encode(b"fake file content").decode()


class TestBulkUploadAttachments(unittest.TestCase):
    def setUp(self):
        self.auth_manager = _make_auth_manager()
        self.server_config = _make_config()

    def _call(self, params):
        return bulk_upload_attachments(self.auth_manager, self.server_config, params)

    def test_missing_attachments_field(self):
        result = self._call({})
        self.assertFalse(result["success"])

    def test_empty_attachments_list(self):
        result = self._call({"attachments": []})
        self.assertFalse(result["success"])
        self.assertIn("No attachments", result["message"])

    def test_too_many_attachments(self):
        items = [
            {
                "table_name": "incident",
                "table_sys_id": f"inc{i:03d}",
                "file_name": f"file{i}.txt",
                "file_content_base64": _VALID_BASE64,
            }
            for i in range(51)
        ]
        result = self._call({"attachments": items})
        self.assertFalse(result["success"])
        self.assertIn("50", result["message"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer X"}
        auth.instance_url = None
        # ServerConfig without an instance_url makes _get_instance_url return None
        no_url_config = MagicMock()
        no_url_config.instance_url = None
        result = bulk_upload_attachments(
            auth,
            no_url_config,
            {
                "attachments": [
                    {
                        "table_name": "incident",
                        "table_sys_id": "inc001",
                        "file_name": "f.txt",
                        "file_content_base64": _VALID_BASE64,
                    }
                ]
            },
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers(self):
        # An auth manager whose get_headers() returns None triggers the "no headers" path
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev99999.service-now.com"
        no_headers_config = MagicMock()
        no_headers_config.instance_url = "https://dev99999.service-now.com"
        no_headers_config.get_headers = None
        result = bulk_upload_attachments(
            auth,
            no_headers_config,
            {
                "attachments": [
                    {
                        "table_name": "incident",
                        "table_sys_id": "inc001",
                        "file_name": "f.txt",
                        "file_content_base64": _VALID_BASE64,
                    }
                ]
            },
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_single_upload_success(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        result = self._call(
            {
                "attachments": [
                    {
                        "table_name": "incident",
                        "table_sys_id": "inc001",
                        "file_name": "report.pdf",
                        "file_content_base64": _VALID_BASE64,
                        "content_type": "application/pdf",
                    }
                ]
            }
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["uploaded"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(len(result["results"]), 1)
        self.assertTrue(result["results"][0]["success"])
        self.assertEqual(result["results"][0]["attachment"]["sys_id"], "att001")

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_multiple_uploads_all_success(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        items = [
            {
                "table_name": "incident",
                "table_sys_id": f"inc00{i}",
                "file_name": f"file{i}.pdf",
                "file_content_base64": _VALID_BASE64,
            }
            for i in range(3)
        ]
        result = self._call({"attachments": items})
        self.assertTrue(result["success"])
        self.assertEqual(result["uploaded"], 3)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(mock_req.call_count, 3)

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_partial_failure(self, mock_req):
        success_resp = _make_response(201, {"result": FAKE_ATTACHMENT})
        error_resp = MagicMock(spec=requests.Response)
        error_resp.status_code = 500
        error_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_req.side_effect = [success_resp, error_resp]

        result = self._call(
            {
                "attachments": [
                    {
                        "table_name": "incident",
                        "table_sys_id": "inc001",
                        "file_name": "ok.pdf",
                        "file_content_base64": _VALID_BASE64,
                    },
                    {
                        "table_name": "incident",
                        "table_sys_id": "inc002",
                        "file_name": "fail.pdf",
                        "file_content_base64": _VALID_BASE64,
                    },
                ]
            }
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["uploaded"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertTrue(result["results"][0]["success"])
        self.assertFalse(result["results"][1]["success"])
        self.assertIn("Upload failed", result["results"][1]["message"])

    def test_invalid_base64_per_item(self):
        result = self._call(
            {
                "attachments": [
                    {
                        "table_name": "incident",
                        "table_sys_id": "inc001",
                        "file_name": "bad.pdf",
                        "file_content_base64": "!!!not-valid-base64!!!",
                    }
                ]
            }
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["failed"], 1)
        self.assertIn("Invalid base64", result["results"][0]["message"])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_request_exception_per_item(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("Connection refused")
        result = self._call(
            {
                "attachments": [
                    {
                        "table_name": "incident",
                        "table_sys_id": "inc001",
                        "file_name": "f.pdf",
                        "file_content_base64": _VALID_BASE64,
                    }
                ]
            }
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["failed"], 1)
        self.assertIn("Upload failed", result["results"][0]["message"])

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_encryption_context_passed(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        self._call(
            {
                "attachments": [
                    {
                        "table_name": "incident",
                        "table_sys_id": "inc001",
                        "file_name": "secure.pdf",
                        "file_content_base64": _VALID_BASE64,
                        "encryption_context": "enc_ctx_001",
                    }
                ]
            }
        )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["params"]["encryption_context"], "enc_ctx_001")

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_default_content_type(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        self._call(
            {
                "attachments": [
                    {
                        "table_name": "incident",
                        "table_sys_id": "inc001",
                        "file_name": "blob.bin",
                        "file_content_base64": _VALID_BASE64,
                    }
                ]
            }
        )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/octet-stream")

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_result_includes_table_metadata(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        result = self._call(
            {
                "attachments": [
                    {
                        "table_name": "change_request",
                        "table_sys_id": "chg001",
                        "file_name": "notes.txt",
                        "file_content_base64": _VALID_BASE64,
                    }
                ]
            }
        )
        r = result["results"][0]
        self.assertEqual(r["table_name"], "change_request")
        self.assertEqual(r["table_sys_id"], "chg001")
        self.assertEqual(r["file_name"], "notes.txt")

    @patch("servicenow_mcp.tools.attachment_tools._make_request")
    def test_mixed_base64_error_and_success(self, mock_req):
        mock_req.return_value = _make_response(201, {"result": FAKE_ATTACHMENT})
        result = self._call(
            {
                "attachments": [
                    {
                        "table_name": "incident",
                        "table_sys_id": "inc001",
                        "file_name": "bad.pdf",
                        "file_content_base64": "@@BAD@@",
                    },
                    {
                        "table_name": "incident",
                        "table_sys_id": "inc002",
                        "file_name": "good.pdf",
                        "file_content_base64": _VALID_BASE64,
                    },
                ]
            }
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["uploaded"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertFalse(result["results"][0]["success"])
        self.assertTrue(result["results"][1]["success"])
        self.assertEqual(mock_req.call_count, 1)
