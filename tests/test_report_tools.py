"""Tests for report_tools.py (sys_report table)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.report_tools import (
    GetReportParams,
    ListReportsParams,
    RunReportParams,
    _format_report,
    _normalise_ref,
    _resolve_report_sys_id,
    get_report,
    list_reports,
    run_report,
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

RAW_REPORT = {
    "sys_id": SYS_ID_32,
    "title": "Open Incidents",
    "table": "incident",
    "type": "list",
    "description": "All open incidents",
    "category": "Service Desk",
    "user": {"display_value": "admin", "value": "b" * 32},
    "active": "true",
    "is_scheduled": "false",
    "sys_created_on": "2024-01-01 00:00:00",
    "sys_updated_on": "2024-06-01 00:00:00",
}

RAW_REPORT_DETAIL = dict(RAW_REPORT, **{
    "field": "number",
    "group_by": "priority",
    "order_by": "number",
    "filter": "active=true^state!=6",
    "conditions": "active=true^state!=6",
    "trend_field": "",
    "sum_field": "",
    "count_field": "",
    "show_query": "",
    "sys_created_by": "admin",
    "sys_updated_by": "admin",
})


# ---------------------------------------------------------------------------
# _normalise_ref
# ---------------------------------------------------------------------------


class TestNormaliseRef:
    def test_dict_with_display_value(self):
        assert _normalise_ref({"display_value": "Alice", "value": "xyz"}) == "Alice"

    def test_dict_without_display_value(self):
        assert _normalise_ref({"value": "xyz"}) == "xyz"

    def test_plain_string(self):
        assert _normalise_ref("plain") == "plain"

    def test_none(self):
        assert _normalise_ref(None) is None


# ---------------------------------------------------------------------------
# _format_report
# ---------------------------------------------------------------------------


class TestFormatReport:
    def test_basic_fields(self):
        result = _format_report(RAW_REPORT)
        assert result["sys_id"] == SYS_ID_32
        assert result["title"] == "Open Incidents"
        assert result["table"] == "incident"
        assert result["report_type"] == "list"
        assert result["description"] == "All open incidents"
        assert result["category"] == "Service Desk"
        assert result["active"] == "true"

    def test_user_ref_normalised(self):
        result = _format_report(RAW_REPORT)
        assert result["user"] == "admin"

    def test_timestamps_renamed(self):
        result = _format_report(RAW_REPORT)
        assert "created_on" in result
        assert "updated_on" in result
        assert "sys_created_on" not in result
        assert "sys_updated_on" not in result


# ---------------------------------------------------------------------------
# _resolve_report_sys_id
# ---------------------------------------------------------------------------


class TestResolveReportSysId:
    def test_returns_sys_id_unchanged(self):
        result = _resolve_report_sys_id(SYS_ID_32, "https://x.service-now.com", {})
        assert result == SYS_ID_32

    def test_resolves_title_to_sys_id(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        with patch("servicenow_mcp.tools.report_tools._make_request", return_value=mock_resp):
            result = _resolve_report_sys_id("Open Incidents", "https://x.service-now.com", {})
        assert result == SYS_ID_32

    def test_returns_none_when_not_found(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"result": []}
        with patch("servicenow_mcp.tools.report_tools._make_request", return_value=mock_resp):
            result = _resolve_report_sys_id("Missing Report", "https://x.service-now.com", {})
        assert result is None

    def test_returns_none_on_request_exception(self):
        import requests
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            side_effect=requests.exceptions.RequestException("err"),
        ):
            result = _resolve_report_sys_id("Bad Title", "https://x.service-now.com", {})
        assert result is None


# ---------------------------------------------------------------------------
# list_reports
# ---------------------------------------------------------------------------


class TestListReports:
    def _make_response(self, items):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"result": items}
        return mock_resp

    def test_success_no_filters(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=self._make_response([RAW_REPORT]),
        ):
            result = list_reports(auth_manager, server_config, {})
        assert result["success"] is True
        assert result["count"] == 1
        assert result["reports"][0]["title"] == "Open Incidents"

    def test_success_with_all_filters(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=self._make_response([RAW_REPORT]),
        ) as mock_req:
            result = list_reports(auth_manager, server_config, {
                "title": "Open",
                "table": "incident",
                "report_type": "list",
                "category": "Service",
                "active": True,
                "limit": 10,
                "offset": 0,
            })
        assert result["success"] is True
        call_kwargs = mock_req.call_args[1]
        query = call_kwargs["params"].get("sysparm_query", "")
        assert "titleLIKEOpen" in query
        assert "table=incident" in query
        assert "type=list" in query
        assert "categoryLIKEService" in query
        assert "active=true" in query

    def test_active_false_filter(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=self._make_response([]),
        ) as mock_req:
            list_reports(auth_manager, server_config, {"active": False})
        query = mock_req.call_args[1]["params"]["sysparm_query"]
        assert "active=false" in query

    def test_empty_result(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=self._make_response([]),
        ):
            result = list_reports(auth_manager, server_config, {})
        assert result["success"] is True
        assert result["count"] == 0

    def test_has_more_pagination(self, auth_manager, server_config):
        items = [dict(RAW_REPORT, sys_id="r" * 32)] * 5
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=self._make_response(items),
        ):
            result = list_reports(auth_manager, server_config, {"limit": 5, "offset": 0})
        assert result.get("has_more") is True
        assert result.get("next_offset") == 5

    def test_request_exception(self, auth_manager, server_config):
        import requests
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            side_effect=requests.exceptions.RequestException("network error"),
        ):
            result = list_reports(auth_manager, server_config, {})
        assert result["success"] is False
        assert "network error" in result["message"]

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        am.get_headers.return_value = {"Authorization": "Bearer token"}
        sc = MagicMock()
        sc.instance_url = None
        result = list_reports(am, sc, {})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, server_config):
        am = MagicMock()
        am.instance_url = "https://instance.service-now.com"
        am.get_headers.return_value = None
        sc = MagicMock()
        sc.instance_url = None
        result = list_reports(am, sc, {})
        assert result["success"] is False

    def test_invalid_params(self, auth_manager, server_config):
        result = list_reports(auth_manager, server_config, {"limit": "not_a_number"})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# get_report
# ---------------------------------------------------------------------------


class TestGetReport:
    def _make_response(self, record, status_code=200):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"result": record}
        return mock_resp

    def test_success_by_sys_id(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=self._make_response(RAW_REPORT_DETAIL),
        ):
            result = get_report(auth_manager, server_config, {"report_id": SYS_ID_32})
        assert result["success"] is True
        assert result["report"]["sys_id"] == SYS_ID_32
        assert result["report"]["title"] == "Open Incidents"

    def test_success_by_title(self, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.raise_for_status.return_value = None
        resolve_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}

        detail_resp = self._make_response(RAW_REPORT_DETAIL)
        responses = [resolve_resp, detail_resp]

        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            side_effect=responses,
        ):
            result = get_report(auth_manager, server_config, {"report_id": "Open Incidents"})
        assert result["success"] is True

    def test_not_found_404(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=self._make_response({}, status_code=404),
        ):
            result = get_report(auth_manager, server_config, {"report_id": SYS_ID_32})
        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_not_found_empty_result(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=self._make_response({}),
        ):
            result = get_report(auth_manager, server_config, {"report_id": SYS_ID_32})
        assert result["success"] is False

    def test_title_not_resolved(self, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.raise_for_status.return_value = None
        resolve_resp.json.return_value = {"result": []}
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=resolve_resp,
        ):
            result = get_report(auth_manager, server_config, {"report_id": "No Such Report"})
        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_request_exception(self, auth_manager, server_config):
        import requests
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            side_effect=requests.exceptions.RequestException("err"),
        ):
            result = get_report(auth_manager, server_config, {"report_id": SYS_ID_32})
        assert result["success"] is False

    def test_missing_report_id(self, auth_manager, server_config):
        result = get_report(auth_manager, server_config, {})
        assert result["success"] is False

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        am.get_headers.return_value = {}
        sc = MagicMock()
        sc.instance_url = None
        result = get_report(am, sc, {"report_id": SYS_ID_32})
        assert result["success"] is False

    def test_no_headers(self, server_config):
        am = MagicMock()
        am.instance_url = "https://instance.service-now.com"
        am.get_headers.return_value = None
        sc = MagicMock()
        sc.instance_url = None
        result = get_report(am, sc, {"report_id": SYS_ID_32})
        assert result["success"] is False

    def test_detail_fields_present(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=self._make_response(RAW_REPORT_DETAIL),
        ):
            result = get_report(auth_manager, server_config, {"report_id": SYS_ID_32})
        report = result["report"]
        assert "group_by" in report
        assert "filter" in report
        assert "order_by" in report


# ---------------------------------------------------------------------------
# run_report
# ---------------------------------------------------------------------------


class TestRunReport:
    def _meta_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"result": RAW_REPORT_DETAIL}
        return mock_resp

    def _data_response(self, rows):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"result": rows}
        return mock_resp

    def test_json_mode_success(self, auth_manager, server_config):
        rows = [{"number": "INC001", "state": "1"}]
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            side_effect=[self._meta_response(), self._data_response(rows)],
        ):
            result = run_report(auth_manager, server_config, {"report_id": SYS_ID_32})
        assert result["success"] is True
        assert result["output_format"] == "json"
        assert result["count"] == 1
        assert result["data"] == rows
        assert result["table"] == "incident"

    def test_json_mode_by_title(self, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.raise_for_status.return_value = None
        resolve_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}

        rows = [{"number": "INC001"}]
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            side_effect=[resolve_resp, self._meta_response(), self._data_response(rows)],
        ):
            result = run_report(auth_manager, server_config, {"report_id": "Open Incidents"})
        assert result["success"] is True
        assert result["count"] == 1

    def test_csv_format_returns_download_url(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=self._meta_response(),
        ):
            result = run_report(auth_manager, server_config, {
                "report_id": SYS_ID_32,
                "output_format": "csv",
            })
        assert result["success"] is True
        assert "download_url" in result
        assert "csv" in result["download_url"]

    def test_pdf_format_returns_download_url(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=self._meta_response(),
        ):
            result = run_report(auth_manager, server_config, {
                "report_id": SYS_ID_32,
                "output_format": "pdf",
            })
        assert result["success"] is True
        assert "download_url" in result
        assert "pdf" in result["download_url"]

    def test_excel_format_returns_download_url(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=self._meta_response(),
        ):
            result = run_report(auth_manager, server_config, {
                "report_id": SYS_ID_32,
                "output_format": "excel",
            })
        assert result["success"] is True
        assert "xlsx" in result["download_url"]

    def test_report_not_found(self, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.raise_for_status.return_value = None
        resolve_resp.json.return_value = {"result": []}
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=resolve_resp,
        ):
            result = run_report(auth_manager, server_config, {"report_id": "Nonexistent"})
        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_meta_fetch_404(self, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"result": {}}
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=mock_resp,
        ):
            result = run_report(auth_manager, server_config, {"report_id": SYS_ID_32})
        assert result["success"] is False

    def test_meta_fetch_empty(self, auth_manager, server_config):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"result": {}}
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=mock_resp,
        ):
            result = run_report(auth_manager, server_config, {"report_id": SYS_ID_32})
        assert result["success"] is False

    def test_meta_request_exception(self, auth_manager, server_config):
        import requests
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            side_effect=requests.exceptions.RequestException("timeout"),
        ):
            result = run_report(auth_manager, server_config, {"report_id": SYS_ID_32})
        assert result["success"] is False
        assert "timeout" in result["message"]

    def test_data_request_exception(self, auth_manager, server_config):
        import requests
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            side_effect=[self._meta_response(), requests.exceptions.RequestException("err")],
        ):
            result = run_report(auth_manager, server_config, {"report_id": SYS_ID_32})
        assert result["success"] is False

    def test_missing_source_table(self, auth_manager, server_config):
        meta_no_table = dict(RAW_REPORT_DETAIL, table="")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"result": meta_no_table}
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            return_value=mock_resp,
        ):
            result = run_report(auth_manager, server_config, {"report_id": SYS_ID_32})
        assert result["success"] is False
        assert "source table" in result["message"]

    def test_limit_capped_at_1000(self, auth_manager, server_config):
        rows = [{"number": "INC001"}]
        with patch(
            "servicenow_mcp.tools.report_tools._make_request",
            side_effect=[self._meta_response(), self._data_response(rows)],
        ) as mock_req:
            run_report(auth_manager, server_config, {"report_id": SYS_ID_32, "limit": 9999})
        data_call = mock_req.call_args_list[1]
        params = data_call[1]["params"]
        assert int(params["sysparm_limit"]) <= 1000

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        am.get_headers.return_value = {}
        sc = MagicMock()
        sc.instance_url = None
        result = run_report(am, sc, {"report_id": SYS_ID_32})
        assert result["success"] is False

    def test_no_headers(self, server_config):
        am = MagicMock()
        am.instance_url = "https://instance.service-now.com"
        am.get_headers.return_value = None
        sc = MagicMock()
        sc.instance_url = None
        result = run_report(am, sc, {"report_id": SYS_ID_32})
        assert result["success"] is False

    def test_missing_report_id(self, auth_manager, server_config):
        result = run_report(auth_manager, server_config, {})
        assert result["success"] is False
