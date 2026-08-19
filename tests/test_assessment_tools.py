"""Tests for assessment_tools.py (asmt_assessment_instance and asmt_metric_type tables)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.assessment_tools import (
    _format_assessment_instance,
    _format_assessment_metric_type,
    _resolve_metric_type_sys_id,
    get_assessment_instance,
    get_assessment_metric_type,
    list_assessment_instances,
    list_assessment_metric_types,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://instance.service-now.com"
INSTANCE_SYS_ID = "a" * 32  # valid 32-char hex (passthrough)
MT_SYS_ID = "b" * 32  # metric type sys_id


@pytest.fixture
def auth_manager():
    am = MagicMock()
    am.instance_url = INSTANCE_URL
    am.get_headers.return_value = {"Authorization": "Bearer token"}
    return am


@pytest.fixture
def server_config():
    sc = MagicMock()
    sc.instance_url = None
    return sc


RAW_INSTANCE = {
    "sys_id": INSTANCE_SYS_ID,
    "metric_type": {"display_value": "Employee Survey", "value": MT_SYS_ID},
    "source_id": "c" * 32,
    "source_table": "incident",
    "state": "complete",
    "user": {"display_value": "jsmith", "value": "d" * 32},
    "assigned_to": {"display_value": "manager_user", "value": "e" * 32},
    "due_date": "2025-12-31",
    "completion_date": "2025-12-30",
    "score": "85",
    "percent_answered": "100",
    "definition": {"display_value": "Q4 Survey", "value": "f" * 32},
    "sys_created_on": "2025-12-01 10:00:00",
    "sys_updated_on": "2025-12-30 15:00:00",
    "sys_created_by": "admin",
}

RAW_METRIC_TYPE = {
    "sys_id": MT_SYS_ID,
    "name": "Employee Survey",
    "description": "Annual employee satisfaction survey",
    "active": "true",
    "type": "survey",
    "category": {"display_value": "HR", "value": "g" * 32},
    "roles": "itil",
    "related_table": "incident",
    "related_filter": "active=true",
    "frequency": "yearly",
    "due_period": "30",
    "sys_created_on": "2025-01-01 09:00:00",
    "sys_updated_on": "2025-06-01 12:00:00",
}


# ---------------------------------------------------------------------------
# _format_assessment_instance
# ---------------------------------------------------------------------------

def test_format_assessment_instance_normalises_refs():
    result = _format_assessment_instance(RAW_INSTANCE)
    assert result["sys_id"] == INSTANCE_SYS_ID
    assert result["metric_type"] == "Employee Survey"
    assert result["user"] == "jsmith"
    assert result["assigned_to"] == "manager_user"
    assert result["definition"] == "Q4 Survey"
    assert result["state"] == "complete"
    assert result["score"] == "85"
    assert result["percent_answered"] == "100"
    assert result["created_on"] == "2025-12-01 10:00:00"
    assert result["updated_on"] == "2025-12-30 15:00:00"
    assert result["created_by"] == "admin"


def test_format_assessment_instance_string_fields():
    raw = dict(RAW_INSTANCE, user="jsmith", metric_type="Survey A", assigned_to=None)
    result = _format_assessment_instance(raw)
    assert result["user"] == "jsmith"
    assert result["metric_type"] == "Survey A"
    assert result["assigned_to"] is None


# ---------------------------------------------------------------------------
# _format_assessment_metric_type
# ---------------------------------------------------------------------------

def test_format_assessment_metric_type_normalises_refs():
    result = _format_assessment_metric_type(RAW_METRIC_TYPE)
    assert result["sys_id"] == MT_SYS_ID
    assert result["name"] == "Employee Survey"
    assert result["description"] == "Annual employee satisfaction survey"
    assert result["active"] == "true"
    assert result["type"] == "survey"
    assert result["category"] == "HR"
    assert result["roles"] == "itil"
    assert result["related_table"] == "incident"
    assert result["frequency"] == "yearly"
    assert result["due_period"] == "30"


def test_format_assessment_metric_type_string_category():
    raw = dict(RAW_METRIC_TYPE, category="HR")
    result = _format_assessment_metric_type(raw)
    assert result["category"] == "HR"


# ---------------------------------------------------------------------------
# _resolve_metric_type_sys_id
# ---------------------------------------------------------------------------

def test_resolve_metric_type_sys_id_passthrough():
    """A 32-char hex string should be returned without any HTTP call."""
    result = _resolve_metric_type_sys_id(INSTANCE_URL, {}, MT_SYS_ID)
    assert result == MT_SYS_ID


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_resolve_metric_type_sys_id_by_name(mock_req):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"sys_id": MT_SYS_ID}]}
    mock_req.return_value = mock_resp
    result = _resolve_metric_type_sys_id(INSTANCE_URL, {}, "Employee Survey")
    assert result == MT_SYS_ID


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_resolve_metric_type_sys_id_not_found(mock_req):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_req.return_value = mock_resp
    result = _resolve_metric_type_sys_id(INSTANCE_URL, {}, "Nonexistent Survey")
    assert result is None


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_resolve_metric_type_sys_id_request_error(mock_req):
    import requests
    mock_req.side_effect = requests.exceptions.RequestException("network error")
    result = _resolve_metric_type_sys_id(INSTANCE_URL, {}, "Employee Survey")
    assert result is None


# ---------------------------------------------------------------------------
# list_assessment_instances
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_instances_success(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_INSTANCE]}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = list_assessment_instances(auth_manager, server_config, {})
    assert result["success"] is True
    assert len(result["instances"]) == 1
    assert result["instances"][0]["state"] == "complete"
    assert result["count"] == 1


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_instances_empty(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = list_assessment_instances(auth_manager, server_config, {})
    assert result["success"] is True
    assert result["instances"] == []
    assert result["count"] == 0


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_instances_state_filter(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    list_assessment_instances(auth_manager, server_config, {"state": "complete"})
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert "state=complete" in query


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_instances_source_table_filter(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    list_assessment_instances(auth_manager, server_config, {"source_table": "incident"})
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert "source_table=incident" in query


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_instances_user_sys_id_filter(mock_req, auth_manager, server_config):
    user_id = "d" * 32
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    list_assessment_instances(auth_manager, server_config, {"user": user_id})
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert f"user={user_id}" in query


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_instances_user_name_filter(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    list_assessment_instances(auth_manager, server_config, {"user": "jsmith"})
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert "user.user_name=jsmith" in query


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id")
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_instances_metric_type_resolved(mock_req, mock_resolve, auth_manager, server_config):
    mock_resolve.return_value = MT_SYS_ID
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    list_assessment_instances(auth_manager, server_config, {"metric_type": "Employee Survey"})
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert f"metric_type={MT_SYS_ID}" in query


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id")
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_instances_metric_type_not_resolved(mock_req, mock_resolve, auth_manager, server_config):
    mock_resolve.return_value = None
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    list_assessment_instances(auth_manager, server_config, {"metric_type": "Nonexistent"})
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert "metric_type.nameLIKENonexistent" in query


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_instances_http_error(mock_req, auth_manager, server_config):
    import requests
    mock_req.side_effect = requests.exceptions.RequestException("connection error")
    result = list_assessment_instances(auth_manager, server_config, {})
    assert result["success"] is False
    assert "Error listing assessment instances" in result["message"]


def test_list_assessment_instances_missing_instance_url(server_config):
    bad_auth = MagicMock()
    bad_auth.instance_url = None
    bad_auth.get_headers.return_value = {}
    # Patch _get_instance_url to return None
    with patch("servicenow_mcp.tools.assessment_tools._get_instance_url", return_value=None):
        result = list_assessment_instances(bad_auth, server_config, {})
    assert result["success"] is False


def test_list_assessment_instances_has_more(auth_manager, server_config):
    """has_more should be True when count == limit."""
    records = [dict(RAW_INSTANCE, sys_id=str(i) * 32) for i in range(20)]
    with patch("servicenow_mcp.tools.assessment_tools._make_request") as mock_req:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": records}
        mock_resp.raise_for_status = MagicMock()
        mock_req.return_value = mock_resp
        result = list_assessment_instances(auth_manager, server_config, {"limit": 20})
    assert result["has_more"] is True
    assert result["next_offset"] == 20


# ---------------------------------------------------------------------------
# get_assessment_instance
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_get_assessment_instance_success(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_INSTANCE}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = get_assessment_instance(
        auth_manager, server_config, {"instance_id": INSTANCE_SYS_ID}
    )
    assert result["success"] is True
    assert result["instance"]["sys_id"] == INSTANCE_SYS_ID
    assert result["instance"]["state"] == "complete"


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_get_assessment_instance_404(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_req.return_value = mock_resp

    result = get_assessment_instance(
        auth_manager, server_config, {"instance_id": INSTANCE_SYS_ID}
    )
    assert result["success"] is False
    assert "not found" in result["message"]


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_get_assessment_instance_empty_result(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": {}}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = get_assessment_instance(
        auth_manager, server_config, {"instance_id": INSTANCE_SYS_ID}
    )
    assert result["success"] is False
    assert "not found" in result["message"]


def test_get_assessment_instance_missing_required_field(auth_manager, server_config):
    result = get_assessment_instance(auth_manager, server_config, {})
    assert result["success"] is False


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_get_assessment_instance_http_error(mock_req, auth_manager, server_config):
    import requests
    mock_req.side_effect = requests.exceptions.RequestException("timeout")
    result = get_assessment_instance(
        auth_manager, server_config, {"instance_id": INSTANCE_SYS_ID}
    )
    assert result["success"] is False
    assert "Error retrieving assessment instance" in result["message"]


# ---------------------------------------------------------------------------
# list_assessment_metric_types
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_metric_types_success(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_METRIC_TYPE]}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = list_assessment_metric_types(auth_manager, server_config, {})
    assert result["success"] is True
    assert len(result["metric_types"]) == 1
    assert result["metric_types"][0]["name"] == "Employee Survey"


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_metric_types_name_filter(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    list_assessment_metric_types(auth_manager, server_config, {"name": "Employee"})
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert "nameLIKEEmployee" in query


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_metric_types_active_filter(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    list_assessment_metric_types(auth_manager, server_config, {"active": True})
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert "active=true" in query


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_metric_types_type_filter(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    list_assessment_metric_types(auth_manager, server_config, {"type": "survey"})
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert "type=survey" in query


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_metric_types_related_table_filter(mock_req, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    list_assessment_metric_types(auth_manager, server_config, {"related_table": "incident"})
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert "related_table=incident" in query


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_list_assessment_metric_types_http_error(mock_req, auth_manager, server_config):
    import requests
    mock_req.side_effect = requests.exceptions.RequestException("timeout")
    result = list_assessment_metric_types(auth_manager, server_config, {})
    assert result["success"] is False
    assert "Error listing assessment metric types" in result["message"]


# ---------------------------------------------------------------------------
# get_assessment_metric_type
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id")
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_get_assessment_metric_type_success(mock_req, mock_resolve, auth_manager, server_config):
    mock_resolve.return_value = MT_SYS_ID
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_METRIC_TYPE}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = get_assessment_metric_type(
        auth_manager, server_config, {"metric_type_id": "Employee Survey"}
    )
    assert result["success"] is True
    assert result["metric_type"]["name"] == "Employee Survey"
    assert result["metric_type"]["type"] == "survey"


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id")
def test_get_assessment_metric_type_not_resolved(mock_resolve, auth_manager, server_config):
    mock_resolve.return_value = None
    result = get_assessment_metric_type(
        auth_manager, server_config, {"metric_type_id": "Nonexistent"}
    )
    assert result["success"] is False
    assert "not found" in result["message"]


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id")
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_get_assessment_metric_type_404(mock_req, mock_resolve, auth_manager, server_config):
    mock_resolve.return_value = MT_SYS_ID
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_req.return_value = mock_resp

    result = get_assessment_metric_type(
        auth_manager, server_config, {"metric_type_id": MT_SYS_ID}
    )
    assert result["success"] is False
    assert "not found" in result["message"]


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id")
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_get_assessment_metric_type_empty_result(mock_req, mock_resolve, auth_manager, server_config):
    mock_resolve.return_value = MT_SYS_ID
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": {}}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = get_assessment_metric_type(
        auth_manager, server_config, {"metric_type_id": MT_SYS_ID}
    )
    assert result["success"] is False
    assert "not found" in result["message"]


def test_get_assessment_metric_type_missing_required(auth_manager, server_config):
    result = get_assessment_metric_type(auth_manager, server_config, {})
    assert result["success"] is False


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id")
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_get_assessment_metric_type_http_error(mock_req, mock_resolve, auth_manager, server_config):
    import requests
    mock_resolve.return_value = MT_SYS_ID
    mock_req.side_effect = requests.exceptions.RequestException("timeout")
    result = get_assessment_metric_type(
        auth_manager, server_config, {"metric_type_id": MT_SYS_ID}
    )
    assert result["success"] is False
    assert "Error retrieving assessment metric type" in result["message"]


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_get_assessment_metric_type_by_sys_id(mock_req, auth_manager, server_config):
    """A 32-char hex metric_type_id should bypass name resolution."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_METRIC_TYPE}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = get_assessment_metric_type(
        auth_manager, server_config, {"metric_type_id": MT_SYS_ID}
    )
    assert result["success"] is True
    assert result["metric_type"]["sys_id"] == MT_SYS_ID
