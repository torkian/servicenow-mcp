"""Tests for the update_request_item tool in request_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.request_tools import (
    _resolve_request_item_sys_id,
    update_request_item,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_RITM_SYS_ID = "c" * 32
FAKE_RITM_NUMBER = "RITM0010001"

FAKE_ITEM_RECORD = {
    "sys_id": FAKE_RITM_SYS_ID,
    "number": FAKE_RITM_NUMBER,
    "short_description": "Laptop - MacBook Pro 16",
    "description": "Development workstation",
    "state": "17",
    "stage": "fulfillment",
    "cat_item": {"display_value": "MacBook Pro 16-inch"},
    "quantity": "1",
    "price": "2499.00",
    "request": {"display_value": "REQ0010001"},
    "assigned_to": {"display_value": "IT Fulfillment"},
    "assignment_group": {"display_value": "IT Hardware"},
    "opened_by": {"display_value": "Jane Smith"},
    "sys_created_on": "2026-05-21 10:00:00",
    "sys_updated_on": "2026-06-29 08:00:00",
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
# _resolve_request_item_sys_id
# ---------------------------------------------------------------------------

class TestResolveRequestItemSysId(unittest.TestCase):

    def test_32_char_hex_passes_through(self):
        result = _resolve_request_item_sys_id(FAKE_RITM_SYS_ID, "https://x.service-now.com", {})
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_RITM_SYS_ID)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_ritm_number_resolved_via_query(self, mock_req):
        mock_req.return_value = _make_response(
            json_body={"result": [{"sys_id": FAKE_RITM_SYS_ID}]}
        )
        result = _resolve_request_item_sys_id(
            FAKE_RITM_NUMBER, "https://x.service-now.com", {"Authorization": "Bearer X"}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_RITM_SYS_ID)
        called_params = mock_req.call_args[1]["params"]
        self.assertIn(FAKE_RITM_NUMBER, called_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_ritm_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        result = _resolve_request_item_sys_id(
            "RITM9999999", "https://x.service-now.com", {}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_http_error_during_resolve_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = _resolve_request_item_sys_id(
            FAKE_RITM_NUMBER, "https://x.service-now.com", {}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error looking up request item", result["message"])


# ---------------------------------------------------------------------------
# update_request_item
# ---------------------------------------------------------------------------

class TestUpdateRequestItem(unittest.TestCase):

    def test_missing_item_id_returns_failure(self):
        result = update_request_item(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_no_fields_provided_returns_failure(self):
        result = update_request_item(
            _make_auth_manager(), _make_config(), {"item_id": FAKE_RITM_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("No fields provided", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_update_by_sys_id_success(self, mock_req):
        mock_req.return_value = _make_response(
            json_body={"result": FAKE_ITEM_RECORD}
        )
        result = update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "state": "17"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Request item updated successfully")
        self.assertEqual(result["sys_id"], FAKE_RITM_SYS_ID)
        self.assertEqual(result["number"], FAKE_RITM_NUMBER)
        self.assertIn("item", result)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_update_by_ritm_number_resolves_then_patches(self, mock_req):
        # First call: resolve RITM number; second call: PATCH
        mock_req.side_effect = [
            _make_response(json_body={"result": [{"sys_id": FAKE_RITM_SYS_ID}]}),
            _make_response(json_body={"result": FAKE_ITEM_RECORD}),
        ]
        result = update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_NUMBER, "state": "18"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(mock_req.call_count, 2)
        patch_call = mock_req.call_args_list[1]
        self.assertEqual(patch_call[0][0], "PATCH")
        self.assertIn(FAKE_RITM_SYS_ID, patch_call[0][1])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_patch_body_contains_state(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM_RECORD})
        update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "state": "4"},
        )
        sent_body = mock_req.call_args[1]["json"]
        self.assertEqual(sent_body["state"], "4")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_patch_body_contains_stage(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM_RECORD})
        update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "stage": "delivery"},
        )
        sent_body = mock_req.call_args[1]["json"]
        self.assertEqual(sent_body["stage"], "delivery")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_patch_body_contains_work_notes(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM_RECORD})
        update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "work_notes": "Item shipped to user"},
        )
        sent_body = mock_req.call_args[1]["json"]
        self.assertEqual(sent_body["work_notes"], "Item shipped to user")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_patch_body_contains_close_notes(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM_RECORD})
        update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "close_notes": "Delivered and confirmed"},
        )
        sent_body = mock_req.call_args[1]["json"]
        self.assertEqual(sent_body["close_notes"], "Delivered and confirmed")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_patch_body_contains_assigned_to(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM_RECORD})
        update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "assigned_to": "jsmith"},
        )
        sent_body = mock_req.call_args[1]["json"]
        self.assertEqual(sent_body["assigned_to"], "jsmith")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_patch_body_contains_assignment_group(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM_RECORD})
        update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "assignment_group": "IT Hardware"},
        )
        sent_body = mock_req.call_args[1]["json"]
        self.assertEqual(sent_body["assignment_group"], "IT Hardware")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_all_fields_in_body(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM_RECORD})
        update_request_item(
            _make_auth_manager(),
            _make_config(),
            {
                "item_id": FAKE_RITM_SYS_ID,
                "state": "18",
                "stage": "completed",
                "assigned_to": "jsmith",
                "assignment_group": "IT Hardware",
                "work_notes": "All done",
                "close_notes": "Fulfilled and closed",
            },
        )
        sent_body = mock_req.call_args[1]["json"]
        self.assertEqual(sent_body["state"], "18")
        self.assertEqual(sent_body["stage"], "completed")
        self.assertEqual(sent_body["assigned_to"], "jsmith")
        self.assertEqual(sent_body["assignment_group"], "IT Hardware")
        self.assertEqual(sent_body["work_notes"], "All done")
        self.assertEqual(sent_body["close_notes"], "Fulfilled and closed")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_404_response_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(status_code=404)
        result = update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "state": "4"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.HTTPError("503 Service Unavailable")
        result = update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "state": "4"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating request item", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "work_notes": "checking in"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating request item", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_ritm_number_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        result = update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": "RITM9999999", "state": "4"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_result_item_has_normalised_reference_fields(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM_RECORD})
        result = update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "state": "17"},
        )
        self.assertTrue(result["success"])
        item = result["item"]
        self.assertEqual(item["cat_item"], "MacBook Pro 16-inch")
        self.assertEqual(item["request"], "REQ0010001")
        self.assertEqual(item["assigned_to"], "IT Fulfillment")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_patch_uses_correct_url(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM_RECORD})
        update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "state": "4"},
        )
        called_url = mock_req.call_args[0][1]
        self.assertIn("sc_req_item", called_url)
        self.assertIn(FAKE_RITM_SYS_ID, called_url)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_none_optional_fields_excluded_from_body(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM_RECORD})
        update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "state": "17"},
        )
        sent_body = mock_req.call_args[1]["json"]
        self.assertNotIn("stage", sent_body)
        self.assertNotIn("assigned_to", sent_body)
        self.assertNotIn("assignment_group", sent_body)
        self.assertNotIn("work_notes", sent_body)
        self.assertNotIn("close_notes", sent_body)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_sys_id_falls_back_to_resolved_sys_id_when_result_empty(self, mock_req):
        empty_record = {}
        mock_req.return_value = _make_response(json_body={"result": empty_record})
        result = update_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID, "state": "4"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_RITM_SYS_ID)


if __name__ == "__main__":
    unittest.main()
