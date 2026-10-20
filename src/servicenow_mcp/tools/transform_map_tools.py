"""
Transform map tools for the ServiceNow MCP server.

Provides tools for managing sys_transform_map records (data import transform
definitions) and for triggering transforms via the Import API.
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

TRANSFORM_MAP_TABLE = "sys_transform_map"

TRANSFORM_MAP_FIELDS = [
    "sys_id",
    "name",
    "source_table",
    "target_table",
    "active",
    "run_business_rules",
    "enforce_mandatory_fields",
    "copy_empty_fields",
    "order",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
    "sys_updated_by",
]


def _format_transform_map(record: Dict) -> Dict:
    """Normalise a raw sys_transform_map record."""
    active = record.get("active")
    if isinstance(active, str):
        active = active.lower() == "true"
    run_business_rules = record.get("run_business_rules")
    if isinstance(run_business_rules, str):
        run_business_rules = run_business_rules.lower() == "true"
    enforce_mandatory = record.get("enforce_mandatory_fields")
    if isinstance(enforce_mandatory, str):
        enforce_mandatory = enforce_mandatory.lower() == "true"
    copy_empty = record.get("copy_empty_fields")
    if isinstance(copy_empty, str):
        copy_empty = copy_empty.lower() == "true"
    source = record.get("source_table")
    if isinstance(source, dict):
        source = source.get("display_value") or source.get("value")
    target = record.get("target_table")
    if isinstance(target, dict):
        target = target.get("display_value") or target.get("value")
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "source_table": source,
        "target_table": target,
        "active": active,
        "run_business_rules": run_business_rules,
        "enforce_mandatory_fields": enforce_mandatory,
        "copy_empty_fields": copy_empty,
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


class ListTransformMapsParams(BaseModel):
    """Parameters for listing sys_transform_map records."""

    limit: Optional[int] = Field(20, description="Maximum number of maps to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    name: Optional[str] = Field(None, description="Filter by name pattern (LIKE match)")
    source_table: Optional[str] = Field(None, description="Filter by source staging table name (LIKE match)")
    target_table: Optional[str] = Field(None, description="Filter by target table name (LIKE match)")
    active: Optional[bool] = Field(None, description="Filter by active state")


class GetTransformMapParams(BaseModel):
    """Parameters for retrieving a single transform map."""

    map_id: str = Field(
        ...,
        description="sys_id (32-char hex) or exact name of the transform map",
    )


class CreateTransformMapParams(BaseModel):
    """Parameters for creating a new sys_transform_map."""

    name: str = Field(..., description="Human-readable name for the transform map")
    source_table: str = Field(
        ...,
        description="Import set staging table name (e.g. 'u_import_users')",
    )
    target_table: str = Field(
        ...,
        description="ServiceNow target table to write records into (e.g. 'sys_user')",
    )
    active: Optional[bool] = Field(True, description="Whether the transform map is active (default true)")
    run_business_rules: Optional[bool] = Field(
        True,
        description="Run business rules on the target table during transform (default true)",
    )
    enforce_mandatory_fields: Optional[bool] = Field(
        True,
        description="Enforce mandatory field constraints on the target table (default true)",
    )
    copy_empty_fields: Optional[bool] = Field(
        False,
        description="Overwrite target fields with empty source values (default false)",
    )
    order: Optional[int] = Field(
        None,
        description="Execution order when multiple maps apply to the same source table",
    )


class UpdateTransformMapParams(BaseModel):
    """Parameters for updating an existing sys_transform_map."""

    map_id: str = Field(..., description="sys_id (32-char hex) or exact name of the transform map to update")
    name: Optional[str] = Field(None, description="New name for the transform map")
    source_table: Optional[str] = Field(None, description="New source staging table")
    target_table: Optional[str] = Field(None, description="New target table")
    active: Optional[bool] = Field(None, description="Enable or disable the map")
    run_business_rules: Optional[bool] = Field(None, description="Toggle business-rule execution")
    enforce_mandatory_fields: Optional[bool] = Field(None, description="Toggle mandatory-field enforcement")
    copy_empty_fields: Optional[bool] = Field(None, description="Toggle copying of empty source fields")
    order: Optional[int] = Field(None, description="New execution order")


class DeleteTransformMapParams(BaseModel):
    """Parameters for deleting a sys_transform_map."""

    map_id: str = Field(..., description="sys_id (32-char hex) or exact name of the transform map to delete")


class RunTransformParams(BaseModel):
    """Parameters for inserting a staging row and triggering its transform."""

    staging_table: str = Field(
        ...,
        description="Name of the import set staging table (e.g. 'u_import_users')",
    )
    data: Dict[str, Any] = Field(
        ...,
        description="Key/value pairs to insert into the staging table; ServiceNow runs the associated transform map automatically",
    )


def list_transform_maps(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List transform map definitions from the sys_transform_map table.

    Supports filtering by name, source table, target table, and active state.
    Results are ordered by name ascending.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListTransformMapsParams.

    Returns:
        Dictionary with ``success``, ``transform_maps`` (list), ``count``,
        and optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListTransformMapsParams)
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
    if validated.source_table:
        query_parts.append(f"source_tableLIKE{validated.source_table}")
    if validated.target_table:
        query_parts.append(f"target_tableLIKE{validated.target_table}")
    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="name",
        fields=",".join(TRANSFORM_MAP_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{TRANSFORM_MAP_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        maps = [_format_transform_map(r) for r in response.json().get("result", [])]
        return _paginated_list_response(maps, validated.limit, validated.offset, "transform_maps")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing transform maps: {e}")
        return {"success": False, "message": f"Error listing transform maps: {_format_http_error(e)}"}


def get_transform_map(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single sys_transform_map record by sys_id or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetTransformMapParams.

    Returns:
        Dictionary with ``success`` and ``transform_map`` keys.
    """
    result = _unwrap_and_validate_params(params, GetTransformMapParams, required_fields=["map_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_transform_map_sys_id(validated.map_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Transform map not found: {validated.map_id}"}

    url = f"{instance_url}/api/now/table/{TRANSFORM_MAP_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(TRANSFORM_MAP_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Transform map not found: {validated.map_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Transform map not found: {validated.map_id}"}
        return {"success": True, "transform_map": _format_transform_map(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving transform map: {e}")
        return {"success": False, "message": f"Error retrieving transform map: {_format_http_error(e)}"}


def create_transform_map(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new transform map in the sys_transform_map table.

    The map defines how rows in a staging (import set) table are translated
    into records in the target table.  Individual field mappings are managed
    separately via sys_transform_entry records.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateTransformMapParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``transform_map`` keys.
    """
    result = _unwrap_and_validate_params(
        params, CreateTransformMapParams, required_fields=["name", "source_table", "target_table"]
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
        "source_table": validated.source_table,
        "target_table": validated.target_table,
        "active": "true" if validated.active else "false",
        "run_business_rules": "true" if validated.run_business_rules else "false",
        "enforce_mandatory_fields": "true" if validated.enforce_mandatory_fields else "false",
        "copy_empty_fields": "true" if validated.copy_empty_fields else "false",
    }
    if validated.order is not None:
        body["order"] = str(validated.order)

    url = f"{instance_url}/api/now/table/{TRANSFORM_MAP_TABLE}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(TRANSFORM_MAP_FIELDS),
    }
    try:
        response = _make_request("POST", url, headers=headers, params=query_params, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Transform map '{validated.name}' created successfully",
            "transform_map": _format_transform_map(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating transform map: {e}")
        return {"success": False, "message": f"Error creating transform map: {_format_http_error(e)}"}


def update_transform_map(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing transform map (PATCH).

    Only the fields supplied are changed; omitted optional fields are left as-is.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdateTransformMapParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``transform_map`` keys.
    """
    result = _unwrap_and_validate_params(params, UpdateTransformMapParams, required_fields=["map_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_transform_map_sys_id(validated.map_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Transform map not found: {validated.map_id}"}

    body: Dict[str, Any] = {}
    if validated.name is not None:
        body["name"] = validated.name
    if validated.source_table is not None:
        body["source_table"] = validated.source_table
    if validated.target_table is not None:
        body["target_table"] = validated.target_table
    if validated.active is not None:
        body["active"] = "true" if validated.active else "false"
    if validated.run_business_rules is not None:
        body["run_business_rules"] = "true" if validated.run_business_rules else "false"
    if validated.enforce_mandatory_fields is not None:
        body["enforce_mandatory_fields"] = "true" if validated.enforce_mandatory_fields else "false"
    if validated.copy_empty_fields is not None:
        body["copy_empty_fields"] = "true" if validated.copy_empty_fields else "false"
    if validated.order is not None:
        body["order"] = str(validated.order)

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    url = f"{instance_url}/api/now/table/{TRANSFORM_MAP_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(TRANSFORM_MAP_FIELDS),
    }
    try:
        response = _make_request("PATCH", url, headers=headers, params=query_params, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"Transform map not found: {validated.map_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Transform map '{validated.map_id}' updated successfully",
            "transform_map": _format_transform_map(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating transform map: {e}")
        return {"success": False, "message": f"Error updating transform map: {_format_http_error(e)}"}


def delete_transform_map(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete a transform map by sys_id or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeleteTransformMapParams.

    Returns:
        Dictionary with ``success`` and ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, DeleteTransformMapParams, required_fields=["map_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_transform_map_sys_id(validated.map_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Transform map not found: {validated.map_id}"}

    url = f"{instance_url}/api/now/table/{TRANSFORM_MAP_TABLE}/{sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {"success": False, "message": f"Transform map not found: {validated.map_id}"}
        if response.status_code in (200, 204):
            return {"success": True, "message": f"Transform map '{validated.map_id}' deleted successfully"}
        response.raise_for_status()
        return {"success": True, "message": f"Transform map '{validated.map_id}' deleted successfully"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting transform map: {e}")
        return {"success": False, "message": f"Error deleting transform map: {_format_http_error(e)}"}


def run_transform(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Insert a row into an import set staging table and trigger its transform map.

    Uses the ServiceNow Import API (POST /api/now/import/{tableName}).  ServiceNow
    automatically runs every active transform map whose source_table matches the
    staging table.  The response includes the import set record sys_id and the
    result of each transform that ran.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching RunTransformParams.

    Returns:
        Dictionary with ``success``, ``message``, ``import_set``, and
        ``transform_results`` (list of per-map outcomes) keys.
    """
    result = _unwrap_and_validate_params(params, RunTransformParams, required_fields=["staging_table", "data"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}/api/now/import/{validated.staging_table}"
    try:
        response = _make_request("POST", url, headers=headers, json=validated.data)
        response.raise_for_status()
        body = response.json()
        result_data = body.get("result", {})
        import_set = None
        transform_results = []
        if isinstance(result_data, list):
            for item in result_data:
                if "import_set" in item or "staging_table" in item:
                    import_set = {
                        "sys_id": item.get("import_set"),
                        "table": item.get("staging_table"),
                        "display_value": item.get("display_value"),
                        "status": item.get("status"),
                    }
                if "transform_map" in item or "error" in item:
                    transform_results.append({
                        "transform_map": item.get("transform_map"),
                        "status": item.get("status"),
                        "error_message": item.get("error_message"),
                        "target_table": item.get("table"),
                        "sys_id": item.get("sys_id"),
                        "display_value": item.get("display_value"),
                    })
        elif isinstance(result_data, dict):
            import_set = {
                "sys_id": result_data.get("import_set"),
                "table": result_data.get("staging_table"),
                "display_value": result_data.get("display_value"),
                "status": result_data.get("status"),
            }
        return {
            "success": True,
            "message": f"Transform triggered on staging table '{validated.staging_table}'",
            "import_set": import_set,
            "transform_results": transform_results,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error running transform: {e}")
        return {"success": False, "message": f"Error running transform: {_format_http_error(e)}"}
