"""
CMDB tools for the ServiceNow MCP server.

Provides tools for managing Configuration Items (CIs) in the ServiceNow
CMDB (Configuration Management Database).
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

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
)

logger = logging.getLogger(__name__)

CMDB_CI_TABLE = "cmdb_ci"

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
