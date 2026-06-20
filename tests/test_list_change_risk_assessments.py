"""Tests for list_change_risk_assessments in change_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.change_tools import (
    _format_risk_assessment,
    list_change_risk_assessments,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
CHANGE_SYS_ID = "b" * 32
QUESTIONNAIRE_SYS_ID = "c" * 32


FAKE_ASSESSMENT = {
    "sys_id": FAKE_SYS_ID,
    "source": {"display_value": "CHG0010001", "value": CHANGE_SYS_ID},
    "source_table": "change_request",
    "questionnaire": {"display_value": "Standard Risk", "value": QUESTIONNAIRE_SYS_ID},
    "result": {"display_value": "Low", "value": "low"},
    "state": {"display_value": "Complete", "value": "complete"},
    "risk": {"display_value": "Low", "value": "1"},
    "sys_created_by": "admin",
    "sys_created_on": "2026-06-20 08:00:00",
    "sys_updated_on": "2026-06-20 09:00:00",
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


def _make_response(status_code, json_data):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    return resp


# ---------------------------------------------------------------------------
# _format_risk_assessment
# ---------------------------------------------------------------------------


class TestFormatRiskAssessment(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_risk_assessment(FAKE_ASSESSMENT)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["change_request"], "CHG0010001")
        self.assertEqual(result["questionnaire"], "Standard Risk")
        self.assertEqual(result["result"], "Low")
        self.assertEqual(result["state"], "Complete")
        self.assertEqual(result["risk"], "Low")
        self.assertEqual(result["created_by"], "admin")
        self.assertEqual(result["created_on"], "2026-06-20 08:00:00")
        self.assertEqual(result["updated_on"], "2026-06-20 09:00:00")

    def test_handles_raw_string_reference_fields(self):
        record = {
            "sys_id": FAKE_SYS_ID,
            "source": "CHG0010001",
            "questionnaire": "Standard Risk",
            "result": "low",
            "state": "complete",
            "risk": "1",
            "sys_created_by": "admin",
            "sys_created_on": "2026-06-20 08:00:00",
            "sys_updated_on": "2026-06-20 09:00:00",
        }
        result = _format_risk_assessment(record)
        self.assertEqual(result["change_request"], "CHG0010001")
        self.assertEqual(result["questionnaire"], "Standard Risk")
        self.assertEqual(result["result"], "low")

    def test_handles_missing_fields(self):
        result = _format_risk_assessment({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["change_request"])
        self.assertIsNone(result["questionnaire"])
        self.assertIsNone(result["result"])
        self.assertIsNone(result["state"])
        self.assertIsNone(result["risk"])
        self.assertIsNone(result["created_by"])
        self.assertIsNone(result["created_on"])
        self.assertIsNone(result["updated_on"])

    def test_dict_value_fallback(self):
        record = {
            "sys_id": FAKE_SYS_ID,
            "source": {"display_value": None, "value": CHANGE_SYS_ID},
            "questionnaire": None,
            "result": None,
            "state": None,
            "risk": None,
            "sys_created_by": None,
            "sys_created_on": None,
            "sys_updated_on": None,
        }
        result = _format_risk_assessment(record)
        self.assertEqual(result["change_request"], CHANGE_SYS_ID)


# ---------------------------------------------------------------------------
# list_change_risk_assessments — no change_id filter
# ---------------------------------------------------------------------------


class TestListChangeRiskAssessmentsNoFilter(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_list_without_change_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_ASSESSMENT]})

        result = list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {"limit": 20, "offset": 0},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])
        assessments = result["risk_assessments"]
        self.assertEqual(len(assessments), 1)
        self.assertEqual(assessments[0]["sys_id"], FAKE_SYS_ID)

        # Must scope to change_request source table
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"]["sysparm_query"]
        self.assertIn("source_table=change_request", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_returns_empty_list(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        result = list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["risk_assessments"], [])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_state_filter_applied(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_ASSESSMENT]})

        list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {"state": "complete"},
        )

        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn("state=complete", query)


# ---------------------------------------------------------------------------
# list_change_risk_assessments — with change_id filter
# ---------------------------------------------------------------------------


class TestListChangeRiskAssessmentsWithChangeId(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_resolves_chg_number(self, mock_req):
        # First call: resolve CHG number → sys_id
        resolve_resp = _make_response(200, {"result": [{"sys_id": CHANGE_SYS_ID}]})
        # Second call: list assessments
        list_resp = _make_response(200, {"result": [FAKE_ASSESSMENT]})
        mock_req.side_effect = [resolve_resp, list_resp]

        result = list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {"change_id": "CHG0010001"},
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

        # The second call's query should filter by source=<sys_id>
        list_call_kwargs = mock_req.call_args_list[1][1]
        query = list_call_kwargs["params"]["sysparm_query"]
        self.assertIn(f"source={CHANGE_SYS_ID}", query)
        self.assertIn("source_table=change_request", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_passthrough_sys_id(self, mock_req):
        # With a 32-char hex sys_id, no resolve call is needed
        mock_req.return_value = _make_response(200, {"result": [FAKE_ASSESSMENT]})

        result = list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {"change_id": CHANGE_SYS_ID},
        )

        self.assertTrue(result["success"])
        # Only one request made (no lookup)
        self.assertEqual(mock_req.call_count, 1)
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        self.assertIn(f"source={CHANGE_SYS_ID}", query)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_change_not_found_returns_error(self, mock_req):
        resolve_resp = _make_response(200, {"result": []})
        mock_req.return_value = resolve_resp

        result = list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {"change_id": "CHG9999999"},
        )

        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])
        self.assertIn("CHG9999999", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_combined_change_id_and_state(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": CHANGE_SYS_ID}]})
        list_resp = _make_response(200, {"result": [FAKE_ASSESSMENT]})
        mock_req.side_effect = [resolve_resp, list_resp]

        list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {"change_id": "CHG0010001", "state": "pending"},
        )

        query = mock_req.call_args_list[1][1]["params"]["sysparm_query"]
        self.assertIn(f"source={CHANGE_SYS_ID}", query)
        self.assertIn("state=pending", query)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestListChangeRiskAssessmentsPagination(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_has_more_when_full_page(self, mock_req):
        assessments = [dict(FAKE_ASSESSMENT, sys_id=f"{i:032x}") for i in range(5)]
        mock_req.return_value = _make_response(200, {"result": assessments})

        result = list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {"limit": 5, "offset": 0},
        )

        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 5)

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_no_has_more_when_partial_page(self, mock_req):
        assessments = [dict(FAKE_ASSESSMENT, sys_id=f"{i:032x}") for i in range(3)]
        mock_req.return_value = _make_response(200, {"result": assessments})

        result = list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {"limit": 5, "offset": 10},
        )

        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_offset_passed_to_api(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})

        list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {"limit": 10, "offset": 20},
        )

        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["sysparm_offset"], 20)
        self.assertEqual(params["sysparm_limit"], 10)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestListChangeRiskAssessmentsErrors(unittest.TestCase):
    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {"error": {"message": "Internal error"}})

        result = list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error listing change risk assessments", result["message"])

    @patch("servicenow_mcp.tools.change_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("connection refused")

        result = list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {},
        )

        self.assertFalse(result["success"])
        self.assertIn("Error listing change risk assessments", result["message"])

    @patch("servicenow_mcp.tools.change_tools._get_instance_url", return_value=None)
    def test_missing_instance_url(self, _mock_url):
        result = list_change_risk_assessments(
            _make_auth_manager(),
            _make_config(),
            {},
        )
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    def test_fields_requested_in_api_call(self):
        with patch("servicenow_mcp.tools.change_tools._make_request") as mock_req:
            mock_req.return_value = _make_response(200, {"result": []})

            list_change_risk_assessments(
                _make_auth_manager(),
                _make_config(),
                {},
            )

            params = mock_req.call_args[1]["params"]
            self.assertIn("sys_id", params["sysparm_fields"])
            self.assertIn("source", params["sysparm_fields"])
            self.assertIn("state", params["sysparm_fields"])


if __name__ == "__main__":
    unittest.main()
