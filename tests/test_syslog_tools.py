"""Tests for syslog_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.syslog_tools import (
    GetSyslogEntryParams,
    ListSyslogEntriesParams,
    _format_syslog_entry,
    get_syslog_entry,
    list_syslog_entries,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig
from servicenow_mcp.auth.auth_manager import AuthManager


FAKE_ENTRY = {
    "sys_id": "abc123",
    "level": "error",
    "message": "Script execution failed",
    "source": "Scripting",
    "type": "Error",
    "sys_created_on": "2026-04-08 10:00:00",
    "sys_created_by": "system",
    "sequence": "42",
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


class TestFormatSyslogEntry(unittest.TestCase):
    def test_all_fields_present(self):
        result = _format_syslog_entry(FAKE_ENTRY)
        self.assertEqual(result["sys_id"], "abc123")
        self.assertEqual(result["level"], "error")
        self.assertEqual(result["message"], "Script execution failed")
        self.assertEqual(result["source"], "Scripting")
        self.assertEqual(result["type"], "Error")
        self.assertEqual(result["created_on"], "2026-04-08 10:00:00")
        self.assertEqual(result["created_by"], "system")
        self.assertEqual(result["sequence"], "42")

    def test_missing_fields_return_none(self):
        result = _format_syslog_entry({})
        for key in ("sys_id", "level", "message", "source", "type", "created_on", "created_by", "sequence"):
            self.assertIsNone(result[key])


class TestListSyslogEntries(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("requests.get")
    def test_list_returns_entries(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_ENTRY]}
        mock_get.return_value = mock_response

        result = list_syslog_entries(
            self.auth_manager,
            self.config,
            {"limit": 10, "offset": 0},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["entries"][0]["sys_id"], "abc123")

    @patch("requests.get")
    def test_list_empty_result(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = list_syslog_entries(self.auth_manager, self.config, {})
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["entries"], [])

    @patch("requests.get")
    def test_list_with_level_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [FAKE_ENTRY]}
        mock_get.return_value = mock_response

        result = list_syslog_entries(
            self.auth_manager,
            self.config,
            {"level": "error"},
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("level=error", query)

    @patch("requests.get")
    def test_list_with_source_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = list_syslog_entries(
            self.auth_manager,
            self.config,
            {"source": "Scripting"},
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("sourceLIKEScripting", query)

    @patch("requests.get")
    def test_list_with_message_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = list_syslog_entries(
            self.auth_manager,
            self.config,
            {"message_contains": "failed"},
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("messageLIKEfailed", query)

    @patch("requests.get")
    def test_list_with_date_range(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_get.return_value = mock_response

        result = list_syslog_entries(
            self.auth_manager,
            self.config,
            {"created_after": "2026-04-01", "created_before": "2026-04-08"},
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_get.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("sys_created_on>=2026-04-01", query)
        self.assertIn("sys_created_on<=2026-04-08", query)

    @patch("requests.get")
    def test_list_request_exception(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("timeout")

        result = list_syslog_entries(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing syslog entries", result["message"])

    def test_list_missing_instance_url(self):
        auth_manager = MagicMock()
        del auth_manager.instance_url
        server_config = MagicMock()
        del server_config.instance_url

        result = list_syslog_entries(auth_manager, server_config, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_list_missing_headers(self):
        auth_manager = MagicMock()
        auth_manager.instance_url = "https://dev99999.service-now.com"
        del auth_manager.get_headers
        server_config = MagicMock()
        del server_config.instance_url
        del server_config.get_headers

        result = list_syslog_entries(auth_manager, server_config, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


class TestGetSyslogEntry(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth_manager = _make_auth_manager()

    @patch("requests.get")
    def test_get_entry_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": FAKE_ENTRY}
        mock_get.return_value = mock_response

        result = get_syslog_entry(
            self.auth_manager,
            self.config,
            {"sys_id": "abc123"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["entry"]["sys_id"], "abc123")
        self.assertEqual(result["entry"]["level"], "error")

    @patch("requests.get")
    def test_get_entry_not_found_404(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = get_syslog_entry(
            self.auth_manager,
            self.config,
            {"sys_id": "nonexistent"},
        )

        self.assertFalse(result["success"])
        self.assertIn("nonexistent", result["message"])

    @patch("requests.get")
    def test_get_entry_empty_result(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {}}
        mock_get.return_value = mock_response

        result = get_syslog_entry(
            self.auth_manager,
            self.config,
            {"sys_id": "xyz"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("requests.get")
    def test_get_entry_request_exception(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("timeout")

        result = get_syslog_entry(
            self.auth_manager,
            self.config,
            {"sys_id": "abc123"},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error retrieving syslog entry", result["message"])

    def test_get_entry_missing_sys_id(self):
        result = get_syslog_entry(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])

    def test_get_entry_missing_instance_url(self):
        auth_manager = MagicMock()
        del auth_manager.instance_url
        server_config = MagicMock()
        del server_config.instance_url

        result = get_syslog_entry(auth_manager, server_config, {"sys_id": "abc"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])


class TestSyslogParams(unittest.TestCase):
    def test_list_params_defaults(self):
        p = ListSyslogEntriesParams()
        self.assertEqual(p.limit, 20)
        self.assertEqual(p.offset, 0)
        self.assertIsNone(p.level)
        self.assertIsNone(p.source)
        self.assertIsNone(p.message_contains)
        self.assertIsNone(p.created_after)
        self.assertIsNone(p.created_before)

    def test_get_params_requires_sys_id(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            GetSyslogEntryParams()

    def test_get_params_valid(self):
        p = GetSyslogEntryParams(sys_id="abc123")
        self.assertEqual(p.sys_id, "abc123")


if __name__ == "__main__":
    unittest.main()
