"""Tests for bulk_update_incidents in bulk_tools.py."""

import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.bulk_tools import (
    BulkUpdateIncidentsParams,
    IncidentUpdate,
    _is_sys_id,
    bulk_update_incidents,
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


class TestIsSysId(unittest.TestCase):
    def test_32_hex_chars_is_sys_id(self):
        self.assertTrue(_is_sys_id("a" * 32))
        self.assertTrue(_is_sys_id("0123456789abcdef" * 2))
        self.assertTrue(_is_sys_id("ABCDEF0123456789" * 2))

    def test_incident_number_is_not_sys_id(self):
        self.assertFalse(_is_sys_id("INC0010001"))

    def test_31_chars_not_sys_id(self):
        self.assertFalse(_is_sys_id("a" * 31))

    def test_33_chars_not_sys_id(self):
        self.assertFalse(_is_sys_id("a" * 33))

    def test_non_hex_chars_not_sys_id(self):
        self.assertFalse(_is_sys_id("g" * 32))


class TestBulkUpdateIncidentsValidation(unittest.TestCase):
    def test_empty_updates_returns_failure(self):
        params = BulkUpdateIncidentsParams.__new__(BulkUpdateIncidentsParams)
        object.__setattr__(params, "updates", [])
        result = bulk_update_incidents(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("No updates provided", result["message"])

    def test_over_100_updates_returns_failure(self):
        params = BulkUpdateIncidentsParams.__new__(BulkUpdateIncidentsParams)
        too_many = [
            IncidentUpdate(incident_id=_SYS_ID_A, short_description=f"Update {i}")
            for i in range(101)
        ]
        object.__setattr__(params, "updates", too_many)
        result = bulk_update_incidents(_config(), _auth(), params)
        self.assertFalse(result["success"])
        self.assertIn("Too many updates", result["message"])
        self.assertIn("101", result["message"])

    def test_exactly_100_updates_is_accepted(self):
        """100 updates should not trigger the size-limit guard."""
        params = BulkUpdateIncidentsParams.__new__(BulkUpdateIncidentsParams)
        updates = [
            IncidentUpdate(incident_id=("0" * 31 + str(i % 10)), short_description=f"u{i}")
            for i in range(100)
        ]
        # All fake sys_ids so no resolution GET is needed; patch batch call
        object.__setattr__(params, "updates", updates)
        with patch("servicenow_mcp.tools.bulk_tools.requests.post") as mock_post:
            mock_post.return_value = _batch_response(
                [
                    {"id": str(i), "statusCode": 200, "statusText": "OK", "body": "{}"}
                    for i in range(100)
                ]
            )
            result = bulk_update_incidents(_config(), _auth(), params)
        self.assertNotIn("Too many updates", result.get("message", ""))


class TestBulkUpdateIncidentsAllSysIds(unittest.TestCase):
    """When all incident_ids are already sys_ids, no resolution GET is issued."""

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_single_sys_id_update_success(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateIncidentsParams(
            updates=[IncidentUpdate(incident_id=_SYS_ID_A, state="2")]
        )
        result = bulk_update_incidents(_config(), _auth(), params)

        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 0)
        # incident_id enriched in results
        self.assertEqual(result["results"][0]["incident_id"], _SYS_ID_A)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_multiple_sys_ids_patch_url_contains_sys_id(self, mock_post):
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 200, "statusText": "OK", "body": "{}"},
            ]
        )
        params = BulkUpdateIncidentsParams(
            updates=[
                IncidentUpdate(incident_id=_SYS_ID_A, priority="1"),
                IncidentUpdate(incident_id=_SYS_ID_B, state="6"),
            ]
        )
        bulk_update_incidents(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        urls = [r["url"] for r in payload["requests"]]
        self.assertIn(f"/api/now/v2/table/incident/{_SYS_ID_A}", urls)
        self.assertIn(f"/api/now/v2/table/incident/{_SYS_ID_B}", urls)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_patch_method_used_in_batch(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateIncidentsParams(
            updates=[IncidentUpdate(incident_id=_SYS_ID_A, work_notes="test")]
        )
        bulk_update_incidents(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["requests"][0]["method"], "PATCH")

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_only_provided_fields_in_body(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateIncidentsParams(
            updates=[IncidentUpdate(incident_id=_SYS_ID_A, state="6", close_notes="done")]
        )
        bulk_update_incidents(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        body = json.loads(payload["requests"][0]["body"])
        self.assertEqual(body, {"state": "6", "close_notes": "done"})
        self.assertNotIn("priority", body)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_all_updatable_fields_passed_through(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateIncidentsParams(
            updates=[
                IncidentUpdate(
                    incident_id=_SYS_ID_A,
                    short_description="sd",
                    description="desc",
                    state="2",
                    category="software",
                    subcategory="email",
                    priority="2",
                    impact="2",
                    urgency="2",
                    assigned_to="john",
                    assignment_group="helpdesk",
                    work_notes="wn",
                    close_notes="cn",
                    close_code="solved",
                )
            ]
        )
        bulk_update_incidents(_config(), _auth(), params)

        payload = mock_post.call_args[1]["json"]
        body = json.loads(payload["requests"][0]["body"])
        for field in (
            "short_description", "description", "state", "category", "subcategory",
            "priority", "impact", "urgency", "assigned_to", "assignment_group",
            "work_notes", "close_notes", "close_code",
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
        params = BulkUpdateIncidentsParams(
            updates=[
                IncidentUpdate(incident_id=_SYS_ID_A, state="2"),
                IncidentUpdate(incident_id=_SYS_ID_B, state="6"),
            ]
        )
        result = bulk_update_incidents(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 1)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_batch_request_exception_returns_failure(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("refused")
        params = BulkUpdateIncidentsParams(
            updates=[IncidentUpdate(incident_id=_SYS_ID_A, state="2")]
        )
        result = bulk_update_incidents(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("Batch request failed", result["message"])


class TestBulkUpdateIncidentsNumberResolution(unittest.TestCase):
    """Tests covering the number → sys_id resolution path."""

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_incident_number_resolved_before_batch(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "INC0010001", "sys_id": _SYS_ID_A}]
        )
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateIncidentsParams(
            updates=[IncidentUpdate(incident_id="INC0010001", state="2")]
        )
        result = bulk_update_incidents(_config(), _auth(), params)

        self.assertTrue(result["success"])
        # GET must have been called to resolve the number
        mock_get.assert_called_once()
        # The PATCH URL in the batch should contain the resolved sys_id
        payload = mock_post.call_args[1]["json"]
        self.assertIn(_SYS_ID_A, payload["requests"][0]["url"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_resolution_query_uses_numberIN_operator(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [
                {"number": "INC0010001", "sys_id": _SYS_ID_A},
                {"number": "INC0010002", "sys_id": _SYS_ID_B},
            ]
        )
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 200, "statusText": "OK", "body": "{}"},
            ]
        )
        params = BulkUpdateIncidentsParams(
            updates=[
                IncidentUpdate(incident_id="INC0010001", state="2"),
                IncidentUpdate(incident_id="INC0010002", priority="3"),
            ]
        )
        bulk_update_incidents(_config(), _auth(), params)

        get_kwargs = mock_get.call_args[1]
        query = get_kwargs["params"]["sysparm_query"]
        self.assertTrue(query.startswith("numberIN"))
        self.assertIn("INC0010001", query)
        self.assertIn("INC0010002", query)

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_single_get_issued_for_all_numbers(self, mock_get, mock_post):
        """Even with 3 numbers, only one GET should be issued."""
        ids = [f"aa{str(i).zfill(30)}" for i in range(3)]
        mock_get.return_value = _get_response(
            [{"number": f"INC000{i}", "sys_id": ids[i]} for i in range(3)]
        )
        mock_post.return_value = _batch_response(
            [
                {"id": str(i), "statusCode": 200, "statusText": "OK", "body": "{}"}
                for i in range(3)
            ]
        )
        params = BulkUpdateIncidentsParams(
            updates=[
                IncidentUpdate(incident_id=f"INC000{i}", state="2") for i in range(3)
            ]
        )
        bulk_update_incidents(_config(), _auth(), params)
        self.assertEqual(mock_get.call_count, 1)

    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_unresolved_number_returns_failure(self, mock_get):
        mock_get.return_value = _get_response([])  # no results → number not found
        params = BulkUpdateIncidentsParams(
            updates=[IncidentUpdate(incident_id="INC0099999", state="2")]
        )
        result = bulk_update_incidents(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("INC0099999", result["message"])
        self.assertIn("INC0099999", result.get("unresolved", []))

    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_resolution_network_error_returns_failure(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("network down")
        params = BulkUpdateIncidentsParams(
            updates=[IncidentUpdate(incident_id="INC0010001", state="2")]
        )
        result = bulk_update_incidents(_config(), _auth(), params)

        self.assertFalse(result["success"])
        self.assertIn("resolve incident numbers", result["message"])

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_mixed_sys_ids_and_numbers(self, mock_get, mock_post):
        """If some are sys_ids and some are numbers, only one GET for numbers."""
        mock_get.return_value = _get_response(
            [{"number": "INC0010001", "sys_id": _SYS_ID_B}]
        )
        mock_post.return_value = _batch_response(
            [
                {"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"},
                {"id": "1", "statusCode": 200, "statusText": "OK", "body": "{}"},
            ]
        )
        params = BulkUpdateIncidentsParams(
            updates=[
                IncidentUpdate(incident_id=_SYS_ID_A, state="2"),
                IncidentUpdate(incident_id="INC0010001", priority="3"),
            ]
        )
        result = bulk_update_incidents(_config(), _auth(), params)

        self.assertTrue(result["success"])
        mock_get.assert_called_once()  # only one GET for the number
        mock_post.assert_called_once()  # one batch PATCH for both

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    def test_no_get_issued_when_all_sys_ids(self, mock_post):
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateIncidentsParams(
            updates=[IncidentUpdate(incident_id=_SYS_ID_A, state="2")]
        )
        with patch("servicenow_mcp.tools.bulk_tools.requests.get") as mock_get:
            bulk_update_incidents(_config(), _auth(), params)
            mock_get.assert_not_called()

    @patch("servicenow_mcp.tools.bulk_tools.requests.post")
    @patch("servicenow_mcp.tools.bulk_tools.requests.get")
    def test_result_entries_carry_incident_id(self, mock_get, mock_post):
        mock_get.return_value = _get_response(
            [{"number": "INC0010001", "sys_id": _SYS_ID_A}]
        )
        mock_post.return_value = _batch_response(
            [{"id": "0", "statusCode": 200, "statusText": "OK", "body": "{}"}]
        )
        params = BulkUpdateIncidentsParams(
            updates=[IncidentUpdate(incident_id="INC0010001", state="2")]
        )
        result = bulk_update_incidents(_config(), _auth(), params)

        self.assertEqual(result["results"][0]["incident_id"], "INC0010001")


if __name__ == "__main__":
    unittest.main()
