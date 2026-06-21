"""Tests for bulk_update_change_tasks in bulk_tools.py."""

import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.bulk_tools import (
    BulkUpdateChangeTasksParams,
    ChangeTaskUpdate,
    bulk_update_change_tasks,
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


class TestBulkUpdateChangeTasksValidation(unittest.TestCase):
    def test_empty_updates_returns_failure(self):
        params = BulkUpdateChangeTasksParams.__new__(BulkUpdateChangeTasksParams)
        object.__setattr__(params, "updates", [])
        result = bulk_update_change_tasks(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("No updates provided", result["message"])

    def test_over_100_updates_returns_failure(self):
        params = BulkUpdateChangeTasksParams.__new__(BulkUpdateChangeTasksParams)
        too_many = [
            ChangeTaskUpdate(task_id=_SYS_ID_A, short_description=f"Update {i}")
            for i in range(101)
        ]
        object.__setattr__(params, "updates", too_many)
        result = bulk_update_change_tasks(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Too many updates", result["message"])
        self.assertIn("101", result["message"])

    def test_exactly_100_updates_is_accepted(self):
        params = BulkUpdateChangeTasksParams.__new__(BulkUpdateChangeTasksParams)
        updates = [
            ChangeTaskUpdate(
                task_id=("0" * 31 + str(i % 10)), short_description=f"u{i}"
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
            result = bulk_update_change_tasks(_config(), _auth(), params)
        self.assertNotIn("Too many updates", result.get("message", ""))


class TestBulkUpdateChangeTasksAllSysIds(unittest.TestCase):
    """When all task_ids are already sys_ids, no resolution GET is issued."""

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_single_sys_id_update_success(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[ChangeTaskUpdate(task_id=_SYS_ID_A, state="2")]
        )
        result = bulk_update_change_tasks(_config(), _auth(), params)

        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["results"][0]["task_id"], _SYS_ID_A)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_multiple_sys_ids_patch_url_contains_sys_id(self, mock_post):
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 200, "statusText": "OK", "body": "{}"},
            ]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[
                ChangeTaskUpdate(task_id=_SYS_ID_A, state="2"),
                ChangeTaskUpdate(task_id=_SYS_ID_B, state="3"),
            ]
        )
        bulk_update_change_tasks(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        urls = [r["url"] for r in payload["requests"]]
        self.assertIn(f"/api/now/v2/table/change_task/{_SYS_ID_A}", urls)
        self.assertIn(f"/api/now/v2/table/change_task/{_SYS_ID_B}", urls)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_patch_method_used_in_batch(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[ChangeTaskUpdate(task_id=_SYS_ID_A, work_notes="in progress")]
        )
        bulk_update_change_tasks(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["requests"][0]["method"], "PATCH")

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_only_provided_fields_in_body(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[
                ChangeTaskUpdate(task_id=_SYS_ID_A, state="2", assigned_to="john.doe")
            ]
        )
        bulk_update_change_tasks(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        body = json.loads(payload["requests"][0]["body"])
        self.assertEqual(body, {"state": "2", "assigned_to": "john.doe"})
        self.assertNotIn("close_notes", body)
        self.assertNotIn("description", body)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_all_updatable_fields_passed_through(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[
                ChangeTaskUpdate(
                    task_id=_SYS_ID_A,
                    short_description="sd",
                    description="desc",
                    state="2",
                    assigned_to="john",
                    assignment_group="network",
                    planned_start_date="2026-06-21 08:00:00",
                    planned_end_date="2026-06-21 10:00:00",
                    work_notes="wn",
                    close_notes="cn",
                )
            ]
        )
        bulk_update_change_tasks(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        body = json.loads(payload["requests"][0]["body"])
        for field in (
            "short_description", "description", "state", "assigned_to",
            "assignment_group", "planned_start_date", "planned_end_date",
            "work_notes", "close_notes",
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
        params = BulkUpdateChangeTasksParams(
            updates=[
                ChangeTaskUpdate(task_id=_SYS_ID_A, state="2"),
                ChangeTaskUpdate(task_id=_SYS_ID_B, state="3"),
            ]
        )
        result = bulk_update_change_tasks(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 1)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_batch_request_exception_returns_failure(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("refused")
        params = BulkUpdateChangeTasksParams(
            updates=[ChangeTaskUpdate(task_id=_SYS_ID_A, state="2")]
        )
        result = bulk_update_change_tasks(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("Batch request failed", result["message"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_result_entries_carry_task_id_for_sys_id_input(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[ChangeTaskUpdate(task_id=_SYS_ID_A, state="2")]
        )
        result = bulk_update_change_tasks(_config(), _auth(), params)
        self.assertEqual(result["results"][0]["task_id"], _SYS_ID_A)


class TestBulkUpdateChangeTasksNumberResolution(unittest.TestCase):
    """Tests covering the CTASK number → sys_id resolution path."""

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_ctask_number_resolved_before_batch(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "CTASK0001234", "sys_id": _SYS_ID_A}]
        )
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[ChangeTaskUpdate(task_id="CTASK0001234", state="2")]
        )
        result = bulk_update_change_tasks(_config(), _auth(), params)

        self.assertTrue(result["success"])
        mock_get.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        self.assertIn(_SYS_ID_A, payload["requests"][0]["url"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_resolution_query_targets_change_task_table(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "CTASK0001234", "sys_id": _SYS_ID_A}]
        )
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[ChangeTaskUpdate(task_id="CTASK0001234", state="2")]
        )
        bulk_update_change_tasks(_config(), _auth(), params)

        get_url = mock_get.call_args[0][0]
        self.assertIn("change_task", get_url)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_resolution_query_uses_numberIN_operator(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [
                {"number": "CTASK0001234", "sys_id": _SYS_ID_A},
                {"number": "CTASK0001235", "sys_id": _SYS_ID_B},
            ]
        )
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 200, "statusText": "OK", "body": "{}"},
            ]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[
                ChangeTaskUpdate(task_id="CTASK0001234", state="2"),
                ChangeTaskUpdate(task_id="CTASK0001235", state="3"),
            ]
        )
        bulk_update_change_tasks(_config(), _auth(), params)

        get_kwargs = mock_get.call_args[1]
        query = get_kwargs["params"]["sysparm_query"]
        self.assertTrue(query.startswith("numberIN"))
        self.assertIn("CTASK0001234", query)
        self.assertIn("CTASK0001235", query)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_single_get_issued_for_all_numbers(self, mock_get, mock_post):
        ids = [f"cc{str(i).zfill(30)}" for i in range(3)]
        mock_get.return_value = _get_response(
            [{"number": f"CTASK000{i}", "sys_id": ids[i]} for i in range(3)]
        )
        mock_post.return_value = _batch_response(
            [
                {"id": str(i), "statusCode": 200, "statusText": "OK", "body": "{}"}
                for i in range(3)
            ]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[
                ChangeTaskUpdate(task_id=f"CTASK000{i}", state="2") for i in range(3)
            ]
        )
        bulk_update_change_tasks(_config(), _auth(), params)
        self.assertEqual(mock_get.call_count, 1)

    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_unresolved_number_returns_failure(self, mock_get):
        mock_get.return_value = _get_response([])
        params = BulkUpdateChangeTasksParams(
            updates=[ChangeTaskUpdate(task_id="CTASK0099999", state="2")]
        )
        result = bulk_update_change_tasks(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("CTASK0099999", result["message"])
        self.assertIn("CTASK0099999", result.get("unresolved", []))

    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_resolution_network_error_returns_failure(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("network down")
        params = BulkUpdateChangeTasksParams(
            updates=[ChangeTaskUpdate(task_id="CTASK0001234", state="2")]
        )
        result = bulk_update_change_tasks(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("resolve change task numbers", result["message"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_mixed_sys_ids_and_numbers(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "CTASK0001234", "sys_id": _SYS_ID_B}]
        )
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 200, "statusText": "OK", "body": "{}"},
            ]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[
                ChangeTaskUpdate(task_id=_SYS_ID_A, state="2"),
                ChangeTaskUpdate(task_id="CTASK0001234", state="3"),
            ]
        )
        result = bulk_update_change_tasks(_config(), _auth(), params)

        self.assertTrue(result["success"])
        mock_get.assert_called_once()
        mock_post.assert_called_once()

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_no_get_issued_when_all_sys_ids(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[ChangeTaskUpdate(task_id=_SYS_ID_A, state="2")]
        )
        with patch("servicenow_mcp.tools.bulk_tools.requests.get") as mock_get:
            bulk_update_change_tasks(_config(), _auth(), params)
            mock_get.assert_not_called()

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_result_entries_carry_task_id(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "CTASK0001234", "sys_id": _SYS_ID_A}]
        )
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[ChangeTaskUpdate(task_id="CTASK0001234", state="2")]
        )
        result = bulk_update_change_tasks(_config(), _auth(), params)

        self.assertEqual(result["results"][0]["task_id"], "CTASK0001234")

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_close_notes_and_work_notes_in_body(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "CTASK0001234", "sys_id": _SYS_ID_A}]
        )
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateChangeTasksParams(
            updates=[
                ChangeTaskUpdate(
                    task_id="CTASK0001234",
                    state="3",
                    close_notes="completed successfully",
                    work_notes="final update",
                )
            ]
        )
        bulk_update_change_tasks(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        body = json.loads(payload["requests"][0]["body"])
        self.assertEqual(body["state"], "3")
        self.assertEqual(body["close_notes"], "completed successfully")
        self.assertEqual(body["work_notes"], "final update")


if __name__ == "__main__":
    unittest.main()
