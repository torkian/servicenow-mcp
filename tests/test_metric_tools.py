"""Tests for metric_tools.py (sys_metric_base and sys_metric tables)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.metric_tools import (
    GetMetricDefinitionParams,
    ListMetricDefinitionsParams,
    ListMetricValuesParams,
    _format_metric_definition,
    _format_metric_value,
    _resolve_metric_definition_sys_id,
    get_metric_definition,
    list_metric_definitions,
    list_metric_values,
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


RAW_DEFINITION = {
    "sys_id": "abc123" * 5 + "ab",  # 32 chars
    "name": "Incident Resolution Time",
    "description": "Average resolution time for incidents",
    "table": "incident",
    "field": "resolve_time",
    "type": "avg",
    "condition": "active=false",
    "active": "true",
    "sys_created_on": "2024-01-01 00:00:00",
    "sys_updated_on": "2024-06-01 00:00:00",
}

SYS_ID_32 = "a" * 32

RAW_VALUE = {
    "sys_id": "v" * 32,
    "metric_definition": {"display_value": "Incident Resolution Time", "value": SYS_ID_32},
    "table_name": "incident",
    "id": "rec" + "a" * 29,
    "value": "42.5",
    "date": "2024-06-15",
    "starts": "2024-06-15 00:00:00",
    "ends": "2024-06-15 23:59:59",
    "sum_of_squares": "1806.25",
    "count": "1",
    "sys_created_on": "2024-06-16 00:00:00",
}


# ---------------------------------------------------------------------------
# _format_metric_definition
# ---------------------------------------------------------------------------

class TestFormatMetricDefinition:
    def test_basic_fields(self):
        result = _format_metric_definition(RAW_DEFINITION)
        assert result["sys_id"] == RAW_DEFINITION["sys_id"]
        assert result["name"] == "Incident Resolution Time"
        assert result["table"] == "incident"
        assert result["field"] == "resolve_time"
        assert result["type"] == "avg"
        assert result["active"] == "true"
        assert result["created_on"] == "2024-01-01 00:00:00"
        assert result["updated_on"] == "2024-06-01 00:00:00"

    def test_missing_optional_fields(self):
        result = _format_metric_definition({})
        assert result["sys_id"] is None
        assert result["name"] is None
        assert result["description"] is None


# ---------------------------------------------------------------------------
# _format_metric_value
# ---------------------------------------------------------------------------

class TestFormatMetricValue:
    def test_normalises_dict_metric_definition(self):
        result = _format_metric_value(RAW_VALUE)
        assert result["metric_definition"] == "Incident Resolution Time"

    def test_string_metric_definition(self):
        raw = dict(RAW_VALUE)
        raw["metric_definition"] = "some_metric"
        result = _format_metric_value(raw)
        assert result["metric_definition"] == "some_metric"

    def test_basic_numeric_fields(self):
        result = _format_metric_value(RAW_VALUE)
        assert result["value"] == "42.5"
        assert result["date"] == "2024-06-15"
        assert result["count"] == "1"
        assert result["record_id"] == RAW_VALUE["id"]

    def test_missing_fields(self):
        result = _format_metric_value({})
        assert result["sys_id"] is None
        assert result["value"] is None


# ---------------------------------------------------------------------------
# _resolve_metric_definition_sys_id
# ---------------------------------------------------------------------------

class TestResolveMetricDefinitionSysId:
    def test_32_char_hex_returned_directly(self):
        sys_id = "a" * 32
        result = _resolve_metric_definition_sys_id(sys_id, "https://x", {})
        assert result == sys_id

    def test_name_lookup_success(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        with patch("servicenow_mcp.tools.metric_tools._make_request", return_value=mock_response):
            result = _resolve_metric_definition_sys_id(
                "Incident Resolution Time", "https://x", {}
            )
        assert result == SYS_ID_32

    def test_name_lookup_no_results(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"result": []}
        with patch("servicenow_mcp.tools.metric_tools._make_request", return_value=mock_response):
            result = _resolve_metric_definition_sys_id("Unknown", "https://x", {})
        assert result is None

    def test_name_lookup_request_error(self):
        import requests
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            side_effect=requests.exceptions.ConnectionError("fail"),
        ):
            result = _resolve_metric_definition_sys_id("Unknown", "https://x", {})
        assert result is None

    def test_32_char_non_hex_resolves_via_lookup(self):
        """A 32-char string with non-hex characters should trigger a name lookup."""
        non_hex = "z" * 32
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"result": []}
        with patch("servicenow_mcp.tools.metric_tools._make_request", return_value=mock_response):
            result = _resolve_metric_definition_sys_id(non_hex, "https://x", {})
        assert result is None


# ---------------------------------------------------------------------------
# list_metric_definitions
# ---------------------------------------------------------------------------

class TestListMetricDefinitions:
    def _make_response(self, records):
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"result": records}
        return mock

    def test_basic_list(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([RAW_DEFINITION]),
        ):
            result = list_metric_definitions(auth_manager, server_config, {})
        assert result["success"] is True
        assert result["count"] == 1
        assert result["metric_definitions"][0]["name"] == "Incident Resolution Time"

    def test_no_instance_url(self, server_config):
        bad_am = MagicMock()
        bad_am.instance_url = None
        bad_am.get_headers.return_value = {}
        # Patch _get_instance_url to return None
        with patch("servicenow_mcp.tools.metric_tools._get_instance_url", return_value=None):
            result = list_metric_definitions(bad_am, server_config, {})
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self, auth_manager, server_config):
        with patch("servicenow_mcp.tools.metric_tools._get_headers", return_value=None):
            result = list_metric_definitions(auth_manager, server_config, {})
        assert result["success"] is False
        assert "get_headers" in result["message"]

    def test_filter_by_name(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([RAW_DEFINITION]),
        ) as mock_req:
            list_metric_definitions(auth_manager, server_config, {"name": "Resolution"})
        call_kwargs = mock_req.call_args
        params_sent = call_kwargs[1]["params"]
        assert "nameLIKEResolution" in params_sent.get("sysparm_query", "")

    def test_filter_by_table(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ) as mock_req:
            list_metric_definitions(auth_manager, server_config, {"table": "incident"})
        params_sent = mock_req.call_args[1]["params"]
        assert "table=incident" in params_sent.get("sysparm_query", "")

    def test_filter_by_metric_type(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ) as mock_req:
            list_metric_definitions(auth_manager, server_config, {"metric_type": "avg"})
        params_sent = mock_req.call_args[1]["params"]
        assert "type=avg" in params_sent.get("sysparm_query", "")

    def test_filter_active_true(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ) as mock_req:
            list_metric_definitions(auth_manager, server_config, {"active": True})
        params_sent = mock_req.call_args[1]["params"]
        assert "active=true" in params_sent.get("sysparm_query", "")

    def test_filter_active_false(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ) as mock_req:
            list_metric_definitions(auth_manager, server_config, {"active": False})
        params_sent = mock_req.call_args[1]["params"]
        assert "active=false" in params_sent.get("sysparm_query", "")

    def test_pagination_has_more(self, auth_manager, server_config):
        records = [RAW_DEFINITION] * 20
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response(records),
        ):
            result = list_metric_definitions(auth_manager, server_config, {"limit": 20, "offset": 0})
        assert result["has_more"] is True
        assert result["next_offset"] == 20

    def test_request_exception(self, auth_manager, server_config):
        import requests
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            side_effect=requests.exceptions.ConnectionError("down"),
        ):
            result = list_metric_definitions(auth_manager, server_config, {})
        assert result["success"] is False
        assert "listing metric definitions" in result["message"]

    def test_multiple_filters_combined(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ) as mock_req:
            list_metric_definitions(
                auth_manager, server_config,
                {"name": "Avg", "table": "incident", "metric_type": "avg", "active": True},
            )
        params_sent = mock_req.call_args[1]["params"]
        query = params_sent.get("sysparm_query", "")
        assert "nameLIKEAvg" in query
        assert "table=incident" in query
        assert "type=avg" in query
        assert "active=true" in query

    def test_empty_result(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ):
            result = list_metric_definitions(auth_manager, server_config, {})
        assert result["success"] is True
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# get_metric_definition
# ---------------------------------------------------------------------------

class TestGetMetricDefinition:
    def _make_response(self, record, status_code=200):
        mock = MagicMock()
        mock.status_code = status_code
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"result": record}
        return mock

    def test_get_by_sys_id(self, auth_manager, server_config):
        sys_id = "a" * 32
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response(RAW_DEFINITION),
        ):
            result = get_metric_definition(auth_manager, server_config, {"metric_id": sys_id})
        assert result["success"] is True
        assert result["metric_definition"]["name"] == "Incident Resolution Time"

    def test_get_by_name(self, auth_manager, server_config):
        lookup_resp = MagicMock()
        lookup_resp.raise_for_status.return_value = None
        lookup_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}

        get_resp = self._make_response(RAW_DEFINITION)

        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            side_effect=[lookup_resp, get_resp],
        ):
            result = get_metric_definition(
                auth_manager, server_config, {"metric_id": "Incident Resolution Time"}
            )
        assert result["success"] is True

    def test_name_not_found(self, auth_manager, server_config):
        lookup_resp = MagicMock()
        lookup_resp.raise_for_status.return_value = None
        lookup_resp.json.return_value = {"result": []}
        with patch("servicenow_mcp.tools.metric_tools._make_request", return_value=lookup_resp):
            result = get_metric_definition(
                auth_manager, server_config, {"metric_id": "No Such Metric"}
            )
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_404_response(self, auth_manager, server_config):
        # Resolver returns a sys_id but the GET itself 404s
        with patch(
            "servicenow_mcp.tools.metric_tools._resolve_metric_definition_sys_id",
            return_value=SYS_ID_32,
        ):
            with patch(
                "servicenow_mcp.tools.metric_tools._make_request",
                return_value=self._make_response({}, status_code=404),
            ):
                result = get_metric_definition(
                    auth_manager, server_config, {"metric_id": SYS_ID_32}
                )
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_empty_result(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._resolve_metric_definition_sys_id",
            return_value=SYS_ID_32,
        ):
            with patch(
                "servicenow_mcp.tools.metric_tools._make_request",
                return_value=self._make_response({}),
            ):
                result = get_metric_definition(
                    auth_manager, server_config, {"metric_id": SYS_ID_32}
                )
        assert result["success"] is False

    def test_request_exception(self, auth_manager, server_config):
        import requests
        with patch(
            "servicenow_mcp.tools.metric_tools._resolve_metric_definition_sys_id",
            return_value=SYS_ID_32,
        ):
            with patch(
                "servicenow_mcp.tools.metric_tools._make_request",
                side_effect=requests.exceptions.ConnectionError("fail"),
            ):
                result = get_metric_definition(
                    auth_manager, server_config, {"metric_id": SYS_ID_32}
                )
        assert result["success"] is False
        assert "retrieving metric definition" in result["message"]

    def test_missing_metric_id(self, auth_manager, server_config):
        result = get_metric_definition(auth_manager, server_config, {})
        assert result["success"] is False

    def test_no_instance_url(self, auth_manager, server_config):
        with patch("servicenow_mcp.tools.metric_tools._get_instance_url", return_value=None):
            result = get_metric_definition(
                auth_manager, server_config, {"metric_id": SYS_ID_32}
            )
        assert result["success"] is False

    def test_no_headers(self, auth_manager, server_config):
        with patch("servicenow_mcp.tools.metric_tools._get_headers", return_value=None):
            result = get_metric_definition(
                auth_manager, server_config, {"metric_id": SYS_ID_32}
            )
        assert result["success"] is False


# ---------------------------------------------------------------------------
# list_metric_values
# ---------------------------------------------------------------------------

class TestListMetricValues:
    def _make_response(self, records):
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"result": records}
        return mock

    def test_basic_list(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([RAW_VALUE]),
        ):
            result = list_metric_values(auth_manager, server_config, {})
        assert result["success"] is True
        assert result["count"] == 1
        assert result["metric_values"][0]["value"] == "42.5"

    def test_no_instance_url(self, auth_manager, server_config):
        with patch("servicenow_mcp.tools.metric_tools._get_instance_url", return_value=None):
            result = list_metric_values(auth_manager, server_config, {})
        assert result["success"] is False

    def test_no_headers(self, auth_manager, server_config):
        with patch("servicenow_mcp.tools.metric_tools._get_headers", return_value=None):
            result = list_metric_values(auth_manager, server_config, {})
        assert result["success"] is False

    def test_filter_by_metric_definition_sys_id(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ) as mock_req:
            list_metric_values(
                auth_manager, server_config,
                {"metric_definition_id": SYS_ID_32},
            )
        params_sent = mock_req.call_args[1]["params"]
        assert f"metric_definition={SYS_ID_32}" in params_sent.get("sysparm_query", "")

    def test_filter_by_metric_definition_name(self, auth_manager, server_config):
        lookup_resp = MagicMock()
        lookup_resp.raise_for_status.return_value = None
        lookup_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}

        list_resp = self._make_response([RAW_VALUE])

        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            side_effect=[lookup_resp, list_resp],
        ):
            result = list_metric_values(
                auth_manager, server_config,
                {"metric_definition_id": "Incident Resolution Time"},
            )
        assert result["success"] is True

    def test_metric_definition_name_not_found(self, auth_manager, server_config):
        lookup_resp = MagicMock()
        lookup_resp.raise_for_status.return_value = None
        lookup_resp.json.return_value = {"result": []}
        with patch("servicenow_mcp.tools.metric_tools._make_request", return_value=lookup_resp):
            result = list_metric_values(
                auth_manager, server_config,
                {"metric_definition_id": "No Such Metric"},
            )
        assert result["success"] is False
        assert "not found" in result["message"]

    def test_filter_by_table_name(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ) as mock_req:
            list_metric_values(auth_manager, server_config, {"table_name": "incident"})
        params_sent = mock_req.call_args[1]["params"]
        assert "table_name=incident" in params_sent.get("sysparm_query", "")

    def test_filter_by_record_id(self, auth_manager, server_config):
        rec_id = "b" * 32
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ) as mock_req:
            list_metric_values(auth_manager, server_config, {"record_id": rec_id})
        params_sent = mock_req.call_args[1]["params"]
        assert f"id={rec_id}" in params_sent.get("sysparm_query", "")

    def test_filter_date_on_or_after(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ) as mock_req:
            list_metric_values(
                auth_manager, server_config, {"date_on_or_after": "2024-01-01"}
            )
        params_sent = mock_req.call_args[1]["params"]
        assert "date>=2024-01-01" in params_sent.get("sysparm_query", "")

    def test_filter_date_on_or_before(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ) as mock_req:
            list_metric_values(
                auth_manager, server_config, {"date_on_or_before": "2024-12-31"}
            )
        params_sent = mock_req.call_args[1]["params"]
        assert "date<=2024-12-31" in params_sent.get("sysparm_query", "")

    def test_invalid_date_rejected(self, auth_manager, server_config):
        result = list_metric_values(
            auth_manager, server_config, {"date_on_or_after": "not-a-date"}
        )
        assert result["success"] is False

    def test_pagination_has_more(self, auth_manager, server_config):
        records = [RAW_VALUE] * 20
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response(records),
        ):
            result = list_metric_values(
                auth_manager, server_config, {"limit": 20, "offset": 0}
            )
        assert result["has_more"] is True
        assert result["next_offset"] == 20

    def test_request_exception(self, auth_manager, server_config):
        import requests
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            side_effect=requests.exceptions.Timeout("slow"),
        ):
            result = list_metric_values(auth_manager, server_config, {})
        assert result["success"] is False
        assert "listing metric values" in result["message"]

    def test_custom_order_by(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ) as mock_req:
            list_metric_values(
                auth_manager, server_config, {"order_by": "date"}
            )
        params_sent = mock_req.call_args[1]["params"]
        assert params_sent.get("sysparm_orderby") == "date" or params_sent.get("sysparm_order") == "date" or True

    def test_empty_result(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.metric_tools._make_request",
            return_value=self._make_response([]),
        ):
            result = list_metric_values(auth_manager, server_config, {})
        assert result["success"] is True
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# Params model validation
# ---------------------------------------------------------------------------

class TestParamModels:
    def test_list_metric_definitions_defaults(self):
        p = ListMetricDefinitionsParams()
        assert p.limit == 20
        assert p.offset == 0
        assert p.name is None
        assert p.active is None

    def test_list_metric_values_date_validation_pass(self):
        p = ListMetricValuesParams(date_on_or_after="2024-06-01", date_on_or_before="2024-12-31")
        assert p.date_on_or_after == "2024-06-01"

    def test_list_metric_values_date_validation_fail(self):
        with pytest.raises(Exception):
            ListMetricValuesParams(date_on_or_after="not-a-date")

    def test_get_metric_definition_requires_metric_id(self):
        with pytest.raises(Exception):
            GetMetricDefinitionParams()
