"""Tests for the get_request_item and list_request_items tools in request_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.request_tools import (
    _format_request_item,
    get_request_item,
    list_request_items,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
FAKE_REQ_NUMBER = "REQ0010042"
FAKE_RITM_SYS_ID = "c" * 32

FAKE_ITEM = {
    "sys_id": FAKE_RITM_SYS_ID,
    "number": "RITM0010001",
    "short_description": "Laptop - MacBook Pro 16",
    "description": "Development workstation",
    "state": "1",
    "stage": "Waiting for Approval",
    "cat_item": {"display_value": "MacBook Pro 16-inch"},
    "quantity": "1",
    "price": "2499.00",
    "request": {"display_value": FAKE_REQ_NUMBER},
    "assigned_to": {"display_value": "IT Fulfillment"},
    "assignment_group": {"display_value": "IT Hardware"},
    "opened_by": {"display_value": "Jane Smith"},
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
# _format_request_item
# ---------------------------------------------------------------------------

class TestFormatRequestItem(unittest.TestCase):
    def test_all_fields_mapped(self):
        result = _format_request_item(FAKE_ITEM)
        self.assertEqual(result["sys_id"], FAKE_RITM_SYS_ID)
        self.assertEqual(result["number"], "RITM0010001")
        self.assertEqual(result["short_description"], "Laptop - MacBook Pro 16")
        self.assertEqual(result["state"], "1")
        self.assertEqual(result["stage"], "Waiting for Approval")
        self.assertEqual(result["quantity"], "1")
        self.assertEqual(result["price"], "2499.00")

    def test_reference_fields_extracted(self):
        result = _format_request_item(FAKE_ITEM)
        self.assertEqual(result["cat_item"], "MacBook Pro 16-inch")
        self.assertEqual(result["request"], FAKE_REQ_NUMBER)
        self.assertEqual(result["assigned_to"], "IT Fulfillment")
        self.assertEqual(result["assignment_group"], "IT Hardware")
        self.assertEqual(result["opened_by"], "Jane Smith")

    def test_plain_string_reference_fields(self):
        rec = dict(FAKE_ITEM)
        rec["cat_item"] = "macbook_pro_16"
        rec["request"] = FAKE_REQ_NUMBER
        rec["assigned_to"] = "bob"
        rec["assignment_group"] = "helpdesk"
        rec["opened_by"] = "jsmith"
        result = _format_request_item(rec)
        self.assertEqual(result["cat_item"], "macbook_pro_16")
        self.assertEqual(result["request"], FAKE_REQ_NUMBER)
        self.assertEqual(result["assigned_to"], "bob")
        self.assertEqual(result["assignment_group"], "helpdesk")
        self.assertEqual(result["opened_by"], "jsmith")

    def test_missing_optional_fields_are_none(self):
        result = _format_request_item({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["number"])
        self.assertIsNone(result["cat_item"])
        self.assertIsNone(result["request"])
        self.assertIsNone(result["assigned_to"])

    def test_dates_mapped(self):
        result = _format_request_item(FAKE_ITEM)
        self.assertEqual(result["created_on"], "2026-05-21 10:00:00")
        self.assertEqual(result["updated_on"], "2026-05-21 10:30:00")


# ---------------------------------------------------------------------------
# get_request_item
# ---------------------------------------------------------------------------

class TestGetRequestItem(unittest.TestCase):

    def test_missing_item_id_returns_failure(self):
        result = get_request_item(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_get_by_sys_id_success(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM})
        result = get_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID},
        )
        self.assertTrue(result["success"])
        self.assertIn("item", result)
        self.assertEqual(result["item"]["number"], "RITM0010001")
        self.assertEqual(result["item"]["cat_item"], "MacBook Pro 16-inch")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_get_by_ritm_number_success(self, mock_req):
        mock_req.return_value = _make_response(
            json_body={"result": [FAKE_ITEM]}
        )
        result = get_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": "RITM0010001"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["item"]["sys_id"], FAKE_RITM_SYS_ID)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_get_by_sys_id_404_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(status_code=404)
        result = get_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_get_by_sys_id_empty_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": {}})
        result = get_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_get_by_number_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        result = get_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": "RITM9999999"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_get_by_sys_id_http_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.HTTPError("503 Service Unavailable")
        result = get_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving request item", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_get_by_number_http_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = get_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": "RITM0010001"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving request item", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_sys_id_lookup_uses_direct_url(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM})
        get_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID},
        )
        called_url = mock_req.call_args[0][1]
        self.assertIn(FAKE_RITM_SYS_ID, called_url)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_number_lookup_uses_query_param(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": [FAKE_ITEM]})
        get_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": "RITM0010001"},
        )
        called_params = mock_req.call_args[1]["params"]
        self.assertIn("RITM0010001", called_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_display_value_param_set(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM})
        get_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID},
        )
        called_params = mock_req.call_args[1]["params"]
        self.assertEqual(called_params.get("sysparm_display_value"), "true")
        self.assertEqual(called_params.get("sysparm_exclude_reference_link"), "true")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_reference_fields_normalised(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM})
        result = get_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID},
        )
        self.assertEqual(result["item"]["assigned_to"], "IT Fulfillment")
        self.assertEqual(result["item"]["assignment_group"], "IT Hardware")
        self.assertEqual(result["item"]["opened_by"], "Jane Smith")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_dates_present_in_result(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": FAKE_ITEM})
        result = get_request_item(
            _make_auth_manager(),
            _make_config(),
            {"item_id": FAKE_RITM_SYS_ID},
        )
        self.assertEqual(result["item"]["created_on"], "2026-05-21 10:00:00")
        self.assertEqual(result["item"]["updated_on"], "2026-05-21 10:30:00")


# ---------------------------------------------------------------------------
# list_request_items
# ---------------------------------------------------------------------------

class TestListRequestItems(unittest.TestCase):

    def test_missing_request_id_returns_failure(self):
        result = list_request_items(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_basic_list_by_sys_id(self, mock_req):
        # The sys_id passthrough means only one HTTP call: the list itself
        mock_req.return_value = _make_response(
            json_body={"result": [FAKE_ITEM]}
        )
        result = list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID},
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["number"], "RITM0010001")
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_basic_list_by_number(self, mock_req):
        # First call: resolve REQ number → sys_id; second call: list items
        mock_req.side_effect = [
            _make_response(json_body={"result": [{"sys_id": FAKE_SYS_ID}]}),
            _make_response(json_body={"result": [FAKE_ITEM]}),
        ]
        result = list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_REQ_NUMBER},
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["cat_item"], "MacBook Pro 16-inch")

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_request_not_found_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        result = list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_REQ_NUMBER},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_state_filter_included_in_query(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        result = list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID, "state": "1"},
        )
        self.assertTrue(result["success"])
        called_params = mock_req.call_args[1]["params"]
        self.assertIn("state=1", called_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_request_sys_id_in_query(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        result = list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID},
        )
        self.assertTrue(result["success"])
        called_params = mock_req.call_args[1]["params"]
        self.assertIn(f"request={FAKE_SYS_ID}", called_params.get("sysparm_query", ""))

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_pagination_metadata(self, mock_req):
        items = [FAKE_ITEM] * 5
        mock_req.return_value = _make_response(json_body={"result": items})
        result = list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID, "limit": 5, "offset": 0},
        )
        self.assertIn("has_more", result)
        self.assertIn("next_offset", result)
        self.assertEqual(result["next_offset"], 5)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_no_more_pages_when_fewer_than_limit(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": [FAKE_ITEM]})
        result = list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID, "limit": 20, "offset": 0},
        )
        self.assertFalse(result["has_more"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_empty_result_returns_success(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        result = list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["items"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        # First call resolves (passthrough sys_id, no HTTP call), second call fails
        mock_req.side_effect = requests.exceptions.HTTPError("503 Service Unavailable")
        result = list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error listing request items", result["message"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_connection_error_during_list_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_offset_and_limit_forwarded(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID, "limit": 10, "offset": 20},
        )
        called_params = mock_req.call_args[1]["params"]
        self.assertEqual(called_params.get("sysparm_limit"), 10)
        self.assertEqual(called_params.get("sysparm_offset"), 20)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_fields_restricted_to_known_fields(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID},
        )
        called_params = mock_req.call_args[1]["params"]
        # sysparm_fields should be present and include key fields
        fields_param = called_params.get("sysparm_fields", "")
        self.assertIn("sys_id", fields_param)
        self.assertIn("number", fields_param)
        self.assertIn("cat_item", fields_param)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_multiple_items_returned(self, mock_req):
        item2 = dict(FAKE_ITEM)
        item2["sys_id"] = "d" * 32
        item2["number"] = "RITM0010002"
        item2["short_description"] = "Monitor 4K"
        mock_req.return_value = _make_response(json_body={"result": [FAKE_ITEM, item2]})
        result = list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        numbers = [i["number"] for i in result["items"]]
        self.assertIn("RITM0010001", numbers)
        self.assertIn("RITM0010002", numbers)

    @patch("servicenow_mcp.tools.request_tools._make_request")
    def test_reference_link_excluded(self, mock_req):
        mock_req.return_value = _make_response(json_body={"result": []})
        list_request_items(
            _make_auth_manager(),
            _make_config(),
            {"request_id": FAKE_SYS_ID},
        )
        called_params = mock_req.call_args[1]["params"]
        self.assertEqual(called_params.get("sysparm_exclude_reference_link"), "true")


if __name__ == "__main__":
    unittest.main()
