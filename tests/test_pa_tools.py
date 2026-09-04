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
