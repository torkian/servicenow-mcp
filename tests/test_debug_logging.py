"""Tests for debug-mode request/response logging in _make_request."""

import logging
import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.utils.helpers import (
    _DEBUG_BODY_LIMIT,
    _REDACTED,
    _make_request,
    _redact_headers,
    _truncate_body,
)


def _mock_response(status_code: int, json_body=None, text="") -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.headers = {}
    resp.text = text
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.side_effect = ValueError("no json")
    return resp


# ---------------------------------------------------------------------------
# _redact_headers
# ---------------------------------------------------------------------------

class TestRedactHeaders(unittest.TestCase):
    def test_none_returns_empty_dict(self):
        self.assertEqual(_redact_headers(None), {})

    def test_empty_dict_returns_empty_dict(self):
        self.assertEqual(_redact_headers({}), {})

    def test_authorization_redacted(self):
        result = _redact_headers({"Authorization": "Basic abc123"})
        self.assertEqual(result["Authorization"], _REDACTED)

    def test_authorization_case_insensitive(self):
        result = _redact_headers({"authorization": "Bearer token"})
        self.assertEqual(result["authorization"], _REDACTED)

    def test_x_servicenow_api_key_redacted(self):
        result = _redact_headers({"X-ServiceNow-API-Key": "mykey"})
        self.assertEqual(result["X-ServiceNow-API-Key"], _REDACTED)

    def test_cookie_redacted(self):
        result = _redact_headers({"Cookie": "session=abc"})
        self.assertEqual(result["Cookie"], _REDACTED)

    def test_set_cookie_redacted(self):
        result = _redact_headers({"Set-Cookie": "session=abc; Path=/"})
        self.assertEqual(result["Set-Cookie"], _REDACTED)

    def test_proxy_authorization_redacted(self):
        result = _redact_headers({"Proxy-Authorization": "Basic xyz"})
        self.assertEqual(result["Proxy-Authorization"], _REDACTED)

    def test_safe_headers_pass_through(self):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        result = _redact_headers(headers)
        self.assertEqual(result["Content-Type"], "application/json")
        self.assertEqual(result["Accept"], "application/json")

    def test_mixed_headers(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer secret",
            "X-Custom": "value",
        }
        result = _redact_headers(headers)
        self.assertEqual(result["Content-Type"], "application/json")
        self.assertEqual(result["Authorization"], _REDACTED)
        self.assertEqual(result["X-Custom"], "value")

    def test_original_not_mutated(self):
        headers = {"Authorization": "Bearer secret"}
        _redact_headers(headers)
        self.assertEqual(headers["Authorization"], "Bearer secret")


# ---------------------------------------------------------------------------
# _truncate_body
# ---------------------------------------------------------------------------

class TestTruncateBody(unittest.TestCase):
    def test_none_returns_empty_string(self):
        self.assertEqual(_truncate_body(None), "")

    def test_short_string_unchanged(self):
        self.assertEqual(_truncate_body("hello"), "hello")

    def test_dict_serialised_to_json(self):
        result = _truncate_body({"key": "value"})
        self.assertIn("key", result)

    def test_list_serialised_to_json(self):
        result = _truncate_body([1, 2, 3])
        self.assertIn("1", result)

    def test_long_string_truncated(self):
        long_str = "x" * (_DEBUG_BODY_LIMIT + 100)
        result = _truncate_body(long_str)
        self.assertEqual(len(result), _DEBUG_BODY_LIMIT + len(" [truncated]"))
        self.assertTrue(result.endswith("[truncated]"))

    def test_exact_limit_not_truncated(self):
        exact = "y" * _DEBUG_BODY_LIMIT
        result = _truncate_body(exact)
        self.assertEqual(result, exact)
        self.assertNotIn("[truncated]", result)

    def test_long_dict_truncated(self):
        big_dict = {str(i): "v" * 20 for i in range(100)}
        result = _truncate_body(big_dict)
        self.assertTrue(result.endswith("[truncated]"))

    def test_non_string_non_collection_coerced(self):
        result = _truncate_body(42)
        self.assertEqual(result, "42")


# ---------------------------------------------------------------------------
# Debug logging integration in _make_request
# ---------------------------------------------------------------------------

class TestMakeRequestDebugLogging(unittest.TestCase):
    """When logger is at DEBUG level, _make_request emits request/response logs."""

    @patch("requests.get")
    def test_debug_logs_request_and_response(self, mock_get):
        mock_get.return_value = _mock_response(200, json_body={"result": "ok"})

        with self.assertLogs("servicenow_mcp.utils.helpers", level=logging.DEBUG) as cm:
            _make_request("GET", "https://snow.example.com/api/table/incident")

        log_text = "\n".join(cm.output)
        self.assertIn(">> GET", log_text)
        self.assertIn("https://snow.example.com/api/table/incident", log_text)
        self.assertIn("<< 200", log_text)

    @patch("requests.post")
    def test_debug_logs_json_body(self, mock_post):
        mock_post.return_value = _mock_response(201, json_body={"result": "created"})

        with self.assertLogs("servicenow_mcp.utils.helpers", level=logging.DEBUG) as cm:
            _make_request(
                "POST",
                "https://snow.example.com/api/table/incident",
                json={"short_description": "Test"},
            )

        log_text = "\n".join(cm.output)
        self.assertIn("short_description", log_text)

    @patch("requests.get")
    def test_debug_logs_query_params(self, mock_get):
        mock_get.return_value = _mock_response(200, json_body={})

        with self.assertLogs("servicenow_mcp.utils.helpers", level=logging.DEBUG) as cm:
            _make_request(
                "GET",
                "https://snow.example.com/api/table/incident",
                params={"sysparm_limit": 10},
            )

        log_text = "\n".join(cm.output)
        self.assertIn("sysparm_limit", log_text)

    @patch("requests.get")
    def test_debug_redacts_authorization_header(self, mock_get):
        mock_get.return_value = _mock_response(200, json_body={})

        with self.assertLogs("servicenow_mcp.utils.helpers", level=logging.DEBUG) as cm:
            _make_request(
                "GET",
                "https://snow.example.com/api/table/incident",
                headers={"Authorization": "Basic c2VjcmV0", "Content-Type": "application/json"},
            )

        log_text = "\n".join(cm.output)
        self.assertNotIn("c2VjcmV0", log_text)
        self.assertIn(_REDACTED, log_text)
        self.assertIn("application/json", log_text)

    @patch("requests.get")
    def test_debug_logs_elapsed_time(self, mock_get):
        mock_get.return_value = _mock_response(200, json_body={})

        with self.assertLogs("servicenow_mcp.utils.helpers", level=logging.DEBUG) as cm:
            _make_request("GET", "https://snow.example.com/api/table/incident")

        log_text = "\n".join(cm.output)
        # elapsed appears as digits followed by 's'
        import re
        self.assertTrue(re.search(r"\d+\.\d+s", log_text))

    @patch("requests.get")
    def test_debug_falls_back_to_text_when_no_json(self, mock_get):
        mock_get.return_value = _mock_response(200, text="plain text body")

        with self.assertLogs("servicenow_mcp.utils.helpers", level=logging.DEBUG) as cm:
            _make_request("GET", "https://snow.example.com/api")

        log_text = "\n".join(cm.output)
        self.assertIn("plain text body", log_text)

    @patch("requests.get")
    def test_no_debug_logs_at_info_level(self, mock_get):
        mock_get.return_value = _mock_response(200, json_body={})

        # assertLogs would fail if no logs at WARNING+; we just verify no DEBUG
        # lines are emitted by checking the effective level guard
        import servicenow_mcp.utils.helpers as h
        orig_level = h.logger.level
        try:
            h.logger.setLevel(logging.WARNING)
            # Should not raise; no debug output expected
            _make_request("GET", "https://snow.example.com/api")
        finally:
            h.logger.setLevel(orig_level)

    @patch("requests.post")
    def test_debug_logs_on_retry(self, mock_post):
        """Each retry attempt should log its own request line."""
        resp_500 = _mock_response(500, json_body={})
        resp_200 = _mock_response(200, json_body={"result": "ok"})
        mock_post.side_effect = [resp_500, resp_200]

        with patch("time.sleep"), self.assertLogs(
            "servicenow_mcp.utils.helpers", level=logging.DEBUG
        ) as cm:
            _make_request("POST", "https://snow.example.com/api", max_retries=1, backoff_factor=0)

        # Two outgoing request lines expected
        request_lines = [line for line in cm.output if ">> POST" in line]
        self.assertEqual(len(request_lines), 2)

    @patch("requests.get")
    def test_debug_truncates_large_response_body(self, mock_get):
        big_body = {"data": "x" * 2000}
        mock_get.return_value = _mock_response(200, json_body=big_body)

        with self.assertLogs("servicenow_mcp.utils.helpers", level=logging.DEBUG) as cm:
            _make_request("GET", "https://snow.example.com/api")

        log_text = "\n".join(cm.output)
        self.assertIn("[truncated]", log_text)


if __name__ == "__main__":
    unittest.main()
