"""Tests for department_tools.py (cmn_department table)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.department_tools import (
    GetDepartmentParams,
    ListDepartmentsParams,
    _build_department_query,
    _format_department,
    _resolve_department_sys_id,
    get_department,
    list_departments,
)

# ---------------------------------------------------------------------------
# Constants / fixtures
# ---------------------------------------------------------------------------

INSTANCE_URL = "https://instance.service-now.com"
DEPT_SYS_ID = "d" * 32


@pytest.fixture
def auth_manager():
    am = MagicMock()
    am.get_headers.return_value = {"Authorization": "Bearer token"}
    return am


@pytest.fixture
def config():
    cfg = MagicMock()
    cfg.instance_url = INSTANCE_URL
    return cfg


RAW_DEPARTMENT = {
    "sys_id": DEPT_SYS_ID,
    "name": "Engineering",
    "description": "Software engineering department",
    "id": "ENG-001",
    "parent": {"display_value": "Technology", "value": "parent_sys_id"},
    "dept_head": {"display_value": "Alice Smith", "value": "head_sys_id"},
    "company": {"display_value": "Acme Corp", "value": "company_sys_id"},
    "cost_center": {"display_value": "CC-1001", "value": "cc_sys_id"},
    "sys_created_on": "2024-01-01 08:00:00",
    "sys_updated_on": "2025-03-15 10:00:00",
    "sys_created_by": "admin",
}


# ---------------------------------------------------------------------------
# _format_department
# ---------------------------------------------------------------------------


def test_format_department_basic():
    """Scalar fields are passed through and reference fields normalised."""
    result = _format_department(RAW_DEPARTMENT)
    assert result["sys_id"] == DEPT_SYS_ID
    assert result["name"] == "Engineering"
    assert result["description"] == "Software engineering department"
    assert result["id"] == "ENG-001"
    assert result["parent"] == "Technology"
    assert result["dept_head"] == "Alice Smith"
    assert result["company"] == "Acme Corp"
    assert result["cost_center"] == "CC-1001"
    assert result["created_on"] == "2024-01-01 08:00:00"
    assert result["updated_on"] == "2025-03-15 10:00:00"
    assert result["created_by"] == "admin"


def test_format_department_missing_fields():
    """Missing fields return None without error."""
    result = _format_department({})
    assert result["sys_id"] is None
    assert result["name"] is None
    assert result["description"] is None
    assert result["id"] is None
    assert result["parent"] is None
    assert result["dept_head"] is None
    assert result["company"] is None
    assert result["cost_center"] is None


def test_format_department_scalar_references():
    """Scalar (non-dict) reference values are returned as-is."""
    record = {**RAW_DEPARTMENT, "parent": "plain-string", "company": None}
    result = _format_department(record)
    assert result["parent"] == "plain-string"
    assert result["company"] is None


def test_format_department_ref_fallback_to_value():
    """Reference dicts without display_value fall back to value."""
    record = {**RAW_DEPARTMENT, "dept_head": {"value": "fallback_id"}}
    result = _format_department(record)
    assert result["dept_head"] == "fallback_id"


# ---------------------------------------------------------------------------
# _build_department_query
# ---------------------------------------------------------------------------


def test_build_department_query_empty():
    params = ListDepartmentsParams()
    assert _build_department_query(params) == ""


def test_build_department_query_name():
    params = ListDepartmentsParams(name="Eng")
    assert _build_department_query(params) == "nameLIKEEng"


def test_build_department_query_company():
    params = ListDepartmentsParams(company="Acme")
    assert _build_department_query(params) == "companyLIKEAcme"


def test_build_department_query_combined():
    params = ListDepartmentsParams(name="Eng", company="Acme")
    q = _build_department_query(params)
    assert "nameLIKEEng" in q
    assert "companyLIKEAcme" in q
    assert "^" in q


def test_build_department_query_raw():
    params = ListDepartmentsParams(query="active=true")
    assert _build_department_query(params) == "active=true"


# ---------------------------------------------------------------------------
# _resolve_department_sys_id
# ---------------------------------------------------------------------------


def test_resolve_department_sys_id_hex_passthrough():
    """32-char hex string is returned directly without any HTTP call."""
    result = _resolve_department_sys_id(INSTANCE_URL, {}, DEPT_SYS_ID)
    assert result == DEPT_SYS_ID


def test_resolve_department_sys_id_name_lookup():
    """Name-based lookup hits the API and returns the first sys_id."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"sys_id": DEPT_SYS_ID}]}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=mock_resp) as mock_get:
        result = _resolve_department_sys_id(INSTANCE_URL, {}, "Engineering")
    assert result == DEPT_SYS_ID
    mock_get.assert_called_once()


def test_resolve_department_sys_id_not_found():
    """Returns None when the name lookup returns no results."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=mock_resp):
        result = _resolve_department_sys_id(INSTANCE_URL, {}, "Unknown Dept")
    assert result is None


def test_resolve_department_sys_id_request_error():
    """Returns None on network error."""
    import requests as req_lib
    with patch("servicenow_mcp.tools.department_tools.requests.get", side_effect=req_lib.RequestException("err")):
        result = _resolve_department_sys_id(INSTANCE_URL, {}, "Engineering")
    assert result is None


# ---------------------------------------------------------------------------
# list_departments
# ---------------------------------------------------------------------------


def test_list_departments_success(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_DEPARTMENT]}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=mock_resp):
        result = list_departments(config, auth_manager, ListDepartmentsParams())
    assert "records" in result
    assert len(result["records"]) == 1
    assert result["records"][0]["name"] == "Engineering"
    assert result["count"] == 1
    assert result["has_more"] is False
    assert result["next_offset"] is None


def test_list_departments_has_more(config, auth_manager):
    """When result count equals limit, has_more=True and next_offset is set."""
    records = [RAW_DEPARTMENT] * 20
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": records}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=mock_resp):
        result = list_departments(config, auth_manager, ListDepartmentsParams(limit=20, offset=0))
    assert result["has_more"] is True
    assert result["next_offset"] == 20


def test_list_departments_with_name_filter(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [RAW_DEPARTMENT]}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=mock_resp) as mock_get:
        list_departments(config, auth_manager, ListDepartmentsParams(name="Eng"))
    call_kwargs = mock_get.call_args
    assert "nameLIKEEng" in call_kwargs[1]["params"].get("sysparm_query", "")


def test_list_departments_with_company_filter(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=mock_resp) as mock_get:
        list_departments(config, auth_manager, ListDepartmentsParams(company="Acme"))
    call_kwargs = mock_get.call_args
    assert "companyLIKEAcme" in call_kwargs[1]["params"].get("sysparm_query", "")


def test_list_departments_http_error(config, auth_manager):
    import requests as req_lib
    err_resp = MagicMock()
    err_resp.status_code = 500
    exc = req_lib.HTTPError(response=err_resp)
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = exc
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=mock_resp):
        result = list_departments(config, auth_manager, ListDepartmentsParams())
    assert "error" in result
    assert "500" in result["error"]


def test_list_departments_request_exception(config, auth_manager):
    import requests as req_lib
    with patch(
        "servicenow_mcp.tools.department_tools.requests.get",
        side_effect=req_lib.RequestException("connection refused"),
    ):
        result = list_departments(config, auth_manager, ListDepartmentsParams())
    assert "error" in result
    assert "Request failed" in result["error"]


def test_list_departments_empty(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=mock_resp):
        result = list_departments(config, auth_manager, ListDepartmentsParams())
    assert result["records"] == []
    assert result["count"] == 0
    assert result["has_more"] is False


# ---------------------------------------------------------------------------
# get_department
# ---------------------------------------------------------------------------


def test_get_department_by_sys_id_success(config, auth_manager):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": RAW_DEPARTMENT}
    mock_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=mock_resp):
        result = get_department(config, auth_manager, GetDepartmentParams(department_id=DEPT_SYS_ID))
    assert "department" in result
    assert result["department"]["name"] == "Engineering"


def test_get_department_by_name_success(config, auth_manager):
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": [{"sys_id": DEPT_SYS_ID}]}
    resolve_resp.raise_for_status = MagicMock()

    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json.return_value = {"result": RAW_DEPARTMENT}
    get_resp.raise_for_status = MagicMock()

    with patch(
        "servicenow_mcp.tools.department_tools.requests.get",
        side_effect=[resolve_resp, get_resp],
    ):
        result = get_department(config, auth_manager, GetDepartmentParams(department_id="Engineering"))
    assert "department" in result
    assert result["department"]["sys_id"] == DEPT_SYS_ID


def test_get_department_not_found_resolve(config, auth_manager):
    """Returns error when name cannot be resolved."""
    resolve_resp = MagicMock()
    resolve_resp.json.return_value = {"result": []}
    resolve_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=resolve_resp):
        result = get_department(config, auth_manager, GetDepartmentParams(department_id="Unknown"))
    assert "error" in result
    assert "Unknown" in result["error"]


def test_get_department_404(config, auth_manager):
    """404 from the detail endpoint returns an error dict."""
    not_found_resp = MagicMock()
    not_found_resp.status_code = 404
    not_found_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=not_found_resp):
        result = get_department(config, auth_manager, GetDepartmentParams(department_id=DEPT_SYS_ID))
    assert "error" in result


def test_get_department_empty_result(config, auth_manager):
    """Empty result body returns an error dict."""
    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.json.return_value = {"result": None}
    ok_resp.raise_for_status = MagicMock()
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=ok_resp):
        result = get_department(config, auth_manager, GetDepartmentParams(department_id=DEPT_SYS_ID))
    assert "error" in result


def test_get_department_http_error(config, auth_manager):
    import requests as req_lib
    err_resp = MagicMock()
    err_resp.status_code = 403
    exc = req_lib.HTTPError(response=err_resp)
    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.raise_for_status.side_effect = exc
    with patch("servicenow_mcp.tools.department_tools.requests.get", return_value=ok_resp):
        result = get_department(config, auth_manager, GetDepartmentParams(department_id=DEPT_SYS_ID))
    assert "error" in result
    assert "403" in result["error"]


def test_get_department_request_exception(config, auth_manager):
    import requests as req_lib
    with patch(
        "servicenow_mcp.tools.department_tools.requests.get",
        side_effect=req_lib.RequestException("timeout"),
    ):
        result = get_department(config, auth_manager, GetDepartmentParams(department_id=DEPT_SYS_ID))
    assert "error" in result
    assert "Request failed" in result["error"]
