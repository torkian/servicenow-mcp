"""Tests for bulk_update_change_requests in bulk_tools.py."""

import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.bulk_tools import (
    BulkUpdateChangeRequestsParams,
    ChangeRequestUpdate,
    bulk_update_change_requests,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

_AUTH_CONFIG = AuthConfig(
    type=AuthType.BASIC,
    basic=BasicAuthConfig(username="admin", password="password"),
)
_FAKE_HEADERS = {"Authorization": "Basic YWRtaW46cGFzc3dvcmQ="}
_SYS_ID_A = "a" * 32
_SYS_ID_B = "b" * 32


def _config() -> ServerConfig:
    return ServerConfig(instance_url="https://dev99999.service-now.com", auth=_AUTH_CONFIG)


def _auth() -> MagicMock:
    m = MagicMock(spec=AuthManager)
    m.get_headers.return_value = _FAKE_HEADERS
    return m


def _batch_response(items: list) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"servicedRequests": items}
    return mock_resp


def _get_response(results: list) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": results}
    return mock_resp


class TestBulkUpdateChangeRequestsValidation(unittest.TestCase):
    def test_empty_updates_returns_failure(self):
        params = BulkUpdateChangeRequestsParams.__new__(BulkUpdateChangeRequestsParams)
        object.__setattr__(params, "updates", [])
        result = bulk_update_change_requests(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("No updates provided", result["message"])

    def test_over_100_updates_returns_failure(self):
        params = BulkUpdateChangeRequestsParams.__new__(BulkUpdateChangeRequestsParams)
        too_many = [
            ChangeRequestUpdate(change_id=_SYS_ID_A, short_description=f"Update {i}")
            for i in range(101)
        ]
        object.__setattr__(params, "updates", too_many)
        result = bulk_update_change_requests(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Too many updates", result["message"])
        self.assertIn("101", result["message"])

    def test_exactly_100_updates_is_accepted(self):
        params = BulkUpdateChangeRequestsParams.__new__(BulkUpdateChangeRequestsParams)
        updates = [
            ChangeRequestUpdate(
                change_id=("0" * 31 + str(i % 10)), short_description=f"u{i}"
            )
            for i in range(100)
        ]
        object.__setattr__(params, "updates", updates)
        with patch("servicenow_mcp.tools.bulk_tools.requests.post") as mock_post:
            mock_post.return_value = _batch_response(
                [
                    {"id": str(i), "statusCode": 200, "statusText": "OK", "body": "{}"}
                    for i in range(100)
                ]
            )
            result = bulk_update_change_requests(_config(), _auth(), params)
        self.assertNotIn("Too many updates", result.get("message", ""))


class TestBulkUpdateChangeRequestsAllSysIds(unittest.TestCase):
    """When all change_ids are already sys_ids, no resolution GET is issued."""

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_single_sys_id_update_success(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[ChangeRequestUpdate(change_id=_SYS_ID_A, state="0")]
        )
        result = bulk_update_change_requests(_config(), _auth(), params)

        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["results"][0]["change_id"], _SYS_ID_A)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_multiple_sys_ids_patch_url_contains_sys_id(self, mock_post):
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 200, "statusText": "OK", "body": "{}"},
            ]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[
                ChangeRequestUpdate(change_id=_SYS_ID_A, risk="low"),
                ChangeRequestUpdate(change_id=_SYS_ID_B, state="-1"),
            ]
        )
        bulk_update_change_requests(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        urls = [r["url"] for r in payload["requests"]]
        self.assertIn(f"/api/now/v2/table/change_request/{_SYS_ID_A}", urls)
        self.assertIn(f"/api/now/v2/table/change_request/{_SYS_ID_B}", urls)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_patch_method_used_in_batch(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[ChangeRequestUpdate(change_id=_SYS_ID_A, work_notes="scheduled")]
        )
        bulk_update_change_requests(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["requests"][0]["method"], "PATCH")

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_only_provided_fields_in_body(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[
                ChangeRequestUpdate(change_id=_SYS_ID_A, state="1", risk="moderate")
            ]
        )
        bulk_update_change_requests(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        body = json.loads(payload["requests"][0]["body"])
        self.assertEqual(body, {"state": "1", "risk": "moderate"})
        self.assertNotIn("priority", body)
        self.assertNotIn("category", body)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_all_updatable_fields_passed_through(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[
                ChangeRequestUpdate(
                    change_id=_SYS_ID_A,
                    short_description="sd",
                    description="desc",
                    state="1",
                    type="normal",
                    category="network",
                    risk="low",
                    impact="2",
                    priority="3",
                    assignment_group="change_cab",
                    assigned_to="john",
                    start_date="2026-06-01 08:00:00",
                    end_date="2026-06-01 10:00:00",
                    work_notes="wn",
                )
            ]
        )
        bulk_update_change_requests(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        body = json.loads(payload["requests"][0]["body"])
        for field in (
            "short_description", "description", "state", "type", "category",
            "risk", "impact", "priority", "assignment_group", "assigned_to",
            "start_date", "end_date", "work_notes",
        ):
            self.assertIn(field, body)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_partial_failure_reflected_in_result(self, mock_post):
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 403, "statusText": "Forbidden", "body": "{}"},
            ]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[
                ChangeRequestUpdate(change_id=_SYS_ID_A, state="1"),
                ChangeRequestUpdate(change_id=_SYS_ID_B, state="-1"),
            ]
        )
        result = bulk_update_change_requests(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 1)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_batch_request_exception_returns_failure(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("refused")
        params = BulkUpdateChangeRequestsParams(
            updates=[ChangeRequestUpdate(change_id=_SYS_ID_A, state="1")]
        )
        result = bulk_update_change_requests(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("Batch request failed", result["message"])


class TestBulkUpdateChangeRequestsNumberResolution(unittest.TestCase):
    """Tests covering the number → sys_id resolution path."""

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_change_number_resolved_before_batch(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "CHG0010001", "sys_id": _SYS_ID_A}]
        )
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[ChangeRequestUpdate(change_id="CHG0010001", state="1")]
        )
        result = bulk_update_change_requests(_config(), _auth(), params)

        self.assertTrue(result["success"])
        mock_get.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        self.assertIn(_SYS_ID_A, payload["requests"][0]["url"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_resolution_query_targets_change_request_table(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "CHG0010001", "sys_id": _SYS_ID_A}]
        )
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[ChangeRequestUpdate(change_id="CHG0010001", state="1")]
        )
        bulk_update_change_requests(_config(), _auth(), params)

        get_url = mock_get.call_args[0][0]
        self.assertIn("change_request", get_url)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_resolution_query_uses_numberIN_operator(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [
                {"number": "CHG0010001", "sys_id": _SYS_ID_A},
                {"number": "CHG0010002", "sys_id": _SYS_ID_B},
            ]
        )
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 200, "statusText": "OK", "body": "{}"},
            ]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[
                ChangeRequestUpdate(change_id="CHG0010001", state="1"),
                ChangeRequestUpdate(change_id="CHG0010002", risk="high"),
            ]
        )
        bulk_update_change_requests(_config(), _auth(), params)

        get_kwargs = mock_get.call_args[1]
        query = get_kwargs["params"]["sysparm_query"]
        self.assertTrue(query.startswith("numberIN"))
        self.assertIn("CHG0010001", query)
        self.assertIn("CHG0010002", query)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_single_get_issued_for_all_numbers(self, mock_get, mock_post):
        ids = [f"cc{str(i).zfill(30)}" for i in range(3)]
        mock_get.return_value = _get_response(
            [{"number": f"CHG000{i}", "sys_id": ids[i]} for i in range(3)]
        )
        mock_post.return_value = _batch_response(
            [
                {"id": str(i), "statusCode": 200, "statusText": "OK", "body": "{}"}
                for i in range(3)
            ]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[
                ChangeRequestUpdate(change_id=f"CHG000{i}", state="1") for i in range(3)
            ]
        )
        bulk_update_change_requests(_config(), _auth(), params)
        self.assertEqual(mock_get.call_count, 1)

    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_unresolved_number_returns_failure(self, mock_get):
        mock_get.return_value = _get_response([])
        params = BulkUpdateChangeRequestsParams(
            updates=[ChangeRequestUpdate(change_id="CHG0099999", state="1")]
        )
        result = bulk_update_change_requests(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("CHG0099999", result["message"])
        self.assertIn("CHG0099999", result.get("unresolved", []))

    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_resolution_network_error_returns_failure(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("network down")
        params = BulkUpdateChangeRequestsParams(
            updates=[ChangeRequestUpdate(change_id="CHG0010001", state="1")]
        )
        result = bulk_update_change_requests(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("resolve change request numbers", result["message"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_mixed_sys_ids_and_numbers(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "CHG0010001", "sys_id": _SYS_ID_B}]
        )
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 200, "statusText": "OK", "body": "{}"},
            ]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[
                ChangeRequestUpdate(change_id=_SYS_ID_A, state="1"),
                ChangeRequestUpdate(change_id="CHG0010001", risk="low"),
            ]
        )
        result = bulk_update_change_requests(_config(), _auth(), params)

        self.assertTrue(result["success"])
        mock_get.assert_called_once()
        mock_post.assert_called_once()

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_no_get_issued_when_all_sys_ids(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[ChangeRequestUpdate(change_id=_SYS_ID_A, state="1")]
        )
        with patch("servicenow_mcp.tools.bulk_tools.requests.get") as mock_get:
            bulk_update_change_requests(_config(), _auth(), params)
            mock_get.assert_not_called()

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_result_entries_carry_change_id(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "CHG0010001", "sys_id": _SYS_ID_A}]
        )
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[ChangeRequestUpdate(change_id="CHG0010001", state="1")]
        )
        result = bulk_update_change_requests(_config(), _auth(), params)

        self.assertEqual(result["results"][0]["change_id"], "CHG0010001")

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_result_entries_carry_change_id_for_sys_id_input(self, mock_get, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeRequestsParams(
            updates=[ChangeRequestUpdate(change_id=_SYS_ID_A, state="1")]
        )
        result = bulk_update_change_requests(_config(), _auth(), params)

        self.assertEqual(result["results"][0]["change_id"], _SYS_ID_A)
        mock_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
