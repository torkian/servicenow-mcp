"""Tests for close_incident_task tool."""

import unittest
from unittest.mock import MagicMock, patch

import requests as req

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.incident_task_tools import close_incident_task
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestCloseIncidentTask(unittest.TestCase):
    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test", password="test"),
        )
        self.config = ServerConfig(
            instance_url="https://dev12345.service-now.com",
            auth=auth_config,
        )
        self.auth_manager = MagicMock(spec=AuthManager)
        self.auth_manager.get_headers.return_value = {"Authorization": "Bearer FAKE_TOKEN"}

    def _patch_resp(self, status_code=200, json_body=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_body or {}
        resp.raise_for_status = MagicMock()
        return resp

    # ------------------------------------------------------------------ #
    # Success paths                                                        #
    # ------------------------------------------------------------------ #

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    @patch("servicenow_mcp.tools.incident_task_tools.requests.patch")
    def test_close_by_task_number(self, mock_patch, mock_get):
        """Close a task using its TASK number; lookup resolves to sys_id."""
        lookup_resp = self._patch_resp(json_body={"result": [{"sys_id": "task_sys_id_001"}]})
        mock_get.return_value = lookup_resp

        patch_resp = self._patch_resp(
            json_body={
                "result": {
                    "sys_id": "task_sys_id_001",
                    "number": "TASK0010001",
                    "state": "3",
                    "close_notes": "All done",
                }
            }
        )
        mock_patch.return_value = patch_resp

        result = close_incident_task(
            self.auth_manager,
            self.config,
            {"task_id": "TASK0010001", "close_notes": "All done"},
        )

        self.assertTrue(result["success"])
        self.assertIn("TASK0010001", result["message"])
        self.assertEqual(result["task"]["sys_id"], "task_sys_id_001")
        self.assertEqual(result["task"]["state"], "3")
        body_sent = mock_patch.call_args[1]["json"]
        self.assertEqual(body_sent["state"], "3")
        self.assertEqual(body_sent["close_notes"], "All done")

    @patch("servicenow_mcp.tools.incident_task_tools.requests.patch")
    def test_close_by_sys_id_skips_lookup(self, mock_patch):
        """Supplying a 32-char hex sys_id skips the lookup GET."""
        task_sys_id = "a" * 32

        patch_resp = self._patch_resp(
            json_body={"result": {"sys_id": task_sys_id, "number": "TASK0010002", "state": "3"}}
        )
        mock_patch.return_value = patch_resp

        result = close_incident_task(
            self.auth_manager,
            self.config,
            {"task_id": task_sys_id},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["task"]["sys_id"], task_sys_id)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    @patch("servicenow_mcp.tools.incident_task_tools.requests.patch")
    def test_close_with_work_notes(self, mock_patch, mock_get):
        """work_notes are forwarded in the PATCH body."""
        lookup_resp = self._patch_resp(json_body={"result": [{"sys_id": "task_sys_id_003"}]})
        mock_get.return_value = lookup_resp

        patch_resp = self._patch_resp(
            json_body={"result": {"sys_id": "task_sys_id_003", "state": "3"}}
        )
        mock_patch.return_value = patch_resp

        result = close_incident_task(
            self.auth_manager,
            self.config,
            {"task_id": "TASK0010003", "work_notes": "Resolved via automation"},
        )

        self.assertTrue(result["success"])
        body_sent = mock_patch.call_args[1]["json"]
        self.assertEqual(body_sent["work_notes"], "Resolved via automation")

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    @patch("servicenow_mcp.tools.incident_task_tools.requests.patch")
    def test_close_with_all_optional_fields(self, mock_patch, mock_get):
        """Both close_notes and work_notes are forwarded."""
        lookup_resp = self._patch_resp(json_body={"result": [{"sys_id": "task_sys_id_004"}]})
        mock_get.return_value = lookup_resp

        patch_resp = self._patch_resp(
            json_body={"result": {"sys_id": "task_sys_id_004", "state": "3"}}
        )
        mock_patch.return_value = patch_resp

        result = close_incident_task(
            self.auth_manager,
            self.config,
            {
                "task_id": "TASK0010004",
                "close_notes": "Completed",
                "work_notes": "Done",
            },
        )

        self.assertTrue(result["success"])
        body_sent = mock_patch.call_args[1]["json"]
        self.assertEqual(body_sent["close_notes"], "Completed")
        self.assertEqual(body_sent["work_notes"], "Done")
        self.assertEqual(body_sent["state"], "3")

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    @patch("servicenow_mcp.tools.incident_task_tools.requests.patch")
    def test_close_minimal_params(self, mock_patch, mock_get):
        """Closing with only task_id sends just state=3 in the body."""
        lookup_resp = self._patch_resp(json_body={"result": [{"sys_id": "task_sys_id_005"}]})
        mock_get.return_value = lookup_resp

        patch_resp = self._patch_resp(
            json_body={"result": {"sys_id": "task_sys_id_005", "state": "3"}}
        )
        mock_patch.return_value = patch_resp

        result = close_incident_task(
            self.auth_manager,
            self.config,
            {"task_id": "TASK0010005"},
        )

        self.assertTrue(result["success"])
        body_sent = mock_patch.call_args[1]["json"]
        self.assertNotIn("close_notes", body_sent)
        self.assertNotIn("work_notes", body_sent)

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    @patch("servicenow_mcp.tools.incident_task_tools.requests.patch")
    def test_close_unwraps_nested_params(self, mock_patch, mock_get):
        """Params wrapped in {"params": {...}} are properly unwrapped."""
        lookup_resp = self._patch_resp(json_body={"result": [{"sys_id": "task_sys_id_006"}]})
        mock_get.return_value = lookup_resp

        patch_resp = self._patch_resp(
            json_body={"result": {"sys_id": "task_sys_id_006", "state": "3"}}
        )
        mock_patch.return_value = patch_resp

        result = close_incident_task(
            self.auth_manager,
            self.config,
            {"params": {"task_id": "TASK0010006"}},
        )

        self.assertTrue(result["success"])

    # ------------------------------------------------------------------ #
    # Failure paths                                                        #
    # ------------------------------------------------------------------ #

    def test_close_missing_task_id(self):
        """Missing task_id fails validation."""
        result = close_incident_task(self.auth_manager, self.config, {})
        self.assertFalse(result["success"])
        self.assertIn("task_id", result["message"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_close_task_not_found_by_number(self, mock_get):
        """Return failure when number lookup returns no results."""
        lookup_resp = self._patch_resp(json_body={"result": []})
        mock_get.return_value = lookup_resp

        result = close_incident_task(
            self.auth_manager,
            self.config,
            {"task_id": "TASK9999999"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    @patch("servicenow_mcp.tools.incident_task_tools.requests.patch")
    def test_close_patch_returns_404(self, mock_patch, mock_get):
        """404 from PATCH returns a not-found error."""
        lookup_resp = self._patch_resp(json_body={"result": [{"sys_id": "task_sys_id_007"}]})
        mock_get.return_value = lookup_resp

        patch_resp = self._patch_resp(status_code=404, json_body={})
        mock_patch.return_value = patch_resp

        result = close_incident_task(
            self.auth_manager,
            self.config,
            {"task_id": "TASK0010007"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    @patch("servicenow_mcp.tools.incident_task_tools.requests.patch")
    def test_close_http_error(self, mock_patch, mock_get):
        """Network error during PATCH returns success=False."""
        lookup_resp = self._patch_resp(json_body={"result": [{"sys_id": "task_sys_id_008"}]})
        mock_get.return_value = lookup_resp

        mock_patch.side_effect = req.exceptions.RequestException("503 Unavailable")

        result = close_incident_task(
            self.auth_manager,
            self.config,
            {"task_id": "TASK0010008"},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error closing incident task", result["message"])

    @patch("servicenow_mcp.tools.incident_task_tools.requests.get")
    def test_close_lookup_raises_exception(self, mock_get):
        """Exception during lookup causes task not found."""
        mock_get.side_effect = req.exceptions.RequestException("Connection error")

        result = close_incident_task(
            self.auth_manager,
            self.config,
            {"task_id": "TASK0010009"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])


if __name__ == "__main__":
    unittest.main()
