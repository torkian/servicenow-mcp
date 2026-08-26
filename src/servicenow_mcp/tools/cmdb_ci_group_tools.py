"""
CMDB CI Group tools for the ServiceNow MCP server.

Provides tools for querying CI groups from the cmdb_ci_group table.
CI groups are logical collections of configuration items used for batch
maintenance windows, relationship views, and alert groupings.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

CMDB_CI_GROUP_TABLE = "cmdb_ci_group"

_CI_GROUP_FIELDS = [
    "sys_id",
    "name",
    "type",
    "active",
    "description",
    "manager",
    "sys_class_name",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListCMDBCIGroupsParams(BaseModel):
    """Parameters for listing CMDB CI groups."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    name: Optional[str] = Field(
        None,
        description="Filter by CI group name (case-insensitive substring match)",
    )
    group_type: Optional[str] = Field(
        None,
        description=(
            "Filter by group type stored in the 'type' field "
            "(e.g. 'manual', 'dynamic', or any value defined in your instance)"
        ),
    )
    active: Optional[bool] = Field(
        None,
        description="Filter by active flag. True returns only active groups, False only inactive.",
    )
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetCMDBCIGroupParams(BaseModel):
    """Parameters for retrieving a single CMDB CI group."""

    sys_id: str = Field(..., description="sys_id of the cmdb_ci_group record to retrieve")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_ci_group(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw cmdb_ci_group record."""

    def _ref(value):
        if isinstance(value, dict):
            return value.get("display_value") or value.get("value")
        return value

    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "type": _ref(record.get("type")),
        "active": record.get("active"),
        "description": record.get("description"),
        "manager": _ref(record.get("manager")),
        "sys_class_name": _ref(record.get("sys_class_name")),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def _build_ci_group_query(params: ListCMDBCIGroupsParams) -> str:
    """Build the sysparm_query string from filter parameters."""
    parts: List[str] = []
    if params.name:
        parts.append(f"nameLIKE{params.name}")
    if params.group_type:
        parts.append(f"type={params.group_type}")
    if params.active is not None:
        parts.append(f"active={'true' if params.active else 'false'}")
    if params.query:
        parts.append(params.query)
    return "^".join(parts)


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def list_cmdb_ci_groups(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListCMDBCIGroupsParams,
) -> Dict[str, Any]:
    """List CMDB CI groups with optional filters.

    Queries the cmdb_ci_group table and returns a paginated list of CI group
    records. Supports filtering by name, type, and active state.

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
    url = f"{base_url}/api/now/table/{CMDB_CI_GROUP_TABLE}"

    request_params: Dict[str, Any] = {
        "sysparm_fields": ",".join(_CI_GROUP_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_orderby": "name",
    }
    query = _build_ci_group_query(params)
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
    records = [_format_ci_group(r) for r in data]

    has_more = len(records) == params.limit
    return {
        "records": records,
        "count": len(records),
        "has_more": has_more,
        "next_offset": (params.offset or 0) + len(records) if has_more else None,
    }


def get_cmdb_ci_group(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetCMDBCIGroupParams,
) -> Dict[str, Any]:
    """Retrieve a single CMDB CI group by sys_id.

    Returns the full detail of a cmdb_ci_group record. Returns a structured
    error if the record is not found or if the request fails.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters including the required sys_id.

    Returns:
        Dictionary with a ``ci_group`` key on success, or ``error`` on failure.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")
    url = f"{base_url}/api/now/table/{CMDB_CI_GROUP_TABLE}/{params.sys_id}"

    request_params = {
        "sysparm_fields": ",".join(_CI_GROUP_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        if response.status_code == 404:
            return {"error": f"CMDB CI group not found: {params.sys_id}"}
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    result = response.json().get("result")
    if not result:
        return {"error": f"CMDB CI group not found: {params.sys_id}"}

    return {"ci_group": _format_ci_group(result)}
