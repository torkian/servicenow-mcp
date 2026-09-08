"""Tests for update_pa_indicator and delete_pa_indicator in pa_tools.py."""

import pytest
import requests
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.pa_tools import (
    DeletePAIndicatorParams,
    UpdatePAIndicatorParams,
    delete_pa_indicator,
    update_pa_indicator,
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
    "name": "Open Incidents",
    "description": "Count of open incidents",
    "indicator_group": {"display_value": "ITSM", "value": "b" * 32},
    "unit": {"display_value": "Count", "value": "c" * 32},
    "direction": "1",
    "frequency": "daily",
    "active": "true",
    "formula": "count",
    "condition": "stateIN1,2",
    "table": {"display_value": "Incident", "value": "incident"},
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-09-07 00:00:00",
}


# ---------------------------------------------------------------------------
# UpdatePAIndicatorParams validation
# ---------------------------------------------------------------------------


class TestUpdatePAIndicatorParams:
    def test_requires_indicator_id(self):
        with pytest.raises(Exception):
            UpdatePAIndicatorParams()

    def test_all_optional_fields_default_none(self):
        p = UpdatePAIndicatorParams(indicator_id=SYS_ID_32)
        assert p.name is None
        assert p.description is None
        assert p.table is None
        assert p.condition is None
        assert p.formula is None
        assert p.frequency is None
        assert p.direction is None
        assert p.active is None
        assert p.unit is None
        assert p.indicator_group is None

    def test_accepts_all_fields(self):
        p = UpdatePAIndicatorParams(
            indicator_id=SYS_ID_32,
            name="Updated Name",
            description="Updated desc",
            table="incident",
            condition="stateIN1,2",
            formula="count",
            frequency="weekly",
            direction="minimize",
            active=False,
            unit="some_unit",
            indicator_group="some_group",
        )
        assert p.name == "Updated Name"
        assert p.direction == "minimize"
        assert p.active is False


# ---------------------------------------------------------------------------
# DeletePAIndicatorParams validation
# ---------------------------------------------------------------------------


class TestDeletePAIndicatorParams:
    def test_requires_indicator_id(self):
        with pytest.raises(Exception):
            DeletePAIndicatorParams()

    def test_accepts_sys_id(self):
        p = DeletePAIndicatorParams(indicator_id=SYS_ID_32)
        assert p.indicator_id == SYS_ID_32

    def test_accepts_name(self):
        p = DeletePAIndicatorParams(indicator_id="Open Incidents")
        assert p.indicator_id == "Open Incidents"


# ---------------------------------------------------------------------------
# update_pa_indicator
# ---------------------------------------------------------------------------


class TestUpdatePAIndicator:
    def _make_resp(self, data, status=200):
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = {"result": data}
        resp.raise_for_status = MagicMock()
        return resp

    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        am.get_headers.return_value = {}
        result = update_pa_indicator(am, server_config, {"indicator_id": SYS_ID_32, "name": "X"})
        assert not result["success"]
        assert "instance_url" in result["message"]

    def test_no_headers(self, server_config):
        am = MagicMock()
        am.instance_url = "https://instance.service-now.com"
        am.get_headers.return_value = None
        result = update_pa_indicator(am, server_config, {"indicator_id": SYS_ID_32, "name": "X"})
        assert not result["success"]
        assert "get_headers" in result["message"]

    def test_indicator_not_found_by_name(self, auth_manager, server_config):
        not_found_resp = MagicMock()
        not_found_resp.status_code = 200
        not_found_resp.json.return_value = {"result": []}
        not_found_resp.raise_for_status = MagicMock()
        with patch(
            "servicenow_mcp.tools.pa_tools._make_request", return_value=not_found_resp
        ):
            result = update_pa_indicator(
                auth_manager, server_config, {"indicator_id": "NonExistent", "name": "Y"}
            )
        assert not result["success"]
        assert "not found" in result["message"]

    def test_empty_body_rejected(self, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.status_code = 200
        resolve_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        resolve_resp.raise_for_status = MagicMock()
        with patch(
            "servicenow_mcp.tools.pa_tools._make_request", return_value=resolve_resp
        ):
            result = update_pa_indicator(
                auth_manager, server_config, {"indicator_id": SYS_ID_32}
            )
        assert not result["success"]
        assert "No fields" in result["message"]

    def test_successful_update(self, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.status_code = 200
        resolve_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        resolve_resp.raise_for_status = MagicMock()

        patch_resp = MagicMock()
        patch_resp.status_code = 200
        patch_resp.json.return_value = {"result": RAW_INDICATOR}
        patch_resp.raise_for_status = MagicMock()

        call_count = [0]

        def side_effect(method, url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return resolve_resp
            return patch_resp

        with patch("servicenow_mcp.tools.pa_tools._make_request", side_effect=side_effect):
            result = update_pa_indicator(
                auth_manager,
                server_config,
                {"indicator_id": "Open Incidents", "name": "Updated Name", "active": True},
            )
        assert result["success"]
        assert "updated successfully" in result["message"]
        assert result["indicator"]["sys_id"] == SYS_ID_32

    def test_successful_update_with_sys_id(self, auth_manager, server_config):
        patch_resp = MagicMock()
        patch_resp.status_code = 200
        patch_resp.json.return_value = {"result": RAW_INDICATOR}
        patch_resp.raise_for_status = MagicMock()

        with patch("servicenow_mcp.tools.pa_tools._make_request", return_value=patch_resp):
            result = update_pa_indicator(
                auth_manager,
                server_config,
                {"indicator_id": SYS_ID_32, "frequency": "weekly"},
            )
        assert result["success"]
        assert result["indicator"]["frequency"] == "daily"

    def test_direction_alias_normalize_maximize(self, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.status_code = 200
        resolve_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        resolve_resp.raise_for_status = MagicMock()

        patch_resp = MagicMock()
        patch_resp.status_code = 200
        patch_resp.json.return_value = {"result": RAW_INDICATOR}
        patch_resp.raise_for_status = MagicMock()

        call_count = [0]

        def side_effect(method, url, **kwargs):
            call_count[0] += 1
            return resolve_resp if call_count[0] == 1 else patch_resp

        captured_body = {}

        def capturing_side_effect(method, url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return resolve_resp
            captured_body.update(kwargs.get("json", {}))
            return patch_resp

        call_count[0] = 0
        with patch(
            "servicenow_mcp.tools.pa_tools._make_request", side_effect=capturing_side_effect
        ):
            result = update_pa_indicator(
                auth_manager,
                server_config,
                {"indicator_id": "Open Incidents", "direction": "maximize"},
            )
        assert result["success"]
        assert captured_body.get("direction") == "1"

    def test_direction_alias_normalize_minimize(self, auth_manager, server_config):
        patch_resp = MagicMock()
        patch_resp.status_code = 200
        patch_resp.json.return_value = {"result": RAW_INDICATOR}
        patch_resp.raise_for_status = MagicMock()

        captured_body = {}

        def capturing_side_effect(method, url, **kwargs):
            captured_body.update(kwargs.get("json", {}))
            return patch_resp

        with patch(
            "servicenow_mcp.tools.pa_tools._make_request", side_effect=capturing_side_effect
        ):
            result = update_pa_indicator(
                auth_manager,
                server_config,
                {"indicator_id": SYS_ID_32, "direction": "minimize"},
            )
        assert result["success"]
        assert captured_body.get("direction") == "2"

    def test_active_false_serialized(self, auth_manager, server_config):
        patch_resp = MagicMock()
        patch_resp.status_code = 200
        patch_resp.json.return_value = {"result": RAW_INDICATOR}
        patch_resp.raise_for_status = MagicMock()

        captured_body = {}

        def capturing_side_effect(method, url, **kwargs):
            captured_body.update(kwargs.get("json", {}))
            return patch_resp

        with patch(
            "servicenow_mcp.tools.pa_tools._make_request", side_effect=capturing_side_effect
        ):
            result = update_pa_indicator(
                auth_manager,
                server_config,
                {"indicator_id": SYS_ID_32, "active": False},
            )
        assert result["success"]
        assert captured_body.get("active") == "false"

    def test_http_404_returns_not_found(self, auth_manager, server_config):
        patch_resp = MagicMock()
        patch_resp.status_code = 200
        patch_resp.json.return_value = {"result": RAW_INDICATOR}
        patch_resp.raise_for_status = MagicMock()

        http_err_resp = MagicMock()
        http_err_resp.status_code = 404
        http_err = requests.exceptions.HTTPError(response=http_err_resp)
        err_resp = MagicMock()
        err_resp.raise_for_status.side_effect = http_err

        call_count = [0]

        def side_effect(method, url, **kwargs):
            call_count[0] += 1
            # First call is _resolve_pa_indicator_sys_id which returns SYS_ID_32 (hex)
            # so no lookup needed — we pass sys_id directly
            return err_resp

        with patch("servicenow_mcp.tools.pa_tools._make_request", side_effect=side_effect):
            result = update_pa_indicator(
                auth_manager,
                server_config,
                {"indicator_id": SYS_ID_32, "name": "X"},
            )
        assert not result["success"]
        assert "not found" in result["message"]

    def test_http_500_returns_error(self, auth_manager, server_config):
        http_err_resp = MagicMock()
        http_err_resp.status_code = 500
        http_err_resp.text = '{"error":{"message":"Internal error","detail":""}}'
        http_err = requests.exceptions.HTTPError(response=http_err_resp)
        err_resp = MagicMock()
        err_resp.raise_for_status.side_effect = http_err

        with patch("servicenow_mcp.tools.pa_tools._make_request", return_value=err_resp):
            result = update_pa_indicator(
                auth_manager,
                server_config,
                {"indicator_id": SYS_ID_32, "name": "X"},
            )
        assert not result["success"]

    def test_network_error(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.pa_tools._make_request",
            side_effect=requests.exceptions.ConnectionError("timeout"),
        ):
            result = update_pa_indicator(
                auth_manager,
                server_config,
                {"indicator_id": SYS_ID_32, "name": "X"},
            )
        assert not result["success"]
        assert "timeout" in result["message"]

    def test_invalid_params(self, auth_manager, server_config):
        result = update_pa_indicator(auth_manager, server_config, {})
        assert not result["success"]


# ---------------------------------------------------------------------------
# delete_pa_indicator
# ---------------------------------------------------------------------------


class TestDeletePAIndicator:
    def test_no_instance_url(self, server_config):
        am = MagicMock()
        am.instance_url = None
        am.get_headers.return_value = {}
        result = delete_pa_indicator(am, server_config, {"indicator_id": SYS_ID_32})
        assert not result["success"]
        assert "instance_url" in result["message"]

    def test_no_headers(self, server_config):
        am = MagicMock()
        am.instance_url = "https://instance.service-now.com"
        am.get_headers.return_value = None
        result = delete_pa_indicator(am, server_config, {"indicator_id": SYS_ID_32})
        assert not result["success"]
        assert "get_headers" in result["message"]

    def test_indicator_not_found_by_name(self, auth_manager, server_config):
        not_found_resp = MagicMock()
        not_found_resp.status_code = 200
        not_found_resp.json.return_value = {"result": []}
        not_found_resp.raise_for_status = MagicMock()
        with patch(
            "servicenow_mcp.tools.pa_tools._make_request", return_value=not_found_resp
        ):
            result = delete_pa_indicator(
                auth_manager, server_config, {"indicator_id": "NonExistent"}
            )
        assert not result["success"]
        assert "not found" in result["message"]

    def test_successful_delete_204(self, auth_manager, server_config):
        del_resp = MagicMock()
        del_resp.status_code = 204
        del_resp.raise_for_status = MagicMock()

        with patch("servicenow_mcp.tools.pa_tools._make_request", return_value=del_resp):
            result = delete_pa_indicator(
                auth_manager, server_config, {"indicator_id": SYS_ID_32}
            )
        assert result["success"]
        assert "deleted successfully" in result["message"]
        assert result["indicator_sys_id"] == SYS_ID_32

    def test_successful_delete_200(self, auth_manager, server_config):
        del_resp = MagicMock()
        del_resp.status_code = 200
        del_resp.raise_for_status = MagicMock()

        with patch("servicenow_mcp.tools.pa_tools._make_request", return_value=del_resp):
            result = delete_pa_indicator(
                auth_manager, server_config, {"indicator_id": SYS_ID_32}
            )
        assert result["success"]
        assert result["indicator_sys_id"] == SYS_ID_32

    def test_successful_delete_by_name(self, auth_manager, server_config):
        resolve_resp = MagicMock()
        resolve_resp.status_code = 200
        resolve_resp.json.return_value = {"result": [{"sys_id": SYS_ID_32}]}
        resolve_resp.raise_for_status = MagicMock()

        del_resp = MagicMock()
        del_resp.status_code = 204
        del_resp.raise_for_status = MagicMock()

        call_count = [0]

        def side_effect(method, url, **kwargs):
            call_count[0] += 1
            return resolve_resp if call_count[0] == 1 else del_resp

        with patch("servicenow_mcp.tools.pa_tools._make_request", side_effect=side_effect):
            result = delete_pa_indicator(
                auth_manager, server_config, {"indicator_id": "Open Incidents"}
            )
        assert result["success"]
        assert result["indicator_sys_id"] == SYS_ID_32

    def test_http_404_returns_not_found(self, auth_manager, server_config):
        http_err_resp = MagicMock()
        http_err_resp.status_code = 404
        http_err = requests.exceptions.HTTPError(response=http_err_resp)
        err_resp = MagicMock()
        err_resp.status_code = 404
        err_resp.raise_for_status.side_effect = http_err

        with patch("servicenow_mcp.tools.pa_tools._make_request", return_value=err_resp):
            result = delete_pa_indicator(
                auth_manager, server_config, {"indicator_id": SYS_ID_32}
            )
        assert not result["success"]
        assert "not found" in result["message"]

    def test_http_500_returns_error(self, auth_manager, server_config):
        http_err_resp = MagicMock()
        http_err_resp.status_code = 500
        http_err_resp.text = '{"error":{"message":"Internal error","detail":""}}'
        http_err = requests.exceptions.HTTPError(response=http_err_resp)
        err_resp = MagicMock()
        err_resp.status_code = 500
        err_resp.raise_for_status.side_effect = http_err

        with patch("servicenow_mcp.tools.pa_tools._make_request", return_value=err_resp):
            result = delete_pa_indicator(
                auth_manager, server_config, {"indicator_id": SYS_ID_32}
            )
        assert not result["success"]

    def test_network_error(self, auth_manager, server_config):
        with patch(
            "servicenow_mcp.tools.pa_tools._make_request",
            side_effect=requests.exceptions.ConnectionError("conn refused"),
        ):
            result = delete_pa_indicator(
                auth_manager, server_config, {"indicator_id": SYS_ID_32}
            )
        assert not result["success"]
        assert "conn refused" in result["message"]

    def test_invalid_params(self, auth_manager, server_config):
        result = delete_pa_indicator(auth_manager, server_config, {})
        assert not result["success"]
