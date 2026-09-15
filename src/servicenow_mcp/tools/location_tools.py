"""
Location tools for the ServiceNow MCP server.

Provides tools for querying and managing location records in the
cmn_location table.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

LOCATION_TABLE = "cmn_location"

_LOCATION_FIELDS = [
    "sys_id",
    "name",
    "street",
    "city",
    "state",
    "country",
    "zip",
    "phone",
    "fax",
    "latitude",
    "longitude",
    "full_name",
    "parent",
    "company",
    "contact",
    "time_zone",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListLocationsParams(BaseModel):
    """Parameters for listing locations."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    name: Optional[str] = Field(
        None,
        description="Filter by location name (case-insensitive substring match)",
    )
    city: Optional[str] = Field(None, description="Filter by city name (substring match)")
    country: Optional[str] = Field(None, description="Filter by country code or name (substring match)")
    company: Optional[str] = Field(
        None,
        description="Filter by company name or sys_id",
    )
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetLocationParams(BaseModel):
    """Parameters for retrieving a single location."""

    location_id: str = Field(
        ...,
        description="The sys_id or exact name of the location to retrieve.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_location(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw cmn_location record."""

    def _ref(value):
        if isinstance(value, dict):
            return value.get("display_value") or value.get("value")
        return value

    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "full_name": record.get("full_name"),
        "street": record.get("street"),
        "city": record.get("city"),
        "state": record.get("state"),
        "country": record.get("country"),
        "zip": record.get("zip"),
        "phone": record.get("phone"),
        "fax": record.get("fax"),
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
        "parent": _ref(record.get("parent")),
        "company": _ref(record.get("company")),
        "contact": _ref(record.get("contact")),
        "time_zone": record.get("time_zone"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def _build_location_query(params: ListLocationsParams) -> str:
    """Build the sysparm_query string from filter parameters."""
    parts: List[str] = []
    if params.name:
        parts.append(f"nameLIKE{params.name}")
    if params.city:
        parts.append(f"cityLIKE{params.city}")
    if params.country:
        parts.append(f"countryLIKE{params.country}")
    if params.company:
        parts.append(f"companyLIKE{params.company}")
    if params.query:
        parts.append(params.query)
    return "^".join(parts)


def _resolve_location_sys_id(
    instance_url: str,
    headers: Dict,
    location_id: str,
) -> Optional[str]:
    """Return sys_id for a location name, or passthrough if already a sys_id."""
    if len(location_id) == 32 and all(c in "0123456789abcdef" for c in location_id):
        return location_id
    url = f"{instance_url.rstrip('/')}/api/now/table/{LOCATION_TABLE}"
    try:
        response = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={location_id}",
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


def list_locations(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListLocationsParams,
) -> Dict[str, Any]:
    """List location records with optional filters.

    Queries the cmn_location table and returns a paginated list. Supports
    filtering by name, city, country, and company.

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
    url = f"{base_url}/api/now/table/{LOCATION_TABLE}"

    request_params: Dict[str, Any] = {
        "sysparm_fields": ",".join(_LOCATION_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_orderby": "name",
    }
    query = _build_location_query(params)
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
    records = [_format_location(r) for r in data]

    has_more = len(records) == params.limit
    return {
        "records": records,
        "count": len(records),
        "has_more": has_more,
        "next_offset": (params.offset or 0) + len(records) if has_more else None,
    }


def get_location(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetLocationParams,
) -> Dict[str, Any]:
    """Retrieve a single location by sys_id or exact name.

    Looks up the cmn_location record. If ``location_id`` is not a 32-char hex
    sys_id, a name lookup is attempted first.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters including the required location_id.

    Returns:
        Dictionary with a ``location`` key on success, or ``error`` on failure.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")

    sys_id = _resolve_location_sys_id(base_url, headers, params.location_id)
    if not sys_id:
        return {"error": f"Location not found: {params.location_id}"}

    url = f"{base_url}/api/now/table/{LOCATION_TABLE}/{sys_id}"
    request_params = {
        "sysparm_fields": ",".join(_LOCATION_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        if response.status_code == 404:
            return {"error": f"Location not found: {params.location_id}"}
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    result = response.json().get("result")
    if not result:
        return {"error": f"Location not found: {params.location_id}"}

    return {"location": _format_location(result)}
