"""Tests for bulk_delete_incidents in bulk_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.bulk_tools import (
    BulkDeleteIncidentsParams,
    bulk_delete_incidents,
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


class TestBulkDeleteIncidentsValidation(unittest.TestCase):
    def test_empty_list_returns_failure(self):
        params = BulkDeleteIncidentsParams.__new__(BulkDeleteIncidentsParams)
        object.__setattr__(params, "incident_ids", [])
        result = bulk_delete_incidents(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("No incident IDs provided", result["message"])

    def test_over_100_ids_returns_failure(self):
        params = BulkDeleteIncidentsParams.__new__(BulkDeleteIncidentsParams)
        object.__setattr__(params, "incident_ids", [_SYS_ID_A] * 101)
        result = bulk_delete_incidents(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Too many incidents", result["message"])
        self.assertIn("101", result["message"])

    def test_exactly_100_ids_accepted(self):
        params = BulkDeleteIncidentsParams.__new__(BulkDeleteIncidentsParams)
        object.__setattr__(params, "incident_ids", [_SYS_ID_A] * 100)
        with patch("servicenow_mcp.tools.bulk_tools.requests.post") as mock_post:
            mock_post.return_value = _batch_response(
                [{"id": str(i), "statusCode": 204, "statusText": "No Content", "body": ""}
                 for i in range(100)]
            )
            result = bulk_delete_incidents(_config(), _auth(), params)
        self.assertNotIn("Too many incidents", result.get("message", ""))


class TestBulkDeleteIncidentsAllSysIds(unittest.TestCase):
    """When all incident_ids are already sys_ids, no resolution GET is issued."""

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_single_sys_id_delete_success(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 204, "statusText": "No Content", "body": ""}]
        )
        params = BulkDeleteIncidentsParams(incident_ids=[_SYS_ID_A])
        result = bulk_delete_incidents(_config(), _auth(), params)

        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["results"][0]["incident_id"], _SYS_ID_A)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_multiple_sys_ids_delete_url_correct(self, mock_post):
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 204, "statusText": "No Content", "body": ""},
                {"id": "1", "statusCode": 204, "statusText": "No Content", "body": ""},
            ]
        )
        params = BulkDeleteIncidentsParams(incident_ids=[_SYS_ID_A, _SYS_ID_B])
        bulk_delete_incidents(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        urls = [r["url"] for r in payload["requests"]]
        self.assertIn(f"/api/now/v2/table/incident/{_SYS_ID_A}", urls)
        self.assertIn(f"/api/now/v2/table/incident/{_SYS_ID_B}", urls)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_delete_method_used_in_batch(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 204, "statusText": "No Content", "body": ""}]
        )
        params = BulkDeleteIncidentsParams(incident_ids=[_SYS_ID_A])
        bulk_delete_incidents(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["requests"][0]["method"], "DELETE")

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_incident_id_enriched_in_results(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 204, "statusText": "No Content", "body": ""}]
        )
        params = BulkDeleteIncidentsParams(incident_ids=[_SYS_ID_A])
        result = bulk_delete_incidents(_config(), _auth(), params)

        self.assertEqual(result["results"][0]["incident_id"], _SYS_ID_A)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_404_response_reported_as_failed(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 404, "statusText": "Not Found", "body": "{}"}]
        )
        params = BulkDeleteIncidentsParams(incident_ids=[_SYS_ID_A])
        result = bulk_delete_incidents(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertEqual(result["failed"], 1)
        self.assertFalse(result["results"][0]["ok"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_partial_failures_reported_correctly(self, mock_post):
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 204, "statusText": "No Content", "body": ""},
                {"id": "1", "statusCode": 404, "statusText": "Not Found", "body": "{}"},
            ]
        )
        params = BulkDeleteIncidentsParams(incident_ids=[_SYS_ID_A, _SYS_ID_B])
        result = bulk_delete_incidents(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 1)


class TestBulkDeleteIncidentsNumberResolution(unittest.TestCase):
    """Tests for the INC-number → sys_id resolution path."""

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_incident_number_resolved_to_sys_id(self, mock_get, mock_post):
        mock_get.return_value = _get_response([{"number": "INC0010001", "sys_id": _SYS_ID_A}])
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 204, "statusText": "No Content", "body": ""}]
        )
        params = BulkDeleteIncidentsParams(incident_ids=["INC0010001"])
        result = bulk_delete_incidents(_config(), _auth(), params)

        self.assertTrue(result["success"])
        self.assertEqual(result["results"][0]["incident_id"], "INC0010001")

        payload = mock_post.call_args[1]["json"]
        self.assertIn(_SYS_ID_A, payload["requests"][0]["url"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_unresolved_number_returns_failure(self, mock_get):
        mock_get.return_value = _get_response([])
        params = BulkDeleteIncidentsParams(incident_ids=["INC9999999"])
        result = bulk_delete_incidents(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("INC9999999", result["message"])
        self.assertIn("INC9999999", result["unresolved"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_resolution_http_error_propagated(self, mock_get):
        mock_get.side_effect = requests.RequestException("connection error")
        params = BulkDeleteIncidentsParams(incident_ids=["INC0010001"])
        result = bulk_delete_incidents(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("Failed to resolve incident numbers", result["message"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_mixed_sys_ids_and_numbers(self, mock_get, mock_post):
        mock_get.return_value = _get_response([{"number": "INC0010001", "sys_id": _SYS_ID_A}])
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 204, "statusText": "No Content", "body": ""},
                {"id": "1", "statusCode": 204, "statusText": "No Content", "body": ""},
            ]
        )
        params = BulkDeleteIncidentsParams(incident_ids=["INC0010001", _SYS_ID_B])
        result = bulk_delete_incidents(_config(), _auth(), params)

        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 2)
        ids = [r["incident_id"] for r in result["results"]]
        self.assertIn("INC0010001", ids)
        self.assertIn(_SYS_ID_B, ids)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_batch_post_failure_returns_failure(self, mock_post):
        mock_post.side_effect = requests.RequestException("timeout")
        params = BulkDeleteIncidentsParams(incident_ids=[_SYS_ID_A])
        result = bulk_delete_incidents(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("failed", result["message"].lower())


if __name__ == "__main__":
    unittest.main()
