"""Tests for cmdb_relationship_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.cmdb_relationship_tools import (
    _format_rel_type,
    _format_relationship,
    create_ci_relationship,
    delete_ci_relationship,
    get_ci_relationship,
    list_ci_relationship_types,
    list_ci_relationships,
)
from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_REL = {
    "sys_id": "rel001",
    "parent": "ci001",
    "child": "ci002",
    "type": "reltype001",
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-04-01 00:00:00",
}

FAKE_REL_REF = {
    "sys_id": "rel002",
    "parent": {"value": "ci003", "display_value": "Server A"},
    "child": {"value": "ci004", "display_value": "Server B"},
    "type": {"value": "reltype002", "display_value": "Depends on::Used by"},
    "sys_created_on": "2026-02-01 00:00:00",
    "sys_updated_on": "2026-04-10 00:00:00",
}

FAKE_REL_TYPE = {
    "sys_id": "reltype001",
    "name": "Depends on::Used by",
    "parent_descriptor": "Depends on",
    "child_descriptor": "Used by",
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


# ---------------------------------------------------------------------------
# _format_relationship
# ---------------------------------------------------------------------------


class TestFormatRelationship(unittest.TestCase):
    def test_string_values(self):
        result = _format_relationship(FAKE_REL)
        self.assertEqual(result["sys_id"], "rel001")
        self.assertEqual(result["parent"], "ci001")
        self.assertEqual(result["child"], "ci002")
        self.assertEqual(result["type"], "reltype001")
        self.assertEqual(result["created_on"], "2026-01-01 00:00:00")
        self.assertEqual(result["updated_on"], "2026-04-01 00:00:00")

    def test_reference_dict_values(self):
        result = _format_relationship(FAKE_REL_REF)
        self.assertEqual(result["parent"], "ci003")
        self.assertEqual(result["child"], "ci004")
        self.assertEqual(result["type"], "reltype002")

    def test_empty_record(self):
        result = _format_relationship({})
        self.assertIsNone(result["sys_id"])
        self.assertEqual(result["parent"], "")
        self.assertEqual(result["child"], "")
        self.assertEqual(result["type"], "")

    def test_ref_dict_missing_value_falls_back_to_display(self):
        record = {"parent": {"display_value": "Fallback Name"}, "child": "", "type": ""}
        result = _format_relationship(record)
        self.assertEqual(result["parent"], "Fallback Name")


# ---------------------------------------------------------------------------
# _format_rel_type
# ---------------------------------------------------------------------------


class TestFormatRelType(unittest.TestCase):
    def test_all_fields(self):
        result = _format_rel_type(FAKE_REL_TYPE)
        self.assertEqual(result["sys_id"], "reltype001")
        self.assertEqual(result["name"], "Depends on::Used by")
        self.assertEqual(result["parent_descriptor"], "Depends on")
        self.assertEqual(result["child_descriptor"], "Used by")

    def test_empty(self):
        result = _format_rel_type({})
        for key in ("sys_id", "name", "parent_descriptor", "child_descriptor"):
            self.assertIsNone(result[key])


# ---------------------------------------------------------------------------
# list_ci_relationships
# ---------------------------------------------------------------------------


class TestListCIRelationships(unittest.TestCase):
    def setUp(self):
        self.auth_manager = _make_auth_manager()
        self.server_config = _make_config()

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_success_no_filters(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_REL]}
        mock_req.return_value = mock_resp

        result = list_ci_relationships(
            self.auth_manager, self.server_config, {"limit": 10, "offset": 0}
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["relationships"]), 1)
        self.assertEqual(result["relationships"][0]["sys_id"], "rel001")

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_filter_by_parent(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_REL]}
        mock_req.return_value = mock_resp

        result = list_ci_relationships(
            self.auth_manager,
            self.server_config,
            {"parent_ci": "ci001"},
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("parent=ci001", query)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_filter_by_child(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_REL]}
        mock_req.return_value = mock_resp

        result = list_ci_relationships(
            self.auth_manager,
            self.server_config,
            {"child_ci": "ci002"},
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("child=ci002", query)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_filter_by_type(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_REL]}
        mock_req.return_value = mock_resp

        result = list_ci_relationships(
            self.auth_manager,
            self.server_config,
            {"relationship_type": "reltype001"},
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("type=reltype001", query)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_filter_combined(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        result = list_ci_relationships(
            self.auth_manager,
            self.server_config,
            {"parent_ci": "ci001", "child_ci": "ci002", "relationship_type": "reltype001"},
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("parent=ci001", query)
        self.assertIn("child=ci002", query)
        self.assertIn("type=reltype001", query)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_raw_query_appended(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        result = list_ci_relationships(
            self.auth_manager,
            self.server_config,
            {"query": "sys_created_on>2026-01-01"},
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("sys_created_on>2026-01-01", query)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_pagination_keys(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_REL] * 5}
        mock_req.return_value = mock_resp

        result = list_ci_relationships(
            self.auth_manager, self.server_config, {"limit": 5, "offset": 0}
        )

        self.assertIn("has_more", result)
        self.assertIn("count", result)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_request_exception(self, mock_req):
        import requests

        mock_req.side_effect = requests.exceptions.ConnectionError("network error")

        result = list_ci_relationships(self.auth_manager, self.server_config, {})

        self.assertFalse(result["success"])
        self.assertIn("Error listing CI relationships", result["message"])

    def test_invalid_params(self):
        result = list_ci_relationships(
            self.auth_manager, self.server_config, {"limit": "not-a-number"}
        )
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer X"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None

        result = list_ci_relationships(auth, config, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev.service-now.com"

        result = list_ci_relationships(auth, config, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])


# ---------------------------------------------------------------------------
# get_ci_relationship
# ---------------------------------------------------------------------------


class TestGetCIRelationship(unittest.TestCase):
    def setUp(self):
        self.auth_manager = _make_auth_manager()
        self.server_config = _make_config()

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_success(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": FAKE_REL}
        mock_req.return_value = mock_resp

        result = get_ci_relationship(
            self.auth_manager, self.server_config, {"sys_id": "rel001"}
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["relationship"]["sys_id"], "rel001")

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_not_found_404(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_req.return_value = mock_resp

        result = get_ci_relationship(
            self.auth_manager, self.server_config, {"sys_id": "nope"}
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {}}
        mock_req.return_value = mock_resp

        result = get_ci_relationship(
            self.auth_manager, self.server_config, {"sys_id": "rel001"}
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_missing_sys_id(self):
        result = get_ci_relationship(self.auth_manager, self.server_config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_request_exception(self, mock_req):
        import requests

        mock_req.side_effect = requests.exceptions.Timeout("timed out")

        result = get_ci_relationship(
            self.auth_manager, self.server_config, {"sys_id": "rel001"}
        )

        self.assertFalse(result["success"])
        self.assertIn("Error retrieving CI relationship", result["message"])


# ---------------------------------------------------------------------------
# create_ci_relationship
# ---------------------------------------------------------------------------


class TestCreateCIRelationship(unittest.TestCase):
    def setUp(self):
        self.auth_manager = _make_auth_manager()
        self.server_config = _make_config()

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_success(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"result": FAKE_REL}
        mock_req.return_value = mock_resp

        result = create_ci_relationship(
            self.auth_manager,
            self.server_config,
            {
                "parent_ci": "ci001",
                "child_ci": "ci002",
                "relationship_type": "reltype001",
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], "rel001")
        self.assertIn("relationship", result)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_body_sent_correctly(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"result": FAKE_REL}
        mock_req.return_value = mock_resp

        create_ci_relationship(
            self.auth_manager,
            self.server_config,
            {
                "parent_ci": "PARENT",
                "child_ci": "CHILD",
                "relationship_type": "RELTYPE",
            },
        )

        call_kwargs = mock_req.call_args
        body = call_kwargs[1]["json"]
        self.assertEqual(body["parent"], "PARENT")
        self.assertEqual(body["child"], "CHILD")
        self.assertEqual(body["type"], "RELTYPE")

    def test_missing_required_fields(self):
        result = create_ci_relationship(
            self.auth_manager,
            self.server_config,
            {"parent_ci": "ci001"},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_request_exception(self, mock_req):
        import requests

        mock_req.side_effect = requests.exceptions.HTTPError("403 Forbidden")

        result = create_ci_relationship(
            self.auth_manager,
            self.server_config,
            {
                "parent_ci": "ci001",
                "child_ci": "ci002",
                "relationship_type": "reltype001",
            },
        )

        self.assertFalse(result["success"])
        self.assertIn("Error creating CI relationship", result["message"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer X"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None

        result = create_ci_relationship(
            auth,
            config,
            {"parent_ci": "ci001", "child_ci": "ci002", "relationship_type": "rt"},
        )
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev.service-now.com"

        result = create_ci_relationship(
            auth,
            config,
            {"parent_ci": "ci001", "child_ci": "ci002", "relationship_type": "rt"},
        )
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# delete_ci_relationship
# ---------------------------------------------------------------------------


class TestDeleteCIRelationship(unittest.TestCase):
    def setUp(self):
        self.auth_manager = _make_auth_manager()
        self.server_config = _make_config()

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_success_204(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_req.return_value = mock_resp

        result = delete_ci_relationship(
            self.auth_manager, self.server_config, {"sys_id": "rel001"}
        )

        self.assertTrue(result["success"])
        self.assertIn("deleted successfully", result["message"])

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_success_200(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_req.return_value = mock_resp

        result = delete_ci_relationship(
            self.auth_manager, self.server_config, {"sys_id": "rel001"}
        )

        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_not_found_404(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_req.return_value = mock_resp

        result = delete_ci_relationship(
            self.auth_manager, self.server_config, {"sys_id": "nope"}
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_missing_sys_id(self):
        result = delete_ci_relationship(self.auth_manager, self.server_config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_request_exception(self, mock_req):
        import requests

        mock_req.side_effect = requests.exceptions.ConnectionError("down")

        result = delete_ci_relationship(
            self.auth_manager, self.server_config, {"sys_id": "rel001"}
        )

        self.assertFalse(result["success"])
        self.assertIn("Error deleting CI relationship", result["message"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer X"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None

        result = delete_ci_relationship(auth, config, {"sys_id": "rel001"})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev.service-now.com"

        result = delete_ci_relationship(auth, config, {"sys_id": "rel001"})
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# list_ci_relationship_types
# ---------------------------------------------------------------------------


class TestListCIRelationshipTypes(unittest.TestCase):
    def setUp(self):
        self.auth_manager = _make_auth_manager()
        self.server_config = _make_config()

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_success(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_REL_TYPE]}
        mock_req.return_value = mock_resp

        result = list_ci_relationship_types(self.auth_manager, self.server_config, {})

        self.assertTrue(result["success"])
        self.assertEqual(len(result["relationship_types"]), 1)
        self.assertEqual(result["relationship_types"][0]["name"], "Depends on::Used by")

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_filter_by_name(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_REL_TYPE]}
        mock_req.return_value = mock_resp

        result = list_ci_relationship_types(
            self.auth_manager, self.server_config, {"name": "Depends"}
        )

        self.assertTrue(result["success"])
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"].get("sysparm_query", "")
        self.assertIn("nameLIKEDepends", query)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        result = list_ci_relationship_types(self.auth_manager, self.server_config, {})

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_pagination(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [FAKE_REL_TYPE] * 10}
        mock_req.return_value = mock_resp

        result = list_ci_relationship_types(
            self.auth_manager, self.server_config, {"limit": 10, "offset": 5}
        )

        self.assertTrue(result["success"])
        self.assertIn("has_more", result)
        self.assertIn("next_offset", result)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_request_exception(self, mock_req):
        import requests

        mock_req.side_effect = requests.exceptions.ConnectionError("no network")

        result = list_ci_relationship_types(self.auth_manager, self.server_config, {})

        self.assertFalse(result["success"])
        self.assertIn("Error listing CI relationship types", result["message"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer X"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None

        result = list_ci_relationship_types(auth, config, {})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev.service-now.com"
        config = MagicMock()
        config.instance_url = "https://dev.service-now.com"

        result = list_ci_relationship_types(auth, config, {})
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
