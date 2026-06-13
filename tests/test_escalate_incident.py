"""Tests for escalate_incident tool."""

import unittest
from unittest.mock import MagicMock, patch

from requests.exceptions import RequestException

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.incident_tools import EscalateIncidentParams, escalate_incident
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig


class TestEscalateIncident(unittest.TestCase):

    def setUp(self):
        auth_config = AuthConfig(
            type=AuthType.BASIC,
            basic=BasicAuthConfig(username="test", password="test"),
        )
        self.config = ServerConfig(
            instance_url="https://dev12345.service-now.com",
            auth=auth_config,
        )
        self.auth = MagicMock(spec=AuthManager)
        self.auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}

    def _ok_resp(self, body):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = body
        resp.raise_for_status = MagicMock()
        return resp

    def _not_found_resp(self):
        resp = MagicMock()
        resp.status_code = 404
        resp.json.return_value = {}
        resp.raise_for_status = MagicMock()
        return resp

    # ------------------------------------------------------------------ #
    # Success via incident number                                          #
    # ------------------------------------------------------------------ #

    @patch("servicenow_mcp.tools.incident_tools.requests.patch")
    @patch("servicenow_mcp.tools.incident_tools.requests.get")
    def test_escalate_by_number_priority_only(self, mock_get, mock_patch):
        """Escalate by incident number with only priority supplied."""
        mock_get.return_value = self._ok_resp(
            {"result": [{"sys_id": "inc_sys_001", "number": "INC0010001"}]}
        )
        mock_patch.return_value = self._ok_resp(
            {"result": {"sys_id": "inc_sys_001", "number": "INC0010001"}}
        )

        params = EscalateIncidentParams(incident_id="INC0010001", priority="1")
        result = escalate_incident(self.config, self.auth, params)

        self.assertTrue(result.success)
        self.assertIn("Critical", result.message)
        self.assertNotIn("reassigned", result.message)
        self.assertEqual(result.incident_id, "inc_sys_001")
        body = mock_patch.call_args[1]["json"]
        self.assertEqual(body["priority"], "1")
        self.assertNotIn("assignment_group", body)
        self.assertNotIn("work_notes", body)

    @patch("servicenow_mcp.tools.incident_tools.requests.patch")
    @patch("servicenow_mcp.tools.incident_tools.requests.get")
    def test_escalate_with_assignment_group(self, mock_get, mock_patch):
        """Escalate with a new assignment group included."""
        mock_get.return_value = self._ok_resp(
            {"result": [{"sys_id": "inc_sys_002", "number": "INC0010002"}]}
        )
        mock_patch.return_value = self._ok_resp(
            {"result": {"sys_id": "inc_sys_002", "number": "INC0010002"}}
        )

        params = EscalateIncidentParams(
            incident_id="INC0010002",
            priority="2",
            assignment_group="Network Operations",
        )
        result = escalate_incident(self.config, self.auth, params)

        self.assertTrue(result.success)
        self.assertIn("High", result.message)
        self.assertIn("Network Operations", result.message)
        body = mock_patch.call_args[1]["json"]
        self.assertEqual(body["priority"], "2")
        self.assertEqual(body["assignment_group"], "Network Operations")

    @patch("servicenow_mcp.tools.incident_tools.requests.patch")
    @patch("servicenow_mcp.tools.incident_tools.requests.get")
    def test_escalate_with_audit_note(self, mock_get, mock_patch):
        """Audit note is sent as work_notes in the PATCH body."""
        mock_get.return_value = self._ok_resp(
            {"result": [{"sys_id": "inc_sys_003", "number": "INC0010003"}]}
        )
        mock_patch.return_value = self._ok_resp(
            {"result": {"sys_id": "inc_sys_003", "number": "INC0010003"}}
        )

        params = EscalateIncidentParams(
            incident_id="INC0010003",
            priority="2",
            audit_note="Escalating due to customer SLA breach",
        )
        result = escalate_incident(self.config, self.auth, params)

        self.assertTrue(result.success)
        body = mock_patch.call_args[1]["json"]
        self.assertEqual(body["work_notes"], "Escalating due to customer SLA breach")

    # ------------------------------------------------------------------ #
    # Success via sys_id (skips lookup GET)                                #
    # ------------------------------------------------------------------ #

    @patch("servicenow_mcp.tools.incident_tools.requests.patch")
    def test_escalate_by_sys_id_skips_lookup(self, mock_patch):
        """32-char hex sys_id bypasses the lookup GET entirely."""
        sys_id = "a" * 32
        mock_patch.return_value = self._ok_resp(
            {"result": {"sys_id": sys_id, "number": "INC0010004"}}
        )

        params = EscalateIncidentParams(incident_id=sys_id, priority="3")
        result = escalate_incident(self.config, self.auth, params)

        self.assertTrue(result.success)
        self.assertIn("Moderate", result.message)
        self.assertEqual(result.incident_id, sys_id)

    # ------------------------------------------------------------------ #
    # All priority labels                                                  #
    # ------------------------------------------------------------------ #

    @patch("servicenow_mcp.tools.incident_tools.requests.patch")
    def test_priority_labels(self, mock_patch):
        """Verify human-readable labels for each numeric priority."""
        sys_id = "b" * 32
        labels = {
            "1": "Critical",
            "2": "High",
            "3": "Moderate",
            "4": "Low",
            "5": "Planning",
        }
        for code, label in labels.items():
            mock_patch.return_value = self._ok_resp(
                {"result": {"sys_id": sys_id, "number": "INC001"}}
            )
            params = EscalateIncidentParams(incident_id=sys_id, priority=code)
            result = escalate_incident(self.config, self.auth, params)
            self.assertTrue(result.success, f"Failed for priority {code}")
            self.assertIn(label, result.message, f"Label missing for priority {code}")

    # ------------------------------------------------------------------ #
    # Not-found cases                                                      #
    # ------------------------------------------------------------------ #

    @patch("servicenow_mcp.tools.incident_tools.requests.get")
    def test_number_not_found(self, mock_get):
        """Empty result from lookup returns failure without calling PATCH."""
        mock_get.return_value = self._ok_resp({"result": []})

        params = EscalateIncidentParams(incident_id="INC9999999", priority="1")
        result = escalate_incident(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("not found", result.message.lower())

    @patch("servicenow_mcp.tools.incident_tools.requests.patch")
    def test_patch_returns_404(self, mock_patch):
        """PATCH returning 404 is handled gracefully."""
        sys_id = "c" * 32
        mock_patch.return_value = self._not_found_resp()

        params = EscalateIncidentParams(incident_id=sys_id, priority="2")
        result = escalate_incident(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("not found", result.message.lower())

    # ------------------------------------------------------------------ #
    # Network error paths                                                  #
    # ------------------------------------------------------------------ #

    @patch("servicenow_mcp.tools.incident_tools.requests.get")
    def test_lookup_network_error(self, mock_get):
        """RequestException during lookup produces a failure response."""
        mock_get.side_effect = RequestException("connection refused")

        params = EscalateIncidentParams(incident_id="INC0010005", priority="1")
        result = escalate_incident(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to find incident", result.message)

    @patch("servicenow_mcp.tools.incident_tools.requests.patch")
    def test_patch_network_error(self, mock_patch):
        """RequestException during PATCH produces a failure response."""
        sys_id = "d" * 32
        mock_patch.side_effect = RequestException("timeout")

        params = EscalateIncidentParams(incident_id=sys_id, priority="1")
        result = escalate_incident(self.config, self.auth, params)

        self.assertFalse(result.success)
        self.assertIn("Failed to escalate incident", result.message)

    # ------------------------------------------------------------------ #
    # All optional fields together                                         #
    # ------------------------------------------------------------------ #

    @patch("servicenow_mcp.tools.incident_tools.requests.patch")
    def test_all_optional_fields(self, mock_patch):
        """Supplying both assignment_group and audit_note sends all fields."""
        sys_id = "e" * 32
        mock_patch.return_value = self._ok_resp(
            {"result": {"sys_id": sys_id, "number": "INC0010006"}}
        )

        params = EscalateIncidentParams(
            incident_id=sys_id,
            priority="1",
            assignment_group="Major Incident Team",
            audit_note="P1 bridge opened",
        )
        result = escalate_incident(self.config, self.auth, params)

        self.assertTrue(result.success)
        body = mock_patch.call_args[1]["json"]
        self.assertEqual(body["priority"], "1")
        self.assertEqual(body["assignment_group"], "Major Incident Team")
        self.assertEqual(body["work_notes"], "P1 bridge opened")
        self.assertIn("Critical", result.message)
        self.assertIn("Major Incident Team", result.message)


if __name__ == "__main__":
    unittest.main()
