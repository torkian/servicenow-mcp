"""Tests for RateLimitTracker and its integration with _make_request."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.utils.helpers import RateLimitTracker, _make_request


def _mock_response(status_code: int, headers: dict = None) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = {}
    return resp


class TestRateLimitTrackerUpdate(unittest.TestCase):
    """RateLimitTracker.update() parses response headers correctly."""

    def setUp(self):
        self.tracker = RateLimitTracker()

    def test_parses_x_ratelimit_remaining(self):
        resp = _mock_response(200, {"X-RateLimit-Remaining": "80"})
        self.tracker.update(resp)
        self.assertEqual(self.tracker.remaining, 80)

    def test_parses_ratelimit_remaining_alternate_header(self):
        resp = _mock_response(200, {"RateLimit-Remaining": "50"})
        self.tracker.update(resp)
        self.assertEqual(self.tracker.remaining, 50)

    def test_x_ratelimit_takes_precedence_over_ratelimit(self):
        resp = _mock_response(200, {"X-RateLimit-Remaining": "70", "RateLimit-Remaining": "30"})
        self.tracker.update(resp)
        self.assertEqual(self.tracker.remaining, 70)

    def test_parses_x_ratelimit_limit(self):
        resp = _mock_response(200, {"X-RateLimit-Limit": "100"})
        self.tracker.update(resp)
        self.assertEqual(self.tracker.limit, 100)

    def test_parses_ratelimit_limit_alternate_header(self):
        resp = _mock_response(200, {"RateLimit-Limit": "200"})
        self.tracker.update(resp)
        self.assertEqual(self.tracker.limit, 200)

    def test_parses_x_ratelimit_reset(self):
        resp = _mock_response(200, {"X-RateLimit-Reset": "1700000000"})
        self.tracker.update(resp)
        self.assertAlmostEqual(self.tracker.reset_at, 1700000000.0)

    def test_parses_ratelimit_reset_alternate_header(self):
        resp = _mock_response(200, {"RateLimit-Reset": "1700000099"})
        self.tracker.update(resp)
        self.assertAlmostEqual(self.tracker.reset_at, 1700000099.0)

    def test_ignores_non_numeric_remaining(self):
        resp = _mock_response(200, {"X-RateLimit-Remaining": "bad"})
        self.tracker.update(resp)
        self.assertIsNone(self.tracker.remaining)

    def test_no_headers_leaves_state_none(self):
        resp = _mock_response(200, {})
        self.tracker.update(resp)
        self.assertIsNone(self.tracker.remaining)
        self.assertIsNone(self.tracker.limit)
        self.assertIsNone(self.tracker.reset_at)

    def test_accumulates_state_across_calls(self):
        self.tracker.update(_mock_response(200, {"X-RateLimit-Limit": "100", "X-RateLimit-Remaining": "90"}))
        self.tracker.update(_mock_response(200, {"X-RateLimit-Remaining": "80"}))
        self.assertEqual(self.tracker.remaining, 80)
        self.assertEqual(self.tracker.limit, 100)


class TestRateLimitTrackerWarning(unittest.TestCase):
    """RateLimitTracker logs a warning when remaining falls below threshold."""

    def test_logs_warning_at_or_below_threshold(self):
        tracker = RateLimitTracker(warning_threshold=0.1)
        resp = _mock_response(200, {"X-RateLimit-Remaining": "9", "X-RateLimit-Limit": "100"})
        with self.assertLogs("servicenow_mcp.utils.helpers", level="WARNING") as cm:
            tracker.update(resp)
        self.assertTrue(any("Rate limit warning" in msg for msg in cm.output))
        self.assertTrue(any("9/100" in msg for msg in cm.output))

    def test_no_warning_above_threshold(self):
        tracker = RateLimitTracker(warning_threshold=0.1)
        resp = _mock_response(200, {"X-RateLimit-Remaining": "50", "X-RateLimit-Limit": "100"})
        # assertLogs fails if no logs emitted — use assertNoLogs (Python 3.10+) or try/except
        with self.assertRaises(AssertionError):
            with self.assertLogs("servicenow_mcp.utils.helpers", level="WARNING"):
                tracker.update(resp)

    def test_warning_includes_reset_timestamp_when_present(self):
        tracker = RateLimitTracker(warning_threshold=0.1)
        resp = _mock_response(200, {
            "X-RateLimit-Remaining": "5",
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Reset": "1700000000",
        })
        with self.assertLogs("servicenow_mcp.utils.helpers", level="WARNING") as cm:
            tracker.update(resp)
        self.assertTrue(any("1700000000" in msg for msg in cm.output))

    def test_no_warning_when_limit_missing(self):
        tracker = RateLimitTracker(warning_threshold=0.1)
        resp = _mock_response(200, {"X-RateLimit-Remaining": "5"})
        # No limit → can't compute ratio → no warning
        with self.assertRaises(AssertionError):
            with self.assertLogs("servicenow_mcp.utils.helpers", level="WARNING"):
                tracker.update(resp)


class TestRateLimitTrackerThrottle(unittest.TestCase):
    """RateLimitTracker.check_and_throttle() sleeps when quota is critical."""

    @patch("time.sleep")
    def test_no_sleep_when_state_unknown(self, mock_sleep):
        tracker = RateLimitTracker()
        tracker.check_and_throttle()
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_no_sleep_above_throttle_threshold(self, mock_sleep):
        tracker = RateLimitTracker(throttle_threshold=0.05)
        tracker.remaining = 10
        tracker.limit = 100
        tracker.check_and_throttle()
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_sleeps_when_at_or_below_throttle_threshold(self, mock_sleep):
        tracker = RateLimitTracker(throttle_threshold=0.05)
        tracker.remaining = 4
        tracker.limit = 100
        tracker.check_and_throttle()
        mock_sleep.assert_called_once_with(1.0)

    @patch("time.sleep")
    @patch("time.time")
    def test_sleeps_until_reset_when_available(self, mock_time, mock_sleep):
        mock_time.return_value = 1700000000.0
        tracker = RateLimitTracker(throttle_threshold=0.05)
        tracker.remaining = 2
        tracker.limit = 100
        tracker.reset_at = 1700000030.0
        tracker.check_and_throttle()
        mock_sleep.assert_called_once_with(30.0)

    @patch("time.sleep")
    @patch("time.time")
    def test_sleep_capped_at_60_seconds(self, mock_time, mock_sleep):
        mock_time.return_value = 1700000000.0
        tracker = RateLimitTracker(throttle_threshold=0.05)
        tracker.remaining = 1
        tracker.limit = 100
        tracker.reset_at = 1700000300.0  # 300 s in the future
        tracker.check_and_throttle()
        mock_sleep.assert_called_once_with(60.0)

    @patch("time.sleep")
    @patch("time.time")
    def test_falls_back_to_1s_when_reset_in_past(self, mock_time, mock_sleep):
        mock_time.return_value = 1700000100.0
        tracker = RateLimitTracker(throttle_threshold=0.05)
        tracker.remaining = 3
        tracker.limit = 100
        tracker.reset_at = 1700000050.0  # already passed
        tracker.check_and_throttle()
        mock_sleep.assert_called_once_with(1.0)

    @patch("time.sleep")
    def test_logs_critical_warning_before_sleeping(self, mock_sleep):
        tracker = RateLimitTracker(throttle_threshold=0.05)
        tracker.remaining = 2
        tracker.limit = 100
        with self.assertLogs("servicenow_mcp.utils.helpers", level="WARNING") as cm:
            tracker.check_and_throttle()
        self.assertTrue(any("Rate limit critical" in msg for msg in cm.output))

    @patch("time.sleep")
    def test_no_sleep_when_limit_is_zero(self, mock_sleep):
        tracker = RateLimitTracker(throttle_threshold=0.05)
        tracker.remaining = 0
        tracker.limit = 0
        tracker.check_and_throttle()
        mock_sleep.assert_not_called()


class TestRateLimitTrackerUtilization(unittest.TestCase):
    """RateLimitTracker.utilization property."""

    def test_none_when_state_unknown(self):
        tracker = RateLimitTracker()
        self.assertIsNone(tracker.utilization)

    def test_zero_when_none_used(self):
        tracker = RateLimitTracker()
        tracker.remaining = 100
        tracker.limit = 100
        self.assertAlmostEqual(tracker.utilization, 0.0)

    def test_full_when_exhausted(self):
        tracker = RateLimitTracker()
        tracker.remaining = 0
        tracker.limit = 100
        self.assertAlmostEqual(tracker.utilization, 1.0)

    def test_partial_utilization(self):
        tracker = RateLimitTracker()
        tracker.remaining = 75
        tracker.limit = 100
        self.assertAlmostEqual(tracker.utilization, 0.25)

    def test_none_when_limit_zero(self):
        tracker = RateLimitTracker()
        tracker.remaining = 0
        tracker.limit = 0
        self.assertIsNone(tracker.utilization)


class TestRateLimitTrackerReset(unittest.TestCase):
    """RateLimitTracker.reset() clears all state."""

    def test_reset_clears_state(self):
        tracker = RateLimitTracker()
        tracker.remaining = 10
        tracker.limit = 100
        tracker.reset_at = 1700000000.0
        tracker.reset()
        self.assertIsNone(tracker.remaining)
        self.assertIsNone(tracker.limit)
        self.assertIsNone(tracker.reset_at)


class TestMakeRequestTrackerIntegration(unittest.TestCase):
    """_make_request integrates with RateLimitTracker correctly."""

    @patch("requests.get")
    def test_tracker_updated_after_successful_response(self, mock_get):
        mock_get.return_value = _mock_response(200, {
            "X-RateLimit-Remaining": "95",
            "X-RateLimit-Limit": "100",
        })
        tracker = RateLimitTracker()
        _make_request("GET", "https://example.com/api", rate_limit_tracker=tracker)
        self.assertEqual(tracker.remaining, 95)
        self.assertEqual(tracker.limit, 100)

    @patch("time.sleep")
    @patch("requests.get")
    def test_tracker_updated_on_retried_responses(self, mock_get, mock_sleep):
        resp_500 = _mock_response(500, {"X-RateLimit-Remaining": "50", "X-RateLimit-Limit": "100"})
        resp_200 = _mock_response(200, {"X-RateLimit-Remaining": "49", "X-RateLimit-Limit": "100"})
        mock_get.side_effect = [resp_500, resp_200]
        tracker = RateLimitTracker()
        _make_request("GET", "https://example.com/api", rate_limit_tracker=tracker, max_retries=3)
        self.assertEqual(tracker.remaining, 49)

    @patch("time.sleep")
    @patch("requests.get")
    def test_check_and_throttle_called_before_each_attempt(self, mock_get, mock_sleep):
        mock_get.side_effect = [_mock_response(500), _mock_response(200)]
        tracker = RateLimitTracker()
        tracker.remaining = 3
        tracker.limit = 100

        throttle_calls = []
        original_check = tracker.check_and_throttle

        def recording_check():
            throttle_calls.append(1)
            return original_check()

        tracker.check_and_throttle = recording_check
        _make_request("GET", "https://example.com/api", rate_limit_tracker=tracker, max_retries=3)
        # Called once per attempt: attempt 0 (500) and attempt 1 (200)
        self.assertEqual(len(throttle_calls), 2)

    @patch("time.sleep")
    @patch("requests.get")
    def test_no_existing_tests_broken_by_default_tracker(self, mock_get, mock_sleep):
        # Default tracker has remaining=None so check_and_throttle is a no-op;
        # existing retry behaviour is unchanged.
        mock_get.side_effect = [_mock_response(500), _mock_response(200)]
        result = _make_request("GET", "https://example.com/api", max_retries=3, backoff_factor=1.0)
        self.assertEqual(result.status_code, 200)
        mock_sleep.assert_called_once_with(1.0)

    @patch("requests.get")
    def test_custom_tracker_isolates_state_from_module_level(self, mock_get):
        mock_get.return_value = _mock_response(200, {"X-RateLimit-Remaining": "42", "X-RateLimit-Limit": "100"})
        tracker_a = RateLimitTracker()
        tracker_b = RateLimitTracker()
        _make_request("GET", "https://example.com/a", rate_limit_tracker=tracker_a)
        self.assertEqual(tracker_a.remaining, 42)
        self.assertIsNone(tracker_b.remaining)

    @patch("time.sleep")
    @patch("requests.get")
    def test_tracker_triggers_throttle_when_critical(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(200, {})
        tracker = RateLimitTracker(throttle_threshold=0.05)
        tracker.remaining = 3
        tracker.limit = 100
        with self.assertLogs("servicenow_mcp.utils.helpers", level="WARNING"):
            _make_request("GET", "https://example.com/api", rate_limit_tracker=tracker)
        mock_sleep.assert_called_once_with(1.0)


if __name__ == "__main__":
    unittest.main()
