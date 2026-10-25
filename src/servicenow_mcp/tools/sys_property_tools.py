"""
System property tools for the ServiceNow MCP server.

Provides tools for reading, writing, and deleting system properties stored in
the sys_properties table.  Properties are global key-value settings accessible
via gs.getProperty() in server-side scripts.
"""

import logging
from typing import Any, Dict, Optional

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

SYS_PROPERTY_TABLE = "sys_properties"

SYS_PROPERTY_FIELDS = [
    "sys_id",
    "name",
    "value",
    "type",
    "description",
    "suffix",
    "category",
    "choices",
    "read_roles",
    "write_roles",
    "private",
    "ignore_cache",
    "encrypt",
    "sys_created_on",
    "sys_updated_on",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListPropertiesParams(BaseModel):
    """Parameters for listing system properties."""

    name: Optional[str] = Field(
        None,
        description="Filter by property name (substring match, e.g. 'glide.email').",
    )
    category: Optional[str] = Field(
        None,
        description="Filter by property category (exact match).",
    )
    type: Optional[str] = Field(
        None,
        description="Filter by property type (e.g. 'string', 'true_false', 'integer').",
    )
    limit: Optional[int] = Field(20, description="Maximum number of properties to return (default 20).")
    offset: Optional[int] = Field(0, description="Offset for pagination.")


class GetPropertyParams(BaseModel):
    """Parameters for retrieving a single system property."""

    property_id: str = Field(
        ...,
        description=(
            "Name or sys_id of the property to retrieve. "
            "A 32-character hex string is treated as a sys_id; "
            "otherwise an exact name lookup is performed."
        ),
    )


class SetPropertyParams(BaseModel):
    """Parameters for creating or updating a system property."""

    name: str = Field(
        ...,
        description="The property key name (e.g. 'com.myapp.feature_enabled').",
    )
    value: str = Field(
        ...,
        description="The value to store for this property.",
    )
    description: Optional[str] = Field(
        None,
        description="Human-readable description of the property.",
    )
    type: Optional[str] = Field(
        None,
        description="Property type (e.g. 'string', 'true_false', 'integer', 'choice'). Defaults to 'string'.",
    )
    category: Optional[str] = Field(
        None,
        description="Category used to group related properties.",
    )
    private: Optional[bool] = Field(
        None,
        description="When true the property value is hidden from non-privileged users.",
    )
    encrypt: Optional[bool] = Field(
        None,
        description="When true the value is stored encrypted at rest.",
    )
    read_roles: Optional[str] = Field(
        None,
        description="Comma-separated list of roles permitted to read this property.",
    )
    write_roles: Optional[str] = Field(
        None,
        description="Comma-separated list of roles permitted to write this property.",
    )


class DeletePropertyParams(BaseModel):
    """Parameters for deleting a system property."""

    property_id: str = Field(
        ...,
        description=(
            "Name or sys_id of the property to delete. "
            "A 32-character hex string is treated as a sys_id; "
            "otherwise an exact name lookup is performed."
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_property_sys_id(
    property_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a property name to its sys_id.

    A 32-character hex string is returned unchanged.  Otherwise an exact
    name lookup against sys_properties is performed.

    Returns ``None`` when the property cannot be found.
    """
    if len(property_id) == 32 and all(c in "0123456789abcdefABCDEF" for c in property_id):
        return property_id
    url = f"{instance_url}/api/now/table/{SYS_PROPERTY_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={property_id}",
                "sysparm_fields": "sys_id",
                "sysparm_limit": "1",
                "sysparm_exclude_reference_link": "true",
            },
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        if results:
            return results[0].get("sys_id")
    except requests.exceptions.RequestException:
        pass
    return None


def _format_property(record: Dict) -> Dict:
    """Normalise a raw sys_properties record."""
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "value": record.get("value"),
        "type": record.get("type"),
        "description": record.get("description"),
        "suffix": record.get("suffix"),
        "category": record.get("category"),
        "choices": record.get("choices"),
        "read_roles": record.get("read_roles"),
        "write_roles": record.get("write_roles"),
        "private": record.get("private"),
        "ignore_cache": record.get("ignore_cache"),
        "encrypt": record.get("encrypt"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def list_properties(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List system properties from the sys_properties table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListPropertiesParams.

    Returns:
        Dictionary with ``success``, ``properties`` (list), ``count``, and
        optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListPropertiesParams)
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

    if validated.name:
        query_parts.append(f"nameLIKE{validated.name}")
    if validated.category:
        query_parts.append(f"category={validated.category}")
    if validated.type:
        query_parts.append(f"type={validated.type}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="name",
        fields=",".join(SYS_PROPERTY_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{SYS_PROPERTY_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        props = [_format_property(r) for r in response.json().get("result", [])]
        return _paginated_list_response(props, validated.limit, validated.offset, "properties")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing properties: {e}")
        return {"success": False, "message": f"Error listing properties: {_format_http_error(e)}"}


def get_property(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single system property by name or sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetPropertyParams.

    Returns:
        Dictionary with ``success`` and ``property`` keys on success.
    """
    result = _unwrap_and_validate_params(
        params, GetPropertyParams, required_fields=["property_id"]
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

    sys_id = _resolve_property_sys_id(validated.property_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Property not found: {validated.property_id}"}

    url = f"{instance_url}/api/now/table/{SYS_PROPERTY_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_fields": ",".join(SYS_PROPERTY_FIELDS),
        "sysparm_exclude_reference_link": "true",
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Property not found: {validated.property_id}"}
        response.raise_for_status()
        record = response.json().get("result")
        if not record:
            return {"success": False, "message": f"Property not found: {validated.property_id}"}
        return {"success": True, "property": _format_property(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving property: {e}")
        return {"success": False, "message": f"Error retrieving property: {_format_http_error(e)}"}


def set_property(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create or update a system property.

    If a property with the given ``name`` already exists it is updated (PATCH);
    otherwise a new record is created (POST).

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching SetPropertyParams.

    Returns:
        Dictionary with ``success``, ``property``, and ``action`` ('created'
        or 'updated') keys on success.
    """
    result = _unwrap_and_validate_params(
        params, SetPropertyParams, required_fields=["name", "value"]
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
        "name": validated.name,
        "value": validated.value,
    }
    if validated.description is not None:
        body["description"] = validated.description
    if validated.type is not None:
        body["type"] = validated.type
    if validated.category is not None:
        body["category"] = validated.category
    if validated.private is not None:
        body["private"] = "true" if validated.private else "false"
    if validated.encrypt is not None:
        body["encrypt"] = "true" if validated.encrypt else "false"
    if validated.read_roles is not None:
        body["read_roles"] = validated.read_roles
    if validated.write_roles is not None:
        body["write_roles"] = validated.write_roles

    existing_sys_id = _resolve_property_sys_id(validated.name, instance_url, headers)

    try:
        if existing_sys_id:
            url = f"{instance_url}/api/now/table/{SYS_PROPERTY_TABLE}/{existing_sys_id}"
            response = _make_request("PATCH", url, headers=headers, json=body)
            if response.status_code == 404:
                return {"success": False, "message": f"Property not found during update: {validated.name}"}
            response.raise_for_status()
            record = response.json().get("result", {})
            return {
                "success": True,
                "action": "updated",
                "property": _format_property(record),
            }
        else:
            url = f"{instance_url}/api/now/table/{SYS_PROPERTY_TABLE}"
            response = _make_request("POST", url, headers=headers, json=body)
            response.raise_for_status()
            record = response.json().get("result", {})
            return {
                "success": True,
                "action": "created",
                "property": _format_property(record),
            }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error setting property: {e}")
        return {"success": False, "message": f"Error setting property: {_format_http_error(e)}"}


def delete_property(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete a system property by name or sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeletePropertyParams.

    Returns:
        Dictionary with ``success`` and ``message`` keys.
    """
    result = _unwrap_and_validate_params(
        params, DeletePropertyParams, required_fields=["property_id"]
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

    sys_id = _resolve_property_sys_id(validated.property_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Property not found: {validated.property_id}"}

    url = f"{instance_url}/api/now/table/{SYS_PROPERTY_TABLE}/{sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {"success": False, "message": f"Property not found: {validated.property_id}"}
        if response.status_code not in (200, 204):
            response.raise_for_status()
        return {
            "success": True,
            "message": f"Property '{validated.property_id}' deleted successfully",
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting property: {e}")
        return {"success": False, "message": f"Error deleting property: {_format_http_error(e)}"}
