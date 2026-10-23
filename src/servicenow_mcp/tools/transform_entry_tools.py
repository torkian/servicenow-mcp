"""
Transform entry tools for the ServiceNow MCP server.

Provides tools for managing sys_transform_entry records — field-level mappings
within a transform map that describe how staging columns are mapped to target
table fields.
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

TRANSFORM_ENTRY_TABLE = "sys_transform_entry"
TRANSFORM_MAP_TABLE = "sys_transform_map"

TRANSFORM_ENTRY_FIELDS = [
    "sys_id",
    "name",
    "map",
    "source_field",
    "target_field",
    "coalesce",
    "coalesce_empty_fields",
    "active",
    "default_value",
    "type",
    "value",
    "script",
    "order",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
    "sys_updated_by",
]


def _format_transform_entry(record: Dict) -> Dict:
    """Normalise a raw sys_transform_entry record."""
    map_ref = record.get("map")
    if isinstance(map_ref, dict):
        map_ref = map_ref.get("display_value") or map_ref.get("value")

    coalesce = record.get("coalesce")
    if isinstance(coalesce, str):
        coalesce = coalesce.lower() == "true"

    coalesce_empty = record.get("coalesce_empty_fields")
    if isinstance(coalesce_empty, str):
        coalesce_empty = coalesce_empty.lower() == "true"

    active = record.get("active")
    if isinstance(active, str):
        active = active.lower() == "true"

    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "map": map_ref,
        "source_field": record.get("source_field"),
        "target_field": record.get("target_field"),
        "coalesce": coalesce,
        "coalesce_empty_fields": coalesce_empty,
        "active": active,
        "default_value": record.get("default_value"),
        "type": record.get("type"),
        "value": record.get("value"),
        "script": record.get("script"),
        "order": record.get("order"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
        "updated_by": record.get("sys_updated_by"),
    }


def _resolve_transform_map_sys_id(
    map_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Return the sys_id for a transform map given a sys_id or exact name."""
    if len(map_id) == 32 and all(c in "0123456789abcdef" for c in map_id.lower()):
        return map_id
    url = f"{instance_url}/api/now/table/{TRANSFORM_MAP_TABLE}"
    params: Dict[str, Any] = {
        "sysparm_query": f"name={map_id}",
        "sysparm_limit": "1",
        "sysparm_fields": "sys_id",
        "sysparm_exclude_reference_link": "true",
    }
    try:
        resp = _make_request("GET", url, headers=headers, params=params)
        resp.raise_for_status()
        results = resp.json().get("result", [])
        return results[0]["sys_id"] if results else None
    except requests.exceptions.RequestException:
        return None


class ListTransformEntriesParams(BaseModel):
    """Parameters for listing sys_transform_entry records."""

    map_id: Optional[str] = Field(
        None,
        description="sys_id (32-char hex) or exact name of the parent transform map to scope entries",
    )
    source_field: Optional[str] = Field(None, description="Filter by source field name (LIKE match)")
    target_field: Optional[str] = Field(None, description="Filter by target field name (LIKE match)")
    active: Optional[bool] = Field(None, description="Filter by active state")
    coalesce: Optional[bool] = Field(None, description="Filter by coalesce (key field) flag")
    limit: Optional[int] = Field(20, description="Maximum number of entries to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")


class GetTransformEntryParams(BaseModel):
    """Parameters for retrieving a single sys_transform_entry record."""

    entry_id: str = Field(
        ...,
        description="sys_id (32-char hex) of the transform entry",
    )


class CreateTransformEntryParams(BaseModel):
    """Parameters for creating a new sys_transform_entry."""

    map_id: str = Field(
        ...,
        description="sys_id (32-char hex) or exact name of the parent transform map",
    )
    source_field: str = Field(
        ...,
        description="Column name in the import set staging table",
    )
    target_field: str = Field(
        ...,
        description="Column name in the target ServiceNow table",
    )
    active: Optional[bool] = Field(True, description="Whether the entry is active (default true)")
    coalesce: Optional[bool] = Field(
        False,
        description="Use this field as a coalesce key for matching existing records (default false)",
    )
    coalesce_empty_fields: Optional[bool] = Field(
        False,
        description="Coalesce even when the source value is empty (default false)",
    )
    default_value: Optional[str] = Field(None, description="Default value to use when the source field is empty")
    type: Optional[str] = Field(
        None,
        description="Entry type: 'field' (direct map), 'script' (script transform), or 'use_source_script'",
    )
    value: Optional[str] = Field(None, description="Literal value override (used when type is 'value')")
    script: Optional[str] = Field(None, description="JavaScript transform script (used when type is 'script')")
    order: Optional[int] = Field(None, description="Execution order for this entry within the transform map")


class UpdateTransformEntryParams(BaseModel):
    """Parameters for updating an existing sys_transform_entry."""

    entry_id: str = Field(
        ...,
        description="sys_id (32-char hex) of the transform entry to update",
    )
    source_field: Optional[str] = Field(None, description="New source field name")
    target_field: Optional[str] = Field(None, description="New target field name")
    active: Optional[bool] = Field(None, description="Enable or disable this entry")
    coalesce: Optional[bool] = Field(None, description="Toggle coalesce key flag")
    coalesce_empty_fields: Optional[bool] = Field(None, description="Toggle coalesce-on-empty behaviour")
    default_value: Optional[str] = Field(None, description="New default value")
    type: Optional[str] = Field(None, description="New entry type")
    value: Optional[str] = Field(None, description="New literal value override")
    script: Optional[str] = Field(None, description="New transform script")
    order: Optional[int] = Field(None, description="New execution order")


def list_transform_entries(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List transform entry field mappings from sys_transform_entry.

    Optionally scoped to a specific transform map. Supports filtering by
    source_field, target_field, active state, and coalesce flag. Results are
    ordered by order ascending.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListTransformEntriesParams.

    Returns:
        Dictionary with ``success``, ``transform_entries`` (list), ``count``,
        and optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListTransformEntriesParams)
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
    if validated.map_id:
        map_sys_id = _resolve_transform_map_sys_id(validated.map_id, instance_url, headers)
        if not map_sys_id:
            return {"success": False, "message": f"Transform map not found: {validated.map_id}"}
        query_parts.append(f"map={map_sys_id}")
    if validated.source_field:
        query_parts.append(f"source_fieldLIKE{validated.source_field}")
    if validated.target_field:
        query_parts.append(f"target_fieldLIKE{validated.target_field}")
    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")
    if validated.coalesce is not None:
        query_parts.append(f"coalesce={'true' if validated.coalesce else 'false'}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="order",
        fields=",".join(TRANSFORM_ENTRY_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{TRANSFORM_ENTRY_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        entries = [_format_transform_entry(r) for r in response.json().get("result", [])]
        return _paginated_list_response(entries, validated.limit, validated.offset, "transform_entries")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing transform entries: {e}")
        return {"success": False, "message": f"Error listing transform entries: {_format_http_error(e)}"}


def get_transform_entry(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single sys_transform_entry record by sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetTransformEntryParams.

    Returns:
        Dictionary with ``success`` and ``transform_entry`` keys.
    """
    result = _unwrap_and_validate_params(params, GetTransformEntryParams, required_fields=["entry_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}/api/now/table/{TRANSFORM_ENTRY_TABLE}/{validated.entry_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(TRANSFORM_ENTRY_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Transform entry not found: {validated.entry_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Transform entry not found: {validated.entry_id}"}
        return {"success": True, "transform_entry": _format_transform_entry(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving transform entry: {e}")
        return {"success": False, "message": f"Error retrieving transform entry: {_format_http_error(e)}"}


def create_transform_entry(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new field mapping entry in a transform map.

    Required: map_id, source_field, target_field.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateTransformEntryParams.

    Returns:
        Dictionary with ``success`` and ``transform_entry`` keys.
    """
    result = _unwrap_and_validate_params(
        params, CreateTransformEntryParams, required_fields=["map_id", "source_field", "target_field"]
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

    map_sys_id = _resolve_transform_map_sys_id(validated.map_id, instance_url, headers)
    if not map_sys_id:
        return {"success": False, "message": f"Transform map not found: {validated.map_id}"}

    body: Dict[str, Any] = {
        "map": map_sys_id,
        "source_field": validated.source_field,
        "target_field": validated.target_field,
    }
    if validated.active is not None:
        body["active"] = "true" if validated.active else "false"
    if validated.coalesce is not None:
        body["coalesce"] = "true" if validated.coalesce else "false"
    if validated.coalesce_empty_fields is not None:
        body["coalesce_empty_fields"] = "true" if validated.coalesce_empty_fields else "false"
    if validated.default_value is not None:
        body["default_value"] = validated.default_value
    if validated.type is not None:
        body["type"] = validated.type
    if validated.value is not None:
        body["value"] = validated.value
    if validated.script is not None:
        body["script"] = validated.script
    if validated.order is not None:
        body["order"] = str(validated.order)

    url = f"{instance_url}/api/now/table/{TRANSFORM_ENTRY_TABLE}"
    try:
        response = _make_request("POST", url, headers=headers, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {"success": True, "transform_entry": _format_transform_entry(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating transform entry: {e}")
        return {"success": False, "message": f"Error creating transform entry: {_format_http_error(e)}"}


def update_transform_entry(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing sys_transform_entry by sys_id (PATCH).

    At least one field besides entry_id must be provided.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdateTransformEntryParams.

    Returns:
        Dictionary with ``success`` and ``transform_entry`` keys.
    """
    result = _unwrap_and_validate_params(params, UpdateTransformEntryParams, required_fields=["entry_id"])
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
    if validated.source_field is not None:
        body["source_field"] = validated.source_field
    if validated.target_field is not None:
        body["target_field"] = validated.target_field
    if validated.active is not None:
        body["active"] = "true" if validated.active else "false"
    if validated.coalesce is not None:
        body["coalesce"] = "true" if validated.coalesce else "false"
    if validated.coalesce_empty_fields is not None:
        body["coalesce_empty_fields"] = "true" if validated.coalesce_empty_fields else "false"
    if validated.default_value is not None:
        body["default_value"] = validated.default_value
    if validated.type is not None:
        body["type"] = validated.type
    if validated.value is not None:
        body["value"] = validated.value
    if validated.script is not None:
        body["script"] = validated.script
    if validated.order is not None:
        body["order"] = str(validated.order)

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    url = f"{instance_url}/api/now/table/{TRANSFORM_ENTRY_TABLE}/{validated.entry_id}"
    try:
        response = _make_request("PATCH", url, headers=headers, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"Transform entry not found: {validated.entry_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {"success": True, "transform_entry": _format_transform_entry(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating transform entry: {e}")
        return {"success": False, "message": f"Error updating transform entry: {_format_http_error(e)}"}
