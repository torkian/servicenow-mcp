"""
CMDB affinity tools for the ServiceNow MCP server.

Provides tools for querying CI affinity rules from the cmdb_ci_affinity
table. Affinity rules define co-location or anti-affinity constraints
between configuration items (e.g., for VM placement policies).
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

CMDB_CI_AFFINITY_TABLE = "cmdb_ci_affinity"

_AFFINITY_FIELDS = [
    "sys_id",
    "name",
    "type",
    "active",
    "description",
    "scope",
    "condition",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListCIAffinitiesParams(BaseModel):
    """Parameters for listing CMDB CI affinity rules."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    name: Optional[str] = Field(
        None,
        description="Filter by affinity rule name (case-insensitive substring match)",
    )
    affinity_type: Optional[str] = Field(
        None,
        description=(
            "Filter by affinity type stored in the 'type' field "
            "(e.g. 'affinity', 'anti_affinity', or any custom value defined in your instance)"
        ),
    )
    ci_sys_id: Optional[str] = Field(
        None,
        description=(
            "Filter rules that reference a specific CI sys_id. "
            "Appended as a raw condition on the 'cmdb_ci' field when present."
        ),
    )
    active: Optional[bool] = Field(
        None,
        description="Filter by active flag. True returns only active rules, False only inactive.",
    )
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetCIAffinityParams(BaseModel):
    """Parameters for retrieving a single CI affinity rule."""

    sys_id: str = Field(..., description="sys_id of the cmdb_ci_affinity record to retrieve")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_affinity(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw cmdb_ci_affinity record."""

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
        "scope": _ref(record.get("scope")),
        "condition": record.get("condition"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def _build_query(params: ListCIAffinitiesParams) -> str:
    """Build the sysparm_query string from filter parameters."""
    parts: List[str] = []
    if params.name:
        parts.append(f"nameLIKE{params.name}")
    if params.affinity_type:
        parts.append(f"type={params.affinity_type}")
    if params.ci_sys_id:
        parts.append(f"cmdb_ci={params.ci_sys_id}")
    if params.active is not None:
        parts.append(f"active={'true' if params.active else 'false'}")
    if params.query:
        parts.append(params.query)
    return "^".join(parts)


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def list_ci_affinities(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListCIAffinitiesParams,
) -> Dict[str, Any]:
    """List CMDB CI affinity rules with optional filters.

    Queries the cmdb_ci_affinity table and returns a paginated list of
    affinity rule records. Supports filtering by name, type, active state,
    and a specific CI sys_id.

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
    url = f"{base_url}/api/now/table/{CMDB_CI_AFFINITY_TABLE}"

    request_params: Dict[str, Any] = {
        "sysparm_fields": ",".join(_AFFINITY_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
    }
    query = _build_query(params)
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
    records = [_format_affinity(r) for r in data]

    has_more = len(records) == params.limit
    return {
        "records": records,
        "count": len(records),
        "has_more": has_more,
        "next_offset": (params.offset or 0) + len(records) if has_more else None,
    }


def get_ci_affinity(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetCIAffinityParams,
) -> Dict[str, Any]:
    """Retrieve a single CMDB CI affinity rule by sys_id.

    Returns the full detail of a cmdb_ci_affinity record. Returns a
    structured error if the record is not found or if the request fails.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters including the required sys_id.

    Returns:
        Dictionary with an ``affinity`` key on success, or ``error`` on failure.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")
    url = f"{base_url}/api/now/table/{CMDB_CI_AFFINITY_TABLE}/{params.sys_id}"

    request_params = {
        "sysparm_fields": ",".join(_AFFINITY_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        if response.status_code == 404:
            return {"error": f"CI affinity record not found: {params.sys_id}"}
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    result = response.json().get("result")
    if not result:
        return {"error": f"CI affinity record not found: {params.sys_id}"}

    return {"affinity": _format_affinity(result)}
