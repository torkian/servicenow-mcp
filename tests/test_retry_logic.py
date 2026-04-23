"""Tests for _make_request exponential-backoff retry helper."""

import unittest
from unittest.mock import MagicMock, call, patch

import requests

from servicenow_mcp.utils.helpers import _make_request


def _mock_response(status_code: int, json_body=None) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.headers = {}
    resp.json.return_value = json_body or {}
    return resp


class TestMakeRequestSuccess(unittest.TestCase):
    """_make_request returns response immediately on 2xx / non-retryable codes."""

    @patch("requests.get")
    def test_get_200_no_retry(self, mock_get):
        mock_get.return_value = _mock_response(200)
        result = _make_request("GET", "https://example.com/api", max_retries=3)
        self.assertEqual(result.status_code, 200)
        mock_get.assert_called_once_with("https://example.com/api")

    @patch("requests.post")
    def test_post_201_no_retry(self, mock_post):
        mock_post.return_value = _mock_response(201)
        result = _make_request("POST", "https://example.com/api", json={"k": "v"})
        self.assertEqual(result.status_code, 201)
        mock_post.assert_called_once_with("https://example.com/api", json={"k": "v"})

    @patch("requests.put")
    def test_put_method(self, mock_put):
        mock_put.return_value = _mock_response(200)
        _make_request("PUT", "https://example.com/api/1", json={})
        mock_put.assert_called_once()

    @patch("requests.patch")
    def test_patch_method(self, mock_patch):
        mock_patch.return_value = _mock_response(200)
        _make_request("PATCH", "https://example.com/api/1", json={})
        mock_patch.assert_called_once()

    @patch("requests.delete")
    def test_delete_method(self, mock_delete):
        mock_delete.return_value = _mock_response(204)
        _make_request("DELETE", "https://example.com/api/1")
        mock_delete.assert_called_once()

    @patch("requests.get")
    def test_case_insensitive_method(self, mock_get):
        mock_get.return_value = _mock_response(200)
        _make_request("get", "https://example.com/api")
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_kwargs_forwarded(self, mock_get):
        mock_get.return_value = _mock_response(200)
        _make_request("GET", "https://x.com", headers={"A": "B"}, params={"q": "1"}, timeout=30)
        mock_get.assert_called_once_with(
            "https://x.com", headers={"A": "B"}, params={"q": "1"}, timeout=30
        )


class TestMakeRequestNonRetryableErrors(unittest.TestCase):
    """Client errors (4xx except 429) are returned immediately."""

    @patch("requests.get")
    def test_400_not_retried(self, mock_get):
        mock_get.return_value = _mock_response(400)
        result = _make_request("GET", "https://example.com/api", max_retries=3)
        self.assertEqual(result.status_code, 400)
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_401_not_retried(self, mock_get):
        mock_get.return_value = _mock_response(401)
        result = _make_request("GET", "https://example.com/api", max_retries=3)
        self.assertEqual(result.status_code, 401)
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_403_not_retried(self, mock_get):
        mock_get.return_value = _mock_response(403)
        _make_request("GET", "https://example.com/api", max_retries=3)
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_404_not_retried(self, mock_get):
        mock_get.return_value = _mock_response(404)
        _make_request("GET", "https://example.com/api", max_retries=3)
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_422_not_retried(self, mock_get):
        mock_get.return_value = _mock_response(422)
        _make_request("GET", "https://example.com/api", max_retries=3)
        mock_get.assert_called_once()


class TestMakeRequestRetryOnTransientHTTP(unittest.TestCase):
    """Retryable HTTP status codes trigger retry with backoff."""

    @patch("time.sleep")
    @patch("requests.get")
    def test_500_retried_then_succeeds(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            _mock_response(500),
            _mock_response(200),
        ]
        result = _make_request("GET", "https://example.com/api", max_retries=3, backoff_factor=1.0)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)  # backoff_factor * 2^0

    @patch("time.sleep")
    @patch("requests.get")
    def test_502_retried_then_succeeds(self, mock_get, mock_sleep):
        mock_get.side_effect = [_mock_response(502), _mock_response(200)]
        _make_request("GET", "https://example.com/api", max_retries=3, backoff_factor=1.0)
        mock_sleep.assert_called_once_with(1.0)

    @patch("time.sleep")
    @patch("requests.get")
    def test_503_retried_then_succeeds(self, mock_get, mock_sleep):
        mock_get.side_effect = [_mock_response(503), _mock_response(200)]
        _make_request("GET", "https://example.com/api", max_retries=3, backoff_factor=1.0)
        mock_sleep.assert_called_once_with(1.0)

    @patch("time.sleep")
    @patch("requests.get")
    def test_504_retried_then_succeeds(self, mock_get, mock_sleep):
        mock_get.side_effect = [_mock_response(504), _mock_response(200)]
        _make_request("GET", "https://example.com/api", max_retries=3, backoff_factor=1.0)
        mock_sleep.assert_called_once_with(1.0)

    @patch("time.sleep")
    @patch("requests.get")
    def test_exponential_backoff_delays(self, mock_get, mock_sleep):
        # 500, 500, 500, 200 → sleeps: 1.0, 2.0, 4.0
        mock_get.side_effect = [
            _mock_response(500),
            _mock_response(500),
            _mock_response(500),
            _mock_response(200),
        ]
        result = _make_request("GET", "https://example.com/api", max_retries=3, backoff_factor=1.0)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(mock_get.call_count, 4)
        self.assertEqual(mock_sleep.call_args_list, [call(1.0), call(2.0), call(4.0)])

    @patch("time.sleep")
    @patch("requests.get")
    def test_backoff_factor_scales_delay(self, mock_get, mock_sleep):
        mock_get.side_effect = [_mock_response(503), _mock_response(200)]
        _make_request("GET", "https://example.com/api", max_retries=3, backoff_factor=2.0)
        mock_sleep.assert_called_once_with(2.0)  # 2.0 * 2^0

    @patch("time.sleep")
    @patch("requests.get")
    def test_max_retries_exhausted_returns_last_response(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(500)
        result = _make_request("GET", "https://example.com/api", max_retries=2, backoff_factor=1.0)
        self.assertEqual(result.status_code, 500)
        # Attempt 0 + 2 retries = 3 total calls; sleeps after attempt 0 and 1
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep")
    @patch("requests.get")
    def test_zero_retries_returns_transient_immediately(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(503)
        result = _make_request("GET", "https://example.com/api", max_retries=0)
        self.assertEqual(result.status_code, 503)
        mock_get.assert_called_once()
        mock_sleep.assert_not_called()


class TestMakeRequest429RateLimit(unittest.TestCase):
    """429 responses respect Retry-After header."""

    @patch("time.sleep")
    @patch("requests.get")
    def test_429_uses_retry_after_header(self, mock_get, mock_sleep):
        resp_429 = _mock_response(429)
        resp_429.headers = {"Retry-After": "5"}
        mock_get.side_effect = [resp_429, _mock_response(200)]
        _make_request("GET", "https://example.com/api", max_retries=3, backoff_factor=1.0)
        mock_sleep.assert_called_once_with(5.0)

    @patch("time.sleep")
    @patch("requests.get")
    def test_429_falls_back_to_backoff_without_header(self, mock_get, mock_sleep):
        resp_429 = _mock_response(429)
        resp_429.headers = {}
        mock_get.side_effect = [resp_429, _mock_response(200)]
        _make_request("GET", "https://example.com/api", max_retries=3, backoff_factor=1.0)
        mock_sleep.assert_called_once_with(1.0)  # backoff_factor * 2^0


class TestMakeRequestNetworkErrors(unittest.TestCase):
    """Network errors trigger retry with backoff; re-raise after max_retries."""

    @patch("time.sleep")
    @patch("requests.get")
    def test_connection_error_retried_then_succeeds(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("refused"),
            _mock_response(200),
        ]
        result = _make_request("GET", "https://example.com/api", max_retries=3, backoff_factor=1.0)
        self.assertEqual(result.status_code, 200)
        mock_sleep.assert_called_once_with(1.0)

    @patch("time.sleep")
    @patch("requests.get")
    def test_timeout_retried_then_succeeds(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            requests.exceptions.Timeout("timed out"),
            _mock_response(200),
        ]
        result = _make_request("GET", "https://example.com/api", max_retries=3, backoff_factor=1.0)
        self.assertEqual(result.status_code, 200)
        mock_sleep.assert_called_once_with(1.0)

    @patch("time.sleep")
    @patch("requests.get")
    def test_connection_error_exhausted_raises(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.exceptions.ConnectionError("always fails")
        with self.assertRaises(requests.exceptions.ConnectionError):
            _make_request("GET", "https://example.com/api", max_retries=2, backoff_factor=1.0)
        self.assertEqual(mock_get.call_count, 3)  # 1 + 2 retries
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep")
    @patch("requests.get")
    def test_timeout_zero_retries_raises(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.exceptions.Timeout("timed out")
        with self.assertRaises(requests.exceptions.Timeout):
            _make_request("GET", "https://example.com/api", max_retries=0)
        mock_get.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("requests.get")
    def test_non_retryable_exception_raises_immediately(self, mock_get, mock_sleep):
        # ValueError is not retryable and should propagate immediately
        mock_get.side_effect = ValueError("bad args")
        with self.assertRaises(ValueError):
            _make_request("GET", "https://example.com/api", max_retries=3)
        mock_get.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("requests.get")
    def test_exponential_backoff_on_connection_error(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            requests.exceptions.ConnectionError(),
            requests.exceptions.ConnectionError(),
            _mock_response(200),
        ]
        _make_request("GET", "https://example.com/api", max_retries=3, backoff_factor=1.0)
        self.assertEqual(mock_sleep.call_args_list, [call(1.0), call(2.0)])


class TestMakeRequestLogging(unittest.TestCase):
    """Retry events are logged at WARNING level."""

    @patch("time.sleep")
    @patch("requests.get")
    def test_warning_logged_on_transient_status(self, mock_get, mock_sleep):
        mock_get.side_effect = [_mock_response(503), _mock_response(200)]
        with self.assertLogs("servicenow_mcp.utils.helpers", level="WARNING") as cm:
            _make_request("GET", "https://example.com/api", max_retries=3)
        self.assertTrue(any("503" in msg for msg in cm.output))

    @patch("time.sleep")
    @patch("requests.get")
    def test_warning_logged_on_connection_error(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("refused"),
            _mock_response(200),
        ]
        with self.assertLogs("servicenow_mcp.utils.helpers", level="WARNING") as cm:
            _make_request("GET", "https://example.com/api", max_retries=3)
        self.assertTrue(any("refused" in msg or "retry" in msg.lower() for msg in cm.output))


if __name__ == "__main__":
    unittest.main()
