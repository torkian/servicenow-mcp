"""Tests for pa_tools.py (Performance Analytics pa_indicator and pa_score tables)."""

import pytest
import requests
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.pa_tools import (
    CreatePAIndicatorParams,
    GetPAIndicatorParams,
    ListPAIndicatorsParams,
    ListPAScoresParams,
    _format_pa_indicator,
    _format_pa_score,
    _resolve_pa_indicator_sys_id,
    create_pa_indicator,
    get_pa_indicator,
    list_pa_indicators,
    list_pa_scores,
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

RAW_INDICATOR = {
    "sys_id": SYS_ID_32,
    "name": "Incident Count",
    "description": "Total open incidents",
    "indicator_group": {"display_value": "ITSM", "value": "b" * 32},
    "unit": {"display_value": "Count", "value": "c" * 32},
    "direction": "2",  # minimise
    "frequency": "daily",
    "active": "true",
    "formula": "COUNT(active=true)",
    "condition": "active=true",
    "table": {"display_value": "Incident", "value": "incident"},
    "sys_created_on": "2024-01-01 00:00:00",
    "sys_updated_on": "2024-06-01 00:00:00",
}

RAW_SCORE = {
    "sys_id": "s" * 32,
    "indicator": {"display_value": "Incident Count", "value": SYS_ID_32},
    "period": {"display_value": "2024-06-15", "value": "p" * 32},
    "value": "42",
    "breakdownvalue": {"display_value": "High Priority", "value": "bv" * 16},
    "sys_created_on": "2024-06-16 00:00:00",
}


# ---------------------------------------------------------------------------
# _format_pa_indicator
# ---------------------------------------------------------------------------


class TestFormatPAIndicator:
    def test_basic_fields(self):
        result = _format_pa_indicator(RAW_INDICATOR)
        assert result["sys_id"] == SYS_ID_32
        assert result["name"] == "Incident Count"
        assert result["description"] == "Total open incidents"
        assert result["direction"] == "2"
        assert result["frequency"] == "daily"
        assert result["active"] == "true"
        assert result["formula"] == "COUNT(active=true)"
        assert result["condition"] == "active=true"
        assert result["created_on"] == "2024-01-01 00:00:00"
        assert result["updated_on"] == "2024-06-01 00:00:00"

    def test_reference_fields_extracted(self):
        result = _format_pa_indicator(RAW_INDICATOR)
        assert result["indicator_group"] == "ITSM"
        assert result["unit"] == "Count"
        assert result["table"] == "Incident"

    def test_string_reference_fields(self):
        rec = {**RAW_INDICATOR, "indicator_group": "My Group", "unit": "pct", "table": "problem"}
        result = _format_pa_indicator(rec)
        assert result["indicator_group"] == "My Group"
        assert result["unit"] == "pct"
        assert result["table"] == "problem"

    def test_missing_fields_return_none(self):
        result = _format_pa_indicator({})
        assert result["sys_id"] is None
        assert result["name"] is None
        assert result["indicator_group"] is None


# ---------------------------------------------------------------------------
# _format_pa_score
# ---------------------------------------------------------------------------


class TestFormatPAScore:
    def test_basic_fields(self):
        result = _format_pa_score(RAW_SCORE)
        assert result["sys_id"] == "s" * 32
        assert result["value"] == "42"
        assert result["created_on"] == "2024-06-16 00:00:00"

    def test_reference_fields_extracted(self):
        result = _format_pa_score(RAW_SCORE)
        assert result["indicator"] == "Incident Count"
        assert result["period"] == "2024-06-15"
        assert result["breakdown_value"] == "High Priority"

    def test_string_indicator(self):
        rec = {**RAW_SCORE, "indicator": "Incident Count"}
        result = _format_pa_score(rec)
        assert result["indicator"] == "Incident Count"

    def test_missing_fields_return_none(self):
        result = _format_pa_score({})
        assert result["sys_id"] is None
        assert result["value"] is None


# ---------------------------------------------------------------------------
# _resolve_pa_indicator_sys_id
# ---------------------------------------------------------------------------


class TestResolvePAIndicatorSysId:
    def test_hex_sys_id_returned_directly(self):
        result = _resolve_pa_indicator_sys_id(SYS_ID_32, "https://x.com", {})
        assert result == SYS_ID_32

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_resolved_to_sys_id(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        mock_req.return_value = mock_resp
        result = _resolve_pa_indicator_sys_id("Incident Count", "https://x.com", {})
        assert result == SYS_ID_32

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_not_found_returns_none(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = _resolve_pa_indicator_sys_id("Unknown", "https://x.com", {})
        assert result is None

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception_returns_none(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("fail")
        result = _resolve_pa_indicator_sys_id("Indicator", "https://x.com", {})
        assert result is None


# ---------------------------------------------------------------------------
# list_pa_indicators
# ---------------------------------------------------------------------------


class TestListPAIndicators:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_returns_indicators(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_INDICATOR]}
        mock_req.return_value = mock_resp
        result = list_pa_indicators(auth_manager, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is True
        assert len(result["indicators"]) == 1
        assert result["indicators"][0]["name"] == "Incident Count"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_filter(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_indicators(
            auth_manager, server_config, {"name": "Incident", "limit": 10, "offset": 0}
        )
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "nameLIKEIncident" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_active_filter_true(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        list_pa_indicators(
            auth_manager, server_config, {"active": True, "limit": 10, "offset": 0}
        )
        call_params = mock_req.call_args[1]["params"]
        assert "active=true" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_active_filter_false(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        list_pa_indicators(
            auth_manager, server_config, {"active": False, "limit": 10, "offset": 0}
        )
        call_params = mock_req.call_args[1]["params"]
        assert "active=false" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_frequency_filter(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        list_pa_indicators(
            auth_manager, server_config, {"frequency": "daily", "limit": 10, "offset": 0}
        )
        call_params = mock_req.call_args[1]["params"]
        assert "frequency=daily" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_indicator_group_filter(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        list_pa_indicators(
            auth_manager, server_config, {"indicator_group": "ITSM", "limit": 10, "offset": 0}
        )
        call_params = mock_req.call_args[1]["params"]
        assert "indicator_group.nameLIKEITSM" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": {"message": "Server error", "detail": "internal"}}
        http_err = requests.exceptions.HTTPError(response=mock_resp)
        mock_req.return_value = MagicMock()
        mock_req.return_value.raise_for_status.side_effect = http_err
        result = list_pa_indicators(auth_manager, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_network_error(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("down")
        result = list_pa_indicators(auth_manager, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is False
        assert "down" in result["message"]

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        server_config.instance_url = None
        result = list_pa_indicators(am, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, server_config):
        am = MagicMock()
        am.instance_url = "https://x.com"
        am.get_headers.return_value = None
        server_config.instance_url = None
        result = list_pa_indicators(am, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is False
        assert "headers" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_has_more_pagination(self, mock_req, auth_manager, server_config):
        indicators = [dict(RAW_INDICATOR, name=f"Indicator {i}") for i in range(5)]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": indicators}
        mock_req.return_value = mock_resp
        result = list_pa_indicators(auth_manager, server_config, {"limit": 5, "offset": 0})
        assert result["has_more"] is True
        assert result["next_offset"] == 5

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_invalid_params(self, mock_req, auth_manager, server_config):
        result = list_pa_indicators(auth_manager, server_config, {"limit": "bad"})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# get_pa_indicator
# ---------------------------------------------------------------------------


class TestGetPAIndicator:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_get_by_sys_id(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_INDICATOR}
        mock_req.return_value = mock_resp
        result = get_pa_indicator(auth_manager, server_config, {"indicator_id": SYS_ID_32})
        assert result["success"] is True
        assert result["indicator"]["name"] == "Incident Count"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_get_by_name(self, mock_req, auth_manager, server_config):
        # First call: resolve name, second call: fetch record
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        fetch_resp = MagicMock()
        fetch_resp.json.return_value = {"result": RAW_INDICATOR}
        mock_req.side_effect = [resolve_resp, fetch_resp]
        result = get_pa_indicator(
            auth_manager, server_config, {"indicator_id": "Incident Count"}
        )
        assert result["success"] is True
        assert result["indicator"]["sys_id"] == SYS_ID_32

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_not_found(self, mock_req, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": []}
        mock_req.return_value = resolve_resp
        result = get_pa_indicator(auth_manager, server_config, {"indicator_id": "Unknown"})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_404_response(self, mock_req, auth_manager, server_config):
        mock_resp_404 = MagicMock()
        mock_resp_404.status_code = 404
        http_err = requests.exceptions.HTTPError(response=mock_resp_404)
        fetch_resp = MagicMock()
        fetch_resp.raise_for_status.side_effect = http_err
        mock_req.return_value = fetch_resp
        result = get_pa_indicator(auth_manager, server_config, {"indicator_id": SYS_ID_32})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_empty_result(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": None}
        mock_req.return_value = mock_resp
        result = get_pa_indicator(auth_manager, server_config, {"indicator_id": SYS_ID_32})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error_non_404(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": {"message": "fail", "detail": ""}}
        http_err = requests.exceptions.HTTPError(response=mock_resp)
        fetch_resp = MagicMock()
        fetch_resp.raise_for_status.side_effect = http_err
        mock_req.return_value = fetch_resp
        result = get_pa_indicator(auth_manager, server_config, {"indicator_id": SYS_ID_32})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_network_error(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("down")
        result = get_pa_indicator(auth_manager, server_config, {"indicator_id": SYS_ID_32})
        assert result["success"] is False

    def test_missing_indicator_id(self, auth_manager, server_config):
        result = get_pa_indicator(auth_manager, server_config, {})
        assert result["success"] is False

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        server_config.instance_url = None
        result = get_pa_indicator(am, server_config, {"indicator_id": SYS_ID_32})
        assert result["success"] is False

    def test_no_headers(self, server_config):
        am = MagicMock()
        am.instance_url = "https://x.com"
        am.get_headers.return_value = None
        server_config.instance_url = None
        result = get_pa_indicator(am, server_config, {"indicator_id": SYS_ID_32})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# list_pa_scores
# ---------------------------------------------------------------------------


class TestListPAScores:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_returns_scores(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_SCORE]}
        mock_req.return_value = mock_resp
        result = list_pa_scores(auth_manager, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is True
        assert len(result["scores"]) == 1
        assert result["scores"][0]["value"] == "42"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_indicator_id_filter_sys_id(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_SCORE]}
        mock_req.return_value = mock_resp
        result = list_pa_scores(
            auth_manager,
            server_config,
            {"indicator_id": SYS_ID_32, "limit": 10, "offset": 0},
        )
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert f"indicator={SYS_ID_32}" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_indicator_id_filter_name(self, mock_req, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        scores_resp = MagicMock()
        scores_resp.json.return_value = {"result": [RAW_SCORE]}
        mock_req.side_effect = [resolve_resp, scores_resp]
        result = list_pa_scores(
            auth_manager,
            server_config,
            {"indicator_id": "Incident Count", "limit": 10, "offset": 0},
        )
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert f"indicator={SYS_ID_32}" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_indicator_id_name_not_found(self, mock_req, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": []}
        mock_req.return_value = resolve_resp
        result = list_pa_scores(
            auth_manager,
            server_config,
            {"indicator_id": "Unknown Indicator", "limit": 10, "offset": 0},
        )
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_period_start_filter(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        list_pa_scores(
            auth_manager,
            server_config,
            {"period_start": "2024-01-01", "limit": 10, "offset": 0},
        )
        call_params = mock_req.call_args[1]["params"]
        assert "sys_created_on>=2024-01-01" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_period_end_filter(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        list_pa_scores(
            auth_manager,
            server_config,
            {"period_end": "2024-12-31", "limit": 10, "offset": 0},
        )
        call_params = mock_req.call_args[1]["params"]
        assert "sys_created_on<=2024-12-31" in call_params.get("sysparm_query", "")

    def test_invalid_period_start(self, auth_manager, server_config):
        result = list_pa_scores(
            auth_manager, server_config, {"period_start": "not-a-date", "limit": 10, "offset": 0}
        )
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": {"message": "Error", "detail": ""}}
        http_err = requests.exceptions.HTTPError(response=mock_resp)
        mock_req.return_value = MagicMock()
        mock_req.return_value.raise_for_status.side_effect = http_err
        result = list_pa_scores(auth_manager, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_network_error(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("down")
        result = list_pa_scores(auth_manager, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is False
        assert "down" in result["message"]

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        server_config.instance_url = None
        result = list_pa_scores(am, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is False

    def test_no_headers(self, server_config):
        am = MagicMock()
        am.instance_url = "https://x.com"
        am.get_headers.return_value = None
        server_config.instance_url = None
        result = list_pa_scores(am, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_has_more_pagination(self, mock_req, auth_manager, server_config):
        scores = [dict(RAW_SCORE, sys_id=f"s{i}" * 16) for i in range(5)]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": scores}
        mock_req.return_value = mock_resp
        result = list_pa_scores(auth_manager, server_config, {"limit": 5, "offset": 0})
        assert result["has_more"] is True
        assert result["next_offset"] == 5

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_no_filters(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_SCORE]}
        mock_req.return_value = mock_resp
        result = list_pa_scores(auth_manager, server_config, {"limit": 20, "offset": 0})
        assert result["success"] is True
        # No filter means empty query
        call_params = mock_req.call_args[1]["params"]
        assert call_params.get("sysparm_query", "") == ""


# ---------------------------------------------------------------------------
# Param model validation
# ---------------------------------------------------------------------------


class TestParamModels:
    def test_list_pa_indicators_defaults(self):
        p = ListPAIndicatorsParams()
        assert p.limit == 20
        assert p.offset == 0
        assert p.name is None
        assert p.active is None
        assert p.frequency is None
        assert p.indicator_group is None

    def test_get_pa_indicator_requires_indicator_id(self):
        import pydantic
        with pytest.raises((pydantic.ValidationError, Exception)):
            GetPAIndicatorParams()

    def test_list_pa_scores_date_validation_valid(self):
        p = ListPAScoresParams(period_start="2024-01-01", period_end="2024-12-31")
        assert p.period_start == "2024-01-01"
        assert p.period_end == "2024-12-31"

    def test_list_pa_scores_date_validation_invalid(self):
        import pydantic
        with pytest.raises((pydantic.ValidationError, ValueError)):
            ListPAScoresParams(period_start="01-01-2024")

    def test_list_pa_scores_defaults(self):
        p = ListPAScoresParams()
        assert p.limit == 20
        assert p.offset == 0
        assert p.indicator_id is None
        assert p.period_start is None
        assert p.period_end is None


# ---------------------------------------------------------------------------
# create_pa_indicator tests
# ---------------------------------------------------------------------------

RAW_CREATED_INDICATOR = {
    "sys_id": "c" * 32,
    "name": "New KPI",
    "description": "A test KPI",
    "indicator_group": {"display_value": "ITSM", "value": "b" * 32},
    "unit": {"display_value": "Count", "value": "u" * 32},
    "direction": "1",
    "frequency": "daily",
    "active": "true",
    "formula": "count",
    "condition": "active=true",
    "table": "incident",
    "sys_created_on": "2024-01-15 10:00:00",
    "sys_updated_on": "2024-01-15 10:00:00",
}


class TestCreatePAIndicator:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_success_minimal(self, mock_req, auth_manager, server_config):
        """Create with only the required name field."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_CREATED_INDICATOR}
        mock_req.return_value = mock_resp
        result = create_pa_indicator(auth_manager, server_config, {"name": "New KPI"})
        assert result["success"] is True
        assert result["indicator"]["name"] == "New KPI"
        assert "created successfully" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_success_all_fields(self, mock_req, auth_manager, server_config):
        """Create with all optional fields supplied."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_CREATED_INDICATOR}
        mock_req.return_value = mock_resp
        result = create_pa_indicator(
            auth_manager,
            server_config,
            {
                "name": "New KPI",
                "description": "A test KPI",
                "table": "incident",
                "condition": "active=true",
                "formula": "count",
                "frequency": "daily",
                "direction": "1",
                "active": True,
                "unit": "u" * 32,
                "indicator_group": "b" * 32,
            },
        )
        assert result["success"] is True
        # Verify body was posted with all fields
        call_json = mock_req.call_args[1]["json"]
        assert call_json["name"] == "New KPI"
        assert call_json["table"] == "incident"
        assert call_json["formula"] == "count"
        assert call_json["frequency"] == "daily"
        assert call_json["direction"] == "1"
        assert call_json["active"] == "true"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_direction_alias_maximize(self, mock_req, auth_manager, server_config):
        """Direction alias 'maximize' is normalised to '1'."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_CREATED_INDICATOR}
        mock_req.return_value = mock_resp
        create_pa_indicator(
            auth_manager, server_config, {"name": "KPI", "direction": "maximize"}
        )
        call_json = mock_req.call_args[1]["json"]
        assert call_json["direction"] == "1"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_direction_alias_minimize(self, mock_req, auth_manager, server_config):
        """Direction alias 'minimize' is normalised to '2'."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_CREATED_INDICATOR}
        mock_req.return_value = mock_resp
        create_pa_indicator(
            auth_manager, server_config, {"name": "KPI", "direction": "minimize"}
        )
        call_json = mock_req.call_args[1]["json"]
        assert call_json["direction"] == "2"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_direction_alias_minimise(self, mock_req, auth_manager, server_config):
        """Direction alias 'minimise' (British) is normalised to '2'."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_CREATED_INDICATOR}
        mock_req.return_value = mock_resp
        create_pa_indicator(
            auth_manager, server_config, {"name": "KPI", "direction": "minimise"}
        )
        call_json = mock_req.call_args[1]["json"]
        assert call_json["direction"] == "2"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_active_false_serialised_as_string(self, mock_req, auth_manager, server_config):
        """active=False is sent as the string 'false'."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_CREATED_INDICATOR}
        mock_req.return_value = mock_resp
        create_pa_indicator(auth_manager, server_config, {"name": "KPI", "active": False})
        call_json = mock_req.call_args[1]["json"]
        assert call_json["active"] == "false"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {}
        mock_req.return_value = mock_resp
        http_err = requests.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
        result = create_pa_indicator(auth_manager, server_config, {"name": "KPI"})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_network_error(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("offline")
        result = create_pa_indicator(auth_manager, server_config, {"name": "KPI"})
        assert result["success"] is False
        assert "offline" in result["message"]

    def test_missing_required_name(self, auth_manager, server_config):
        result = create_pa_indicator(auth_manager, server_config, {})
        assert result["success"] is False

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        server_config.instance_url = None
        result = create_pa_indicator(am, server_config, {"name": "KPI"})
        assert result["success"] is False

    def test_no_headers(self, server_config):
        am = MagicMock()
        am.instance_url = "https://x.com"
        am.get_headers.return_value = None
        server_config.instance_url = None
        result = create_pa_indicator(am, server_config, {"name": "KPI"})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_none_optional_fields_excluded_from_body(self, mock_req, auth_manager, server_config):
        """Optional fields that are None should not appear in the POST body."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_CREATED_INDICATOR}
        mock_req.return_value = mock_resp
        create_pa_indicator(auth_manager, server_config, {"name": "KPI"})
        call_json = mock_req.call_args[1]["json"]
        assert "description" not in call_json
        assert "table" not in call_json
        assert "condition" not in call_json
        assert "formula" not in call_json
        assert "unit" not in call_json
        assert "indicator_group" not in call_json

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_posts_to_correct_url(self, mock_req, auth_manager, server_config):
        """Verify the request is a POST to the pa_indicator table endpoint."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_CREATED_INDICATOR}
        mock_req.return_value = mock_resp
        create_pa_indicator(auth_manager, server_config, {"name": "KPI"})
        call_args = mock_req.call_args
        assert call_args[0][0] == "POST"
        assert "pa_indicator" in call_args[0][1]


class TestCreatePAIndicatorParams:
    def test_requires_name(self):
        import pydantic
        with pytest.raises((pydantic.ValidationError, Exception)):
            CreatePAIndicatorParams()

    def test_active_defaults_to_true(self):
        p = CreatePAIndicatorParams(name="KPI")
        assert p.active is True

    def test_all_optional_fields_none(self):
        p = CreatePAIndicatorParams(name="KPI")
        assert p.description is None
        assert p.table is None
        assert p.condition is None
        assert p.formula is None
        assert p.frequency is None
        assert p.direction is None
        assert p.unit is None
        assert p.indicator_group is None

# ---------------------------------------------------------------------------
# PA Dashboard fixtures
# ---------------------------------------------------------------------------

DASHBOARD_SYS_ID = "d" * 32

RAW_DASHBOARD = {
    "sys_id": DASHBOARD_SYS_ID,
    "title": "ITSM Overview",
    "description": "Key ITSM metrics dashboard",
    "owner": {"display_value": "admin", "value": "e" * 32},
    "active": "true",
    "order": "100",
    "sys_created_on": "2024-01-01 00:00:00",
    "sys_updated_on": "2024-06-01 00:00:00",
}


# ---------------------------------------------------------------------------
# _format_pa_dashboard
# ---------------------------------------------------------------------------


class TestFormatPADashboard:
    def test_basic_fields(self):
        from servicenow_mcp.tools.pa_tools import _format_pa_dashboard
        result = _format_pa_dashboard(RAW_DASHBOARD)
        assert result["sys_id"] == DASHBOARD_SYS_ID
        assert result["title"] == "ITSM Overview"
        assert result["description"] == "Key ITSM metrics dashboard"
        assert result["owner"] == "admin"
        assert result["active"] == "true"
        assert result["order"] == "100"
        assert result["created_on"] == "2024-01-01 00:00:00"
        assert result["updated_on"] == "2024-06-01 00:00:00"

    def test_owner_string(self):
        from servicenow_mcp.tools.pa_tools import _format_pa_dashboard
        rec = dict(RAW_DASHBOARD)
        rec["owner"] = "admin"
        result = _format_pa_dashboard(rec)
        assert result["owner"] == "admin"

    def test_missing_fields(self):
        from servicenow_mcp.tools.pa_tools import _format_pa_dashboard
        result = _format_pa_dashboard({})
        assert result["sys_id"] is None
        assert result["title"] is None
        assert result["owner"] is None


# ---------------------------------------------------------------------------
# _resolve_pa_dashboard_sys_id
# ---------------------------------------------------------------------------


class TestResolvePADashboardSysId:
    def test_hex_sys_id_returned_directly(self):
        from servicenow_mcp.tools.pa_tools import _resolve_pa_dashboard_sys_id
        result = _resolve_pa_dashboard_sys_id(DASHBOARD_SYS_ID, "https://x.com", {})
        assert result == DASHBOARD_SYS_ID

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_resolved_to_sys_id(self, mock_req):
        from servicenow_mcp.tools.pa_tools import _resolve_pa_dashboard_sys_id
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [{"sys_id": DASHBOARD_SYS_ID}]}
        mock_req.return_value = mock_resp
        result = _resolve_pa_dashboard_sys_id("ITSM Overview", "https://x.com", {})
        assert result == DASHBOARD_SYS_ID

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_not_found_returns_none(self, mock_req):
        from servicenow_mcp.tools.pa_tools import _resolve_pa_dashboard_sys_id
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = _resolve_pa_dashboard_sys_id("Unknown Dashboard", "https://x.com", {})
        assert result is None

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_error_returns_none(self, mock_req):
        from servicenow_mcp.tools.pa_tools import _resolve_pa_dashboard_sys_id
        mock_req.side_effect = requests.exceptions.RequestException("network error")
        result = _resolve_pa_dashboard_sys_id("Some Dashboard", "https://x.com", {})
        assert result is None


# ---------------------------------------------------------------------------
# list_pa_dashboards
# ---------------------------------------------------------------------------


class TestListPADashboards:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_returns_dashboards(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_dashboards
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_DASHBOARD]}
        mock_req.return_value = mock_resp
        result = list_pa_dashboards(auth_manager, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is True
        assert len(result["dashboards"]) == 1
        assert result["dashboards"][0]["title"] == "ITSM Overview"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_title_filter(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_dashboards
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_dashboards(auth_manager, server_config, {"title": "ITSM"})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "titleLIKEITSM" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_active_filter_true(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_dashboards
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_dashboards(auth_manager, server_config, {"active": True})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "active=true" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_owner_filter(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_dashboards
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_dashboards(auth_manager, server_config, {"owner": "jsmith"})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "owner.user_nameLIKEjsmith" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_dashboards
        resp = MagicMock()
        resp.status_code = 500
        resp.json.return_value = {}
        mock_req.return_value = resp
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        result = list_pa_dashboards(auth_manager, server_config, {})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_connection_error(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_dashboards
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_pa_dashboards(auth_manager, server_config, {})
        assert result["success"] is False

    def test_no_instance_url(self, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_dashboards
        am = MagicMock()
        am.instance_url = None
        am.get_headers.return_value = {}
        server_config.instance_url = None
        result = list_pa_dashboards(am, server_config, {})
        assert result["success"] is False

    def test_no_headers(self, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_dashboards
        am = MagicMock()
        am.instance_url = "https://x.com"
        am.get_headers.return_value = None
        server_config.instance_url = None
        result = list_pa_dashboards(am, server_config, {})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_has_more_pagination(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_dashboards
        mock_resp = MagicMock()
        # Return exactly limit records so has_more=True is set
        mock_resp.json.return_value = {"result": [RAW_DASHBOARD] * 5}
        mock_req.return_value = mock_resp
        result = list_pa_dashboards(auth_manager, server_config, {"limit": 5, "offset": 0})
        assert result["success"] is True
        assert result.get("has_more") is True
        assert result.get("next_offset") == 5

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_no_filters(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_dashboards
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_dashboards(auth_manager, server_config, {})
        assert result["success"] is True
        assert result["dashboards"] == []


# ---------------------------------------------------------------------------
# get_pa_dashboard
# ---------------------------------------------------------------------------


class TestGetPADashboard:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_get_by_sys_id(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_dashboard
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_DASHBOARD}
        mock_req.return_value = mock_resp
        result = get_pa_dashboard(auth_manager, server_config, {"dashboard_id": DASHBOARD_SYS_ID})
        assert result["success"] is True
        assert result["dashboard"]["title"] == "ITSM Overview"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_get_by_title(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_dashboard
        # First call resolves name, second fetches the record
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": [{"sys_id": DASHBOARD_SYS_ID}]}
        get_resp = MagicMock()
        get_resp.json.return_value = {"result": RAW_DASHBOARD}
        mock_req.side_effect = [resolve_resp, get_resp]
        result = get_pa_dashboard(auth_manager, server_config, {"dashboard_id": "ITSM Overview"})
        assert result["success"] is True
        assert result["dashboard"]["sys_id"] == DASHBOARD_SYS_ID

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_title_not_found(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_dashboard
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = get_pa_dashboard(auth_manager, server_config, {"dashboard_id": "Nonexistent"})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_empty_result(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_dashboard
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": None}
        mock_req.return_value = mock_resp
        result = get_pa_dashboard(auth_manager, server_config, {"dashboard_id": DASHBOARD_SYS_ID})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_404_error(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_dashboard
        resp = MagicMock()
        resp.status_code = 404
        resp.json.return_value = {}
        mock_req.return_value = resp
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        result = get_pa_dashboard(auth_manager, server_config, {"dashboard_id": DASHBOARD_SYS_ID})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error_non_404(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_dashboard
        resp = MagicMock()
        resp.status_code = 500
        resp.json.return_value = {"error": {"message": "Internal Server Error", "detail": ""}}
        mock_req.return_value = resp
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        result = get_pa_dashboard(auth_manager, server_config, {"dashboard_id": DASHBOARD_SYS_ID})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_connection_error(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_dashboard
        # First call (resolve sys_id) returns successfully
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": [{"sys_id": DASHBOARD_SYS_ID}]}
        mock_req.side_effect = [resolve_resp, requests.exceptions.ConnectionError("timeout")]
        result = get_pa_dashboard(auth_manager, server_config, {"dashboard_id": "ITSM Overview"})
        assert result["success"] is False

    def test_no_instance_url(self, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_dashboard
        am = MagicMock()
        am.instance_url = None
        am.get_headers.return_value = {}
        server_config.instance_url = None
        result = get_pa_dashboard(am, server_config, {"dashboard_id": DASHBOARD_SYS_ID})
        assert result["success"] is False

    def test_no_headers(self, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_dashboard
        am = MagicMock()
        am.instance_url = "https://x.com"
        am.get_headers.return_value = None
        server_config.instance_url = None
        result = get_pa_dashboard(am, server_config, {"dashboard_id": DASHBOARD_SYS_ID})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# ListPADashboardsParams / GetPADashboardParams model validation
# ---------------------------------------------------------------------------


class TestPADashboardParams:
    def test_list_defaults(self):
        from servicenow_mcp.tools.pa_tools import ListPADashboardsParams
        p = ListPADashboardsParams()
        assert p.limit == 20
        assert p.offset == 0
        assert p.title is None
        assert p.active is None
        assert p.owner is None

    def test_get_requires_dashboard_id(self):
        from servicenow_mcp.tools.pa_tools import GetPADashboardParams
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GetPADashboardParams()

    def test_get_with_sys_id(self):
        from servicenow_mcp.tools.pa_tools import GetPADashboardParams
        p = GetPADashboardParams(dashboard_id=DASHBOARD_SYS_ID)
        assert p.dashboard_id == DASHBOARD_SYS_ID


# ---------------------------------------------------------------------------
# Widget fixtures
# ---------------------------------------------------------------------------

WIDGET_SYS_ID = "e" * 32

RAW_WIDGET = {
    "sys_id": WIDGET_SYS_ID,
    "name": "Open Incidents Chart",
    "description": "Bar chart of open incidents by priority",
    "indicator": {"display_value": "Incident Count", "value": SYS_ID_32},
    "widget_type": "chart",
    "active": "true",
    "home_page": {"display_value": "ITSM Overview", "value": DASHBOARD_SYS_ID},
    "breakdown": {"display_value": "Priority", "value": "bk" * 16},
    "color": "blue",
    "sys_created_on": "2024-02-01 00:00:00",
    "sys_updated_on": "2024-07-01 00:00:00",
}


# ---------------------------------------------------------------------------
# _format_pa_widget
# ---------------------------------------------------------------------------


class TestFormatPAWidget:
    def test_basic_fields(self):
        from servicenow_mcp.tools.pa_tools import _format_pa_widget
        result = _format_pa_widget(RAW_WIDGET)
        assert result["sys_id"] == WIDGET_SYS_ID
        assert result["name"] == "Open Incidents Chart"
        assert result["description"] == "Bar chart of open incidents by priority"
        assert result["widget_type"] == "chart"
        assert result["active"] == "true"
        assert result["color"] == "blue"
        assert result["created_on"] == "2024-02-01 00:00:00"
        assert result["updated_on"] == "2024-07-01 00:00:00"

    def test_reference_fields_extracted(self):
        from servicenow_mcp.tools.pa_tools import _format_pa_widget
        result = _format_pa_widget(RAW_WIDGET)
        assert result["indicator"] == "Incident Count"
        assert result["home_page"] == "ITSM Overview"
        assert result["breakdown"] == "Priority"

    def test_string_reference_fields(self):
        from servicenow_mcp.tools.pa_tools import _format_pa_widget
        rec = {**RAW_WIDGET, "indicator": "Inc Count", "home_page": "My DB", "breakdown": None}
        result = _format_pa_widget(rec)
        assert result["indicator"] == "Inc Count"
        assert result["home_page"] == "My DB"
        assert result["breakdown"] is None

    def test_empty_record(self):
        from servicenow_mcp.tools.pa_tools import _format_pa_widget
        result = _format_pa_widget({})
        assert result["sys_id"] is None
        assert result["name"] is None


# ---------------------------------------------------------------------------
# _resolve_pa_widget_sys_id
# ---------------------------------------------------------------------------


class TestResolvePAWidgetSysId:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_hex_passthrough(self, mock_req):
        from servicenow_mcp.tools.pa_tools import _resolve_pa_widget_sys_id
        result = _resolve_pa_widget_sys_id(WIDGET_SYS_ID, "https://x.com", {})
        assert result == WIDGET_SYS_ID
        mock_req.assert_not_called()

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_lookup_found(self, mock_req):
        from servicenow_mcp.tools.pa_tools import _resolve_pa_widget_sys_id
        resp = MagicMock()
        resp.json.return_value = {"result": [{"sys_id": WIDGET_SYS_ID}]}
        mock_req.return_value = resp
        result = _resolve_pa_widget_sys_id("Open Incidents Chart", "https://x.com", {})
        assert result == WIDGET_SYS_ID

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_lookup_not_found(self, mock_req):
        from servicenow_mcp.tools.pa_tools import _resolve_pa_widget_sys_id
        resp = MagicMock()
        resp.json.return_value = {"result": []}
        mock_req.return_value = resp
        result = _resolve_pa_widget_sys_id("Unknown Widget", "https://x.com", {})
        assert result is None

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception_returns_none(self, mock_req):
        from servicenow_mcp.tools.pa_tools import _resolve_pa_widget_sys_id
        mock_req.side_effect = requests.exceptions.RequestException("network error")
        result = _resolve_pa_widget_sys_id("Some Widget", "https://x.com", {})
        assert result is None


# ---------------------------------------------------------------------------
# list_pa_widgets
# ---------------------------------------------------------------------------


class TestListPAWidgets:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_returns_widgets(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_WIDGET]}
        mock_req.return_value = mock_resp
        result = list_pa_widgets(auth_manager, server_config, {"limit": 10, "offset": 0})
        assert result["success"] is True
        assert len(result["widgets"]) == 1
        assert result["widgets"][0]["name"] == "Open Incidents Chart"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_filter(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_widgets(auth_manager, server_config, {"name": "Incident"})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "nameLIKEIncident" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_active_filter_true(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_widgets(auth_manager, server_config, {"active": True})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "active=true" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_active_filter_false(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_widgets(auth_manager, server_config, {"active": False})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "active=false" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_widget_type_filter(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_widgets(auth_manager, server_config, {"widget_type": "chart"})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "widget_type=chart" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_indicator_id_filter_by_sys_id(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_WIDGET]}
        mock_req.return_value = mock_resp
        result = list_pa_widgets(auth_manager, server_config, {"indicator_id": SYS_ID_32})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert f"indicator={SYS_ID_32}" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_indicator_id_filter_by_name(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        # First call resolves indicator name, second lists widgets
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        list_resp = MagicMock()
        list_resp.json.return_value = {"result": [RAW_WIDGET]}
        mock_req.side_effect = [resolve_resp, list_resp]
        result = list_pa_widgets(auth_manager, server_config, {"indicator_id": "Incident Count"})
        assert result["success"] is True

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_indicator_not_found(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": []}
        mock_req.return_value = resolve_resp
        result = list_pa_widgets(auth_manager, server_config, {"indicator_id": "Unknown Indicator"})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_dashboard_id_filter_by_sys_id(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_WIDGET]}
        mock_req.return_value = mock_resp
        result = list_pa_widgets(auth_manager, server_config, {"dashboard_id": DASHBOARD_SYS_ID})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert f"home_page={DASHBOARD_SYS_ID}" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_dashboard_id_filter_by_title(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": [{"sys_id": DASHBOARD_SYS_ID}]}
        list_resp = MagicMock()
        list_resp.json.return_value = {"result": [RAW_WIDGET]}
        mock_req.side_effect = [resolve_resp, list_resp]
        result = list_pa_widgets(auth_manager, server_config, {"dashboard_id": "ITSM Overview"})
        assert result["success"] is True

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_dashboard_not_found(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": []}
        mock_req.return_value = resolve_resp
        result = list_pa_widgets(auth_manager, server_config, {"dashboard_id": "Unknown Dashboard"})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        resp = MagicMock()
        resp.status_code = 500
        resp.json.return_value = {}
        mock_req.return_value = resp
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        result = list_pa_widgets(auth_manager, server_config, {})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_connection_error(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
        result = list_pa_widgets(auth_manager, server_config, {})
        assert result["success"] is False

    def test_no_instance_url(self, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        am = MagicMock()
        am.instance_url = None
        am.get_headers.return_value = {}
        server_config.instance_url = None
        result = list_pa_widgets(am, server_config, {})
        assert result["success"] is False

    def test_no_headers(self, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        am = MagicMock()
        am.instance_url = "https://x.com"
        am.get_headers.return_value = None
        server_config.instance_url = None
        result = list_pa_widgets(am, server_config, {})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_has_more_pagination(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_WIDGET] * 5}
        mock_req.return_value = mock_resp
        result = list_pa_widgets(auth_manager, server_config, {"limit": 5, "offset": 0})
        assert result["success"] is True
        assert result.get("has_more") is True
        assert result.get("next_offset") == 5

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_no_filters(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import list_pa_widgets
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_widgets(auth_manager, server_config, {})
        assert result["success"] is True
        assert result["widgets"] == []


# ---------------------------------------------------------------------------
# get_pa_widget
# ---------------------------------------------------------------------------


class TestGetPAWidget:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_get_by_sys_id(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_widget
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_WIDGET}
        mock_req.return_value = mock_resp
        result = get_pa_widget(auth_manager, server_config, {"widget_id": WIDGET_SYS_ID})
        assert result["success"] is True
        assert result["widget"]["name"] == "Open Incidents Chart"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_get_by_name(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_widget
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": [{"sys_id": WIDGET_SYS_ID}]}
        get_resp = MagicMock()
        get_resp.json.return_value = {"result": RAW_WIDGET}
        mock_req.side_effect = [resolve_resp, get_resp]
        result = get_pa_widget(auth_manager, server_config, {"widget_id": "Open Incidents Chart"})
        assert result["success"] is True
        assert result["widget"]["sys_id"] == WIDGET_SYS_ID

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_not_found(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_widget
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = get_pa_widget(auth_manager, server_config, {"widget_id": "Nonexistent"})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_empty_result(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_widget
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": None}
        mock_req.return_value = mock_resp
        result = get_pa_widget(auth_manager, server_config, {"widget_id": WIDGET_SYS_ID})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_404_error(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_widget
        resp = MagicMock()
        resp.status_code = 404
        resp.json.return_value = {}
        mock_req.return_value = resp
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        result = get_pa_widget(auth_manager, server_config, {"widget_id": WIDGET_SYS_ID})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error_non_404(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_widget
        resp = MagicMock()
        resp.status_code = 500
        resp.json.return_value = {"error": {"message": "Internal Server Error", "detail": ""}}
        mock_req.return_value = resp
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
        result = get_pa_widget(auth_manager, server_config, {"widget_id": WIDGET_SYS_ID})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_connection_error(self, mock_req, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_widget
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": [{"sys_id": WIDGET_SYS_ID}]}
        mock_req.side_effect = [resolve_resp, requests.exceptions.ConnectionError("timeout")]
        result = get_pa_widget(auth_manager, server_config, {"widget_id": "Open Incidents Chart"})
        assert result["success"] is False

    def test_no_instance_url(self, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_widget
        am = MagicMock()
        am.instance_url = None
        am.get_headers.return_value = {}
        server_config.instance_url = None
        result = get_pa_widget(am, server_config, {"widget_id": WIDGET_SYS_ID})
        assert result["success"] is False

    def test_no_headers(self, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_widget
        am = MagicMock()
        am.instance_url = "https://x.com"
        am.get_headers.return_value = None
        server_config.instance_url = None
        result = get_pa_widget(am, server_config, {"widget_id": WIDGET_SYS_ID})
        assert result["success"] is False

    def test_missing_widget_id(self):
        from servicenow_mcp.tools.pa_tools import GetPAWidgetParams
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GetPAWidgetParams()


# ---------------------------------------------------------------------------
# ListPAWidgetsParams / GetPAWidgetParams model validation
# ---------------------------------------------------------------------------


class TestPAWidgetParams:
    def test_list_defaults(self):
        from servicenow_mcp.tools.pa_tools import ListPAWidgetsParams
        p = ListPAWidgetsParams()
        assert p.limit == 20
        assert p.offset == 0
        assert p.name is None
        assert p.active is None
        assert p.widget_type is None
        assert p.indicator_id is None
        assert p.dashboard_id is None

    def test_get_requires_widget_id(self):
        from servicenow_mcp.tools.pa_tools import GetPAWidgetParams
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GetPAWidgetParams()

    def test_get_with_sys_id(self):
        from servicenow_mcp.tools.pa_tools import GetPAWidgetParams
        p = GetPAWidgetParams(widget_id=WIDGET_SYS_ID)
        assert p.widget_id == WIDGET_SYS_ID


# ===========================================================================
# PA Breakdown tools
# ===========================================================================

from servicenow_mcp.tools.pa_tools import (
    GetPABreakdownParams,
    ListPABreakdownsParams,
    _format_pa_breakdown,
    _resolve_pa_breakdown_sys_id,
    get_pa_breakdown,
    list_pa_breakdowns,
)

BREAKDOWN_SYS_ID = "b" * 32

RAW_BREAKDOWN = {
    "sys_id": BREAKDOWN_SYS_ID,
    "name": "Priority",
    "active": "true",
    "table": {"display_value": "Incident", "value": "incident"},
    "field": "priority",
    "filter_condition": "active=true",
    "calculated_from": {"display_value": "Base Breakdown", "value": "c" * 32},
    "sys_created_on": "2024-01-01 00:00:00",
    "sys_updated_on": "2024-06-01 00:00:00",
}


# ---------------------------------------------------------------------------
# _format_pa_breakdown
# ---------------------------------------------------------------------------


class TestFormatPABreakdown:
    def test_basic_fields(self):
        result = _format_pa_breakdown(RAW_BREAKDOWN)
        assert result["sys_id"] == BREAKDOWN_SYS_ID
        assert result["name"] == "Priority"
        assert result["active"] == "true"
        assert result["field"] == "priority"
        assert result["filter_condition"] == "active=true"
        assert result["created_on"] == "2024-01-01 00:00:00"
        assert result["updated_on"] == "2024-06-01 00:00:00"

    def test_reference_fields_extracted(self):
        result = _format_pa_breakdown(RAW_BREAKDOWN)
        assert result["table"] == "Incident"
        assert result["calculated_from"] == "Base Breakdown"

    def test_string_reference_fields(self):
        rec = {**RAW_BREAKDOWN, "table": "incident", "calculated_from": "Some Breakdown"}
        result = _format_pa_breakdown(rec)
        assert result["table"] == "incident"
        assert result["calculated_from"] == "Some Breakdown"

    def test_missing_fields_return_none(self):
        result = _format_pa_breakdown({})
        assert result["sys_id"] is None
        assert result["name"] is None
        assert result["table"] is None
        assert result["calculated_from"] is None


# ---------------------------------------------------------------------------
# _resolve_pa_breakdown_sys_id
# ---------------------------------------------------------------------------


class TestResolvePABreakdownSysId:
    def test_passthrough_32_hex(self):
        result = _resolve_pa_breakdown_sys_id(BREAKDOWN_SYS_ID, "https://inst.sn.com", {})
        assert result == BREAKDOWN_SYS_ID

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_lookup_success(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [{"sys_id": BREAKDOWN_SYS_ID}]}
        mock_req.return_value = mock_resp
        result = _resolve_pa_breakdown_sys_id("Priority", "https://inst.sn.com", {})
        assert result == BREAKDOWN_SYS_ID

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_lookup_not_found(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = _resolve_pa_breakdown_sys_id("Unknown Breakdown", "https://inst.sn.com", {})
        assert result is None

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_name_lookup_request_exception(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("network error")
        result = _resolve_pa_breakdown_sys_id("Priority", "https://inst.sn.com", {})
        assert result is None


# ---------------------------------------------------------------------------
# list_pa_breakdowns
# ---------------------------------------------------------------------------


@pytest.fixture
def bd_auth():
    am = MagicMock()
    am.instance_url = "https://instance.service-now.com"
    am.get_headers.return_value = {"Authorization": "Bearer token"}
    return am


@pytest.fixture
def bd_config():
    sc = MagicMock()
    sc.instance_url = None
    return sc


class TestListPABreakdowns:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_success_empty(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_breakdowns(bd_auth, bd_config, {})
        assert result["success"] is True
        assert result["breakdowns"] == []
        assert result["count"] == 0

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_success_with_records(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_BREAKDOWN]}
        mock_req.return_value = mock_resp
        result = list_pa_breakdowns(bd_auth, bd_config, {})
        assert result["success"] is True
        assert len(result["breakdowns"]) == 1
        assert result["breakdowns"][0]["name"] == "Priority"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_filter_by_name(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_breakdowns(bd_auth, bd_config, {"name": "Priority"})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "nameLIKEPriority" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_filter_by_active_true(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_breakdowns(bd_auth, bd_config, {"active": True})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "active=true" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_filter_by_active_false(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_breakdowns(bd_auth, bd_config, {"active": False})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "active=false" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_filter_by_table(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_breakdowns(bd_auth, bd_config, {"table": "incident"})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "table=incident" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_filter_by_field(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp
        result = list_pa_breakdowns(bd_auth, bd_config, {"field": "priority"})
        assert result["success"] is True
        call_params = mock_req.call_args[1]["params"]
        assert "fieldLIKEpriority" in call_params.get("sysparm_query", "")

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_pagination_has_more(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        records = [dict(RAW_BREAKDOWN, sys_id=f"{i}" * 32) for i in range(5)]
        mock_resp.json.return_value = {"result": records}
        mock_req.return_value = mock_resp
        result = list_pa_breakdowns(bd_auth, bd_config, {"limit": 3, "offset": 0})
        # _paginated_list_response with 5 records and limit=3 → has_more
        assert result["success"] is True

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_req.return_value = mock_resp
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp
        )
        result = list_pa_breakdowns(bd_auth, bd_config, {})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, bd_auth, bd_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("down")
        result = list_pa_breakdowns(bd_auth, bd_config, {})
        assert result["success"] is False

    def test_no_instance_url(self, bd_config):
        am = MagicMock()
        am.instance_url = None
        am.get_headers.return_value = {"Authorization": "Bearer token"}
        bd_config.instance_url = None
        result = list_pa_breakdowns(am, bd_config, {})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, bd_auth, bd_config):
        bd_auth.get_headers.return_value = None
        result = list_pa_breakdowns(bd_auth, bd_config, {})
        assert result["success"] is False
        assert "get_headers" in result["message"]

    def test_invalid_params(self, bd_auth, bd_config):
        result = list_pa_breakdowns(bd_auth, bd_config, {"limit": "bad"})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# get_pa_breakdown
# ---------------------------------------------------------------------------


class TestGetPABreakdown:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_success_by_sys_id(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_BREAKDOWN}
        mock_req.return_value = mock_resp
        result = get_pa_breakdown(bd_auth, bd_config, {"breakdown_id": BREAKDOWN_SYS_ID})
        assert result["success"] is True
        assert result["breakdown"]["name"] == "Priority"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_success_by_name(self, mock_req, bd_auth, bd_config):
        # First call: resolver lookup; second call: direct GET
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = {"result": [{"sys_id": BREAKDOWN_SYS_ID}]}
        get_resp = MagicMock()
        get_resp.json.return_value = {"result": RAW_BREAKDOWN}
        mock_req.side_effect = [lookup_resp, get_resp]
        result = get_pa_breakdown(bd_auth, bd_config, {"breakdown_id": "Priority"})
        assert result["success"] is True
        assert result["breakdown"]["name"] == "Priority"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_not_found_by_name(self, mock_req, bd_auth, bd_config):
        lookup_resp = MagicMock()
        lookup_resp.json.return_value = {"result": []}
        mock_req.return_value = lookup_resp
        result = get_pa_breakdown(bd_auth, bd_config, {"breakdown_id": "Unknown"})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_empty_result(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": None}
        mock_req.return_value = mock_resp
        result = get_pa_breakdown(bd_auth, bd_config, {"breakdown_id": BREAKDOWN_SYS_ID})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_404_error(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        err = requests.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = err
        mock_req.return_value = mock_resp
        result = get_pa_breakdown(bd_auth, bd_config, {"breakdown_id": BREAKDOWN_SYS_ID})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error_non_404(self, mock_req, bd_auth, bd_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": {"message": "Internal Error", "detail": "boom"}}
        err = requests.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = err
        mock_req.return_value = mock_resp
        result = get_pa_breakdown(bd_auth, bd_config, {"breakdown_id": BREAKDOWN_SYS_ID})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, bd_auth, bd_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("down")
        result = get_pa_breakdown(bd_auth, bd_config, {"breakdown_id": BREAKDOWN_SYS_ID})
        assert result["success"] is False

    def test_missing_required_param(self, bd_auth, bd_config):
        result = get_pa_breakdown(bd_auth, bd_config, {})
        assert result["success"] is False

    def test_no_instance_url(self, bd_config):
        am = MagicMock()
        am.instance_url = None
        am.get_headers.return_value = {"Authorization": "Bearer token"}
        bd_config.instance_url = None
        result = get_pa_breakdown(am, bd_config, {"breakdown_id": BREAKDOWN_SYS_ID})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, bd_auth, bd_config):
        bd_auth.get_headers.return_value = None
        result = get_pa_breakdown(bd_auth, bd_config, {"breakdown_id": BREAKDOWN_SYS_ID})
        assert result["success"] is False
        assert "get_headers" in result["message"]


# ---------------------------------------------------------------------------
# ListPABreakdownsParams / GetPABreakdownParams validation
# ---------------------------------------------------------------------------


class TestPABreakdownParams:
    def test_list_defaults(self):
        p = ListPABreakdownsParams()
        assert p.limit == 20
        assert p.offset == 0
        assert p.name is None
        assert p.active is None
        assert p.table is None
        assert p.field is None

    def test_list_with_all_fields(self):
        p = ListPABreakdownsParams(
            limit=10, offset=5, name="Cat", active=True, table="incident", field="category"
        )
        assert p.limit == 10
        assert p.name == "Cat"
        assert p.active is True
        assert p.table == "incident"
        assert p.field == "category"

    def test_get_requires_breakdown_id(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GetPABreakdownParams()

    def test_get_with_sys_id(self):
        p = GetPABreakdownParams(breakdown_id=BREAKDOWN_SYS_ID)
        assert p.breakdown_id == BREAKDOWN_SYS_ID

    def test_get_with_name(self):
        p = GetPABreakdownParams(breakdown_id="Priority")
        assert p.breakdown_id == "Priority"


# ---------------------------------------------------------------------------
# update_pa_dashboard / delete_pa_dashboard
# ---------------------------------------------------------------------------

# Use distinct names to avoid collision with module-level DASHBOARD_SYS_ID / RAW_DASHBOARD
UPD_DASHBOARD_SYS_ID = "9" * 32  # 32-char hex → resolver returns directly, no extra API call

UPD_RAW_DASHBOARD = {
    "sys_id": UPD_DASHBOARD_SYS_ID,
    "title": "My PA Dashboard",
    "description": "PA overview",
    "owner": {"display_value": "Admin", "value": "e" * 32},
    "active": "true",
    "order": "10",
    "sys_created_on": "2024-01-01 00:00:00",
    "sys_updated_on": "2024-06-01 00:00:00",
}


def _mock_upd_dashboard_resp(raw=None, status=200):
    if raw is None:
        raw = UPD_RAW_DASHBOARD
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"result": raw}
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def dash_auth():
    am = MagicMock()
    am.instance_url = "https://instance.service-now.com"
    am.get_headers.return_value = {"Authorization": "Bearer token"}
    return am


@pytest.fixture
def dash_config():
    sc = MagicMock()
    sc.instance_url = None
    return sc


class TestUpdatePADashboard:
    def test_update_title_by_sys_id(self, dash_auth, dash_config):
        from servicenow_mcp.tools.pa_tools import update_pa_dashboard

        # UPD_DASHBOARD_SYS_ID is 32-char hex → resolver returns it directly (no extra call)
        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = _mock_upd_dashboard_resp()
            result = update_pa_dashboard(
                dash_auth, dash_config,
                {"dashboard_id": UPD_DASHBOARD_SYS_ID, "title": "New Title"},
            )
        assert result["success"] is True
        assert "dashboard" in result
        assert "updated" in result["message"]
        call_args = mock_req.call_args
        assert call_args[0][0] == "PATCH"
        assert UPD_DASHBOARD_SYS_ID in call_args[0][1]
        assert call_args[1]["json"]["title"] == "New Title"

    def test_update_active_false(self, dash_auth, dash_config):
        from servicenow_mcp.tools.pa_tools import update_pa_dashboard

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = _mock_upd_dashboard_resp()
            result = update_pa_dashboard(
                dash_auth, dash_config,
                {"dashboard_id": UPD_DASHBOARD_SYS_ID, "active": False},
            )
        assert result["success"] is True
        assert mock_req.call_args[1]["json"]["active"] == "false"

    def test_update_active_true(self, dash_auth, dash_config):
        from servicenow_mcp.tools.pa_tools import update_pa_dashboard

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = _mock_upd_dashboard_resp()
            result = update_pa_dashboard(
                dash_auth, dash_config,
                {"dashboard_id": UPD_DASHBOARD_SYS_ID, "active": True},
            )
        assert result["success"] is True
        assert mock_req.call_args[1]["json"]["active"] == "true"

    def test_update_order(self, dash_auth, dash_config):
        from servicenow_mcp.tools.pa_tools import update_pa_dashboard

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = _mock_upd_dashboard_resp()
            result = update_pa_dashboard(
                dash_auth, dash_config,
                {"dashboard_id": UPD_DASHBOARD_SYS_ID, "order": 5},
            )
        assert result["success"] is True
        assert mock_req.call_args[1]["json"]["order"] == "5"

    def test_update_owner(self, dash_auth, dash_config):
        from servicenow_mcp.tools.pa_tools import update_pa_dashboard

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = _mock_upd_dashboard_resp()
            result = update_pa_dashboard(
                dash_auth, dash_config,
                {"dashboard_id": UPD_DASHBOARD_SYS_ID, "owner": "admin"},
            )
        assert result["success"] is True
        assert mock_req.call_args[1]["json"]["owner"] == "admin"

    def test_no_fields_rejects(self, dash_auth, dash_config):
        from servicenow_mcp.tools.pa_tools import update_pa_dashboard

        result = update_pa_dashboard(
            dash_auth, dash_config, {"dashboard_id": UPD_DASHBOARD_SYS_ID}
        )
        assert result["success"] is False
        assert "No fields" in result["message"]

    def test_dashboard_not_found_by_name(self, dash_auth, dash_config):
        """Name-based lookup that returns no results → not found."""
        from servicenow_mcp.tools.pa_tools import update_pa_dashboard

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.side_effect = [
                # resolver GET returns empty list
                MagicMock(status_code=200, json=MagicMock(return_value={"result": []}),
                           raise_for_status=MagicMock()),
            ]
            result = update_pa_dashboard(
                dash_auth, dash_config,
                {"dashboard_id": "Not A Dashboard", "title": "x"},
            )
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_404_on_patch_name_lookup(self, dash_auth, dash_config):
        """Name-based lookup succeeds, PATCH raises 404."""
        from servicenow_mcp.tools.pa_tools import update_pa_dashboard

        http_err = requests.exceptions.HTTPError(response=MagicMock(status_code=404))
        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.side_effect = [
                # first call: resolver finds the dashboard by name
                MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={"result": [{"sys_id": UPD_DASHBOARD_SYS_ID}]}),
                    raise_for_status=MagicMock(),
                ),
                # second call: PATCH raises 404
                http_err,
            ]
            result = update_pa_dashboard(
                dash_auth, dash_config,
                {"dashboard_id": "My PA Dashboard", "title": "New"},
            )
        assert result["success"] is False

    def test_no_instance_url(self, dash_config):
        from servicenow_mcp.tools.pa_tools import update_pa_dashboard

        am = MagicMock()
        am.instance_url = None
        dash_config.instance_url = None
        result = update_pa_dashboard(am, dash_config, {"dashboard_id": UPD_DASHBOARD_SYS_ID, "title": "x"})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, dash_auth, dash_config):
        from servicenow_mcp.tools.pa_tools import update_pa_dashboard

        dash_auth.get_headers.return_value = None
        result = update_pa_dashboard(dash_auth, dash_config, {"dashboard_id": UPD_DASHBOARD_SYS_ID, "title": "x"})
        assert result["success"] is False
        assert "get_headers" in result["message"]

    def test_request_exception_direct_sys_id(self, dash_auth, dash_config):
        """PATCH raises ConnectionError for a direct sys_id call (no resolver call)."""
        from servicenow_mcp.tools.pa_tools import update_pa_dashboard

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            # Only one call: the PATCH itself (sys_id bypasses resolver)
            mock_req.side_effect = requests.exceptions.ConnectionError("timeout")
            result = update_pa_dashboard(
                dash_auth, dash_config,
                {"dashboard_id": UPD_DASHBOARD_SYS_ID, "title": "x"},
            )
        assert result["success"] is False
        assert "timeout" in result["message"]


# ---------------------------------------------------------------------------
# delete_pa_dashboard
# ---------------------------------------------------------------------------


class TestDeletePADashboard:
    def test_delete_by_sys_id_204(self, dash_auth, dash_config):
        from servicenow_mcp.tools.pa_tools import delete_pa_dashboard

        del_resp = MagicMock()
        del_resp.status_code = 204
        del_resp.raise_for_status = MagicMock()
        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = del_resp
            result = delete_pa_dashboard(
                dash_auth, dash_config, {"dashboard_id": UPD_DASHBOARD_SYS_ID}
            )
        assert result["success"] is True
        assert result["dashboard_sys_id"] == UPD_DASHBOARD_SYS_ID
        assert mock_req.call_args[0][0] == "DELETE"

    def test_delete_by_sys_id_200(self, dash_auth, dash_config):
        from servicenow_mcp.tools.pa_tools import delete_pa_dashboard

        del_resp = MagicMock()
        del_resp.status_code = 200
        del_resp.raise_for_status = MagicMock()
        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = del_resp
            result = delete_pa_dashboard(
                dash_auth, dash_config, {"dashboard_id": UPD_DASHBOARD_SYS_ID}
            )
        assert result["success"] is True

    def test_delete_not_found_by_name(self, dash_auth, dash_config):
        """Name-based lookup returns empty list → not found."""
        from servicenow_mcp.tools.pa_tools import delete_pa_dashboard

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"result": []}),
                raise_for_status=MagicMock(),
            )
            result = delete_pa_dashboard(
                dash_auth, dash_config, {"dashboard_id": "Ghost Dashboard"}
            )
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_delete_404_http_error_name_lookup(self, dash_auth, dash_config):
        """Name-based lookup succeeds, DELETE raises 404."""
        from servicenow_mcp.tools.pa_tools import delete_pa_dashboard

        http_err = requests.exceptions.HTTPError(response=MagicMock(status_code=404))
        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.side_effect = [
                MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={"result": [{"sys_id": UPD_DASHBOARD_SYS_ID}]}),
                    raise_for_status=MagicMock(),
                ),
                http_err,
            ]
            result = delete_pa_dashboard(
                dash_auth, dash_config, {"dashboard_id": "My PA Dashboard"}
            )
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_delete_no_instance_url(self, dash_config):
        from servicenow_mcp.tools.pa_tools import delete_pa_dashboard

        am = MagicMock()
        am.instance_url = None
        dash_config.instance_url = None
        result = delete_pa_dashboard(am, dash_config, {"dashboard_id": UPD_DASHBOARD_SYS_ID})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_delete_no_headers(self, dash_auth, dash_config):
        from servicenow_mcp.tools.pa_tools import delete_pa_dashboard

        dash_auth.get_headers.return_value = None
        result = delete_pa_dashboard(dash_auth, dash_config, {"dashboard_id": UPD_DASHBOARD_SYS_ID})
        assert result["success"] is False
        assert "get_headers" in result["message"]

    def test_delete_network_error_direct_sys_id(self, dash_auth, dash_config):
        """DELETE raises ConnectionError for a direct sys_id (no resolver call)."""
        from servicenow_mcp.tools.pa_tools import delete_pa_dashboard

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            # Only one call: the DELETE itself (sys_id bypasses resolver)
            mock_req.side_effect = requests.exceptions.ConnectionError("network failure")
            result = delete_pa_dashboard(
                dash_auth, dash_config, {"dashboard_id": UPD_DASHBOARD_SYS_ID}
            )
        assert result["success"] is False
        assert "network failure" in result["message"]


# ---------------------------------------------------------------------------
# update_pa_breakdown
# ---------------------------------------------------------------------------

UPD_BREAKDOWN_SYS_ID = "8" * 32  # distinct 32-char hex to avoid collisions

UPD_RAW_BREAKDOWN = {
    "sys_id": UPD_BREAKDOWN_SYS_ID,
    "name": "Priority",
    "active": "true",
    "table": "incident",
    "field": "priority",
    "filter_condition": "",
    "calculated_from": {"display_value": "", "value": ""},
    "sys_created_on": "2024-01-01 00:00:00",
    "sys_updated_on": "2024-06-01 00:00:00",
}


def _mock_upd_breakdown_resp(raw=None, status=200):
    if raw is None:
        raw = UPD_RAW_BREAKDOWN
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"result": raw}
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def bd2_auth():
    am = MagicMock()
    am.instance_url = "https://instance.service-now.com"
    am.get_headers.return_value = {"Authorization": "Bearer token"}
    return am


@pytest.fixture
def bd2_config():
    sc = MagicMock()
    sc.instance_url = None
    return sc


class TestUpdatePABreakdown:
    def test_update_name_by_sys_id(self, bd2_auth, bd2_config):
        from servicenow_mcp.tools.pa_tools import update_pa_breakdown

        # UPD_BREAKDOWN_SYS_ID is 32-char hex → resolver returns it directly
        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = _mock_upd_breakdown_resp()
            result = update_pa_breakdown(
                bd2_auth, bd2_config,
                {"breakdown_id": UPD_BREAKDOWN_SYS_ID, "name": "Urgency"},
            )
        assert result["success"] is True
        assert "breakdown" in result
        assert mock_req.call_args[1]["json"]["name"] == "Urgency"

    def test_update_active_false(self, bd2_auth, bd2_config):
        from servicenow_mcp.tools.pa_tools import update_pa_breakdown

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = _mock_upd_breakdown_resp()
            result = update_pa_breakdown(
                bd2_auth, bd2_config,
                {"breakdown_id": UPD_BREAKDOWN_SYS_ID, "active": False},
            )
        assert result["success"] is True
        assert mock_req.call_args[1]["json"]["active"] == "false"

    def test_update_table_and_field(self, bd2_auth, bd2_config):
        from servicenow_mcp.tools.pa_tools import update_pa_breakdown

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = _mock_upd_breakdown_resp()
            result = update_pa_breakdown(
                bd2_auth, bd2_config,
                {"breakdown_id": UPD_BREAKDOWN_SYS_ID, "table": "problem", "field": "state"},
            )
        assert result["success"] is True
        body = mock_req.call_args[1]["json"]
        assert body["table"] == "problem"
        assert body["field"] == "state"

    def test_update_filter_condition(self, bd2_auth, bd2_config):
        from servicenow_mcp.tools.pa_tools import update_pa_breakdown

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = _mock_upd_breakdown_resp()
            result = update_pa_breakdown(
                bd2_auth, bd2_config,
                {"breakdown_id": UPD_BREAKDOWN_SYS_ID, "filter_condition": "active=true"},
            )
        assert result["success"] is True
        assert mock_req.call_args[1]["json"]["filter_condition"] == "active=true"

    def test_no_fields_rejects(self, bd2_auth, bd2_config):
        from servicenow_mcp.tools.pa_tools import update_pa_breakdown

        result = update_pa_breakdown(bd2_auth, bd2_config, {"breakdown_id": UPD_BREAKDOWN_SYS_ID})
        assert result["success"] is False
        assert "No fields" in result["message"]

    def test_breakdown_not_found_by_name(self, bd2_auth, bd2_config):
        """Name-based lookup returns empty list → not found."""
        from servicenow_mcp.tools.pa_tools import update_pa_breakdown

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"result": []}),
                raise_for_status=MagicMock(),
            )
            result = update_pa_breakdown(
                bd2_auth, bd2_config,
                {"breakdown_id": "Ghost Breakdown", "name": "x"},
            )
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_404_on_patch_name_lookup(self, bd2_auth, bd2_config):
        """Name-based lookup succeeds, PATCH raises 404."""
        from servicenow_mcp.tools.pa_tools import update_pa_breakdown

        http_err = requests.exceptions.HTTPError(response=MagicMock(status_code=404))
        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.side_effect = [
                MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={"result": [{"sys_id": UPD_BREAKDOWN_SYS_ID}]}),
                    raise_for_status=MagicMock(),
                ),
                http_err,
            ]
            result = update_pa_breakdown(
                bd2_auth, bd2_config,
                {"breakdown_id": "Priority", "name": "Urgency"},
            )
        assert result["success"] is False

    def test_no_instance_url(self, bd2_config):
        from servicenow_mcp.tools.pa_tools import update_pa_breakdown

        am = MagicMock()
        am.instance_url = None
        bd2_config.instance_url = None
        result = update_pa_breakdown(am, bd2_config, {"breakdown_id": UPD_BREAKDOWN_SYS_ID, "name": "x"})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, bd2_auth, bd2_config):
        from servicenow_mcp.tools.pa_tools import update_pa_breakdown

        bd2_auth.get_headers.return_value = None
        result = update_pa_breakdown(bd2_auth, bd2_config, {"breakdown_id": UPD_BREAKDOWN_SYS_ID, "name": "x"})
        assert result["success"] is False
        assert "get_headers" in result["message"]

    def test_request_exception_direct_sys_id(self, bd2_auth, bd2_config):
        """PATCH raises Timeout for a direct sys_id call (no resolver call)."""
        from servicenow_mcp.tools.pa_tools import update_pa_breakdown

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            # Only one call: the PATCH itself (sys_id bypasses resolver)
            mock_req.side_effect = requests.exceptions.Timeout("timed out")
            result = update_pa_breakdown(
                bd2_auth, bd2_config,
                {"breakdown_id": UPD_BREAKDOWN_SYS_ID, "name": "x"},
            )
        assert result["success"] is False
        assert "timed out" in result["message"]


# ---------------------------------------------------------------------------
# delete_pa_breakdown
# ---------------------------------------------------------------------------


class TestDeletePABreakdown:
    def test_delete_by_sys_id_204(self, bd2_auth, bd2_config):
        from servicenow_mcp.tools.pa_tools import delete_pa_breakdown

        del_resp = MagicMock()
        del_resp.status_code = 204
        del_resp.raise_for_status = MagicMock()
        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = del_resp
            result = delete_pa_breakdown(
                bd2_auth, bd2_config, {"breakdown_id": UPD_BREAKDOWN_SYS_ID}
            )
        assert result["success"] is True
        assert result["breakdown_sys_id"] == UPD_BREAKDOWN_SYS_ID
        assert mock_req.call_args[0][0] == "DELETE"

    def test_delete_by_sys_id_200(self, bd2_auth, bd2_config):
        from servicenow_mcp.tools.pa_tools import delete_pa_breakdown

        del_resp = MagicMock()
        del_resp.status_code = 200
        del_resp.raise_for_status = MagicMock()
        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = del_resp
            result = delete_pa_breakdown(
                bd2_auth, bd2_config, {"breakdown_id": UPD_BREAKDOWN_SYS_ID}
            )
        assert result["success"] is True

    def test_delete_not_found_by_name(self, bd2_auth, bd2_config):
        """Name-based lookup returns empty list → not found."""
        from servicenow_mcp.tools.pa_tools import delete_pa_breakdown

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value={"result": []}),
                raise_for_status=MagicMock(),
            )
            result = delete_pa_breakdown(
                bd2_auth, bd2_config, {"breakdown_id": "Ghost Breakdown"}
            )
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_delete_404_http_error_name_lookup(self, bd2_auth, bd2_config):
        """Name-based lookup succeeds, DELETE raises 404."""
        from servicenow_mcp.tools.pa_tools import delete_pa_breakdown

        http_err = requests.exceptions.HTTPError(response=MagicMock(status_code=404))
        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            mock_req.side_effect = [
                MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={"result": [{"sys_id": UPD_BREAKDOWN_SYS_ID}]}),
                    raise_for_status=MagicMock(),
                ),
                http_err,
            ]
            result = delete_pa_breakdown(
                bd2_auth, bd2_config, {"breakdown_id": "Priority"}
            )
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_delete_no_instance_url(self, bd2_config):
        from servicenow_mcp.tools.pa_tools import delete_pa_breakdown

        am = MagicMock()
        am.instance_url = None
        bd2_config.instance_url = None
        result = delete_pa_breakdown(am, bd2_config, {"breakdown_id": UPD_BREAKDOWN_SYS_ID})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_delete_no_headers(self, bd2_auth, bd2_config):
        from servicenow_mcp.tools.pa_tools import delete_pa_breakdown

        bd2_auth.get_headers.return_value = None
        result = delete_pa_breakdown(bd2_auth, bd2_config, {"breakdown_id": UPD_BREAKDOWN_SYS_ID})
        assert result["success"] is False
        assert "get_headers" in result["message"]

    def test_delete_network_error_direct_sys_id(self, bd2_auth, bd2_config):
        """DELETE raises ConnectionError for a direct sys_id (no resolver call)."""
        from servicenow_mcp.tools.pa_tools import delete_pa_breakdown

        with patch("servicenow_mcp.tools.pa_tools._make_request") as mock_req:
            # Only one call: the DELETE itself (sys_id bypasses resolver)
            mock_req.side_effect = requests.exceptions.ConnectionError("network failure")
            result = delete_pa_breakdown(
                bd2_auth, bd2_config, {"breakdown_id": UPD_BREAKDOWN_SYS_ID}
            )
        assert result["success"] is False
        assert "network failure" in result["message"]


# ---------------------------------------------------------------------------
# UpdatePADashboardParams / DeletePADashboardParams validation
# ---------------------------------------------------------------------------


class TestPADashboardMutationParams:
    def test_update_requires_dashboard_id(self):
        from pydantic import ValidationError
        from servicenow_mcp.tools.pa_tools import UpdatePADashboardParams

        with pytest.raises(ValidationError):
            UpdatePADashboardParams()

    def test_update_all_optional_fields(self):
        from servicenow_mcp.tools.pa_tools import UpdatePADashboardParams

        p = UpdatePADashboardParams(
            dashboard_id=UPD_DASHBOARD_SYS_ID,
            title="New",
            description="desc",
            active=True,
            order=3,
            owner="admin",
        )
        assert p.title == "New"
        assert p.description == "desc"
        assert p.active is True
        assert p.order == 3
        assert p.owner == "admin"

    def test_delete_requires_dashboard_id(self):
        from pydantic import ValidationError
        from servicenow_mcp.tools.pa_tools import DeletePADashboardParams

        with pytest.raises(ValidationError):
            DeletePADashboardParams()

    def test_delete_accepts_sys_id(self):
        from servicenow_mcp.tools.pa_tools import DeletePADashboardParams

        p = DeletePADashboardParams(dashboard_id=UPD_DASHBOARD_SYS_ID)
        assert p.dashboard_id == UPD_DASHBOARD_SYS_ID


# ---------------------------------------------------------------------------
# UpdatePABreakdownParams / DeletePABreakdownParams validation
# ---------------------------------------------------------------------------


class TestPABreakdownMutationParams:
    def test_update_requires_breakdown_id(self):
        from pydantic import ValidationError
        from servicenow_mcp.tools.pa_tools import UpdatePABreakdownParams

        with pytest.raises(ValidationError):
            UpdatePABreakdownParams()

    def test_update_all_optional_fields(self):
        from servicenow_mcp.tools.pa_tools import UpdatePABreakdownParams

        p = UpdatePABreakdownParams(
            breakdown_id=UPD_BREAKDOWN_SYS_ID,
            name="Severity",
            active=False,
            table="problem",
            field="severity",
            filter_condition="active=true",
        )
        assert p.name == "Severity"
        assert p.active is False
        assert p.table == "problem"
        assert p.field == "severity"
        assert p.filter_condition == "active=true"

    def test_delete_requires_breakdown_id(self):
        from pydantic import ValidationError
        from servicenow_mcp.tools.pa_tools import DeletePABreakdownParams

        with pytest.raises(ValidationError):
            DeletePABreakdownParams()

    def test_delete_accepts_name(self):
        from servicenow_mcp.tools.pa_tools import DeletePABreakdownParams

        p = DeletePABreakdownParams(breakdown_id="Priority")
        assert p.breakdown_id == "Priority"


# ---------------------------------------------------------------------------
# PA Target tools
# ---------------------------------------------------------------------------


RAW_TARGET = {
    "sys_id": "t" * 32,
    "indicator": {"display_value": "Incident Count", "value": SYS_ID_32},
    "target": "50",
    "minimum": "10",
    "maximum": "100",
    "period": {"display_value": "Q1 2024", "value": "p" * 32},
    "active": "true",
    "sys_created_on": "2024-01-01 00:00:00",
    "sys_updated_on": "2024-06-01 00:00:00",
}

TARGET_SYS_ID = "t" * 32


class TestFormatPATarget:
    def test_basic_fields(self):
        from servicenow_mcp.tools.pa_tools import _format_pa_target

        result = _format_pa_target(RAW_TARGET)
        assert result["sys_id"] == TARGET_SYS_ID
        assert result["target"] == "50"
        assert result["minimum"] == "10"
        assert result["maximum"] == "100"
        assert result["active"] == "true"
        assert result["created_on"] == "2024-01-01 00:00:00"
        assert result["updated_on"] == "2024-06-01 00:00:00"

    def test_reference_fields_extracted(self):
        from servicenow_mcp.tools.pa_tools import _format_pa_target

        result = _format_pa_target(RAW_TARGET)
        assert result["indicator"] == "Incident Count"
        assert result["period"] == "Q1 2024"

    def test_string_reference_fields(self):
        from servicenow_mcp.tools.pa_tools import _format_pa_target

        rec = {**RAW_TARGET, "indicator": "Inc Count", "period": "2024-Q2"}
        result = _format_pa_target(rec)
        assert result["indicator"] == "Inc Count"
        assert result["period"] == "2024-Q2"

    def test_missing_fields_return_none(self):
        from servicenow_mcp.tools.pa_tools import _format_pa_target

        result = _format_pa_target({})
        assert result["sys_id"] is None
        assert result["target"] is None
        assert result["indicator"] is None


# ---------------------------------------------------------------------------
# ListPATargetsParams
# ---------------------------------------------------------------------------


class TestListPATargetsParams:
    def test_defaults(self):
        from servicenow_mcp.tools.pa_tools import ListPATargetsParams

        p = ListPATargetsParams()
        assert p.limit == 20
        assert p.offset == 0
        assert p.indicator_id is None
        assert p.active is None
        assert p.created_after is None
        assert p.created_before is None

    def test_all_fields(self):
        from servicenow_mcp.tools.pa_tools import ListPATargetsParams

        p = ListPATargetsParams(
            limit=5,
            offset=10,
            indicator_id=SYS_ID_32,
            active=True,
            created_after="2024-01-01",
            created_before="2024-12-31",
        )
        assert p.limit == 5
        assert p.offset == 10
        assert p.indicator_id == SYS_ID_32
        assert p.active is True
        assert p.created_after == "2024-01-01"
        assert p.created_before == "2024-12-31"

    def test_invalid_date_rejected(self):
        from pydantic import ValidationError
        from servicenow_mcp.tools.pa_tools import ListPATargetsParams

        with pytest.raises(ValidationError):
            ListPATargetsParams(created_after="not-a-date")


# ---------------------------------------------------------------------------
# GetPATargetParams
# ---------------------------------------------------------------------------


class TestGetPATargetParams:
    def test_requires_target_id(self):
        from pydantic import ValidationError
        from servicenow_mcp.tools.pa_tools import GetPATargetParams

        with pytest.raises(ValidationError):
            GetPATargetParams()

    def test_accepts_sys_id(self):
        from servicenow_mcp.tools.pa_tools import GetPATargetParams

        p = GetPATargetParams(target_id=TARGET_SYS_ID)
        assert p.target_id == TARGET_SYS_ID


# ---------------------------------------------------------------------------
# list_pa_targets
# ---------------------------------------------------------------------------


class TestListPATargets:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_returns_targets(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_TARGET]}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(auth_manager, server_config, {})
        assert result["success"] is True
        assert len(result["targets"]) == 1
        assert result["targets"][0]["sys_id"] == TARGET_SYS_ID

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_empty_result(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(auth_manager, server_config, {})
        assert result["success"] is True
        assert result["targets"] == []
        assert result["count"] == 0

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_filter_by_active(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_TARGET]}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(auth_manager, server_config, {"active": True})
        assert result["success"] is True
        call_kwargs = mock_req.call_args
        query_str = call_kwargs[1]["params"]["sysparm_query"]
        assert "active=true" in query_str

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_filter_by_inactive(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": []}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(auth_manager, server_config, {"active": False})
        assert result["success"] is True
        call_kwargs = mock_req.call_args
        query_str = call_kwargs[1]["params"]["sysparm_query"]
        assert "active=false" in query_str

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_filter_by_date_range(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_TARGET]}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(
            auth_manager,
            server_config,
            {"created_after": "2024-01-01", "created_before": "2024-12-31"},
        )
        assert result["success"] is True
        call_kwargs = mock_req.call_args
        query_str = call_kwargs[1]["params"]["sysparm_query"]
        assert "sys_created_on>=2024-01-01" in query_str
        assert "sys_created_on<=2024-12-31" in query_str

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_filter_by_indicator_sys_id(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_TARGET]}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(auth_manager, server_config, {"indicator_id": SYS_ID_32})
        assert result["success"] is True
        call_kwargs = mock_req.call_args
        query_str = call_kwargs[1]["params"]["sysparm_query"]
        assert f"indicator={SYS_ID_32}" in query_str

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_indicator_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_filter_by_indicator_name_resolved(
        self, mock_req, mock_resolve, auth_manager, server_config
    ):
        mock_resolve.return_value = SYS_ID_32
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": [RAW_TARGET]}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(auth_manager, server_config, {"indicator_id": "Incident Count"})
        assert result["success"] is True
        mock_resolve.assert_called_once()

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_indicator_sys_id")
    def test_indicator_not_found(self, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = None

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(auth_manager, server_config, {"indicator_id": "Unknown"})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = requests.exceptions.HTTPError(response=mock_resp)
        mock_req.return_value = MagicMock(raise_for_status=MagicMock(side_effect=exc))

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(auth_manager, server_config, {})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("fail")

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(auth_manager, server_config, {})
        assert result["success"] is False
        assert "fail" in result["message"]

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        sc = MagicMock()
        sc.instance_url = None

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(am, sc, {})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, auth_manager, server_config):
        auth_manager.get_headers.return_value = None

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(auth_manager, server_config, {})
        assert result["success"] is False
        assert "get_headers" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_pagination_has_more(self, mock_req, auth_manager, server_config):
        # Return exactly limit=20 items; _paginated_list_response sets has_more when count==limit
        many_targets = [
            {**RAW_TARGET, "sys_id": f"{i}" * 32} for i in range(1, 21)
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": many_targets}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import list_pa_targets

        result = list_pa_targets(auth_manager, server_config, {"limit": 20, "offset": 0})
        assert result["success"] is True
        assert result["has_more"] is True
        assert result["next_offset"] == 20


# ---------------------------------------------------------------------------
# get_pa_target
# ---------------------------------------------------------------------------


class TestGetPATarget:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_returns_target(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_TARGET}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import get_pa_target

        result = get_pa_target(auth_manager, server_config, {"target_id": TARGET_SYS_ID})
        assert result["success"] is True
        assert result["target"]["sys_id"] == TARGET_SYS_ID
        assert result["target"]["target"] == "50"
        assert result["target"]["minimum"] == "10"
        assert result["target"]["maximum"] == "100"

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_empty_result(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": None}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import get_pa_target

        result = get_pa_target(auth_manager, server_config, {"target_id": TARGET_SYS_ID})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_empty_dict_result(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {}}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import get_pa_target

        result = get_pa_target(auth_manager, server_config, {"target_id": TARGET_SYS_ID})
        # empty dict is falsy, treated as not found
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_404_error(self, mock_req, auth_manager, server_config):
        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 404
        exc = requests.exceptions.HTTPError(response=mock_http_resp)
        mock_req.return_value = MagicMock(raise_for_status=MagicMock(side_effect=exc))

        from servicenow_mcp.tools.pa_tools import get_pa_target

        result = get_pa_target(auth_manager, server_config, {"target_id": TARGET_SYS_ID})
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error_non_404(self, mock_req, auth_manager, server_config):
        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 500
        exc = requests.exceptions.HTTPError(response=mock_http_resp)
        mock_req.return_value = MagicMock(raise_for_status=MagicMock(side_effect=exc))

        from servicenow_mcp.tools.pa_tools import get_pa_target

        result = get_pa_target(auth_manager, server_config, {"target_id": TARGET_SYS_ID})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("fail")

        from servicenow_mcp.tools.pa_tools import get_pa_target

        result = get_pa_target(auth_manager, server_config, {"target_id": TARGET_SYS_ID})
        assert result["success"] is False
        assert "fail" in result["message"]

    def test_missing_target_id(self, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import get_pa_target

        result = get_pa_target(auth_manager, server_config, {})
        assert result["success"] is False

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        sc = MagicMock()
        sc.instance_url = None

        from servicenow_mcp.tools.pa_tools import get_pa_target

        result = get_pa_target(am, sc, {"target_id": TARGET_SYS_ID})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, auth_manager, server_config):
        auth_manager.get_headers.return_value = None

        from servicenow_mcp.tools.pa_tools import get_pa_target

        result = get_pa_target(auth_manager, server_config, {"target_id": TARGET_SYS_ID})
        assert result["success"] is False
        assert "get_headers" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_reference_fields_normalised(self, mock_req, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_TARGET}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import get_pa_target

        result = get_pa_target(auth_manager, server_config, {"target_id": TARGET_SYS_ID})
        assert result["success"] is True
        assert result["target"]["indicator"] == "Incident Count"
        assert result["target"]["period"] == "Q1 2024"


# ---------------------------------------------------------------------------
# create_pa_target
# ---------------------------------------------------------------------------


class TestCreatePATarget:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_creates_target_with_all_fields(self, mock_req, auth_manager, server_config):
        # First call: resolve indicator sys_id; second call: POST
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        resolve_resp.raise_for_status = MagicMock()
        create_resp = MagicMock()
        create_resp.json.return_value = {"result": RAW_TARGET}
        create_resp.raise_for_status = MagicMock()
        mock_req.side_effect = [resolve_resp, create_resp]

        from servicenow_mcp.tools.pa_tools import create_pa_target

        result = create_pa_target(
            auth_manager,
            server_config,
            {
                "indicator_id": "Incident Count",
                "target": "50",
                "minimum": "10",
                "maximum": "100",
                "period": "p" * 32,
                "active": True,
            },
        )
        assert result["success"] is True
        assert result["target"]["target"] == "50"
        assert "created" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_creates_target_with_sys_id_indicator(self, mock_req, auth_manager, server_config):
        create_resp = MagicMock()
        create_resp.json.return_value = {"result": RAW_TARGET}
        create_resp.raise_for_status = MagicMock()
        mock_req.return_value = create_resp

        from servicenow_mcp.tools.pa_tools import create_pa_target

        result = create_pa_target(
            auth_manager,
            server_config,
            {"indicator_id": SYS_ID_32, "target": "75"},
        )
        assert result["success"] is True
        assert result["target"]["sys_id"] == TARGET_SYS_ID

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_indicator_not_found(self, mock_req, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.json.return_value = {"result": []}
        resolve_resp.raise_for_status = MagicMock()
        mock_req.return_value = resolve_resp

        from servicenow_mcp.tools.pa_tools import create_pa_target

        result = create_pa_target(
            auth_manager,
            server_config,
            {"indicator_id": "Unknown Indicator"},
        )
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_missing_indicator_id(self, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import create_pa_target

        result = create_pa_target(auth_manager, server_config, {})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error(self, mock_req, auth_manager, server_config):
        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 400
        exc = requests.exceptions.HTTPError(response=mock_http_resp)
        fail_resp = MagicMock()
        fail_resp.raise_for_status = MagicMock(side_effect=exc)
        mock_req.return_value = fail_resp

        from servicenow_mcp.tools.pa_tools import create_pa_target

        result = create_pa_target(
            auth_manager, server_config, {"indicator_id": SYS_ID_32}
        )
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("down")

        from servicenow_mcp.tools.pa_tools import create_pa_target

        result = create_pa_target(
            auth_manager, server_config, {"indicator_id": SYS_ID_32}
        )
        assert result["success"] is False
        assert "down" in result["message"]

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        sc = MagicMock()
        sc.instance_url = None

        from servicenow_mcp.tools.pa_tools import create_pa_target

        result = create_pa_target(am, sc, {"indicator_id": SYS_ID_32})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, auth_manager, server_config):
        auth_manager.get_headers.return_value = None

        from servicenow_mcp.tools.pa_tools import create_pa_target

        result = create_pa_target(auth_manager, server_config, {"indicator_id": SYS_ID_32})
        assert result["success"] is False
        assert "get_headers" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_inactive_target(self, mock_req, auth_manager, server_config):
        create_resp = MagicMock()
        create_resp.json.return_value = {"result": {**RAW_TARGET, "active": "false"}}
        create_resp.raise_for_status = MagicMock()
        mock_req.return_value = create_resp

        from servicenow_mcp.tools.pa_tools import create_pa_target

        result = create_pa_target(
            auth_manager, server_config, {"indicator_id": SYS_ID_32, "active": False}
        )
        assert result["success"] is True
        assert result["target"]["active"] == "false"


# ---------------------------------------------------------------------------
# update_pa_target
# ---------------------------------------------------------------------------


class TestUpdatePATarget:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_updates_target_value(self, mock_req, auth_manager, server_config):
        patch_resp = MagicMock()
        patch_resp.json.return_value = {"result": {**RAW_TARGET, "target": "75"}}
        patch_resp.raise_for_status = MagicMock()
        mock_req.return_value = patch_resp

        from servicenow_mcp.tools.pa_tools import update_pa_target

        result = update_pa_target(
            auth_manager,
            server_config,
            {"target_id": TARGET_SYS_ID, "target": "75"},
        )
        assert result["success"] is True
        assert result["target"]["target"] == "75"
        assert "updated" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_updates_all_fields(self, mock_req, auth_manager, server_config):
        resolve_ind_resp = MagicMock()
        resolve_ind_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        resolve_ind_resp.raise_for_status = MagicMock()
        patch_resp = MagicMock()
        patch_resp.json.return_value = {"result": RAW_TARGET}
        patch_resp.raise_for_status = MagicMock()
        # indicator resolver is called first (name lookup), then the PATCH
        mock_req.side_effect = [resolve_ind_resp, patch_resp]

        from servicenow_mcp.tools.pa_tools import update_pa_target

        result = update_pa_target(
            auth_manager,
            server_config,
            {
                "target_id": TARGET_SYS_ID,
                "indicator_id": "New Indicator",
                "target": "90",
                "minimum": "20",
                "maximum": "150",
                "period": "p" * 32,
                "active": False,
            },
        )
        assert result["success"] is True

    def test_missing_target_id(self, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import update_pa_target

        result = update_pa_target(auth_manager, server_config, {})
        assert result["success"] is False

    def test_no_fields_to_update(self, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import update_pa_target

        result = update_pa_target(
            auth_manager, server_config, {"target_id": TARGET_SYS_ID}
        )
        assert result["success"] is False
        assert "No fields" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_target_id_used_directly_in_url(self, mock_req, auth_manager, server_config):
        # target_id is used directly without resolution; any string is accepted
        patch_resp = MagicMock()
        patch_resp.json.return_value = {"result": RAW_TARGET}
        patch_resp.raise_for_status = MagicMock()
        mock_req.return_value = patch_resp

        from servicenow_mcp.tools.pa_tools import update_pa_target

        result = update_pa_target(
            auth_manager, server_config, {"target_id": "some_sys_id", "target": "50"}
        )
        assert result["success"] is True
        called_url = mock_req.call_args[0][1]
        assert "some_sys_id" in called_url

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_indicator_not_found_during_update(self, mock_req, auth_manager, server_config):
        resolve_ind_resp = MagicMock()
        resolve_ind_resp.json.return_value = {"result": []}
        resolve_ind_resp.raise_for_status = MagicMock()
        mock_req.return_value = resolve_ind_resp

        from servicenow_mcp.tools.pa_tools import update_pa_target

        result = update_pa_target(
            auth_manager,
            server_config,
            {"target_id": TARGET_SYS_ID, "indicator_id": "Unknown"},
        )
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_404_error(self, mock_req, auth_manager, server_config):
        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 404
        exc = requests.exceptions.HTTPError(response=mock_http_resp)
        fail_resp = MagicMock()
        fail_resp.raise_for_status = MagicMock(side_effect=exc)
        mock_req.return_value = fail_resp

        from servicenow_mcp.tools.pa_tools import update_pa_target

        result = update_pa_target(
            auth_manager, server_config, {"target_id": TARGET_SYS_ID, "target": "80"}
        )
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error_non_404(self, mock_req, auth_manager, server_config):
        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 500
        exc = requests.exceptions.HTTPError(response=mock_http_resp)
        fail_resp = MagicMock()
        fail_resp.raise_for_status = MagicMock(side_effect=exc)
        mock_req.return_value = fail_resp

        from servicenow_mcp.tools.pa_tools import update_pa_target

        result = update_pa_target(
            auth_manager, server_config, {"target_id": TARGET_SYS_ID, "target": "80"}
        )
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("fail")

        from servicenow_mcp.tools.pa_tools import update_pa_target

        result = update_pa_target(
            auth_manager, server_config, {"target_id": TARGET_SYS_ID, "target": "80"}
        )
        assert result["success"] is False
        assert "fail" in result["message"]

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        sc = MagicMock()
        sc.instance_url = None

        from servicenow_mcp.tools.pa_tools import update_pa_target

        result = update_pa_target(am, sc, {"target_id": TARGET_SYS_ID, "target": "80"})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, auth_manager, server_config):
        auth_manager.get_headers.return_value = None

        from servicenow_mcp.tools.pa_tools import update_pa_target

        result = update_pa_target(
            auth_manager, server_config, {"target_id": TARGET_SYS_ID, "target": "80"}
        )
        assert result["success"] is False
        assert "get_headers" in result["message"]


# ---------------------------------------------------------------------------
# delete_pa_target
# ---------------------------------------------------------------------------


class TestDeletePATarget:
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_deletes_target_204(self, mock_req, auth_manager, server_config):
        delete_resp = MagicMock()
        delete_resp.status_code = 204
        mock_req.return_value = delete_resp

        from servicenow_mcp.tools.pa_tools import delete_pa_target

        result = delete_pa_target(
            auth_manager, server_config, {"target_id": TARGET_SYS_ID}
        )
        assert result["success"] is True
        assert result["target_sys_id"] == TARGET_SYS_ID
        assert "deleted" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_deletes_target_200(self, mock_req, auth_manager, server_config):
        delete_resp = MagicMock()
        delete_resp.status_code = 200
        mock_req.return_value = delete_resp

        from servicenow_mcp.tools.pa_tools import delete_pa_target

        result = delete_pa_target(
            auth_manager, server_config, {"target_id": TARGET_SYS_ID}
        )
        assert result["success"] is True
        assert result["target_sys_id"] == TARGET_SYS_ID

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_target_id_used_directly_in_url(self, mock_req, auth_manager, server_config):
        # target_id is used directly without resolution
        delete_resp = MagicMock()
        delete_resp.status_code = 204
        mock_req.return_value = delete_resp

        from servicenow_mcp.tools.pa_tools import delete_pa_target

        result = delete_pa_target(
            auth_manager, server_config, {"target_id": "some_target_id"}
        )
        assert result["success"] is True
        called_url = mock_req.call_args[0][1]
        assert "some_target_id" in called_url

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_404_error(self, mock_req, auth_manager, server_config):
        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 404
        exc = requests.exceptions.HTTPError(response=mock_http_resp)
        fail_resp = MagicMock()
        fail_resp.status_code = 404
        fail_resp.raise_for_status = MagicMock(side_effect=exc)
        mock_req.return_value = fail_resp

        from servicenow_mcp.tools.pa_tools import delete_pa_target

        result = delete_pa_target(
            auth_manager, server_config, {"target_id": TARGET_SYS_ID}
        )
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error_non_404(self, mock_req, auth_manager, server_config):
        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 500
        exc = requests.exceptions.HTTPError(response=mock_http_resp)
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.raise_for_status = MagicMock(side_effect=exc)
        mock_req.return_value = fail_resp

        from servicenow_mcp.tools.pa_tools import delete_pa_target

        result = delete_pa_target(
            auth_manager, server_config, {"target_id": TARGET_SYS_ID}
        )
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, auth_manager, server_config):
        mock_req.side_effect = requests.exceptions.ConnectionError("fail")

        from servicenow_mcp.tools.pa_tools import delete_pa_target

        result = delete_pa_target(
            auth_manager, server_config, {"target_id": TARGET_SYS_ID}
        )
        assert result["success"] is False
        assert "fail" in result["message"]

    def test_missing_target_id(self, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import delete_pa_target

        result = delete_pa_target(auth_manager, server_config, {})
        assert result["success"] is False

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        sc = MagicMock()
        sc.instance_url = None

        from servicenow_mcp.tools.pa_tools import delete_pa_target

        result = delete_pa_target(am, sc, {"target_id": TARGET_SYS_ID})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, auth_manager, server_config):
        auth_manager.get_headers.return_value = None

        from servicenow_mcp.tools.pa_tools import delete_pa_target

        result = delete_pa_target(auth_manager, server_config, {"target_id": TARGET_SYS_ID})
        assert result["success"] is False
        assert "get_headers" in result["message"]


# ---------------------------------------------------------------------------
# _resolve_pa_target_sys_id
# ---------------------------------------------------------------------------


class TestResolvePATargetSysId:
    def test_hex_string_returned_directly(self):
        from servicenow_mcp.tools.pa_tools import _resolve_pa_target_sys_id

        # SYS_ID_32 = "a"*32 is a valid hex string
        result = _resolve_pa_target_sys_id(SYS_ID_32, "https://example.service-now.com", {})
        assert result == SYS_ID_32

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_non_hex_lookup_succeeds(self, mock_req):
        resp = MagicMock()
        resp.json.return_value = {"result": [{"sys_id": TARGET_SYS_ID}]}
        resp.raise_for_status = MagicMock()
        mock_req.return_value = resp

        from servicenow_mcp.tools.pa_tools import _resolve_pa_target_sys_id

        result = _resolve_pa_target_sys_id("nonhex_id", "https://example.service-now.com", {})
        assert result == TARGET_SYS_ID

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_non_hex_lookup_not_found(self, mock_req):
        resp = MagicMock()
        resp.json.return_value = {"result": []}
        resp.raise_for_status = MagicMock()
        mock_req.return_value = resp

        from servicenow_mcp.tools.pa_tools import _resolve_pa_target_sys_id

        result = _resolve_pa_target_sys_id("nonhex_id", "https://example.service-now.com", {})
        assert result is None

    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception_returns_none(self, mock_req):
        mock_req.side_effect = requests.exceptions.ConnectionError("fail")

        from servicenow_mcp.tools.pa_tools import _resolve_pa_target_sys_id

        result = _resolve_pa_target_sys_id("nonhex_id", "https://example.service-now.com", {})
        assert result is None

# ---------------------------------------------------------------------------
# create_pa_widget
# ---------------------------------------------------------------------------

BREAKDOWN_SYS_ID_W = "bk" * 16  # 32-char hex-like string for breakdown


class TestCreatePAWidget:
    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_indicator_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_creates_widget_minimal(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = SYS_ID_32
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_WIDGET}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import create_pa_widget

        result = create_pa_widget(
            auth_manager,
            server_config,
            {"name": "Open Incidents Chart", "indicator_id": SYS_ID_32},
        )
        assert result["success"] is True
        assert "widget" in result
        assert "created" in result["message"]
        call_args = mock_req.call_args
        body = call_args[1]["json"]
        assert body["name"] == "Open Incidents Chart"
        assert body["indicator"] == SYS_ID_32

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_breakdown_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_dashboard_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_indicator_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_creates_widget_all_fields(
        self, mock_req, mock_ind, mock_dash, mock_bkdn, auth_manager, server_config
    ):
        mock_ind.return_value = SYS_ID_32
        mock_dash.return_value = DASHBOARD_SYS_ID
        mock_bkdn.return_value = BREAKDOWN_SYS_ID_W
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_WIDGET}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import create_pa_widget

        result = create_pa_widget(
            auth_manager,
            server_config,
            {
                "name": "Open Incidents Chart",
                "indicator_id": SYS_ID_32,
                "widget_type": "chart",
                "dashboard_id": DASHBOARD_SYS_ID,
                "breakdown_id": BREAKDOWN_SYS_ID_W,
                "description": "desc",
                "color": "blue",
                "active": True,
            },
        )
        assert result["success"] is True
        body = mock_req.call_args[1]["json"]
        assert body["widget_type"] == "chart"
        assert body["home_page"] == DASHBOARD_SYS_ID
        assert body["breakdown"] == BREAKDOWN_SYS_ID_W
        assert body["description"] == "desc"
        assert body["color"] == "blue"
        assert body["active"] == "true"

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_indicator_sys_id")
    def test_indicator_not_found(self, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = None

        from servicenow_mcp.tools.pa_tools import create_pa_widget

        result = create_pa_widget(
            auth_manager,
            server_config,
            {"name": "Widget", "indicator_id": "Unknown"},
        )
        assert result["success"] is False
        assert "indicator" in result["message"].lower()

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_indicator_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_dashboard_sys_id")
    def test_dashboard_not_found(self, mock_dash, mock_ind, auth_manager, server_config):
        mock_ind.return_value = SYS_ID_32
        mock_dash.return_value = None

        from servicenow_mcp.tools.pa_tools import create_pa_widget

        result = create_pa_widget(
            auth_manager,
            server_config,
            {"name": "Widget", "indicator_id": SYS_ID_32, "dashboard_id": "Unknown"},
        )
        assert result["success"] is False
        assert "dashboard" in result["message"].lower()

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_indicator_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_breakdown_sys_id")
    def test_breakdown_not_found(self, mock_bkdn, mock_ind, auth_manager, server_config):
        mock_ind.return_value = SYS_ID_32
        mock_bkdn.return_value = None

        from servicenow_mcp.tools.pa_tools import create_pa_widget

        result = create_pa_widget(
            auth_manager,
            server_config,
            {"name": "Widget", "indicator_id": SYS_ID_32, "breakdown_id": "Unknown"},
        )
        assert result["success"] is False
        assert "breakdown" in result["message"].lower()

    def test_missing_required_fields(self, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import create_pa_widget

        result = create_pa_widget(auth_manager, server_config, {"name": "Widget"})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_indicator_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = SYS_ID_32
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        exc = requests.exceptions.HTTPError(response=mock_resp)
        mock_req.return_value = MagicMock(raise_for_status=MagicMock(side_effect=exc))

        from servicenow_mcp.tools.pa_tools import create_pa_widget

        result = create_pa_widget(
            auth_manager, server_config, {"name": "W", "indicator_id": SYS_ID_32}
        )
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_indicator_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = SYS_ID_32
        mock_req.side_effect = requests.exceptions.ConnectionError("fail")

        from servicenow_mcp.tools.pa_tools import create_pa_widget

        result = create_pa_widget(
            auth_manager, server_config, {"name": "W", "indicator_id": SYS_ID_32}
        )
        assert result["success"] is False

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        sc = MagicMock()
        sc.instance_url = None

        from servicenow_mcp.tools.pa_tools import create_pa_widget

        result = create_pa_widget(am, sc, {"name": "W", "indicator_id": SYS_ID_32})
        assert result["success"] is False

    def test_no_headers(self, auth_manager, server_config):
        auth_manager.get_headers.return_value = None

        from servicenow_mcp.tools.pa_tools import create_pa_widget

        result = create_pa_widget(
            auth_manager, server_config, {"name": "W", "indicator_id": SYS_ID_32}
        )
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_indicator_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_inactive_widget(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = SYS_ID_32
        inactive_widget = dict(RAW_WIDGET, active="false")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": inactive_widget}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import create_pa_widget

        result = create_pa_widget(
            auth_manager,
            server_config,
            {"name": "Widget", "indicator_id": SYS_ID_32, "active": False},
        )
        assert result["success"] is True
        body = mock_req.call_args[1]["json"]
        assert body["active"] == "false"


# ---------------------------------------------------------------------------
# update_pa_widget
# ---------------------------------------------------------------------------


class TestUpdatePAWidget:
    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_updates_name(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = WIDGET_SYS_ID
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_WIDGET}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import update_pa_widget

        result = update_pa_widget(
            auth_manager,
            server_config,
            {"widget_id": WIDGET_SYS_ID, "name": "Renamed Widget"},
        )
        assert result["success"] is True
        assert "updated" in result["message"]
        body = mock_req.call_args[1]["json"]
        assert body["name"] == "Renamed Widget"

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_breakdown_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_dashboard_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_indicator_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_updates_all_fields(
        self, mock_req, mock_wid, mock_ind, mock_dash, mock_bkdn, auth_manager, server_config
    ):
        mock_wid.return_value = WIDGET_SYS_ID
        mock_ind.return_value = SYS_ID_32
        mock_dash.return_value = DASHBOARD_SYS_ID
        mock_bkdn.return_value = BREAKDOWN_SYS_ID_W
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": RAW_WIDGET}
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import update_pa_widget

        result = update_pa_widget(
            auth_manager,
            server_config,
            {
                "widget_id": WIDGET_SYS_ID,
                "name": "New Name",
                "indicator_id": SYS_ID_32,
                "widget_type": "scorecard",
                "dashboard_id": DASHBOARD_SYS_ID,
                "breakdown_id": BREAKDOWN_SYS_ID_W,
                "description": "updated",
                "color": "red",
                "active": False,
            },
        )
        assert result["success"] is True
        body = mock_req.call_args[1]["json"]
        assert body["widget_type"] == "scorecard"
        assert body["active"] == "false"
        assert body["indicator"] == SYS_ID_32
        assert body["home_page"] == DASHBOARD_SYS_ID
        assert body["breakdown"] == BREAKDOWN_SYS_ID_W

    def test_missing_widget_id(self, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import update_pa_widget

        result = update_pa_widget(auth_manager, server_config, {"name": "X"})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    def test_no_fields_to_update(self, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = WIDGET_SYS_ID

        from servicenow_mcp.tools.pa_tools import update_pa_widget

        result = update_pa_widget(
            auth_manager, server_config, {"widget_id": WIDGET_SYS_ID}
        )
        assert result["success"] is False
        assert "No fields" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    def test_widget_not_found(self, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = None

        from servicenow_mcp.tools.pa_tools import update_pa_widget

        result = update_pa_widget(
            auth_manager,
            server_config,
            {"widget_id": "unknown", "name": "X"},
        )
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_indicator_sys_id")
    def test_indicator_not_found_during_update(
        self, mock_ind, mock_wid, auth_manager, server_config
    ):
        mock_wid.return_value = WIDGET_SYS_ID
        mock_ind.return_value = None

        from servicenow_mcp.tools.pa_tools import update_pa_widget

        result = update_pa_widget(
            auth_manager,
            server_config,
            {"widget_id": WIDGET_SYS_ID, "indicator_id": "Unknown"},
        )
        assert result["success"] is False
        assert "indicator" in result["message"].lower()

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_404_error(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = WIDGET_SYS_ID
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        exc = requests.exceptions.HTTPError(response=mock_resp)
        mock_req.return_value = MagicMock(raise_for_status=MagicMock(side_effect=exc))

        from servicenow_mcp.tools.pa_tools import update_pa_widget

        result = update_pa_widget(
            auth_manager, server_config, {"widget_id": WIDGET_SYS_ID, "name": "X"}
        )
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error_non_404(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = WIDGET_SYS_ID
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = requests.exceptions.HTTPError(response=mock_resp)
        mock_req.return_value = MagicMock(raise_for_status=MagicMock(side_effect=exc))

        from servicenow_mcp.tools.pa_tools import update_pa_widget

        result = update_pa_widget(
            auth_manager, server_config, {"widget_id": WIDGET_SYS_ID, "name": "X"}
        )
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = WIDGET_SYS_ID
        mock_req.side_effect = requests.exceptions.ConnectionError("fail")

        from servicenow_mcp.tools.pa_tools import update_pa_widget

        result = update_pa_widget(
            auth_manager, server_config, {"widget_id": WIDGET_SYS_ID, "name": "X"}
        )
        assert result["success"] is False

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        sc = MagicMock()
        sc.instance_url = None

        from servicenow_mcp.tools.pa_tools import update_pa_widget

        result = update_pa_widget(am, sc, {"widget_id": WIDGET_SYS_ID, "name": "X"})
        assert result["success"] is False

    def test_no_headers(self, auth_manager, server_config):
        auth_manager.get_headers.return_value = None

        from servicenow_mcp.tools.pa_tools import update_pa_widget

        result = update_pa_widget(
            auth_manager, server_config, {"widget_id": WIDGET_SYS_ID, "name": "X"}
        )
        assert result["success"] is False


# ---------------------------------------------------------------------------
# delete_pa_widget
# ---------------------------------------------------------------------------


class TestDeletePAWidget:
    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_deletes_widget_204(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = WIDGET_SYS_ID
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import delete_pa_widget

        result = delete_pa_widget(
            auth_manager, server_config, {"widget_id": WIDGET_SYS_ID}
        )
        assert result["success"] is True
        assert result["widget_sys_id"] == WIDGET_SYS_ID
        assert "deleted" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_deletes_widget_200(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = WIDGET_SYS_ID
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import delete_pa_widget

        result = delete_pa_widget(
            auth_manager, server_config, {"widget_id": WIDGET_SYS_ID}
        )
        assert result["success"] is True

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    def test_widget_not_found_before_delete(self, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = None

        from servicenow_mcp.tools.pa_tools import delete_pa_widget

        result = delete_pa_widget(
            auth_manager, server_config, {"widget_id": "Unknown Name"}
        )
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_missing_widget_id(self, auth_manager, server_config):
        from servicenow_mcp.tools.pa_tools import delete_pa_widget

        result = delete_pa_widget(auth_manager, server_config, {})
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_404_from_api(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = WIDGET_SYS_ID
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        exc = requests.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = exc
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import delete_pa_widget

        result = delete_pa_widget(
            auth_manager, server_config, {"widget_id": WIDGET_SYS_ID}
        )
        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_http_error_non_404(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = WIDGET_SYS_ID
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = requests.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = exc
        mock_req.return_value = mock_resp

        from servicenow_mcp.tools.pa_tools import delete_pa_widget

        result = delete_pa_widget(
            auth_manager, server_config, {"widget_id": WIDGET_SYS_ID}
        )
        assert result["success"] is False

    @patch("servicenow_mcp.tools.pa_tools._resolve_pa_widget_sys_id")
    @patch("servicenow_mcp.tools.pa_tools._make_request")
    def test_request_exception(self, mock_req, mock_resolve, auth_manager, server_config):
        mock_resolve.return_value = WIDGET_SYS_ID
        mock_req.side_effect = requests.exceptions.ConnectionError("fail")

        from servicenow_mcp.tools.pa_tools import delete_pa_widget

        result = delete_pa_widget(
            auth_manager, server_config, {"widget_id": WIDGET_SYS_ID}
        )
        assert result["success"] is False
        assert "fail" in result["message"]

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        sc = MagicMock()
        sc.instance_url = None

        from servicenow_mcp.tools.pa_tools import delete_pa_widget

        result = delete_pa_widget(am, sc, {"widget_id": WIDGET_SYS_ID})
        assert result["success"] is False

    def test_no_headers(self, auth_manager, server_config):
        auth_manager.get_headers.return_value = None

        from servicenow_mcp.tools.pa_tools import delete_pa_widget

        result = delete_pa_widget(
            auth_manager, server_config, {"widget_id": WIDGET_SYS_ID}
        )
        assert result["success"] is False
