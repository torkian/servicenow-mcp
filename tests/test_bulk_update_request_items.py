"""Tests for bulk_update_request_items in bulk_tools.py."""

import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.bulk_tools import (
    BulkUpdateRequestItemsParams,
    RequestItemUpdate,
    bulk_update_request_items,
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


class TestBulkUpdateRequestItemsValidation(unittest.TestCase):
    def test_empty_updates_returns_failure(self):
        params = BulkUpdateRequestItemsParams.__new__(BulkUpdateRequestItemsParams)
        object.__setattr__(params, "updates", [])
        result = bulk_update_request_items(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("No updates provided", result["message"])

    def test_over_100_updates_returns_failure(self):
        too_many = [
            RequestItemUpdate(item_id=_SYS_ID_A, short_description=f"Update {i}")
            for i in range(101)
        ]
        params = BulkUpdateRequestItemsParams.__new__(BulkUpdateRequestItemsParams)
        object.__setattr__(params, "updates", too_many)
        result = bulk_update_request_items(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Too many updates", result["message"])
        self.assertIn("101", result["message"])

    def test_exactly_100_updates_is_accepted(self):
        updates = [
            RequestItemUpdate(item_id=("0" * 31 + str(i % 10)), short_description=f"u{i}")
            for i in range(100)
        ]
        params = BulkUpdateRequestItemsParams.__new__(BulkUpdateRequestItemsParams)
        object.__setattr__(params, "updates", updates)
        with patch("servicenow_mcp.tools.bulk_tools.requests.post") as mock_post:
            mock_post.return_value = _batch_response(
                [
                    {"id": str(i), "statusCode": 200, "statusText": "OK", "body": "{}"}
                    for i in range(100)
                ]
            )
            result = bulk_update_request_items(_config(), _auth(), params)
        self.assertNotIn("Too many updates", result.get("message", ""))


class TestBulkUpdateRequestItemsAllSysIds(unittest.TestCase):
    """When all item_ids are already sys_ids, no resolution GET is issued."""

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_single_sys_id_update_success(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[RequestItemUpdate(item_id=_SYS_ID_A, state="4")]
        )
        result = bulk_update_request_items(_config(), _auth(), params)

        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["results"][0]["item_id"], _SYS_ID_A)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_multiple_sys_ids_patch_url_contains_sys_id(self, mock_post):
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 200, "statusText": "OK", "body": "{}"},
            ]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[
                RequestItemUpdate(item_id=_SYS_ID_A, state="4"),
                RequestItemUpdate(item_id=_SYS_ID_B, state="6"),
            ]
        )
        bulk_update_request_items(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        urls = [r["url"] for r in payload["requests"]]
        self.assertIn(f"/api/now/v2/table/sc_req_item/{_SYS_ID_A}", urls)
        self.assertIn(f"/api/now/v2/table/sc_req_item/{_SYS_ID_B}", urls)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_patch_method_used_in_batch(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[RequestItemUpdate(item_id=_SYS_ID_A, work_notes="progressing")]
        )
        bulk_update_request_items(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["requests"][0]["method"], "PATCH")

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_only_provided_fields_in_body(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[RequestItemUpdate(item_id=_SYS_ID_A, state="18", close_notes="done")]
        )
        bulk_update_request_items(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        body = json.loads(payload["requests"][0]["body"])
        self.assertEqual(body, {"state": "18", "close_notes": "done"})
        self.assertNotIn("stage", body)
        self.assertNotIn("assigned_to", body)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_all_updatable_fields_passed_through(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[
                RequestItemUpdate(
                    item_id=_SYS_ID_A,
                    short_description="sd",
                    description="desc",
                    state="17",
                    stage="fulfillment",
                    assigned_to="john.doe",
                    assignment_group="helpdesk",
                    work_notes="wn",
                    close_notes="cn",
                )
            ]
        )
        bulk_update_request_items(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        body = json.loads(payload["requests"][0]["body"])
        for field in (
            "short_description", "description", "state", "stage",
            "assigned_to", "assignment_group", "work_notes", "close_notes",
        ):
            self.assertIn(field, body)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_partial_failure_reflected_in_result(self, mock_post):
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 404, "statusText": "Not Found", "body": "{}"},
            ]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[
                RequestItemUpdate(item_id=_SYS_ID_A, state="4"),
                RequestItemUpdate(item_id=_SYS_ID_B, state="6"),
            ]
        )
        result = bulk_update_request_items(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 1)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_batch_request_exception_returns_failure(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("refused")
        params = BulkUpdateRequestItemsParams(
            updates=[RequestItemUpdate(item_id=_SYS_ID_A, state="4")]
        )
        result = bulk_update_request_items(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("failed", result["message"].lower())


class TestBulkUpdateRequestItemsNumberResolution(unittest.TestCase):
    """When item_ids are RITM numbers, a preliminary GET resolves them."""

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_ritm_number_resolved_to_sys_id(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "RITM0010001", "sys_id": _SYS_ID_A}]
        )
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[RequestItemUpdate(item_id="RITM0010001", state="4")]
        )
        result = bulk_update_request_items(_config(), _auth(), params)

        self.assertTrue(result["success"])
        self.assertEqual(result["results"][0]["item_id"], "RITM0010001")

        payload = mock_post.call_args[1]["json"]
        self.assertIn(_SYS_ID_A, payload["requests"][0]["url"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_unresolvable_ritm_returns_failure(self, mock_get):
        mock_get.return_value = _get_response([])
        params = BulkUpdateRequestItemsParams(
            updates=[RequestItemUpdate(item_id="RITM9999999", state="4")]
        )
        result = bulk_update_request_items(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("RITM9999999", result["message"])
        self.assertIn("RITM9999999", result["unresolved"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_mixed_sys_ids_and_numbers(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "RITM0010002", "sys_id": _SYS_ID_B}]
        )
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 200, "statusText": "OK", "body": "{}"},
            ]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[
                RequestItemUpdate(item_id=_SYS_ID_A, state="4"),
                RequestItemUpdate(item_id="RITM0010002", state="6"),
            ]
        )
        result = bulk_update_request_items(_config(), _auth(), params)

        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 2)
        item_ids = [r["item_id"] for r in result["results"]]
        self.assertIn(_SYS_ID_A, item_ids)
        self.assertIn("RITM0010002", item_ids)

    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_resolution_get_failure_returns_failure(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("network error")
        params = BulkUpdateRequestItemsParams(
            updates=[RequestItemUpdate(item_id="RITM0010001", state="4")]
        )
        result = bulk_update_request_items(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("Failed to resolve request item numbers", result["message"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_resolution_get_uses_sc_req_item_table(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "RITM0010001", "sys_id": _SYS_ID_A}]
        )
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[RequestItemUpdate(item_id="RITM0010001", work_notes="note")]
        )
        bulk_update_request_items(_config(), _auth(), params)

        get_url = mock_get.call_args[0][0]
        self.assertIn("sc_req_item", get_url)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_batch_url_uses_v2_table_sc_req_item(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "RITM0010001", "sys_id": _SYS_ID_A}]
        )
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[RequestItemUpdate(item_id="RITM0010001", state="4")]
        )
        bulk_update_request_items(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        self.assertIn("/api/now/v2/table/sc_req_item/", payload["requests"][0]["url"])


class TestRequestItemUpdateModel(unittest.TestCase):
    def test_requires_item_id(self):
        with self.assertRaises(Exception):
            RequestItemUpdate()

    def test_all_optional_fields_default_to_none(self):
        u = RequestItemUpdate(item_id=_SYS_ID_A)
        for field in (
            "short_description", "description", "state", "stage",
            "assigned_to", "assignment_group", "work_notes", "close_notes",
        ):
            self.assertIsNone(getattr(u, field))

    def test_accepts_ritm_number_as_item_id(self):
        u = RequestItemUpdate(item_id="RITM0010001", state="4")
        self.assertEqual(u.item_id, "RITM0010001")
        self.assertEqual(u.state, "4")


class TestBulkUpdateRequestItemsEdgeCases(unittest.TestCase):
    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_item_id_enriched_in_results(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[RequestItemUpdate(item_id=_SYS_ID_A, stage="completed")]
        )
        result = bulk_update_request_items(_config(), _auth(), params)
        self.assertIn("item_id", result["results"][0])
        self.assertEqual(result["results"][0]["item_id"], _SYS_ID_A)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_ok_flag_present_in_results(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[RequestItemUpdate(item_id=_SYS_ID_A, state="18")]
        )
        result = bulk_update_request_items(_config(), _auth(), params)
        self.assertIn("ok", result["results"][0])
        self.assertTrue(result["results"][0]["ok"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_status_code_present_in_results(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateRequestItemsParams(
            updates=[RequestItemUpdate(item_id=_SYS_ID_A, state="4")]
        )
        result = bulk_update_request_items(_config(), _auth(), params)
        self.assertEqual(result["results"][0]["status_code"], 200)


if __name__ == "__main__":
    unittest.main()
