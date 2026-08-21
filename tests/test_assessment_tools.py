"""Tests for assessment_tools.py (asmt_assessment_instance and asmt_metric_type tables)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.assessment_tools import (
    CreateAssessmentInstanceParams,
    ExportAssessmentResultsParams,
    _compute_score_distribution,
    _format_assessment_instance,
    _format_assessment_metric_type,
    _resolve_metric_type_sys_id,
    _resolve_user_sys_id,
    create_assessment_instance,
    export_assessment_results,
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


# ---------------------------------------------------------------------------
# create_assessment_instance
# ---------------------------------------------------------------------------

USER_SYS_ID = "d" * 32
ASSIGNED_SYS_ID = "e" * 32
SOURCE_SYS_ID = "c" * 32


# ---------------------------------------------------------------------------
# _resolve_user_sys_id
# ---------------------------------------------------------------------------

def test_resolve_user_sys_id_passthrough():
    """A 32-char hex sys_id is returned without HTTP calls."""
    result = _resolve_user_sys_id(INSTANCE_URL, {}, USER_SYS_ID)
    assert result == USER_SYS_ID


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_resolve_user_sys_id_by_name(mock_req):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"sys_id": USER_SYS_ID}]}
    mock_req.return_value = mock_resp
    result = _resolve_user_sys_id(INSTANCE_URL, {}, "jsmith")
    assert result == USER_SYS_ID


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_resolve_user_sys_id_not_found(mock_req):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_req.return_value = mock_resp
    result = _resolve_user_sys_id(INSTANCE_URL, {}, "unknown_user")
    assert result is None


@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_resolve_user_sys_id_request_error(mock_req):
    import requests
    mock_req.side_effect = requests.exceptions.RequestException("network error")
    result = _resolve_user_sys_id(INSTANCE_URL, {}, "jsmith")
    assert result is None


# ---------------------------------------------------------------------------
# CreateAssessmentInstanceParams validation
# ---------------------------------------------------------------------------

def test_create_params_valid_minimal():
    p = CreateAssessmentInstanceParams(
        metric_type=MT_SYS_ID,
        source_table="incident",
        source_id=SOURCE_SYS_ID,
    )
    assert p.due_date is None
    assert p.user is None
    assert p.assigned_to is None
    assert p.state is None


def test_create_params_valid_due_date():
    p = CreateAssessmentInstanceParams(
        metric_type=MT_SYS_ID,
        source_table="incident",
        source_id=SOURCE_SYS_ID,
        due_date="2025-12-31",
    )
    assert p.due_date == "2025-12-31"


def test_create_params_invalid_due_date():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CreateAssessmentInstanceParams(
            metric_type=MT_SYS_ID,
            source_table="incident",
            source_id=SOURCE_SYS_ID,
            due_date="31-12-2025",
        )


# ---------------------------------------------------------------------------
# create_assessment_instance – no instance_url / no headers
# ---------------------------------------------------------------------------

def test_create_assessment_instance_no_instance_url(server_config):
    am = MagicMock()
    am.instance_url = None
    sc = MagicMock()
    sc.instance_url = None
    result = create_assessment_instance(
        am, sc,
        {"metric_type": MT_SYS_ID, "source_table": "incident", "source_id": SOURCE_SYS_ID},
    )
    assert result["success"] is False
    assert "instance_url" in result["message"]


def test_create_assessment_instance_no_headers(server_config):
    am = MagicMock()
    am.instance_url = INSTANCE_URL
    am.get_headers.return_value = None
    sc = MagicMock()
    sc.instance_url = None
    result = create_assessment_instance(
        am, sc,
        {"metric_type": MT_SYS_ID, "source_table": "incident", "source_id": SOURCE_SYS_ID},
    )
    assert result["success"] is False
    assert "get_headers" in result["message"]


# ---------------------------------------------------------------------------
# create_assessment_instance – metric_type resolution failures
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=None)
def test_create_assessment_instance_metric_type_not_found(mock_resolve, auth_manager, server_config):
    result = create_assessment_instance(
        auth_manager, server_config,
        {"metric_type": "Nonexistent Survey", "source_table": "incident", "source_id": SOURCE_SYS_ID},
    )
    assert result["success"] is False
    assert "Assessment metric type not found" in result["message"]


# ---------------------------------------------------------------------------
# create_assessment_instance – user/assigned_to resolution failures
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._resolve_user_sys_id", return_value=None)
def test_create_assessment_instance_user_not_found(mock_user, mock_mt, auth_manager, server_config):
    result = create_assessment_instance(
        auth_manager, server_config,
        {
            "metric_type": MT_SYS_ID,
            "source_table": "incident",
            "source_id": SOURCE_SYS_ID,
            "user": "unknown_user",
        },
    )
    assert result["success"] is False
    assert "User not found" in result["message"]


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._resolve_user_sys_id", side_effect=[USER_SYS_ID, None])
def test_create_assessment_instance_assigned_to_not_found(mock_user, mock_mt, auth_manager, server_config):
    result = create_assessment_instance(
        auth_manager, server_config,
        {
            "metric_type": MT_SYS_ID,
            "source_table": "incident",
            "source_id": SOURCE_SYS_ID,
            "user": "jsmith",
            "assigned_to": "unknown_manager",
        },
    )
    assert result["success"] is False
    assert "User not found" in result["message"]


# ---------------------------------------------------------------------------
# create_assessment_instance – success paths
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_create_assessment_instance_minimal_success(mock_req, mock_mt, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": RAW_INSTANCE}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = create_assessment_instance(
        auth_manager, server_config,
        {"metric_type": MT_SYS_ID, "source_table": "incident", "source_id": SOURCE_SYS_ID},
    )
    assert result["success"] is True
    assert result["instance"]["sys_id"] == INSTANCE_SYS_ID
    assert result["instance"]["metric_type"] == "Employee Survey"

    # Body sent to POST should contain the required fields.
    call_kwargs = mock_req.call_args
    body = call_kwargs[1]["json"]
    assert body["metric_type"] == MT_SYS_ID
    assert body["source_table"] == "incident"
    assert body["source_id"] == SOURCE_SYS_ID
    assert "user" not in body
    assert "assigned_to" not in body


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._resolve_user_sys_id", side_effect=[USER_SYS_ID, ASSIGNED_SYS_ID])
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_create_assessment_instance_full_params(mock_req, mock_user, mock_mt, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": RAW_INSTANCE}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = create_assessment_instance(
        auth_manager, server_config,
        {
            "metric_type": "Employee Survey",
            "source_table": "incident",
            "source_id": SOURCE_SYS_ID,
            "user": "jsmith",
            "assigned_to": "manager_user",
            "due_date": "2025-12-31",
            "state": "pending",
        },
    )
    assert result["success"] is True

    body = mock_req.call_args[1]["json"]
    assert body["user"] == USER_SYS_ID
    assert body["assigned_to"] == ASSIGNED_SYS_ID
    assert body["due_date"] == "2025-12-31"
    assert body["state"] == "pending"


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_create_assessment_instance_user_sys_id_passthrough(mock_req, mock_mt, auth_manager, server_config):
    """When user is already a 32-char hex sys_id, no extra lookup is done."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": RAW_INSTANCE}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = create_assessment_instance(
        auth_manager, server_config,
        {
            "metric_type": MT_SYS_ID,
            "source_table": "incident",
            "source_id": SOURCE_SYS_ID,
            "user": USER_SYS_ID,
        },
    )
    assert result["success"] is True
    body = mock_req.call_args[1]["json"]
    assert body["user"] == USER_SYS_ID
    # Only one _make_request call (the POST itself).
    assert mock_req.call_count == 1


# ---------------------------------------------------------------------------
# create_assessment_instance – error paths
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_create_assessment_instance_http_error(mock_req, mock_mt, auth_manager, server_config):
    import requests
    mock_req.side_effect = requests.exceptions.RequestException("500 Internal")
    result = create_assessment_instance(
        auth_manager, server_config,
        {"metric_type": MT_SYS_ID, "source_table": "incident", "source_id": SOURCE_SYS_ID},
    )
    assert result["success"] is False
    assert "Error creating assessment instance" in result["message"]


def test_create_assessment_instance_missing_required(auth_manager, server_config):
    """Missing required fields should return failure from param validation."""
    result = create_assessment_instance(auth_manager, server_config, {"metric_type": MT_SYS_ID})
    assert result["success"] is False


def test_create_assessment_instance_invalid_params(auth_manager, server_config):
    """Invalid due_date format should return failure."""
    result = create_assessment_instance(
        auth_manager, server_config,
        {
            "metric_type": MT_SYS_ID,
            "source_table": "incident",
            "source_id": SOURCE_SYS_ID,
            "due_date": "bad-date",
        },
    )
    assert result["success"] is False


# ---------------------------------------------------------------------------
# _compute_score_distribution
# ---------------------------------------------------------------------------

def test_compute_score_distribution_all_buckets():
    scores = [10.0, 30.0, 60.0, 90.0]
    dist = _compute_score_distribution(scores)
    assert dist["0-25"] == 1
    assert dist["26-50"] == 1
    assert dist["51-75"] == 1
    assert dist["76-100"] == 1


def test_compute_score_distribution_boundaries():
    scores = [0.0, 25.0, 26.0, 50.0, 51.0, 75.0, 76.0, 100.0]
    dist = _compute_score_distribution(scores)
    assert dist["0-25"] == 2
    assert dist["26-50"] == 2
    assert dist["51-75"] == 2
    assert dist["76-100"] == 2


def test_compute_score_distribution_empty():
    dist = _compute_score_distribution([])
    assert dist == {"0-25": 0, "26-50": 0, "51-75": 0, "76-100": 0}


# ---------------------------------------------------------------------------
# ExportAssessmentResultsParams validation
# ---------------------------------------------------------------------------

def test_export_params_valid_minimal():
    p = ExportAssessmentResultsParams(metric_type="Employee Survey")
    assert p.metric_type == "Employee Survey"
    assert p.completed_after is None
    assert p.completed_before is None
    assert p.state is None
    assert p.limit == 200
    assert p.offset == 0


def test_export_params_valid_date_range():
    p = ExportAssessmentResultsParams(
        metric_type="Employee Survey",
        completed_after="2025-01-01",
        completed_before="2025-12-31",
    )
    assert p.completed_after == "2025-01-01"
    assert p.completed_before == "2025-12-31"


def test_export_params_invalid_completed_after():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ExportAssessmentResultsParams(metric_type="Survey", completed_after="01/01/2025")


def test_export_params_invalid_completed_before():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ExportAssessmentResultsParams(metric_type="Survey", completed_before="13/01/2025")


# ---------------------------------------------------------------------------
# export_assessment_results – success paths
# ---------------------------------------------------------------------------

@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_export_assessment_results_success(mock_req, mock_resolve, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_INSTANCE]}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = export_assessment_results(
        auth_manager, server_config, {"metric_type": "Employee Survey"}
    )
    assert result["success"] is True
    assert result["count"] == 1
    assert len(result["instances"]) == 1
    assert "summary" in result
    summary = result["summary"]
    assert summary["metric_type_sys_id"] == MT_SYS_ID
    assert summary["total_instances"] == 1
    assert summary["completed_instances"] == 1
    assert summary["completion_rate_pct"] == 100.0
    assert summary["average_score"] == 85.0
    assert summary["score_distribution"]["76-100"] == 1


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_export_assessment_results_empty(mock_req, mock_resolve, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = export_assessment_results(
        auth_manager, server_config, {"metric_type": "Employee Survey"}
    )
    assert result["success"] is True
    assert result["count"] == 0
    assert result["instances"] == []
    summary = result["summary"]
    assert summary["total_instances"] == 0
    assert summary["completed_instances"] == 0
    assert summary["completion_rate_pct"] == 0.0
    assert summary["average_score"] is None


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_export_assessment_results_date_filters_in_query(mock_req, mock_resolve, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    export_assessment_results(
        auth_manager, server_config,
        {
            "metric_type": "Employee Survey",
            "completed_after": "2025-01-01",
            "completed_before": "2025-12-31",
        },
    )
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert "completion_date>=2025-01-01" in query
    assert "completion_date<=2025-12-31" in query


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_export_assessment_results_state_filter_in_query(mock_req, mock_resolve, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    export_assessment_results(
        auth_manager, server_config,
        {"metric_type": "Employee Survey", "state": "complete"},
    )
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert "state=complete" in query


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_export_assessment_results_metric_type_in_query(mock_req, mock_resolve, auth_manager, server_config):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    export_assessment_results(
        auth_manager, server_config, {"metric_type": "Employee Survey"}
    )
    call_kwargs = mock_req.call_args
    query = call_kwargs[1]["params"].get("sysparm_query", "")
    assert f"metric_type={MT_SYS_ID}" in query


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_export_assessment_results_limit_cap(mock_req, mock_resolve, auth_manager, server_config):
    """Limits above 1000 should be capped at 1000."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    export_assessment_results(
        auth_manager, server_config,
        {"metric_type": "Employee Survey", "limit": 5000},
    )
    call_kwargs = mock_req.call_args
    params = call_kwargs[1]["params"]
    assert params.get("sysparm_limit") <= 1000


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_export_assessment_results_pagination(mock_req, mock_resolve, auth_manager, server_config):
    """has_more should be True when count == limit."""
    records = [dict(RAW_INSTANCE, sys_id=str(i) * 32) for i in range(10)]
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": records}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = export_assessment_results(
        auth_manager, server_config,
        {"metric_type": "Employee Survey", "limit": 10, "offset": 0},
    )
    assert result["has_more"] is True
    assert result["next_offset"] == 10


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_export_assessment_results_non_numeric_score_skipped(mock_req, mock_resolve, auth_manager, server_config):
    """Instances with non-numeric scores should not break the average."""
    raw_no_score = dict(RAW_INSTANCE, score="N/A", state="pending")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [raw_no_score]}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = export_assessment_results(
        auth_manager, server_config, {"metric_type": "Employee Survey"}
    )
    assert result["success"] is True
    assert result["summary"]["average_score"] is None


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_export_assessment_results_none_score_skipped(mock_req, mock_resolve, auth_manager, server_config):
    """Instances with None scores should not break the average."""
    raw_no_score = dict(RAW_INSTANCE, score=None, state="pending")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [raw_no_score]}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = export_assessment_results(
        auth_manager, server_config, {"metric_type": "Employee Survey"}
    )
    assert result["success"] is True
    assert result["summary"]["average_score"] is None


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_export_assessment_results_numeric_4_state_counted(mock_req, mock_resolve, auth_manager, server_config):
    """State value '4' (numeric string for Complete) should count as completed."""
    raw_state_4 = dict(RAW_INSTANCE, state="4")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [raw_state_4]}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = export_assessment_results(
        auth_manager, server_config, {"metric_type": "Employee Survey"}
    )
    assert result["summary"]["completed_instances"] == 1


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_export_assessment_results_filters_applied_in_summary(mock_req, mock_resolve, auth_manager, server_config):
    """Filters applied should be reflected in summary.filters_applied."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    mock_req.return_value = mock_resp

    result = export_assessment_results(
        auth_manager, server_config,
        {
            "metric_type": "Employee Survey",
            "state": "complete",
            "completed_after": "2025-01-01",
            "completed_before": "2025-12-31",
        },
    )
    filters = result["summary"]["filters_applied"]
    assert filters["state"] == "complete"
    assert filters["completed_after"] == "2025-01-01"
    assert filters["completed_before"] == "2025-12-31"


# ---------------------------------------------------------------------------
# export_assessment_results – error / guard paths
# ---------------------------------------------------------------------------

def test_export_assessment_results_missing_required(auth_manager, server_config):
    """Missing metric_type should return failure."""
    result = export_assessment_results(auth_manager, server_config, {})
    assert result["success"] is False


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=None)
def test_export_assessment_results_metric_type_not_found(mock_resolve, auth_manager, server_config):
    result = export_assessment_results(
        auth_manager, server_config, {"metric_type": "Nonexistent"}
    )
    assert result["success"] is False
    assert "not found" in result["message"]


def test_export_assessment_results_no_instance_url(server_config):
    am = MagicMock()
    am.instance_url = None
    sc = MagicMock()
    sc.instance_url = None
    result = export_assessment_results(am, sc, {"metric_type": "Employee Survey"})
    assert result["success"] is False
    assert "instance_url" in result["message"]


def test_export_assessment_results_no_headers(server_config):
    am = MagicMock()
    am.instance_url = INSTANCE_URL
    am.get_headers.return_value = None
    sc = MagicMock()
    sc.instance_url = None
    result = export_assessment_results(am, sc, {"metric_type": "Employee Survey"})
    assert result["success"] is False
    assert "get_headers" in result["message"]


@patch("servicenow_mcp.tools.assessment_tools._resolve_metric_type_sys_id", return_value=MT_SYS_ID)
@patch("servicenow_mcp.tools.assessment_tools._make_request")
def test_export_assessment_results_http_error(mock_req, mock_resolve, auth_manager, server_config):
    import requests
    mock_req.side_effect = requests.exceptions.RequestException("timeout")
    result = export_assessment_results(
        auth_manager, server_config, {"metric_type": "Employee Survey"}
    )
    assert result["success"] is False
    assert "Error exporting assessment results" in result["message"]


def test_export_assessment_results_invalid_date(auth_manager, server_config):
    """Invalid completed_after date format should return failure."""
    result = export_assessment_results(
        auth_manager, server_config,
        {"metric_type": "Employee Survey", "completed_after": "bad-date"},
    )
    assert result["success"] is False
