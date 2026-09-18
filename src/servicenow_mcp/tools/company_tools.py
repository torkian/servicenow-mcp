"""
Company tools for the ServiceNow MCP server.

Provides tools for querying company records in the core_company table.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

COMPANY_TABLE = "core_company"

_COMPANY_FIELDS = [
    "sys_id",
    "name",
    "short_description",
    "notes",
    "phone",
    "fax",
    "website",
    "street",
    "city",
    "state",
    "zip",
    "country",
    "stock_price",
    "stock_symbol",
    "primary",
    "vendor",
    "customer",
    "manufacturer",
    "parent",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListCompaniesParams(BaseModel):
    """Parameters for listing companies."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    name: Optional[str] = Field(
        None,
        description="Filter by company name (case-insensitive substring match)",
    )
    city: Optional[str] = Field(None, description="Filter by city (substring match)")
    country: Optional[str] = Field(None, description="Filter by country (substring match)")
    vendor: Optional[bool] = Field(None, description="Filter by vendor flag")
    customer: Optional[bool] = Field(None, description="Filter by customer flag")
    manufacturer: Optional[bool] = Field(None, description="Filter by manufacturer flag")
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetCompanyParams(BaseModel):
    """Parameters for retrieving a single company."""

    company_id: str = Field(
        ...,
        description="The sys_id or exact name of the company to retrieve.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_company(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw core_company record."""

    def _ref(value):
        if isinstance(value, dict):
            return value.get("display_value") or value.get("value")
        return value

    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "short_description": record.get("short_description"),
        "notes": record.get("notes"),
        "phone": record.get("phone"),
        "fax": record.get("fax"),
        "website": record.get("website"),
        "street": record.get("street"),
        "city": record.get("city"),
        "state": record.get("state"),
        "zip": record.get("zip"),
        "country": record.get("country"),
        "stock_price": record.get("stock_price"),
        "stock_symbol": record.get("stock_symbol"),
        "primary": record.get("primary"),
        "vendor": record.get("vendor"),
        "customer": record.get("customer"),
        "manufacturer": record.get("manufacturer"),
        "parent": _ref(record.get("parent")),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def _build_company_query(params: ListCompaniesParams) -> str:
    """Build the sysparm_query string from filter parameters."""
    parts: List[str] = []
    if params.name:
        parts.append(f"nameLIKE{params.name}")
    if params.city:
        parts.append(f"cityLIKE{params.city}")
    if params.country:
        parts.append(f"countryLIKE{params.country}")
    if params.vendor is not None:
        parts.append(f"vendor={'true' if params.vendor else 'false'}")
    if params.customer is not None:
        parts.append(f"customer={'true' if params.customer else 'false'}")
    if params.manufacturer is not None:
        parts.append(f"manufacturer={'true' if params.manufacturer else 'false'}")
    if params.query:
        parts.append(params.query)
    return "^".join(parts)


def _resolve_company_sys_id(
    instance_url: str,
    headers: Dict,
    company_id: str,
) -> Optional[str]:
    """Return sys_id for a company name, or passthrough if already a sys_id."""
    if len(company_id) == 32 and all(c in "0123456789abcdef" for c in company_id):
        return company_id
    url = f"{instance_url.rstrip('/')}/api/now/table/{COMPANY_TABLE}"
    try:
        response = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={company_id}",
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


def list_companies(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListCompaniesParams,
) -> Dict[str, Any]:
    """List company records with optional filters.

    Queries the core_company table and returns a paginated list. Supports
    filtering by name, city, country, and boolean flags (vendor/customer/manufacturer).

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
    url = f"{base_url}/api/now/table/{COMPANY_TABLE}"

    request_params: Dict[str, Any] = {
        "sysparm_fields": ",".join(_COMPANY_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_orderby": "name",
    }
    query = _build_company_query(params)
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
    records = [_format_company(r) for r in data]

    has_more = len(records) == params.limit
    return {
        "records": records,
        "count": len(records),
        "has_more": has_more,
        "next_offset": (params.offset or 0) + len(records) if has_more else None,
    }


def get_company(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetCompanyParams,
) -> Dict[str, Any]:
    """Retrieve a single company by sys_id or exact name.

    Looks up the core_company record. If ``company_id`` is not a 32-char hex
    sys_id, a name lookup is attempted first.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters including the required company_id.

    Returns:
        Dictionary with a ``company`` key on success, or ``error`` on failure.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")

    sys_id = _resolve_company_sys_id(base_url, headers, params.company_id)
    if not sys_id:
        return {"error": f"Company not found: {params.company_id}"}

    url = f"{base_url}/api/now/table/{COMPANY_TABLE}/{sys_id}"
    request_params = {
        "sysparm_fields": ",".join(_COMPANY_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        if response.status_code == 404:
            return {"error": f"Company not found: {params.company_id}"}
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    result = response.json().get("result")
    if not result:
        return {"error": f"Company not found: {params.company_id}"}

    return {"company": _format_company(result)}
