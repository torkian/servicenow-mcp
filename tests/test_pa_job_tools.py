"""Tests for PA job management tools in pa_tools.py (list_pa_jobs, get_pa_job, trigger_pa_collection)."""

import pytest
import requests
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.pa_tools import (
    GetPAJobParams,
    ListPAJobsParams,
    TriggerPACollectionParams,
    _format_pa_job,
    _resolve_pa_job_sys_id,
    get_pa_job,
    list_pa_jobs,
    trigger_pa_collection,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_manager():
    am = MagicMock()
    am.instance_url = "https://instance.service-now.com"
    am.get_headers.return_value = {"Authorization": "Bearer token"}
    return am


@pytest.fixture
def server_config():
    sc = MagicMock()
    sc.instance_url = None
    return sc


SYS_ID_32 = "a" * 32
IND_SYS_ID = "b" * 32

RAW_JOB = {
    "sys_id": SYS_ID_32,
    "name": "Daily Incident Collection",
    "active": "true",
    "run_type": "daily",
    "run_time": "02:00:00",
    "last_run_time": "2026-09-06 02:00:00",
    "next_run_time": "2026-09-07 02:00:00",
    "last_run_status": "success",
    "indicator": {"display_value": "Incident Count", "value": IND_SYS_ID},
    "breakdown": {"display_value": "Priority", "value": "c" * 32},
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-09-06 02:01:00",
}


# ---------------------------------------------------------------------------
# _format_pa_job
# ---------------------------------------------------------------------------


class TestFormatPAJob:
    def test_basic_fields(self):
        result = _format_pa_job(RAW_JOB)
        assert result["sys_id"] == SYS_ID_32
        assert result["name"] == "Daily Incident Collection"
        assert result["active"] == "true"
        assert result["run_type"] == "daily"
        assert result["run_time"] == "02:00:00"
        assert result["last_run_time"] == "2026-09-06 02:00:00"
        assert result["next_run_time"] == "2026-09-07 02:00:00"
        assert result["last_run_status"] == "success"
        assert result["created_on"] == "2026-01-01 00:00:00"
        assert result["updated_on"] == "2026-09-06 02:01:00"

    def test_reference_fields_extracted(self):
        result = _format_pa_job(RAW_JOB)
        assert result["indicator"] == "Incident Count"
        assert result["breakdown"] == "Priority"

    def test_string_reference_fields(self):
        rec = {**RAW_JOB, "indicator": "Incident Count", "breakdown": "Priority"}
        result = _format_pa_job(rec)
        assert result["indicator"] == "Incident Count"
        assert result["breakdown"] == "Priority"

    def test_missing_fields_return_none(self):
        result = _format_pa_job({})
        assert result["sys_id"] is None
        assert result["name"] is None
        assert result["indicator"] is None
        assert result["breakdown"] is None
        assert result["last_run_status"] is None


# ---------------------------------------------------------------------------
# _resolve_pa_job_sys_id
# ---------------------------------------------------------------------------


class TestResolvePAJobSysId:
    def test_hex_sys_id_returned_directly(self):
        result = _resolve_pa_job_sys_id(SYS_ID_32, "https://x.com", {})
        assert result == SYS_ID_32

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_resolved_to_sys_id(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        mock_req.return_value = mock_resp
        result = _resolve_pa_job_sys_id("Daily Incident Collection", "https://x.com", {})
        assert result == SYS_ID_32

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_not_found_returns_none(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = _resolve_pa_job_sys_id("Unknown Job", "https://x.com", {})
        assert result is None

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception_returns_none(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("fail")
        result = _resolve_pa_job_sys_id("Some Job", "https://x.com", {})
        assert result is None


# ---------------------------------------------------------------------------
# list_pa_jobs
# ---------------------------------------------------------------------------


class TestListPAJobs:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_returns_jobs(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_JOB]}
        mock_req.return_value = mock_resp
        result = list_pa_jobs(auth_manager, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is True
        assert len(result["jobs"]) == 1
        assert result["jobs"][0]["name"] == "Daily Incident Collection"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_filter(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_jobs(
            auth_manager, server_config, {"name": "Daily", "limit": 10, "offset": 0}
        )
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "nameLIKEDaily" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_active_filter_true(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_jobs(
            auth_manager, server_config, {"active": True, "limit": 10, "offset": 0}
        )
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "active=true" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_active_filter_false(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_jobs(
            auth_manager, server_config, {"active": False, "limit": 10, "offset": 0}
        )
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "active=false" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_run_type_filter(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_jobs(
            auth_manager, server_config, {"run_type": "daily", "limit": 10, "offset": 0}
        )
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "run_type=daily" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_last_run_status_filter(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_jobs(
            auth_manager, server_config, {"last_run_status": "failed", "limit": 10, "offset": 0}
        )
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "last_run_status=failed" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_indicator_id_filter_by_sys_id(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_jobs(
            auth_manager, server_config,
            {"indicator_id": IND_SYS_ID, "limit": 10, "offset": 0}
        )
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert f"indicator={IND_SYS_ID}" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_indicator_id_name_not_found(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_jobs(
            auth_manager, server_config,
            {"indicator_id": "Nonexistent Indicator", "limit": 10, "offset": 0}
        )
        assert result["success"] is False
        assert "PA indicator not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": {"message": "Server error"}}
        http_err = requests.exceptions.HTTPError(response=mock_resp)
        mock_req.return_value = MagicMock()
        mock_req.return_value.raise_for_status.side_effect = http_err
        result = list_pa_jobs(auth_manager, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("fail")
        result = list_pa_jobs(auth_manager, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is False
        assert "fail" in result["message"]

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        am.get_headers.return_value = {"Authorization": "Bearer token"}
        sc = MagicMock()
        sc.instance_url = None
        result = list_pa_jobs(am, sc, {"limit": 10, "offset": 0})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, auth_manager, server_config):
        auth_manager.get_headers.return_value = None
        result = list_pa_jobs(auth_manager, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is False
        assert "get_headers" in result["message"]


# ---------------------------------------------------------------------------
# get_pa_job
# ---------------------------------------------------------------------------


class TestGetPAJob:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_returns_job_by_sys_id(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_JOB}
        mock_req.return_value = mock_resp
        result = get_pa_job(auth_manager, server_config, {"job_id": SYS_ID_32})
        assert result["success"] is True
        assert result["job"]["name"] == "Daily Incident Collection"
        assert result["job"]["run_type"] == "daily"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_returns_job_by_name(self, mock_req, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        get_resp = MagicMock()
        get_resp.json.return_value = {"result": RAW_JOB}
        mock_req.side_effect = [resolve_resp, get_resp]
        result = get_pa_job(
            auth_manager, server_config, {"job_id": "Daily Incident Collection"}
        )
        assert result["success"] is True
        assert result["job"]["sys_id"] == SYS_ID_32

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_job_not_found_by_name(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = get_pa_job(auth_manager, server_config, {"job_id": "No Such Job"})
        assert result["success"] is False
        assert "PA job not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_empty_result(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": None}
        mock_req.return_value = mock_resp
        result = get_pa_job(auth_manager, server_config, {"job_id": SYS_ID_32})
        assert result["success"] is False
        assert "PA job not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_404_response(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        http_err = requests.exceptions.HTTPError(response=mock_resp)
        mock_req.return_value = MagicMock()
        mock_req.return_value.raise_for_status.side_effect = http_err
        result = get_pa_job(auth_manager, server_config, {"job_id": SYS_ID_32})
        assert result["success"] is False
        assert "PA job not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error_non_404(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.json.return_value = {"error": {"message": "Service unavailable"}}
        http_err = requests.exceptions.HTTPError(response=mock_resp)
        mock_req.return_value = MagicMock()
        mock_req.return_value.raise_for_status.side_effect = http_err
        result = get_pa_job(auth_manager, server_config, {"job_id": SYS_ID_32})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.Timeout("timed out")
        result = get_pa_job(auth_manager, server_config, {"job_id": SYS_ID_32})
        assert result["success"] is False
        assert "timed out" in result["message"]

    def test_no_instance_url(self):
        am = MagicMock()
        am.instance_url = None
        sc = MagicMock()
        sc.instance_url = None
        result = get_pa_job(am, sc, {"job_id": SYS_ID_32})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, auth_manager, server_config):
        auth_manager.get_headers.return_value = None
        result = get_pa_job(auth_manager, server_config, {"job_id": SYS_ID_32})
        assert result["success"] is False
        assert "get_headers" in result["message"]


# ---------------------------------------------------------------------------
# trigger_pa_collection
# ---------------------------------------------------------------------------


class TestTriggerPACollection:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_trigger_by_sys_id(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"sys_id": SYS_ID_32}}
        mock_req.return_value = mock_resp
        result = trigger_pa_collection(auth_manager, server_config, {"job_id": SYS_ID_32})
        assert result["success"] is True
        assert result["job_sys_id"] == SYS_ID_32
        assert "triggered successfully" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_trigger_by_name(self, mock_req, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        patch_resp = MagicMock()
        patch_resp.json.return_value = {"result": {"sys_id": SYS_ID_32}}
        mock_req.side_effect = [resolve_resp, patch_resp]
        result = trigger_pa_collection(
            auth_manager, server_config, {"job_id": "Daily Incident Collection"}
        )
        assert result["success"] is True
        assert result["job_sys_id"] == SYS_ID_32

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_sends_run_now_patch(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {}}
        mock_req.return_value = mock_resp
        trigger_pa_collection(auth_manager, server_config, {"job_id": SYS_ID_32})
        call_kwargs = mock_req.call_args
        assert call_kwargs[0][0] == "PATCH"
        assert call_kwargs[1]["json"] == {"run_now": "true"}

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_job_not_found_by_name(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = trigger_pa_collection(
            auth_manager, server_config, {"job_id": "Nonexistent Job"}
        )
        assert result["success"] is False
        assert "PA job not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_404_response(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        http_err = requests.exceptions.HTTPError(response=mock_resp)
        mock_req.return_value = MagicMock()
        mock_req.return_value.raise_for_status.side_effect = http_err
        result = trigger_pa_collection(auth_manager, server_config, {"job_id": SYS_ID_32})
        assert result["success"] is False
        assert "PA job not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error_non_404(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": {"message": "Internal error"}}
        http_err = requests.exceptions.HTTPError(response=mock_resp)
        mock_req.return_value = MagicMock()
        mock_req.return_value.raise_for_status.side_effect = http_err
        result = trigger_pa_collection(auth_manager, server_config, {"job_id": SYS_ID_32})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("network down")
        result = trigger_pa_collection(auth_manager, server_config, {"job_id": SYS_ID_32})
        assert result["success"] is False
        assert "network down" in result["message"]

    def test_no_instance_url(self):
        am = MagicMock()
        am.instance_url = None
        sc = MagicMock()
        sc.instance_url = None
        result = trigger_pa_collection(am, sc, {"job_id": SYS_ID_32})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, auth_manager, server_config):
        auth_manager.get_headers.return_value = None
        result = trigger_pa_collection(auth_manager, server_config, {"job_id": SYS_ID_32})
        assert result["success"] is False
        assert "get_headers" in result["message"]


# ---------------------------------------------------------------------------
# Parameter model validation
# ---------------------------------------------------------------------------


class TestPAJobParams:
    def test_list_defaults(self):
        p = ListPAJobsParams()
        assert p.limit == 20
        assert p.offset == 0
        assert p.name is None
        assert p.active is None
        assert p.run_type is None
        assert p.last_run_status is None
        assert p.indicator_id is None

    def test_list_with_all_fields(self):
        p = ListPAJobsParams(
            limit=5,
            offset=10,
            name="Daily",
            active=True,
            run_type="daily",
            last_run_status="success",
            indicator_id=IND_SYS_ID,
        )
        assert p.limit == 5
        assert p.offset == 10
        assert p.name == "Daily"
        assert p.active is True
        assert p.run_type == "daily"
        assert p.last_run_status == "success"
        assert p.indicator_id == IND_SYS_ID

    def test_get_requires_job_id(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GetPAJobParams()

    def test_get_with_sys_id(self):
        p = GetPAJobParams(job_id=SYS_ID_32)
        assert p.job_id == SYS_ID_32

    def test_get_with_name(self):
        p = GetPAJobParams(job_id="Daily Incident Collection")
        assert p.job_id == "Daily Incident Collection"

    def test_trigger_requires_job_id(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TriggerPACollectionParams()

    def test_trigger_with_sys_id(self):
        p = TriggerPACollectionParams(job_id=SYS_ID_32)
        assert p.job_id == SYS_ID_32

    def test_trigger_with_name(self):
        p = TriggerPACollectionParams(job_id="Daily Incident Collection")
        assert p.job_id == "Daily Incident Collection"
