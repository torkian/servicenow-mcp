"""
Service offering tools for the ServiceNow MCP server.

Provides tools for querying service offering records in the service_offering table.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

SERVICE_OFFERING_TABLE = "service_offering"

_SERVICE_OFFERING_FIELDS = [
    "sys_id",
    "name",
    "short_description",
    "description",
    "state",
    "price",
    "currency",
    "availability",
    "business_contact",
    "it_contact",
    "owned_by",
    "managed_by",
    "business_criticality",
    "service_classification",
    "parent",
    "portfolio",
    "version",
    "start_date",
    "end_date",
    "active",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListServiceOfferingsParams(BaseModel):
    """Parameters for listing service offerings."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    name: Optional[str] = Field(
        None,
        description="Filter by offering name (case-insensitive substring match)",
    )
    state: Optional[str] = Field(
        None,
        description="Filter by offering state (e.g. 'operational', 'pipeline', 'retired')",
    )
    active: Optional[bool] = Field(None, description="Filter by active flag")
    service_classification: Optional[str] = Field(
        None, description="Filter by service classification (substring match)"
    )
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetServiceOfferingParams(BaseModel):
    """Parameters for retrieving a single service offering."""

    offering_id: str = Field(
        ...,
        description="The sys_id or exact name of the service offering to retrieve.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_service_offering(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw service_offering record."""

    def _ref(value):
        if isinstance(value, dict):
            return value.get("display_value") or value.get("value")
        return value

    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "short_description": record.get("short_description"),
        "description": record.get("description"),
        "state": record.get("state"),
        "price": record.get("price"),
        "currency": record.get("currency"),
        "availability": record.get("availability"),
        "business_contact": _ref(record.get("business_contact")),
        "it_contact": _ref(record.get("it_contact")),
        "owned_by": _ref(record.get("owned_by")),
        "managed_by": _ref(record.get("managed_by")),
        "business_criticality": record.get("business_criticality"),
        "service_classification": record.get("service_classification"),
        "parent": _ref(record.get("parent")),
        "portfolio": _ref(record.get("portfolio")),
        "version": record.get("version"),
        "start_date": record.get("start_date"),
        "end_date": record.get("end_date"),
        "active": record.get("active"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def _build_service_offering_query(params: ListServiceOfferingsParams) -> str:
    """Build the sysparm_query string from filter parameters."""
    parts: List[str] = []
    if params.name:
        parts.append(f"nameLIKE{params.name}")
    if params.state:
        parts.append(f"state={params.state}")
    if params.active is not None:
        parts.append(f"active={'true' if params.active else 'false'}")
    if params.service_classification:
        parts.append(f"service_classificationLIKE{params.service_classification}")
    if params.query:
        parts.append(params.query)
    return "^".join(parts)


def _resolve_service_offering_sys_id(
    instance_url: str,
    headers: Dict,
    offering_id: str,
) -> Optional[str]:
    """Return sys_id for an offering name, or passthrough if already a sys_id."""
    if len(offering_id) == 32 and all(c in "0123456789abcdef" for c in offering_id):
        return offering_id
    url = f"{instance_url.rstrip('/')}/api/now/table/{SERVICE_OFFERING_TABLE}"
    try:
        response = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={offering_id}",
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


def list_service_offerings(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListServiceOfferingsParams,
) -> Dict[str, Any]:
    """List service offering records with optional filters.

    Queries the service_offering table and returns a paginated list. Supports
    filtering by name, state, active flag, and service classification.

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
    url = f"{base_url}/api/now/table/{SERVICE_OFFERING_TABLE}"

    request_params: Dict[str, Any] = {
        "sysparm_fields": ",".join(_SERVICE_OFFERING_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_orderby": "name",
    }
    query = _build_service_offering_query(params)
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
    records = [_format_service_offering(r) for r in data]

    has_more = len(records) == params.limit
    return {
        "records": records,
        "count": len(records),
        "has_more": has_more,
        "next_offset": (params.offset or 0) + len(records) if has_more else None,
    }


def get_service_offering(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetServiceOfferingParams,
) -> Dict[str, Any]:
    """Retrieve a single service offering by sys_id or exact name.

    Looks up the service_offering record. If ``offering_id`` is not a 32-char
    hex sys_id, a name lookup is attempted first.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters including the required offering_id.

    Returns:
        Dictionary with a ``service_offering`` key on success, or ``error`` on failure.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")

    sys_id = _resolve_service_offering_sys_id(base_url, headers, params.offering_id)
    if not sys_id:
        return {"error": f"Service offering not found: {params.offering_id}"}

    url = f"{base_url}/api/now/table/{SERVICE_OFFERING_TABLE}/{sys_id}"
    request_params = {
        "sysparm_fields": ",".join(_SERVICE_OFFERING_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        if response.status_code == 404:
            return {"error": f"Service offering not found: {params.offering_id}"}
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    result = response.json().get("result")
    if not result:
        return {"error": f"Service offering not found: {params.offering_id}"}

    return {"service_offering": _format_service_offering(result)}
