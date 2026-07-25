"""Tests for scheduled_job_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.scheduled_job_tools import (
    _format_scheduled_job,
    _resolve_scheduled_job_sys_id,
    create_scheduled_job,
    delete_scheduled_job,
    get_scheduled_job,
    list_scheduled_jobs,
    update_scheduled_job,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

FAKE_SYS_ID = "a" * 32
FAKE_USER_SYS_ID = "b" * 32

FAKE_JOB = {
    "sys_id": FAKE_SYS_ID,
    "name": "Nightly Cleanup",
    "active": "true",
    "run_as": {"display_value": "admin", "value": FAKE_USER_SYS_ID},
    "run_type": "daily",
    "run_period": "",
    "run_start": "2026-01-01 00:00:00",
    "run_time": "00:00:00",
    "run_dayofmonth": "",
    "run_dayofweek": "",
    "run_at": "",
    "script": "gs.log('cleanup');",
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-06-01 00:00:00",
    "sys_created_by": "admin",
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
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=resp
        )
    return resp


# ---------------------------------------------------------------------------
# _format_scheduled_job
# ---------------------------------------------------------------------------

class TestFormatScheduledJob(unittest.TestCase):
    def test_formats_all_fields(self):
        result = _format_scheduled_job(FAKE_JOB)
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["name"], "Nightly Cleanup")
        self.assertEqual(result["active"], "true")
        self.assertEqual(result["run_type"], "daily")
        self.assertEqual(result["script"], "gs.log('cleanup');")
        self.assertEqual(result["created_on"], "2026-01-01 00:00:00")
        self.assertEqual(result["updated_on"], "2026-06-01 00:00:00")
        self.assertEqual(result["created_by"], "admin")

    def test_normalises_run_as_reference_dict(self):
        result = _format_scheduled_job(FAKE_JOB)
        self.assertEqual(result["run_as"], "admin")

    def test_handles_string_run_as(self):
        job = {**FAKE_JOB, "run_as": "plain_string"}
        result = _format_scheduled_job(job)
        self.assertEqual(result["run_as"], "plain_string")

    def test_handles_run_as_value_fallback(self):
        job = {**FAKE_JOB, "run_as": {"value": FAKE_USER_SYS_ID}}
        result = _format_scheduled_job(job)
        self.assertEqual(result["run_as"], FAKE_USER_SYS_ID)

    def test_handles_missing_fields(self):
        result = _format_scheduled_job({})
        self.assertIsNone(result["sys_id"])
        self.assertIsNone(result["name"])
        self.assertIsNone(result["active"])
        self.assertIsNone(result["run_as"])
        self.assertIsNone(result["script"])


# ---------------------------------------------------------------------------
# list_scheduled_jobs
# ---------------------------------------------------------------------------

class TestListScheduledJobs(unittest.TestCase):
    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_success_returns_jobs(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_JOB]})
        result = list_scheduled_jobs(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(len(result["jobs"]), 1)
        self.assertEqual(result["jobs"][0]["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["jobs"][0]["name"], "Nightly Cleanup")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = list_scheduled_jobs(_make_auth_manager(), _make_config(), {})
        self.assertTrue(result["success"])
        self.assertEqual(result["jobs"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_name_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(_make_auth_manager(), _make_config(), {"name": "Nightly"})
        query = mock_req.call_args[1]["params"].get("sysparm_query", "")
        self.assertIn("nameLIKENightly", query)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_active_true_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(_make_auth_manager(), _make_config(), {"active": True})
        query = mock_req.call_args[1]["params"].get("sysparm_query", "")
        self.assertIn("active=true", query)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_active_false_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(_make_auth_manager(), _make_config(), {"active": False})
        query = mock_req.call_args[1]["params"].get("sysparm_query", "")
        self.assertIn("active=false", query)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_run_as_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(_make_auth_manager(), _make_config(), {"run_as": "admin"})
        query = mock_req.call_args[1]["params"].get("sysparm_query", "")
        self.assertIn("run_as.nameLIKEadmin", query)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_run_type_filter(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(_make_auth_manager(), _make_config(), {"run_type": "daily"})
        query = mock_req.call_args[1]["params"].get("sysparm_query", "")
        self.assertIn("run_type=daily", query)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_combined_filters(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(
            _make_auth_manager(),
            _make_config(),
            {"name": "Cleanup", "active": True, "run_type": "daily"},
        )
        query = mock_req.call_args[1]["params"].get("sysparm_query", "")
        self.assertIn("nameLIKECleanup", query)
        self.assertIn("active=true", query)
        self.assertIn("run_type=daily", query)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_pagination_params(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(
            _make_auth_manager(), _make_config(), {"limit": 5, "offset": 10}
        )
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params["sysparm_limit"], 5)
        self.assertEqual(params["sysparm_offset"], 10)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_has_more_flag(self, mock_req):
        records = [FAKE_JOB] * 20
        mock_req.return_value = _make_response(200, {"result": records})
        result = list_scheduled_jobs(
            _make_auth_manager(), _make_config(), {"limit": 20, "offset": 0}
        )
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 20)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_has_more_false_when_fewer_results(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_JOB]})
        result = list_scheduled_jobs(
            _make_auth_manager(), _make_config(), {"limit": 20, "offset": 0}
        )
        self.assertFalse(result["has_more"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_uses_get_method(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(_make_auth_manager(), _make_config(), {})
        self.assertEqual(mock_req.call_args[0][0], "GET")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_url_targets_correct_table(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(_make_auth_manager(), _make_config(), {})
        url = mock_req.call_args[0][1]
        self.assertIn("sysauto_script", url)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_fields_requested(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(_make_auth_manager(), _make_config(), {})
        params = mock_req.call_args[1]["params"]
        fields = params.get("sysparm_fields", "")
        self.assertIn("sys_id", fields)
        self.assertIn("name", fields)
        self.assertIn("active", fields)
        self.assertIn("run_as", fields)
        self.assertIn("script", fields)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = list_scheduled_jobs(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing scheduled jobs", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_scheduled_jobs(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])
        self.assertIn("Error listing scheduled jobs", result["message"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        config = MagicMock()
        config.instance_url = None
        result = list_scheduled_jobs(auth, config, {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_returns_count(self, mock_req):
        mock_req.return_value = _make_response(
            200, {"result": [FAKE_JOB, FAKE_JOB]}
        )
        result = list_scheduled_jobs(_make_auth_manager(), _make_config(), {})
        self.assertEqual(result["count"], 2)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_ordered_by_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(_make_auth_manager(), _make_config(), {})
        params = mock_req.call_args[1]["params"]
        self.assertIn("name", params.get("sysparm_orderby", ""))

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_exclude_reference_link_set(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(_make_auth_manager(), _make_config(), {})
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params.get("sysparm_exclude_reference_link"), "true")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_no_query_when_no_filters(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        list_scheduled_jobs(_make_auth_manager(), _make_config(), {})
        params = mock_req.call_args[1]["params"]
        self.assertFalse(params.get("sysparm_query"))

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_normalises_run_as_in_response(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [FAKE_JOB]})
        result = list_scheduled_jobs(_make_auth_manager(), _make_config(), {})
        self.assertEqual(result["jobs"][0]["run_as"], "admin")


# ---------------------------------------------------------------------------
# _resolve_scheduled_job_sys_id
# ---------------------------------------------------------------------------

class TestResolveScheduledJobSysId(unittest.TestCase):
    def test_passthrough_for_valid_sys_id(self):
        result = _resolve_scheduled_job_sys_id("https://dev.service-now.com", {}, FAKE_SYS_ID)
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_name_lookup_returns_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        result = _resolve_scheduled_job_sys_id("https://dev.service-now.com", {}, "Nightly Cleanup")
        self.assertEqual(result, FAKE_SYS_ID)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_name_not_found_returns_none(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = _resolve_scheduled_job_sys_id("https://dev.service-now.com", {}, "Unknown Job")
        self.assertIsNone(result)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_request_error_returns_none(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = _resolve_scheduled_job_sys_id("https://dev.service-now.com", {}, "Any Name")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# get_scheduled_job
# ---------------------------------------------------------------------------

class TestGetScheduledJob(unittest.TestCase):
    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_success_by_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        result = get_scheduled_job(_make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID})
        self.assertTrue(result["success"])
        self.assertIn("job", result)
        self.assertEqual(result["job"]["sys_id"], FAKE_SYS_ID)
        self.assertEqual(result["job"]["name"], "Nightly Cleanup")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_success_by_name(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        get_resp = _make_response(200, {"result": FAKE_JOB})
        mock_req.side_effect = [resolve_resp, get_resp]
        result = get_scheduled_job(_make_auth_manager(), _make_config(), {"job_id": "Nightly Cleanup"})
        self.assertTrue(result["success"])
        self.assertEqual(result["job"]["name"], "Nightly Cleanup")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_not_found_by_name(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = get_scheduled_job(_make_auth_manager(), _make_config(), {"job_id": "Unknown Job"})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_404_returns_failure(self, mock_req):
        get_resp = _make_response(404, {})
        get_resp.raise_for_status = MagicMock()
        mock_req.return_value = get_resp
        result = get_scheduled_job(_make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_empty_result_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": {}})
        result = get_scheduled_job(_make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = get_scheduled_job(_make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving scheduled job", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = get_scheduled_job(_make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("Error retrieving scheduled job", result["message"])

    def test_missing_job_id_returns_failure(self):
        result = get_scheduled_job(_make_auth_manager(), _make_config(), {})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._get_instance_url")
    def test_missing_instance_url_returns_failure(self, mock_url):
        mock_url.return_value = None
        result = get_scheduled_job(_make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("instance_url", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._get_headers")
    @patch("servicenow_mcp.tools.scheduled_job_tools._get_instance_url")
    def test_missing_headers_returns_failure(self, mock_url, mock_headers):
        mock_url.return_value = "https://dev.service-now.com"
        mock_headers.return_value = None
        result = get_scheduled_job(_make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID})
        self.assertFalse(result["success"])
        self.assertIn("get_headers", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_url_includes_sys_id(self, mock_req):
        mock_req.side_effect = [
            _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]}),
            _make_response(200, {"result": FAKE_JOB}),
        ]
        get_scheduled_job(_make_auth_manager(), _make_config(), {"job_id": "Nightly Cleanup"})
        get_call_url = mock_req.call_args_list[1][0][1]
        self.assertIn(FAKE_SYS_ID, get_call_url)
        self.assertIn("sysauto_script", get_call_url)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_display_value_requested(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        get_scheduled_job(_make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID})
        params = mock_req.call_args[1]["params"]
        self.assertEqual(params.get("sysparm_display_value"), "true")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_normalises_run_as_reference(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        result = get_scheduled_job(_make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID})
        self.assertEqual(result["job"]["run_as"], "admin")


# ---------------------------------------------------------------------------
# create_scheduled_job
# ---------------------------------------------------------------------------

class TestCreateScheduledJob(unittest.TestCase):
    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_success_returns_job_and_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        result = create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"name": "Nightly Cleanup", "script": "gs.log('cleanup');"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sys_id"], FAKE_SYS_ID)
        self.assertIn("job", result)
        self.assertEqual(result["job"]["name"], "Nightly Cleanup")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_uses_post_method(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"name": "Cleanup", "script": "gs.log();"},
        )
        self.assertEqual(mock_req.call_args[0][0], "POST")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_url_targets_correct_table(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"name": "Cleanup", "script": "gs.log();"},
        )
        url = mock_req.call_args[0][1]
        self.assertIn("sysauto_script", url)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_sends_name_and_script_in_body(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"name": "Cleanup", "script": "gs.log();"},
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["name"], "Cleanup")
        self.assertEqual(body["script"], "gs.log();")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_active_true_serialised_as_string(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"name": "Cleanup", "script": "gs.log();", "active": True},
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["active"], "true")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_active_false_serialised_as_string(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"name": "Cleanup", "script": "gs.log();", "active": False},
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["active"], "false")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_optional_fields_sent_when_provided(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {
                "name": "Weekly Report",
                "script": "gs.log();",
                "run_type": "weekly",
                "run_time": "08:00:00",
                "run_dayofweek": "2",
                "run_as": "admin",
            },
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["run_type"], "weekly")
        self.assertEqual(body["run_time"], "08:00:00")
        self.assertEqual(body["run_dayofweek"], "2")
        self.assertEqual(body["run_as"], "admin")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_none_fields_excluded_from_body(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"name": "Cleanup", "script": "gs.log();"},
        )
        body = mock_req.call_args[1]["json"]
        self.assertNotIn("run_type", body)
        self.assertNotIn("run_period", body)
        self.assertNotIn("run_at", body)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"name": "Cleanup", "script": "gs.log();"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error creating scheduled job", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"name": "Cleanup", "script": "gs.log();"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error creating scheduled job", result["message"])

    def test_missing_required_name_returns_failure(self):
        result = create_scheduled_job(
            _make_auth_manager(), _make_config(), {"script": "gs.log();"}
        )
        self.assertFalse(result["success"])

    def test_missing_required_script_returns_failure(self):
        result = create_scheduled_job(
            _make_auth_manager(), _make_config(), {"name": "Cleanup"}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._get_instance_url")
    def test_missing_instance_url_returns_failure(self, mock_url):
        mock_url.return_value = None
        result = create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"name": "Cleanup", "script": "gs.log();"},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._get_headers")
    @patch("servicenow_mcp.tools.scheduled_job_tools._get_instance_url")
    def test_missing_headers_returns_failure(self, mock_url, mock_headers):
        mock_url.return_value = "https://dev.service-now.com"
        mock_headers.return_value = None
        result = create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"name": "Cleanup", "script": "gs.log();"},
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_periodically_run_period_field(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {
                "name": "Periodic Check",
                "script": "gs.log();",
                "run_type": "periodically",
                "run_period": "3600",
            },
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["run_type"], "periodically")
        self.assertEqual(body["run_period"], "3600")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_once_run_at_field(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        create_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {
                "name": "One-Time Job",
                "script": "gs.log();",
                "run_type": "once",
                "run_at": "2026-08-01 09:00:00",
            },
        )
        body = mock_req.call_args[1]["json"]
        self.assertEqual(body["run_at"], "2026-08-01 09:00:00")


# ---------------------------------------------------------------------------
# update_scheduled_job
# ---------------------------------------------------------------------------

class TestUpdateScheduledJob(unittest.TestCase):
    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_success_by_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        result = update_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"job_id": FAKE_SYS_ID, "active": False},
        )
        self.assertTrue(result["success"])
        self.assertIn("job", result)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_success_by_name(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        patch_resp = _make_response(200, {"result": FAKE_JOB})
        mock_req.side_effect = [resolve_resp, patch_resp]
        result = update_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"job_id": "Nightly Cleanup", "active": True},
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_uses_patch_method(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        update_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"job_id": FAKE_SYS_ID, "name": "New Name"},
        )
        patch_call = mock_req.call_args_list[-1]
        self.assertEqual(patch_call[0][0], "PATCH")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_url_includes_sys_id(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        update_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"job_id": FAKE_SYS_ID, "name": "New Name"},
        )
        patch_call_url = mock_req.call_args_list[-1][0][1]
        self.assertIn(FAKE_SYS_ID, patch_call_url)
        self.assertIn("sysauto_script", patch_call_url)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_active_false_serialised_as_string(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        update_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"job_id": FAKE_SYS_ID, "active": False},
        )
        body = mock_req.call_args_list[-1][1]["json"]
        self.assertEqual(body["active"], "false")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_active_true_serialised_as_string(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        update_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"job_id": FAKE_SYS_ID, "active": True},
        )
        body = mock_req.call_args_list[-1][1]["json"]
        self.assertEqual(body["active"], "true")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_empty_body_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        result = update_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"job_id": FAKE_SYS_ID},
        )
        self.assertFalse(result["success"])
        self.assertIn("No fields", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_job_not_found_by_name_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = update_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"job_id": "Unknown Job", "name": "New Name"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_404_response_returns_failure(self, mock_req):
        patch_resp = _make_response(404, {})
        patch_resp.raise_for_status = MagicMock()
        mock_req.return_value = patch_resp
        result = update_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"job_id": FAKE_SYS_ID, "name": "New Name"},
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = update_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"job_id": FAKE_SYS_ID, "name": "New Name"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating scheduled job", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = update_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {"job_id": FAKE_SYS_ID, "name": "New Name"},
        )
        self.assertFalse(result["success"])
        self.assertIn("Error updating scheduled job", result["message"])

    def test_missing_job_id_returns_failure(self):
        result = update_scheduled_job(
            _make_auth_manager(), _make_config(), {"name": "New Name"}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._get_instance_url")
    def test_missing_instance_url_returns_failure(self, mock_url):
        mock_url.return_value = None
        result = update_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID, "name": "X"}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._get_headers")
    @patch("servicenow_mcp.tools.scheduled_job_tools._get_instance_url")
    def test_missing_headers_returns_failure(self, mock_url, mock_headers):
        mock_url.return_value = "https://dev.service-now.com"
        mock_headers.return_value = None
        result = update_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID, "name": "X"}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_multiple_fields_sent_in_body(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": FAKE_JOB})
        update_scheduled_job(
            _make_auth_manager(),
            _make_config(),
            {
                "job_id": FAKE_SYS_ID,
                "name": "New Name",
                "run_type": "weekly",
                "run_dayofweek": "3",
            },
        )
        body = mock_req.call_args_list[-1][1]["json"]
        self.assertEqual(body["name"], "New Name")
        self.assertEqual(body["run_type"], "weekly")
        self.assertEqual(body["run_dayofweek"], "3")


# ---------------------------------------------------------------------------
# delete_scheduled_job
# ---------------------------------------------------------------------------

class TestDeleteScheduledJob(unittest.TestCase):
    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_success_by_sys_id_204(self, mock_req):
        delete_resp = _make_response(204, {})
        delete_resp.raise_for_status = MagicMock()
        mock_req.return_value = delete_resp
        result = delete_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID}
        )
        self.assertTrue(result["success"])
        self.assertIn("deleted", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_success_by_sys_id_200(self, mock_req):
        delete_resp = _make_response(200, {})
        delete_resp.raise_for_status = MagicMock()
        mock_req.return_value = delete_resp
        result = delete_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID}
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_success_by_name(self, mock_req):
        resolve_resp = _make_response(200, {"result": [{"sys_id": FAKE_SYS_ID}]})
        delete_resp = _make_response(204, {})
        delete_resp.raise_for_status = MagicMock()
        mock_req.side_effect = [resolve_resp, delete_resp]
        result = delete_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": "Nightly Cleanup"}
        )
        self.assertTrue(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_uses_delete_method(self, mock_req):
        delete_resp = _make_response(204, {})
        delete_resp.raise_for_status = MagicMock()
        mock_req.return_value = delete_resp
        delete_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID}
        )
        delete_call = mock_req.call_args_list[-1]
        self.assertEqual(delete_call[0][0], "DELETE")

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_url_includes_sys_id(self, mock_req):
        delete_resp = _make_response(204, {})
        delete_resp.raise_for_status = MagicMock()
        mock_req.return_value = delete_resp
        delete_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID}
        )
        url = mock_req.call_args_list[-1][0][1]
        self.assertIn(FAKE_SYS_ID, url)
        self.assertIn("sysauto_script", url)

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_404_returns_failure(self, mock_req):
        not_found = _make_response(404, {})
        not_found.raise_for_status = MagicMock()
        mock_req.return_value = not_found
        result = delete_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_job_not_found_by_name_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(200, {"result": []})
        result = delete_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": "Unknown Job"}
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_http_error_returns_failure(self, mock_req):
        mock_req.return_value = _make_response(500, {})
        result = delete_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error deleting scheduled job", result["message"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_connection_error_returns_failure(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = delete_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])
        self.assertIn("Error deleting scheduled job", result["message"])

    def test_missing_job_id_returns_failure(self):
        result = delete_scheduled_job(
            _make_auth_manager(), _make_config(), {}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._get_instance_url")
    def test_missing_instance_url_returns_failure(self, mock_url):
        mock_url.return_value = None
        result = delete_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._get_headers")
    @patch("servicenow_mcp.tools.scheduled_job_tools._get_instance_url")
    def test_missing_headers_returns_failure(self, mock_url, mock_headers):
        mock_url.return_value = "https://dev.service-now.com"
        mock_headers.return_value = None
        result = delete_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID}
        )
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.scheduled_job_tools._make_request")
    def test_message_contains_job_id(self, mock_req):
        delete_resp = _make_response(204, {})
        delete_resp.raise_for_status = MagicMock()
        mock_req.return_value = delete_resp
        result = delete_scheduled_job(
            _make_auth_manager(), _make_config(), {"job_id": FAKE_SYS_ID}
        )
        self.assertIn(FAKE_SYS_ID, result["message"])


if __name__ == "__main__":
    unittest.main()
