"""
Department tools for the ServiceNow MCP server.

Provides tools for querying department records in the cmn_department table.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

DEPARTMENT_TABLE = "cmn_department"

_DEPARTMENT_FIELDS = [
    "sys_id",
    "name",
    "description",
    "parent",
    "dept_head",
    "company",
    "id",
    "cost_center",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListDepartmentsParams(BaseModel):
    """Parameters for listing departments."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    name: Optional[str] = Field(
        None,
        description="Filter by department name (case-insensitive substring match)",
    )
    company: Optional[str] = Field(
        None,
        description="Filter by company name or sys_id (substring match)",
    )
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetDepartmentParams(BaseModel):
    """Parameters for retrieving a single department."""

    department_id: str = Field(
        ...,
        description="The sys_id or exact name of the department to retrieve.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_department(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw cmn_department record."""

    def _ref(value):
        if isinstance(value, dict):
            return value.get("display_value") or value.get("value")
        return value

    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "description": record.get("description"),
        "id": record.get("id"),
        "parent": _ref(record.get("parent")),
        "dept_head": _ref(record.get("dept_head")),
        "company": _ref(record.get("company")),
        "cost_center": _ref(record.get("cost_center")),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def _build_department_query(params: ListDepartmentsParams) -> str:
    """Build the sysparm_query string from filter parameters."""
    parts: List[str] = []
    if params.name:
        parts.append(f"nameLIKE{params.name}")
    if params.company:
        parts.append(f"companyLIKE{params.company}")
    if params.query:
        parts.append(params.query)
    return "^".join(parts)


def _resolve_department_sys_id(
    instance_url: str,
    headers: Dict,
    department_id: str,
) -> Optional[str]:
    """Return sys_id for a department name, or passthrough if already a sys_id."""
    if len(department_id) == 32 and all(c in "0123456789abcdef" for c in department_id):
        return department_id
    url = f"{instance_url.rstrip('/')}/api/now/table/{DEPARTMENT_TABLE}"
    try:
        response = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={department_id}",
                "sysparm_fields": "sys_id",
                "sysparm_limit": 1,
            },
            timeout=30,
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        if results:
            return results[0].get("sys_id")
    except requests.RequestException:
        pass
    return None


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def list_departments(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListDepartmentsParams,
) -> Dict[str, Any]:
    """List department records with optional filters.

    Queries the cmn_department table and returns a paginated list. Supports
    filtering by name and company.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Query parameters.

    Returns:
        Dictionary with ``records``, ``count``, ``has_more``, and
        ``next_offset`` keys, or an ``error`` key on failure.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")
    url = f"{base_url}/api/now/table/{DEPARTMENT_TABLE}"

    request_params: Dict[str, Any] = {
        "sysparm_fields": ",".join(_DEPARTMENT_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_orderby": "name",
    }
    query = _build_department_query(params)
    if query:
        request_params["sysparm_query"] = query

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    data = response.json().get("result", [])
    records = [_format_department(r) for r in data]

    has_more = len(records) == params.limit
    return {
        "records": records,
        "count": len(records),
        "has_more": has_more,
        "next_offset": (params.offset or 0) + len(records) if has_more else None,
    }


def get_department(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetDepartmentParams,
) -> Dict[str, Any]:
    """Retrieve a single department by sys_id or exact name.

    Looks up the cmn_department record. If ``department_id`` is not a 32-char hex
    sys_id, a name lookup is attempted first.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters including the required department_id.

    Returns:
        Dictionary with a ``department`` key on success, or ``error`` on failure.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")

    sys_id = _resolve_department_sys_id(base_url, headers, params.department_id)
    if not sys_id:
        return {"error": f"Department not found: {params.department_id}"}

    url = f"{base_url}/api/now/table/{DEPARTMENT_TABLE}/{sys_id}"
    request_params = {
        "sysparm_fields": ",".join(_DEPARTMENT_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        if response.status_code == 404:
            return {"error": f"Department not found: {params.department_id}"}
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    result = response.json().get("result")
    if not result:
        return {"error": f"Department not found: {params.department_id}"}

    return {"department": _format_department(result)}
