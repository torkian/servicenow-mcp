"""Tests for the delete_catalog_item tool."""

import unittest
from unittest.mock import MagicMock, patch

import requests
from pydantic import ValidationError

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.catalog_tools import DeleteCatalogItemParams, delete_catalog_item
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
FAKE_NAME = "New Employee Laptop"


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev99999.service-now.com", auth=auth_config)


def _make_auth():
    auth = MagicMock(spec=AuthManager)
    auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    return auth


def _make_response(status_code, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


class TestDeleteCatalogItemBySysId(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_delete_by_sys_id_204(self, mock_req):
        mock_req.return_value = _make_response(204)
        params = DeleteCatalogItemParams(item_id=FAKE_SYS_ID)
        result = delete_catalog_item(self.config, self.auth, params)

        self.assertTrue(result.success)
        self.assertIn("deleted successfully", result.message)
        self.assertEqual(result.data["sys_id"], FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_delete_by_sys_id_200(self, mock_req):
        mock_req.return_value = _make_response(200)
        params = DeleteCatalogItemParams(item_id=FAKE_SYS_ID)
        result = delete_catalog_item(self.config, self.auth, params)

        self.assertTrue(result.success)
        self.assertIn("deleted successfully", result.message)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_delete_by_sys_id_404(self, mock_req):
        mock_req.return_value = _make_response(404)
        params = DeleteCatalogItemParams(item_id=FAKE_SYS_ID)
        result = delete_catalog_item(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("not found", result.message.lower())

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_delete_by_sys_id_issues_single_request(self, mock_req):
        mock_req.return_value = _make_response(204)
        params = DeleteCatalogItemParams(item_id=FAKE_SYS_ID)
        delete_catalog_item(self.config, self.auth, params)

        self.assertEqual(mock_req.call_count, 1)
        call_args = mock_req.call_args
        self.assertEqual(call_args[0][0], "DELETE")
        self.assertIn(FAKE_SYS_ID, call_args[0][1])

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_delete_by_sys_id_network_error(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("connection refused")
        params = DeleteCatalogItemParams(item_id=FAKE_SYS_ID)
        result = delete_catalog_item(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("Error deleting catalog item", result.message)


class TestDeleteCatalogItemByName(unittest.TestCase):
    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_delete_by_name_resolves_then_deletes(self, mock_req):
        lookup_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID, "name": FAKE_NAME}]})
        delete_resp = _make_response(204)
        mock_req.side_effect = [lookup_resp, delete_resp]

        params = DeleteCatalogItemParams(item_id=FAKE_NAME)
        result = delete_catalog_item(self.config, self.auth, params)

        self.assertTrue(result.success)
        self.assertEqual(mock_req.call_count, 2)

        get_call = mock_req.call_args_list[0]
        self.assertEqual(get_call[0][0], "GET")
        self.assertIn(FAKE_NAME, get_call[1]["params"]["sysparm_query"])

        del_call = mock_req.call_args_list[1]
        self.assertEqual(del_call[0][0], "DELETE")
        self.assertIn(FAKE_SYS_ID, del_call[0][1])

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_delete_by_name_not_found(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        params = DeleteCatalogItemParams(item_id="Nonexistent Item")
        result = delete_catalog_item(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("not found", result.message.lower())
        self.assertEqual(mock_req.call_count, 1)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_delete_by_name_lookup_fails(self, mock_req):
        mock_req.side_effect = requests.exceptions.RequestException("timeout")
        params = DeleteCatalogItemParams(item_id=FAKE_NAME)
        result = delete_catalog_item(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("Error resolving catalog item", result.message)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_delete_by_name_delete_step_fails(self, mock_req):
        lookup_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID, "name": FAKE_NAME}]})
        mock_req.side_effect = [
            lookup_resp,
            requests.exceptions.RequestException("server error"),
        ]
        params = DeleteCatalogItemParams(item_id=FAKE_NAME)
        result = delete_catalog_item(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("Error deleting catalog item", result.message)

    @patch("servicenow_mcp.tools.catalog_tools._make_request")
    def test_delete_by_name_404_on_delete(self, mock_req):
        lookup_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        delete_resp = _make_response(404)
        mock_req.side_effect = [lookup_resp, delete_resp]

        params = DeleteCatalogItemParams(item_id=FAKE_NAME)
        result = delete_catalog_item(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("not found", result.message.lower())


class TestDeleteCatalogItemParams(unittest.TestCase):
    def test_requires_item_id(self):
        with self.assertRaises(ValidationError):
            DeleteCatalogItemParams()

    def test_accepts_sys_id(self):
        params = DeleteCatalogItemParams(item_id=FAKE_SYS_ID)
        self.assertEqual(params.item_id, FAKE_SYS_ID)

    def test_accepts_name(self):
        params = DeleteCatalogItemParams(item_id=FAKE_NAME)
        self.assertEqual(params.item_id, FAKE_NAME)


if __name__ == "__main__":
    unittest.main()
