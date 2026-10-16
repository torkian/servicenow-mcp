"""
Service Portal and Catalog Portal tools for the ServiceNow MCP server.

Provides tools for querying ServiceNow portal configuration:
  - sp_portal  — Service Portal (modern UI)
  - sc_portal  — Classic Service Catalog Portal
  - sp_page    — Service Portal pages
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

SP_PORTAL_TABLE = "sp_portal"
SC_PORTAL_TABLE = "sc_portal"
SP_PAGE_TABLE = "sp_page"

_SP_PORTAL_FIELDS = [
    "sys_id",
    "title",
    "url_suffix",
    "logo",
    "homepage",
    "login_page",
    "theme",
    "css_variables",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]

_SC_PORTAL_FIELDS = [
    "sys_id",
    "title",
    "url_suffix",
    "logo",
    "catalog",
    "homepage",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]

_SP_PAGE_FIELDS = [
    "sys_id",
    "title",
    "id",
    "internal",
    "draft",
    "portal",
    "template",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListServicePortalsParams(BaseModel):
    """Parameters for listing Service Portal (sp_portal) records."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    title: Optional[str] = Field(None, description="Filter by portal title (case-insensitive substring)")
    url_suffix: Optional[str] = Field(None, description="Filter by URL suffix (exact match)")
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetServicePortalParams(BaseModel):
    """Parameters for retrieving a single Service Portal record."""

    portal_id: str = Field(
        ...,
        description="The sys_id or exact title of the Service Portal to retrieve.",
    )


class ListCatalogPortalsParams(BaseModel):
    """Parameters for listing classic Service Catalog Portal (sc_portal) records."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    title: Optional[str] = Field(None, description="Filter by portal title (case-insensitive substring)")
    url_suffix: Optional[str] = Field(None, description="Filter by URL suffix (exact match)")
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetCatalogPortalParams(BaseModel):
    """Parameters for retrieving a single classic Service Catalog Portal record."""

    portal_id: str = Field(
        ...,
        description="The sys_id or exact title of the Catalog Portal to retrieve.",
    )


class ListPortalPagesParams(BaseModel):
    """Parameters for listing Service Portal pages (sp_page)."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    portal_id: Optional[str] = Field(
        None,
        description="Scope results to a specific portal by sys_id or title",
    )
    title: Optional[str] = Field(None, description="Filter by page title (case-insensitive substring)")
    page_id: Optional[str] = Field(None, description="Filter by page URL id (exact match)")
    include_drafts: bool = Field(False, description="Include draft pages (default false)")
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetPortalPageParams(BaseModel):
    """Parameters for retrieving a single portal page."""

    page_id: str = Field(
        ...,
        description="The sys_id, URL id (e.g. 'index'), or exact title of the page.",
    )
    portal_id: Optional[str] = Field(
        None,
        description="Optional portal sys_id or title to narrow the lookup when page_id is not a sys_id.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ref(value: Any) -> Optional[str]:
    """Normalise a reference field to its display value or raw value."""
    if isinstance(value, dict):
        return value.get("display_value") or value.get("value")
    return value


def _format_sp_portal(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw sp_portal record."""
    return {
        "sys_id": record.get("sys_id"),
        "title": record.get("title"),
        "url_suffix": record.get("url_suffix"),
        "logo": record.get("logo"),
        "homepage": _ref(record.get("homepage")),
        "login_page": _ref(record.get("login_page")),
        "theme": _ref(record.get("theme")),
        "css_variables": record.get("css_variables"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def _format_sc_portal(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw sc_portal record."""
    return {
        "sys_id": record.get("sys_id"),
        "title": record.get("title"),
        "url_suffix": record.get("url_suffix"),
        "logo": record.get("logo"),
        "catalog": _ref(record.get("catalog")),
        "homepage": _ref(record.get("homepage")),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def _format_sp_page(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw sp_page record."""
    return {
        "sys_id": record.get("sys_id"),
        "title": record.get("title"),
        "page_id": record.get("id"),
        "portal": _ref(record.get("portal")),
        "template": _ref(record.get("template")),
        "internal": record.get("internal"),
        "draft": record.get("draft"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def _resolve_portal_sys_id(
    instance_url: str,
    headers: Dict,
    table: str,
    portal_id: str,
) -> Optional[str]:
    """Return sys_id for a portal title, or passthrough if already a sys_id."""
    if len(portal_id) == 32 and all(c in "0123456789abcdef" for c in portal_id):
        return portal_id
    url = f"{instance_url.rstrip('/')}/api/now/table/{table}"
    try:
        response = requests.get(
            url,
            headers=headers,
            params={
                "sysparm_query": f"title={portal_id}",
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


def list_service_portals(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListServicePortalsParams,
) -> Dict[str, Any]:
    """List Service Portal records from the sp_portal table.

    Returns a paginated list of portal configurations. Supports filtering by
    title or URL suffix. Each record includes the portal's homepage, login page,
    theme, and CSS variable configuration.

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
    url = f"{base_url}/api/now/table/{SP_PORTAL_TABLE}"

    parts: List[str] = []
    if params.title:
        parts.append(f"titleLIKE{params.title}")
    if params.url_suffix:
        parts.append(f"url_suffix={params.url_suffix}")
    if params.query:
        parts.append(params.query)
    query = "^".join(parts)

    request_params: Dict[str, Any] = {
        "sysparm_fields": ",".join(_SP_PORTAL_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_orderby": "title",
    }
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
    records = [_format_sp_portal(r) for r in data]
    has_more = len(records) == params.limit
    return {
        "records": records,
        "count": len(records),
        "has_more": has_more,
        "next_offset": (params.offset or 0) + len(records) if has_more else None,
    }


def get_service_portal(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetServicePortalParams,
) -> Dict[str, Any]:
    """Retrieve a single Service Portal record by sys_id or exact title.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters including the required portal_id.

    Returns:
        Dictionary with a ``portal`` key on success, or ``error`` on failure.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")

    sys_id = _resolve_portal_sys_id(base_url, headers, SP_PORTAL_TABLE, params.portal_id)
    if not sys_id:
        return {"error": f"Service Portal not found: {params.portal_id}"}

    url = f"{base_url}/api/now/table/{SP_PORTAL_TABLE}/{sys_id}"
    request_params = {
        "sysparm_fields": ",".join(_SP_PORTAL_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        if response.status_code == 404:
            return {"error": f"Service Portal not found: {params.portal_id}"}
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    result = response.json().get("result")
    if not result:
        return {"error": f"Service Portal not found: {params.portal_id}"}

    return {"portal": _format_sp_portal(result)}


def list_catalog_portals(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListCatalogPortalsParams,
) -> Dict[str, Any]:
    """List classic Service Catalog Portal records from the sc_portal table.

    Returns a paginated list of classic catalog portal configurations. Supports
    filtering by title or URL suffix. Each record includes the linked catalog
    and homepage reference.

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
    url = f"{base_url}/api/now/table/{SC_PORTAL_TABLE}"

    parts: List[str] = []
    if params.title:
        parts.append(f"titleLIKE{params.title}")
    if params.url_suffix:
        parts.append(f"url_suffix={params.url_suffix}")
    if params.query:
        parts.append(params.query)
    query = "^".join(parts)

    request_params: Dict[str, Any] = {
        "sysparm_fields": ",".join(_SC_PORTAL_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_orderby": "title",
    }
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
    records = [_format_sc_portal(r) for r in data]
    has_more = len(records) == params.limit
    return {
        "records": records,
        "count": len(records),
        "has_more": has_more,
        "next_offset": (params.offset or 0) + len(records) if has_more else None,
    }


def get_catalog_portal(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetCatalogPortalParams,
) -> Dict[str, Any]:
    """Retrieve a single classic Catalog Portal record by sys_id or exact title.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters including the required portal_id.

    Returns:
        Dictionary with a ``portal`` key on success, or ``error`` on failure.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")

    sys_id = _resolve_portal_sys_id(base_url, headers, SC_PORTAL_TABLE, params.portal_id)
    if not sys_id:
        return {"error": f"Catalog Portal not found: {params.portal_id}"}

    url = f"{base_url}/api/now/table/{SC_PORTAL_TABLE}/{sys_id}"
    request_params = {
        "sysparm_fields": ",".join(_SC_PORTAL_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        if response.status_code == 404:
            return {"error": f"Catalog Portal not found: {params.portal_id}"}
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    result = response.json().get("result")
    if not result:
        return {"error": f"Catalog Portal not found: {params.portal_id}"}

    return {"portal": _format_sc_portal(result)}


def list_portal_pages(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListPortalPagesParams,
) -> Dict[str, Any]:
    """List Service Portal page records from the sp_page table.

    Returns a paginated list of pages. Supports scoping by portal and filtering
    by title or URL id. Draft pages are excluded by default.

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
    url = f"{base_url}/api/now/table/{SP_PAGE_TABLE}"

    parts: List[str] = []

    if params.portal_id:
        portal_sys_id = _resolve_portal_sys_id(base_url, headers, SP_PORTAL_TABLE, params.portal_id)
        if not portal_sys_id:
            return {"error": f"Service Portal not found: {params.portal_id}"}
        parts.append(f"portal={portal_sys_id}")

    if params.title:
        parts.append(f"titleLIKE{params.title}")
    if params.page_id:
        parts.append(f"id={params.page_id}")
    if not params.include_drafts:
        parts.append("draft=false")
    if params.query:
        parts.append(params.query)

    query = "^".join(parts)

    request_params: Dict[str, Any] = {
        "sysparm_fields": ",".join(_SP_PAGE_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_orderby": "title",
    }
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
    records = [_format_sp_page(r) for r in data]
    has_more = len(records) == params.limit
    return {
        "records": records,
        "count": len(records),
        "has_more": has_more,
        "next_offset": (params.offset or 0) + len(records) if has_more else None,
    }


def get_portal_page(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetPortalPageParams,
) -> Dict[str, Any]:
    """Retrieve a single Service Portal page by sys_id, URL id, or title.

    First attempts a direct GET by sys_id. When ``page_id`` is not a hex
    sys_id, falls back to a table query by ``id`` (URL suffix) and then by
    ``title``. An optional ``portal_id`` narrows the lookup.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters including the required page_id.

    Returns:
        Dictionary with a ``page`` key on success, or ``error`` on failure.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")

    portal_sys_id: Optional[str] = None
    if params.portal_id:
        portal_sys_id = _resolve_portal_sys_id(base_url, headers, SP_PORTAL_TABLE, params.portal_id)
        if not portal_sys_id:
            return {"error": f"Service Portal not found: {params.portal_id}"}

    is_sys_id = len(params.page_id) == 32 and all(c in "0123456789abcdef" for c in params.page_id)

    if is_sys_id:
        url = f"{base_url}/api/now/table/{SP_PAGE_TABLE}/{params.page_id}"
        request_params: Dict[str, Any] = {
            "sysparm_fields": ",".join(_SP_PAGE_FIELDS),
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
        }
        try:
            response = requests.get(url, headers=headers, params=request_params, timeout=30)
            if response.status_code == 404:
                return {"error": f"Portal page not found: {params.page_id}"}
            response.raise_for_status()
        except requests.HTTPError as exc:
            return {"error": f"HTTP {exc.response.status_code}: {exc}"}
        except requests.RequestException as exc:
            return {"error": f"Request failed: {exc}"}

        result = response.json().get("result")
        if not result:
            return {"error": f"Portal page not found: {params.page_id}"}
        return {"page": _format_sp_page(result)}

    # Fall back to query by URL id, then by title
    for query_filter in (f"id={params.page_id}", f"titleLIKE{params.page_id}"):
        parts = [query_filter]
        if portal_sys_id:
            parts.append(f"portal={portal_sys_id}")
        list_url = f"{base_url}/api/now/table/{SP_PAGE_TABLE}"
        list_params: Dict[str, Any] = {
            "sysparm_query": "^".join(parts),
            "sysparm_fields": ",".join(_SP_PAGE_FIELDS),
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_limit": 1,
        }
        try:
            response = requests.get(list_url, headers=headers, params=list_params, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            continue
        results = response.json().get("result", [])
        if results:
            return {"page": _format_sp_page(results[0])}

    return {"error": f"Portal page not found: {params.page_id}"}
