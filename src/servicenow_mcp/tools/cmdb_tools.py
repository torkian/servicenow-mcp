"""
CMDB tools for the ServiceNow MCP server.

Provides tools for managing Configuration Items (CIs) in the ServiceNow
CMDB (Configuration Management Database).
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field, field_validator

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.helpers import (
    _build_sysparm_params,
    _format_http_error,
    _get_headers,
    _get_instance_url,
    _join_query_parts,
    _make_request,
    _paginated_list_response,
    _unwrap_and_validate_params,
    validate_servicenow_datetime,
)

logger = logging.getLogger(__name__)

CMDB_CI_TABLE = "cmdb_ci"
CMDB_CI_OUTAGE_TABLE = "cmdb_ci_outage"

CMDB_CI_OUTAGE_FIELDS = [
    "sys_id",
    "cmdb_ci",
    "type",
    "begin",
    "end",
    "duration",
    "short_description",
    "cause_ci",
    "resolved",
    "resolution_notes",
    "sys_created_on",
    "sys_updated_on",
]

CMDB_CI_FIELDS = [
    "sys_id",
    "name",
    "sys_class_name",
    "category",
    "operational_status",
    "environment",
    "short_description",
    "ip_address",
    "serial_number",
    "asset_tag",
    "install_status",
    "managed_by",
    "owned_by",
    "location",
    "company",
    "sys_created_on",
    "sys_updated_on",
]


class ListCIsParams(BaseModel):
    """Parameters for listing CMDB configuration items."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    ci_class: Optional[str] = Field(
        None,
        description=(
            "CI class table to query (e.g. cmdb_ci_server, cmdb_ci_computer, "
            "cmdb_ci_service). Defaults to cmdb_ci (base class)."
        ),
    )
    name: Optional[str] = Field(None, description="Filter by CI name (substring match)")
    operational_status: Optional[str] = Field(
        None,
        description=(
            "Filter by operational status: 1=Operational, 2=Non-operational, "
            "3=Repair in progress, 4=DR standby, 5=Ready, 6=Retired"
        ),
    )
    environment: Optional[str] = Field(
        None,
        description="Filter by environment (e.g. production, development, test, staging)",
    )
    category: Optional[str] = Field(
        None,
        description="Filter by CI category (e.g. Software, Hardware, Network)",
    )
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetCIParams(BaseModel):
    """Parameters for retrieving a single CMDB configuration item."""

    sys_id: str = Field(..., description="sys_id of the configuration item to retrieve")
    ci_class: Optional[str] = Field(
        None,
        description="CI class table (e.g. cmdb_ci_server). Defaults to cmdb_ci.",
    )


class CreateCIParams(BaseModel):
    """Parameters for creating a new CMDB configuration item."""

    name: str = Field(..., description="Name of the configuration item")
    ci_class: Optional[str] = Field(
        None,
        description=(
            "CI class table to create the record in (e.g. cmdb_ci_server). "
            "Defaults to cmdb_ci."
        ),
    )
    short_description: Optional[str] = Field(None, description="Brief description of the CI")
    category: Optional[str] = Field(None, description="CI category")
    environment: Optional[str] = Field(
        None, description="Environment (production, development, test, staging)"
    )
    operational_status: Optional[str] = Field(
        None,
        description=(
            "Operational status: 1=Operational, 2=Non-operational, "
            "3=Repair in progress, 5=Ready, 6=Retired"
        ),
    )
    install_status: Optional[str] = Field(
        None,
        description=(
            "Install status: 1=Installed, 2=On order, 3=In maintenance, "
            "6=In stock, 7=Retired"
        ),
    )
    ip_address: Optional[str] = Field(None, description="IP address of the CI")
    serial_number: Optional[str] = Field(None, description="Serial number")
    asset_tag: Optional[str] = Field(None, description="Asset tag")
    managed_by: Optional[str] = Field(None, description="sys_id of the user managing this CI")
    owned_by: Optional[str] = Field(None, description="sys_id of the user who owns this CI")
    location: Optional[str] = Field(None, description="sys_id of the location record")
    company: Optional[str] = Field(None, description="sys_id of the company record")


class GetCIClassSchemaParams(BaseModel):
    """Parameters for retrieving the field schema of a CMDB CI class."""

    ci_class: str = Field(
        ...,
        description=(
            "CI class table name to inspect (e.g. cmdb_ci_server, cmdb_ci_computer, "
            "cmdb_ci_service). Use list_cmdb_classes to discover valid class names."
        ),
    )
    mandatory_only: Optional[bool] = Field(
        False,
        description="When True, return only fields that are marked mandatory (default False)",
    )
    include_inherited: Optional[bool] = Field(
        False,
        description=(
            "When True, also return fields inherited from the base cmdb_ci table "
            "(default False — only fields defined on the specific class are returned)"
        ),
    )


class ListCMDBClassesParams(BaseModel):
    """Parameters for listing distinct CMDB CI class names."""

    ci_class: Optional[str] = Field(
        None,
        description=(
            "Base CI class table to query (e.g. cmdb_ci_server). "
            "Defaults to cmdb_ci (base class)."
        ),
    )
    query: Optional[str] = Field(
        None,
        description="Optional ServiceNow encoded query to pre-filter CIs before grouping",
    )
    include_count: Optional[bool] = Field(
        True,
        description="Include the number of CI records per class in the response (default True)",
    )


class GetCIByNameParams(BaseModel):
    """Parameters for the get_ci_by_name lookup shortcut."""

    name: str = Field(..., description="CI name to search for (substring match by default)")
    exact: Optional[bool] = Field(
        False,
        description="When True, perform an exact name match instead of a substring match",
    )
    ci_class: Optional[str] = Field(
        None,
        description=(
            "CI class table to query (e.g. cmdb_ci_server). Defaults to cmdb_ci."
        ),
    )
    limit: Optional[int] = Field(10, description="Maximum number of records to return (default 10)")
    offset: Optional[int] = Field(0, description="Pagination offset")


class UpdateCIParams(BaseModel):
    """Parameters for updating an existing CMDB configuration item."""

    sys_id: str = Field(..., description="sys_id of the configuration item to update")
    ci_class: Optional[str] = Field(
        None,
        description="CI class table (e.g. cmdb_ci_server). Defaults to cmdb_ci.",
    )
    name: Optional[str] = Field(None, description="Updated name")
    short_description: Optional[str] = Field(None, description="Updated description")
    category: Optional[str] = Field(None, description="Updated category")
    environment: Optional[str] = Field(None, description="Updated environment")
    operational_status: Optional[str] = Field(None, description="Updated operational status")
    install_status: Optional[str] = Field(None, description="Updated install status")
    ip_address: Optional[str] = Field(None, description="Updated IP address")
    serial_number: Optional[str] = Field(None, description="Updated serial number")
    asset_tag: Optional[str] = Field(None, description="Updated asset tag")
    managed_by: Optional[str] = Field(None, description="Updated managed_by user sys_id")
    owned_by: Optional[str] = Field(None, description="Updated owned_by user sys_id")
    location: Optional[str] = Field(None, description="Updated location sys_id")
    company: Optional[str] = Field(None, description="Updated company sys_id")


def _format_ci(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw CMDB CI record."""
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "ci_class": record.get("sys_class_name"),
        "category": record.get("category"),
        "operational_status": record.get("operational_status"),
        "environment": record.get("environment"),
        "short_description": record.get("short_description"),
        "ip_address": record.get("ip_address"),
        "serial_number": record.get("serial_number"),
        "asset_tag": record.get("asset_tag"),
        "install_status": record.get("install_status"),
        "managed_by": record.get("managed_by"),
        "owned_by": record.get("owned_by"),
        "location": record.get("location"),
        "company": record.get("company"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _build_body(validated, exclude: List[str]) -> Dict:
    """Build a request body dict from a validated params object, skipping None and excluded fields."""
    body = {}
    field_map = {
        "name": "name",
        "short_description": "short_description",
        "category": "category",
        "environment": "environment",
        "operational_status": "operational_status",
        "install_status": "install_status",
        "ip_address": "ip_address",
        "serial_number": "serial_number",
        "asset_tag": "asset_tag",
        "managed_by": "managed_by",
        "owned_by": "owned_by",
        "location": "location",
        "company": "company",
    }
    for attr, sn_field in field_map.items():
        if attr in exclude:
            continue
        value = getattr(validated, attr, None)
        if value is not None:
            body[sn_field] = value
    return body


def list_cmdb_classes(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Return distinct sys_class_name values from the CMDB using the aggregate API.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListCMDBClassesParams.

    Returns:
        Dictionary with ``success``, ``classes`` (list of {name, count?}), and ``count``.
    """
    result = _unwrap_and_validate_params(params, ListCMDBClassesParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    table = validated.ci_class or CMDB_CI_TABLE
    url = f"{instance_url}/api/now/stats/{table}"
    query_params: Dict[str, Any] = {
        "sysparm_group_by": "sys_class_name",
        "sysparm_count": "true",
    }
    if validated.query:
        query_params["sysparm_query"] = validated.query

    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        stats = response.json().get("result", {}).get("stats", [])
        classes = []
        for item in stats:
            raw = item.get("sys_class_name", "")
            name = raw.get("value", "") if isinstance(raw, dict) else raw
            if not name:
                continue
            entry: Dict[str, Any] = {"name": name}
            if validated.include_count:
                entry["count"] = int(item.get("count", 0))
            classes.append(entry)
        classes.sort(key=lambda x: x["name"])
        return {"success": True, "classes": classes, "count": len(classes)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing CMDB classes: {e}")
        return {"success": False, "message": f"Error listing CMDB classes: {_format_http_error(e)}"}


def list_cis(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List CMDB configuration items with optional filters and pagination.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListCIsParams.

    Returns:
        Dictionary with ``success``, ``cis`` (list), ``count``, and pagination keys.
    """
    result = _unwrap_and_validate_params(params, ListCIsParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    table = validated.ci_class or CMDB_CI_TABLE

    query_parts = []
    if validated.name:
        query_parts.append(f"nameLIKE{validated.name}")
    if validated.operational_status:
        query_parts.append(f"operational_status={validated.operational_status}")
    if validated.environment:
        query_parts.append(f"environment={validated.environment}")
    if validated.category:
        query_parts.append(f"category={validated.category}")
    if validated.query:
        query_parts.append(validated.query)

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        fields=",".join(CMDB_CI_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{table}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        cis = [_format_ci(r) for r in response.json().get("result", [])]
        return _paginated_list_response(cis, validated.limit, validated.offset, "cis")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing CIs: {e}")
        return {"success": False, "message": f"Error listing CIs: {_format_http_error(e)}"}


def get_ci(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single CMDB configuration item by its sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetCIParams.

    Returns:
        Dictionary with ``success`` and ``ci`` keys.
    """
    result = _unwrap_and_validate_params(params, GetCIParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    table = validated.ci_class or CMDB_CI_TABLE
    url = f"{instance_url}/api/now/table/{table}/{validated.sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(CMDB_CI_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"CI not found: {validated.sys_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"CI not found: {validated.sys_id}"}
        return {"success": True, "ci": _format_ci(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving CI: {e}")
        return {"success": False, "message": f"Error retrieving CI: {_format_http_error(e)}"}


def create_ci(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new CMDB configuration item.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateCIParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, and ``ci`` keys.
    """
    result = _unwrap_and_validate_params(params, CreateCIParams, required_fields=["name"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    table = validated.ci_class or CMDB_CI_TABLE
    body = _build_body(validated, exclude=["ci_class"])

    url = f"{instance_url}/api/now/table/{table}"
    try:
        response = _make_request("POST", url, headers=headers, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "sys_id": record.get("sys_id"),
            "ci": _format_ci(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating CI: {e}")
        return {"success": False, "message": f"Error creating CI: {_format_http_error(e)}"}


def update_ci(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing CMDB configuration item.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdateCIParams.

    Returns:
        Dictionary with ``success`` and ``ci`` keys.
    """
    result = _unwrap_and_validate_params(params, UpdateCIParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    body = _build_body(validated, exclude=["sys_id", "ci_class"])
    if not body:
        return {"success": False, "message": "No fields provided to update"}

    table = validated.ci_class or CMDB_CI_TABLE
    url = f"{instance_url}/api/now/table/{table}/{validated.sys_id}"
    try:
        response = _make_request("PATCH", url, headers=headers, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"CI not found: {validated.sys_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {"success": True, "ci": _format_ci(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating CI: {e}")
        return {"success": False, "message": f"Error updating CI: {_format_http_error(e)}"}


def get_ci_by_name(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Search for CMDB configuration items by name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetCIByNameParams.

    Returns:
        Dictionary with ``success``, ``cis`` (list), ``count``, and pagination keys.
    """
    result = _unwrap_and_validate_params(params, GetCIByNameParams, required_fields=["name"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    table = validated.ci_class or CMDB_CI_TABLE
    operator = "=" if validated.exact else "LIKE"
    query = f"name{operator}{validated.name}"

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=query,
        exclude_reference_link=True,
        fields=",".join(CMDB_CI_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{table}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        cis = [_format_ci(r) for r in response.json().get("result", [])]
        return _paginated_list_response(cis, validated.limit, validated.offset, "cis")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error searching CIs by name: {e}")
        return {"success": False, "message": f"Error searching CIs by name: {_format_http_error(e)}"}


class ListCMDBCIOutagesParams(BaseModel):
    """Parameters for listing CMDB CI outage records."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    ci_sys_id: Optional[str] = Field(
        None,
        description="Filter outages by the affected CI sys_id (cmdb_ci field)",
    )
    outage_type: Optional[str] = Field(
        None,
        description="Filter by outage type (e.g. hardware, network, application)",
    )
    resolved: Optional[bool] = Field(
        None,
        description="When True return only resolved outages; False returns open outages",
    )
    begin_after: Optional[str] = Field(
        None,
        description="Return outages that begin on or after this datetime (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)",
    )
    begin_before: Optional[str] = Field(
        None,
        description="Return outages that begin on or before this datetime (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)",
    )
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")

    @field_validator("begin_after", "begin_before", mode="before")
    @classmethod
    def _validate_datetime_fields(cls, v):
        return validate_servicenow_datetime(v)


def _format_ci_outage(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw cmdb_ci_outage record."""

    def _ref(val):
        if isinstance(val, dict):
            return val.get("value") or val.get("display_value")
        return val

    return {
        "sys_id": record.get("sys_id"),
        "ci_sys_id": _ref(record.get("cmdb_ci")),
        "type": record.get("type"),
        "begin": record.get("begin"),
        "end": record.get("end"),
        "duration": record.get("duration"),
        "short_description": record.get("short_description"),
        "cause_ci": _ref(record.get("cause_ci")),
        "resolved": record.get("resolved"),
        "resolution_notes": record.get("resolution_notes"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


class CreateCIOutageParams(BaseModel):
    """Parameters for creating a new CMDB CI outage record."""

    cmdb_ci: str = Field(..., description="sys_id of the affected configuration item")
    begin: str = Field(
        ...,
        description="Outage start datetime (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)",
    )
    type: Optional[str] = Field(
        None,
        description="Outage type (e.g. hardware, network, application, software)",
    )
    end: Optional[str] = Field(
        None,
        description="Outage end datetime (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)",
    )
    short_description: Optional[str] = Field(
        None,
        description="Brief description of the outage",
    )
    cause_ci: Optional[str] = Field(
        None,
        description="sys_id of the CI that caused this outage",
    )
    resolved: Optional[bool] = Field(
        None,
        description="Whether the outage is already resolved",
    )
    resolution_notes: Optional[str] = Field(
        None,
        description="Notes explaining how the outage was resolved",
    )

    @field_validator("begin", "end", mode="before")
    @classmethod
    def _validate_datetime_fields(cls, v):
        return validate_servicenow_datetime(v)


class GetCIOutageParams(BaseModel):
    """Parameters for retrieving a single CMDB CI outage record."""

    sys_id: str = Field(..., description="sys_id of the cmdb_ci_outage record to retrieve")


class DeleteCIOutageParams(BaseModel):
    """Parameters for deleting a CMDB CI outage record."""

    sys_id: str = Field(..., description="sys_id of the cmdb_ci_outage record to delete")


class UpdateCIOutageParams(BaseModel):
    """Parameters for updating an existing CMDB CI outage record."""

    sys_id: str = Field(..., description="sys_id of the cmdb_ci_outage record to update")
    type: Optional[str] = Field(
        None,
        description="Outage type (e.g. hardware, network, application, software)",
    )
    begin: Optional[str] = Field(
        None,
        description="Outage start datetime (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)",
    )
    end: Optional[str] = Field(
        None,
        description="Outage end datetime (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)",
    )
    short_description: Optional[str] = Field(
        None,
        description="Brief description of the outage",
    )
    cause_ci: Optional[str] = Field(
        None,
        description="sys_id of the CI that caused this outage",
    )
    resolved: Optional[bool] = Field(
        None,
        description="Set to True to mark the outage as resolved",
    )
    resolution_notes: Optional[str] = Field(
        None,
        description="Notes explaining how the outage was resolved",
    )

    @field_validator("begin", "end", mode="before")
    @classmethod
    def _validate_datetime_fields(cls, v):
        return validate_servicenow_datetime(v)


def get_ci_outage(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single CMDB CI outage record by its sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetCIOutageParams.

    Returns:
        Dictionary with ``success`` and ``outage`` keys.
    """
    result = _unwrap_and_validate_params(params, GetCIOutageParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}/api/now/table/{CMDB_CI_OUTAGE_TABLE}/{validated.sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(CMDB_CI_OUTAGE_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"CI outage not found: {validated.sys_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"CI outage not found: {validated.sys_id}"}
        return {"success": True, "outage": _format_ci_outage(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving CI outage: {e}")
        return {"success": False, "message": f"Error retrieving CI outage: {_format_http_error(e)}"}


def update_ci_outage(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing CMDB CI outage record via PATCH.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdateCIOutageParams.

    Returns:
        Dictionary with ``success`` and ``outage`` keys.
    """
    result = _unwrap_and_validate_params(params, UpdateCIOutageParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    body: Dict[str, Any] = {}
    if validated.type is not None:
        body["type"] = validated.type
    if validated.begin is not None:
        body["begin"] = validated.begin
    if validated.end is not None:
        body["end"] = validated.end
    if validated.short_description is not None:
        body["short_description"] = validated.short_description
    if validated.cause_ci is not None:
        body["cause_ci"] = validated.cause_ci
    if validated.resolved is not None:
        body["resolved"] = "true" if validated.resolved else "false"
    if validated.resolution_notes is not None:
        body["resolution_notes"] = validated.resolution_notes

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    url = f"{instance_url}/api/now/table/{CMDB_CI_OUTAGE_TABLE}/{validated.sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(CMDB_CI_OUTAGE_FIELDS),
    }
    try:
        response = _make_request("PATCH", url, headers=headers, params=query_params, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"CI outage not found: {validated.sys_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {"success": True, "outage": _format_ci_outage(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating CI outage: {e}")
        return {"success": False, "message": f"Error updating CI outage: {_format_http_error(e)}"}


def create_ci_outage(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new CMDB CI outage record in the cmdb_ci_outage table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateCIOutageParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, and ``outage`` keys.
    """
    result = _unwrap_and_validate_params(
        params, CreateCIOutageParams, required_fields=["cmdb_ci", "begin"]
    )
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    body: Dict[str, Any] = {
        "cmdb_ci": validated.cmdb_ci,
        "begin": validated.begin,
    }
    if validated.type is not None:
        body["type"] = validated.type
    if validated.end is not None:
        body["end"] = validated.end
    if validated.short_description is not None:
        body["short_description"] = validated.short_description
    if validated.cause_ci is not None:
        body["cause_ci"] = validated.cause_ci
    if validated.resolved is not None:
        body["resolved"] = "true" if validated.resolved else "false"
    if validated.resolution_notes is not None:
        body["resolution_notes"] = validated.resolution_notes

    url = f"{instance_url}/api/now/table/{CMDB_CI_OUTAGE_TABLE}"
    try:
        response = _make_request("POST", url, headers=headers, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "sys_id": record.get("sys_id"),
            "outage": _format_ci_outage(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating CI outage: {e}")
        return {"success": False, "message": f"Error creating CI outage: {_format_http_error(e)}"}


def list_cmdb_ci_outages(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List CMDB CI outage records with optional filters and pagination.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListCMDBCIOutagesParams.

    Returns:
        Dictionary with ``success``, ``outages`` (list), ``count``, and pagination keys.
    """
    result = _unwrap_and_validate_params(params, ListCMDBCIOutagesParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    query_parts = []
    if validated.ci_sys_id:
        query_parts.append(f"cmdb_ci={validated.ci_sys_id}")
    if validated.outage_type:
        query_parts.append(f"type={validated.outage_type}")
    if validated.resolved is not None:
        query_parts.append(f"resolved={'true' if validated.resolved else 'false'}")
    if validated.begin_after:
        query_parts.append(f"begin>={validated.begin_after}")
    if validated.begin_before:
        query_parts.append(f"begin<={validated.begin_before}")
    if validated.query:
        query_parts.append(validated.query)

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        fields=",".join(CMDB_CI_OUTAGE_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{CMDB_CI_OUTAGE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        outages = [_format_ci_outage(r) for r in response.json().get("result", [])]
        return _paginated_list_response(outages, validated.limit, validated.offset, "outages")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing CI outages: {e}")
        return {"success": False, "message": f"Error listing CI outages: {_format_http_error(e)}"}


def delete_ci_outage(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete a CMDB CI outage record from the cmdb_ci_outage table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeleteCIOutageParams.

    Returns:
        Dictionary with ``success`` and ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, DeleteCIOutageParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}/api/now/table/{CMDB_CI_OUTAGE_TABLE}/{validated.sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {"success": False, "message": f"CI outage not found: {validated.sys_id}"}
        if response.status_code == 204:
            return {"success": True, "message": f"CI outage {validated.sys_id} deleted successfully"}
        response.raise_for_status()
        return {"success": True, "message": f"CI outage {validated.sys_id} deleted successfully"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting CI outage: {e}")
        return {"success": False, "message": f"Error deleting CI outage: {_format_http_error(e)}"}


_SYS_DICTIONARY_FIELDS = [
    "element",
    "column_label",
    "internal_type",
    "mandatory",
    "max_length",
    "default_value",
    "reference",
    "read_only",
    "active",
]

_SYS_DICTIONARY_TABLE = "sys_dictionary"


def _format_schema_field(record: Dict) -> Dict:
    """Normalise a sys_dictionary record into a concise schema field dict."""

    def _str(v: Any) -> str:
        if isinstance(v, dict):
            return v.get("display_value") or v.get("value") or ""
        return str(v) if v is not None else ""

    ref_raw = record.get("reference", "")
    reference = _str(ref_raw)

    return {
        "field_name": _str(record.get("element")),
        "label": _str(record.get("column_label")),
        "type": _str(record.get("internal_type")),
        "mandatory": str(record.get("mandatory", "")).lower() in ("true", "1"),
        "read_only": str(record.get("read_only", "")).lower() in ("true", "1"),
        "max_length": record.get("max_length"),
        "default_value": _str(record.get("default_value")) or None,
        "reference_table": reference or None,
    }


def get_ci_class_schema(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve the field schema for a CMDB CI class from sys_dictionary.

    Queries the sys_dictionary table to return all active field definitions
    for the specified CI class, including field name, label, data type,
    mandatory flag, max length, default value, and reference table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetCIClassSchemaParams.

    Returns:
        Dictionary with ``success``, ``ci_class``, ``fields`` (list), and
        ``field_count`` keys.
    """
    result = _unwrap_and_validate_params(params, GetCIClassSchemaParams, required_fields=["ci_class"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    classes_to_query = [validated.ci_class]
    if validated.include_inherited and validated.ci_class != CMDB_CI_TABLE:
        classes_to_query.append(CMDB_CI_TABLE)

    query_parts = [f"nameIN{','.join(classes_to_query)}", "active=true", "elementISNOTEMPTY"]
    if validated.mandatory_only:
        query_parts.append("mandatory=true")

    url = f"{instance_url}/api/now/table/{_SYS_DICTIONARY_TABLE}"
    query_params: Dict[str, Any] = {
        "sysparm_query": "^".join(query_parts),
        "sysparm_fields": ",".join(_SYS_DICTIONARY_FIELDS),
        "sysparm_limit": "500",
        "sysparm_offset": "0",
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        records = response.json().get("result", [])

        fields = [_format_schema_field(r) for r in records]
        fields = [f for f in fields if f["field_name"]]
        fields.sort(key=lambda f: (not f["mandatory"], f["field_name"]))

        return {
            "success": True,
            "ci_class": validated.ci_class,
            "include_inherited": validated.include_inherited,
            "mandatory_only": validated.mandatory_only,
            "fields": fields,
            "field_count": len(fields),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving CI class schema: {e}")
        return {
            "success": False,
            "message": f"Error retrieving CI class schema: {_format_http_error(e)}",
        }
