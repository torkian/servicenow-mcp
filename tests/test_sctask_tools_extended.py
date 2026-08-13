"""Extended tests for SCTASK tools — coverage improvements."""

import unittest
from unittest.mock import MagicMock, patch

from requests.exceptions import RequestException

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.sctask_tools import get_sctask, list_sctasks, update_sctask
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


def _make_config():
    return ServerConfig(
        instance_url="https://dev12345.service-now.com",
        auth=AuthConfig(type=AuthType.BASIC, basic=BasicAuthConfig(username="u", password="p")),
    )


def _make_auth():
    auth = MagicMock(spec=AuthManager)
    auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    return auth


class TestGetSCTaskExtended(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    def test_get_missing_instance_url(self):
        auth = MagicMock()
        del auth.instance_url
        config = MagicMock()
        del config.instance_url

        result = get_sctask(auth, config, {"task_number": "SCTASK001"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_get_missing_headers(self):
        auth = MagicMock()
        auth.instance_url = "https://dev12345.service-now.com"
        del auth.get_headers
        config = MagicMock()
        del config.instance_url
        del config.get_headers

        result = get_sctask(auth, config, {"task_number": "SCTASK001"})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.sctask_tools.requests.get")
    def test_get_request_exception(self, mock_get):
        """RequestException during GET → error response."""
        mock_get.side_effect = RequestException("network failure")
        result = get_sctask(self.auth, self.config, {"task_number": "SCTASK001"})
        self.assertFalse(result["success"])
        self.assertIn("Error fetching SCTASK", result["message"])


class TestListSCTasksExtended(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    def test_list_validation_failure(self):
        """Invalid limit value triggers Pydantic validation error."""
        result = list_sctasks(self.auth, self.config, {"limit": "not-a-number"})
        self.assertFalse(result["success"])

    def test_list_missing_instance_url(self):
        auth = MagicMock()
        del auth.instance_url
        config = MagicMock()
        del config.instance_url

        result = list_sctasks(auth, config, {})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_list_missing_headers(self):
        auth = MagicMock()
        auth.instance_url = "https://dev12345.service-now.com"
        del auth.get_headers
        config = MagicMock()
        del config.instance_url
        del config.get_headers

        result = list_sctasks(auth, config, {})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.sctask_tools.requests.get")
    def test_list_with_query_filter(self, mock_get):
        """Extra query string is appended to sysparm_query."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = list_sctasks(self.auth, self.config, {"query": "priority=1"})
        self.assertTrue(result["success"])
        call_params = mock_get.call_args[1]["params"]["sysparm_query"]
        self.assertIn("priority=1", call_params)

    @patch("servicenow_mcp.tools.sctask_tools.requests.get")
    def test_list_request_exception(self, mock_get):
        mock_get.side_effect = RequestException("network down")
        result = list_sctasks(self.auth, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing", result["message"])


class TestUpdateSCTaskExtended(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.auth = _make_auth()

    def test_update_missing_instance_url(self):
        auth = MagicMock()
        del auth.instance_url
        config = MagicMock()
        del config.instance_url

        result = update_sctask(auth, config, {"task_number": "SCTASK001", "state": "2"})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_update_missing_headers(self):
        auth = MagicMock()
        auth.instance_url = "https://dev12345.service-now.com"
        del auth.get_headers
        config = MagicMock()
        del config.instance_url
        del config.get_headers

        result = update_sctask(auth, config, {"task_number": "SCTASK001", "state": "2"})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.sctask_tools.requests.get")
    def test_update_sctask_number_not_found(self, mock_get):
        """SCTASK number lookup returns empty → not found."""
        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": []}),
        )
        result = update_sctask(self.auth, self.config, {
            "task_number": "SCTASK9999999",
            "state": "2",
        })
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.sctask_tools.requests.get")
    def test_update_sctask_number_lookup_exception(self, mock_get):
        """GET during SCTASK number resolution raises RequestException."""
        mock_get.side_effect = RequestException("DNS fail")
        result = update_sctask(self.auth, self.config, {
            "task_number": "SCTASK0001111",
            "state": "2",
        })
        self.assertFalse(result["success"])
        self.assertIn("Error resolving", result["message"])

    @patch("servicenow_mcp.tools.sctask_tools.requests.patch")
    @patch("servicenow_mcp.tools.sctask_tools.requests.get")
    def test_update_with_assignment_group_and_other_fields(self, mock_get, mock_patch):
        """assignment_group, short_description, close_notes fields hit their branches."""
        lookup_resp = MagicMock()
        lookup_resp.raise_for_status = MagicMock()
        lookup_resp.json.return_value = {"result": [{"sys_id": "abc123"}]}
        mock_get.return_value = lookup_resp

        patch_resp = MagicMock()
        patch_resp.raise_for_status = MagicMock()
        patch_resp.json.return_value = {"result": {"sys_id": "abc123"}}
        mock_patch.return_value = patch_resp

        result = update_sctask(self.auth, self.config, {
            "task_number": "SCTASK0525799",
            "assignment_group": "Tier2",
            "assigned_to": "john.doe",
            "short_description": "Updated desc",
            "close_notes": "Done",
        })
        self.assertTrue(result["success"])
        sent_body = mock_patch.call_args[1]["json"]
        self.assertEqual(sent_body["assignment_group"], "Tier2")
        self.assertEqual(sent_body["short_description"], "Updated desc")
        self.assertEqual(sent_body["close_notes"], "Done")

    @patch("servicenow_mcp.tools.sctask_tools.requests.patch")
    @patch("servicenow_mcp.tools.sctask_tools.requests.get")
    def test_update_time_worked_with_invalid_current_format(self, mock_get, mock_patch):
        """current_raw in unrecognised format → parsing exception → current_seconds=0."""
        lookup_resp = MagicMock()
        lookup_resp.raise_for_status = MagicMock()
        lookup_resp.json.return_value = {"result": [{"sys_id": "abc123"}]}

        # Second GET returns an unexpected/empty time_worked format
        time_resp = MagicMock()
        time_resp.raise_for_status = MagicMock()
        time_resp.json.return_value = {"result": {"time_worked": "invalid-format"}}

        mock_get.side_effect = [lookup_resp, time_resp]

        patch_resp = MagicMock()
        patch_resp.raise_for_status = MagicMock()
        patch_resp.json.return_value = {"result": {"sys_id": "abc123"}}
        mock_patch.return_value = patch_resp

        result = update_sctask(self.auth, self.config, {
            "task_number": "SCTASK0525799",
            "time_worked": "01:00:00",
        })
        self.assertTrue(result["success"])
        # With current_seconds=0 (parse failed), total = 01:00:00
        sent_body = mock_patch.call_args[1]["json"]
        self.assertEqual(sent_body["time_worked"], "01:00:00")

    @patch("servicenow_mcp.tools.sctask_tools.requests.patch")
    @patch("servicenow_mcp.tools.sctask_tools.requests.get")
    def test_update_time_worked_get_throws(self, mock_get, mock_patch):
        """Outer try-except: the GET for time_worked throws → fallback to raw value."""
        lookup_resp = MagicMock()
        lookup_resp.raise_for_status = MagicMock()
        lookup_resp.json.return_value = {"result": [{"sys_id": "abc123"}]}

        # Second GET (time_worked fetch) fails
        mock_get.side_effect = [lookup_resp, RequestException("timeout")]

        patch_resp = MagicMock()
        patch_resp.raise_for_status = MagicMock()
        patch_resp.json.return_value = {"result": {"sys_id": "abc123"}}
        mock_patch.return_value = patch_resp

        result = update_sctask(self.auth, self.config, {
            "task_number": "SCTASK0525799",
            "time_worked": "02:30:00",
        })
        self.assertTrue(result["success"])
        # Fallback: raw time_worked is used unchanged
        sent_body = mock_patch.call_args[1]["json"]
        self.assertEqual(sent_body["time_worked"], "02:30:00")

    @patch("servicenow_mcp.tools.sctask_tools.requests.patch")
    @patch("servicenow_mcp.tools.sctask_tools.requests.get")
    def test_update_patch_request_exception(self, mock_get, mock_patch):
        """Final PATCH raises RequestException → error response."""
        lookup_resp = MagicMock()
        lookup_resp.raise_for_status = MagicMock()
        lookup_resp.json.return_value = {"result": [{"sys_id": "abc123"}]}
        mock_get.return_value = lookup_resp

        mock_patch.side_effect = RequestException("server error")

        result = update_sctask(self.auth, self.config, {
            "task_number": "SCTASK0525799",
            "state": "3",
        })
        self.assertFalse(result["success"])
        self.assertIn("Error updating SCTASK", result["message"])

    @patch("servicenow_mcp.tools.sctask_tools.requests.patch")
    def test_update_with_plain_sys_id_skips_lookup(self, mock_patch):
        """A plain sys_id (not starting with SCTASK) skips the number-to-sys_id lookup."""
        mock_patch.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": {"sys_id": "abc123"}}),
        )
        result = update_sctask(self.auth, self.config, {
            "task_number": "abc123plain",
            "state": "2",
        })
        self.assertTrue(result["success"])
        mock_patch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
