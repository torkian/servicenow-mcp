"""Tests for request_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.request_tools import (
    _format_request,
    _resolve_request_sys_id,
    close_request,
    create_request,
    delete_request_item,
    get_request,
    list_requests,
    update_request,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "b" * 32
FAKE_NUMBER = "REQ0010001"

FAKE_REQUEST = {
    "sys_id": FAKE_SYS_ID,
    "number": FAKE_NUMBER,
    "short_description": "New laptop request",
    "description": "I need a MacBook Pro for development work",
    "state": "2",
    "stage": "submitted",
    "priority": "3",
    "urgency": "2",
    "impact": "3",
    "requested_for": {"display_value": "Jane Smith"},
    "opened_by": {"display_value": "Jane Smith"},
    "assigned_to": {"display_value": "IT Fulfillment"},
    "assignment_group": {"display_value": "IT Hardware"},
    "approval": "approved",
    "due_date": "2026-06-01",
    "opened_at": "2026-05-21 10:00:00",
    "closed_at": "",
    "sys_created_on": "2026-05-21 10:00:00",
    "sys_updated_on": "2026-05-21 10:30:00",
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


# ---------------------------------------------------------------------------
# _format_request
# ---------------------------------------------------------------------------

class TestFormatRequest(unittest.TestCase):
    def test_all_fields_mapped(self):
        result = _format_request(FAKE_REQUEST)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["number"], FAKE_NUMBER)
        self.assertEqual(result["short_description"], "New laptop request")
        self.assertEqual(result["state"], "2")
        self.assertEqual(result["stage"], "submitted")
        self.assertEqual(result["approval"], "approved")
        self.assertEqual(result["due_date"], "2026-06-01")

    def test_reference_fields_extracted(self):
        result = _format_request(FAKE_REQUEST)
        self.assertEqual(result["requested_for"], "Jane Smith")
        self.assertEqual(result["opened_by"], "Jane Smith")
        self.assertEqual(result["assigned_to"], "IT Fulfillment")
        self.assertEqual(result["assignment_group"], "IT Hardware")

    def test_plain_string_reference_fields(self):
        rec = dict(FAKE_REQUEST)
        rec["requested_for"] = "jsmith"
        rec["assigned_to"] = "bob"
        rec["assignment_group"] = "helpdesk"
        rec["opened_by"] = "jsmith"
        result = _format_request(rec)
        self.assertEqual(result["requested_for"], "jsmith")
        self.assertEqual(result["assigned_to"], "bob")
        self.assertEqual(result["assignment_group"], "helpdesk")

    def test_missing_optional_fields_are_none(self):
        result = _format_request({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["number"])
        self.assertIsNone(result["requested_for"])


# ---------------------------------------------------------------------------
# _resolve_request_sys_id
# ---------------------------------------------------------------------------

class TestResolveRequestSysId(unittest.TestCase):
    def test_passes_through_sys_id(self):
        result = _resolve_request_sys_id(FAKE_SYS_ID, "https://example.com", {})
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_resolves_number(self, mock_req):
        mock_req.return_value = _make_response(
            json_body={"result": [{"sys_id": FAKE_SYS_ID}]}
        )
        result = _resolve_request_sys_id(FAKE_NUMBER, "https://example.com", {})
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        result = _resolve_request_sys_id(FAKE_NUMBER, "https://example.com", {})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_network_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = _resolve_request_sys_id(FAKE_NUMBER, "https://example.com", {})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# list_requests
# ---------------------------------------------------------------------------

class TestListRequests(unittest.TestCase):
    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_basic_list(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": [FAKE_REQUEST]})
        result = list_requests(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["requests"]), 1)
        self.assertEqual(result["requests"][0]["number"], FAKE_NUMBER)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_all_filters_applied(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        result = list_requests(
            _make_auth_manager(),
            _make_config(),
            {
                "state": "2",
                "requested_for": "jsmith",
                "assigned_to": "bob",
                "assignment_group": "IT Hardware",
                "approval": "approved",
                "query": "laptop",
                "limit": 5,
                "offset": 10,
            },
        )
        self.assertTrue(result["success"])
        called_params = mock_req.call_args[1]["params"]
        self.assertIn("state=2", called_params.get("sysparm_query", ""))
        self.assertIn("requested_for=jsmith", called_params.get("sysparm_query", ""))
        self.assertIn("approval=approved", called_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_pagination_metadata(self, mock_req):
        items = [FAKE_REQUEST] * 5
        mock_req.return_value = _make_response(json_body={"result": items})
        result = list_requests(
            _make_auth_manager(), _make_config(), {"limit": 5, "offset": 0}
        )
        self.assertIn("has_more", result)
        self.assertIn("next_offset", result)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.HTTPError("500")
        result = list_requests(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing requests", result["message"])


# ---------------------------------------------------------------------------
# get_request
# ---------------------------------------------------------------------------

class TestGetRequest(unittest.TestCase):
    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_get_by_sys_id(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_REQUEST})
        result = get_request(
            _make_auth_manager(), _make_config(), {"request_id": FAKE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["request"]["number"], FAKE_NUMBER)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_get_by_number(self, mock_req):
        mock_req.return_value = _make_response(
            json_body={"result": [FAKE_REQUEST]}
        )
        result = get_request(
            _make_auth_manager(), _make_config(), {"request_id": FAKE_NUMBER}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["request"]["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_get_by_number_not_found(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        result = get_request(
            _make_auth_manager(), _make_config(), {"request_id": FAKE_NUMBER}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_get_by_sys_id_404(self, mock_req):
        resp = _make_response(status_code=404, json_body={})
        mock_req.return_value = resp
        result = get_request(
            _make_auth_manager(), _make_config(), {"request_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_get_by_sys_id_empty_result(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": {}})
        result = get_request(
            _make_auth_manager(), _make_config(), {"request_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])

    def test_missing_request_id_returns_failure(self):
        result = get_request(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.HTTPError("500")
        result = get_request(
            _make_auth_manager(), _make_config(), {"request_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# create_request
# ---------------------------------------------------------------------------

class TestCreateRequest(unittest.TestCase):
    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_minimal_create(self, mock_req):
        mock_req.return_value = _make_response(
            json_body={"result": FAKE_REQUEST}
        )
        result = create_request(
            _make_auth_manager(),
            _make_config(),
            {"short_description": "New laptop request"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["number"], FAKE_NUMBER)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_all_optional_fields_sent(self, mock_req):
        mock_req.return_value = _make_response(
            json_body={"result": FAKE_REQUEST}
        )
        result = create_request(
            _make_auth_manager(),
            _make_config(),
            {
                "short_description": "New laptop",
                "description": "MacBook Pro M3",
                "requested_for": "jsmith",
                "assignment_group": "IT Hardware",
                "assigned_to": "bob",
                "priority": "3",
                "urgency": "2",
                "impact": "3",
                "due_date": "2026-06-01",
                "comments": "Urgent",
            },
        )
        self.assertTrue(result["success"])
        body_sent = mock_req.call_args[1]["json"]
        self.assertEqual(body_sent["short_description"], "New laptop")
        self.assertEqual(body_sent["requested_for"], "jsmith")
        self.assertEqual(body_sent["due_date"], "2026-06-01")
        self.assertEqual(body_sent["comments"], "Urgent")

    def test_missing_short_description_returns_failure(self):
        result = create_request(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.HTTPError("500")
        result = create_request(
            _make_auth_manager(),
            _make_config(),
            {"short_description": "Laptop"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error creating request", result["message"])


# ---------------------------------------------------------------------------
# update_request
# ---------------------------------------------------------------------------

class TestUpdateRequest(unittest.TestCase):
    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_update_by_sys_id(self, mock_req):
        mock_req.return_value = _make_response(
            json_body={"result": FAKE_REQUEST}
        )
        result = update_request(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID, "state": "3"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_update_by_number(self, mock_req):
        mock_req.side_effect = [
            _make_response(json_body={"result": [{"sys_id": FAKE_SYS_ID}]}),
            _make_response(json_body={"result": FAKE_REQUEST}),
        ]
        result = update_request(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_NUMBER, "state": "4"},
        )
        self.assertTrue(result["success"])

    def test_missing_request_id_returns_failure(self):
        result = update_request(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_empty_body_returns_failure(self, mock_req):
        result = update_request(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("No fields provided", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_all_fields_sent(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_REQUEST})
        result = update_request(
            _make_auth_manager(),
            _make_config(),
            {
                "request_id": FAKE_SYS_ID,
                "short_description": "Updated description",
                "description": "More details",
                "state": "3",
                "assigned_to": "newuser",
                "assignment_group": "New Group",
                "priority": "2",
                "urgency": "1",
                "impact": "1",
                "due_date": "2026-07-01",
                "work_notes": "Working on it",
                "comments": "Update for requester",
                "close_notes": "Resolved",
            },
        )
        self.assertTrue(result["success"])
        body_sent = mock_req.call_args[1]["json"]
        self.assertEqual(body_sent["state"], "3")
        self.assertEqual(body_sent["assigned_to"], "newuser")
        self.assertEqual(body_sent["close_notes"], "Resolved")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_http_error_on_update_returns_failure(self, mock_req):
        mock_req.side_effect = [
            _make_response(json_body={"result": [{"sys_id": FAKE_SYS_ID}]}),
            requests.exceptions.HTTPError("500"),
        ]
        result = update_request(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_NUMBER, "state": "3"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating request", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_request_not_found_on_update(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        result = update_request(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_NUMBER, "state": "3"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])


# ---------------------------------------------------------------------------
# close_request
# ---------------------------------------------------------------------------

class TestCloseRequest(unittest.TestCase):
    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_success_by_sys_id(self, mock_req):
        closed = dict(FAKE_REQUEST, state="4", closed_at="2026-07-21 10:00:00")
        mock_req.return_value = _make_response(200, {"result": closed})
        result = close_request(_make_auth_manager(), _make_config(), {"request_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertIn("closed", result["message"].lower())
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["request"]["state"], "4")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_success_by_number(self, mock_req):
        closed = dict(FAKE_REQUEST, state="4")
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]}),
            _make_response(200, {"result": closed}),
        ]
        result = close_request(_make_auth_manager(), _make_config(), {"request_id": FAKE_NUMBER})
        self.assertTrue(result["success"])
        self.assertEqual(result["number"], FAKE_NUMBER)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_state_4_sent_in_body(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_REQUEST})
        close_request(_make_auth_manager(), _make_config(), {"request_id": FAKE_SYS_ID})
        patch_call = mock_req.call_args_list[-1]
        body = patch_call[1].get("json", {})
        self.assertEqual(body.get("state"), "4")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_close_notes_included_when_provided(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_REQUEST})
        close_request(
            _make_auth_manager(), _make_config(),
            {"request_id": FAKE_SYS_ID, "close_notes": "Request fulfilled"},
        )
        patch_call = mock_req.call_args_list[-1]
        body = patch_call[1].get("json", {})
        self.assertEqual(body.get("close_notes"), "Request fulfilled")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_work_notes_included_when_provided(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_REQUEST})
        close_request(
            _make_auth_manager(), _make_config(),
            {"request_id": FAKE_SYS_ID, "work_notes": "All items delivered"},
        )
        patch_call = mock_req.call_args_list[-1]
        body = patch_call[1].get("json", {})
        self.assertEqual(body.get("work_notes"), "All items delivered")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_optional_fields_omitted_when_not_provided(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_REQUEST})
        close_request(_make_auth_manager(), _make_config(), {"request_id": FAKE_SYS_ID})
        patch_call = mock_req.call_args_list[-1]
        body = patch_call[1].get("json", {})
        self.assertNotIn("close_notes", body)
        self.assertNotIn("work_notes", body)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_404_returns_not_found(self, mock_req):
        response_404 = _make_response(404, {})
        response_404.raise_for_status = MagicMock()
        mock_req.return_value = response_404
        result = close_request(_make_auth_manager(), _make_config(), {"request_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_request_not_found_by_number(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = close_request(_make_auth_manager(), _make_config(), {"request_id": FAKE_NUMBER})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_missing_request_id_returns_error(self):
        result = close_request(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_network_error_handled(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("unreachable")
        result = close_request(_make_auth_manager(), _make_config(), {"request_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error closing request", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_sys_id_fallback_in_response(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = close_request(_make_auth_manager(), _make_config(), {"request_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_both_close_and_work_notes(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_REQUEST})
        close_request(
            _make_auth_manager(), _make_config(),
            {
                "request_id": FAKE_SYS_ID,
                "close_notes": "Completed",
                "work_notes": "Verified all items",
            },
        )
        patch_call = mock_req.call_args_list[-1]
        body = patch_call[1].get("json", {})
        self.assertEqual(body.get("state"), "4")
        self.assertEqual(body.get("close_notes"), "Completed")
        self.assertEqual(body.get("work_notes"), "Verified all items")


# ---------------------------------------------------------------------------
# delete_request_item
# ---------------------------------------------------------------------------

FAKE_RITM_SYS_ID = "c" * 32
FAKE_RITM_NUMBER = "RITM0010001"


class TestDeleteRequestItem(unittest.TestCase):
    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_delete_by_sys_id_204(self, mock_req):
        mock_req.return_value = _make_response(status_code=204)
        result = delete_request_item(
            _make_auth_manager(), _make_config(), {"item_id": FAKE_RITM_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertIn("deleted", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_delete_by_sys_id_200(self, mock_req):
        mock_req.return_value = _make_response(status_code=200)
        result = delete_request_item(
            _make_auth_manager(), _make_config(), {"item_id": FAKE_RITM_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertIn("deleted", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_delete_by_ritm_number_resolves_and_deletes(self, mock_req):
        mock_req.side_effect = [
            _make_response(json_body={"result": [{"sys_id": FAKE_RITM_SYS_ID}]}),
            _make_response(status_code=204),
        ]
        result = delete_request_item(
            _make_auth_manager(), _make_config(), {"item_id": FAKE_RITM_NUMBER}
        )
        self.assertTrue(result["success"])
        self.assertIn("deleted", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_delete_404_returns_not_found(self, mock_req):
        not_found = _make_response(status_code=404)
        not_found.raise_for_status = MagicMock()
        mock_req.return_value = not_found
        result = delete_request_item(
            _make_auth_manager(), _make_config(), {"item_id": FAKE_RITM_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_ritm_number_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        result = delete_request_item(
            _make_auth_manager(), _make_config(), {"item_id": FAKE_RITM_NUMBER}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_missing_item_id_returns_failure(self):
        result = delete_request_item(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_network_error_during_delete_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("unreachable")
        result = delete_request_item(
            _make_auth_manager(), _make_config(), {"item_id": FAKE_RITM_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error deleting request item", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_network_error_during_resolve_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = delete_request_item(
            _make_auth_manager(), _make_config(), {"item_id": FAKE_RITM_NUMBER}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_correct_delete_url_called(self, mock_req):
        mock_req.return_value = _make_response(status_code=204)
        delete_request_item(
            _make_auth_manager(), _make_config(), {"item_id": FAKE_RITM_SYS_ID}
        )
        call_url = mock_req.call_args[0][1]
        self.assertIn(FAKE_RITM_SYS_ID, call_url)
        self.assertIn("sc_req_item", call_url)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_message_includes_item_id(self, mock_req):
        mock_req.return_value = _make_response(status_code=204)
        result = delete_request_item(
            _make_auth_manager(), _make_config(), {"item_id": FAKE_RITM_SYS_ID}
        )
        self.assertIn(FAKE_RITM_SYS_ID, result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_delete_uses_delete_http_method(self, mock_req):
        mock_req.return_value = _make_response(status_code=204)
        delete_request_item(
            _make_auth_manager(), _make_config(), {"item_id": FAKE_RITM_SYS_ID}
        )
        call_method = mock_req.call_args[0][0]
        self.assertEqual(call_method, "DELETE")


if __name__ == "__main__":
    unittest.main()
