"""
Generic table CRUD tools for the ServiceNow MCP server.

Provides five tools that operate on **any** ServiceNow table:
  - list_records   — paginated query with optional sysparm_query / field filters
  - get_record     — fetch a single record by sys_id
  - create_record  — insert a new record with arbitrary field values
  - update_record  — patch an existing record by sys_id
  - delete_record  — remove a record by sys_id

These are useful for custom tables (e.g. ``u_my_custom_table``) that do not
have their own dedicated tool module, or for quick ad-hoc operations on any
standard table not covered elsewhere.
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
    _make_request,
    _paginated_list_response,
    _unwrap_and_validate_params,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListRecordsParams(BaseModel):
    """Parameters for listing records from any ServiceNow table."""

    table: str = Field(..., description="ServiceNow table name (e.g. 'incident', 'u_my_custom_table')")
    query: Optional[str] = Field(
        None,
        description=(
            "Encoded sysparm_query string (e.g. 'active=true^priority=1'). "
            "Use ServiceNow query notation — fields are ANDed with '^'."
        ),
    )
    fields: Optional[str] = Field(
        None,
        description=(
            "Comma-separated list of field names to return. "
            "If omitted, ServiceNow returns its default field set."
        ),
    )
    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20, max 1000)")
    offset: Optional[int] = Field(0, description="Zero-based offset for pagination")
    order_by: Optional[str] = Field(
        None,
        description=(
            "Sort field and direction. Prefix with 'DESC' for descending, e.g. 'DESCsys_created_on'. "
            "Ascending: 'sys_created_on'. Defaults to ServiceNow table default sort."
        ),
    )
    display_value: Optional[bool] = Field(
        True,
        description="Return display values (human-readable) for reference fields. Defaults to True.",
    )


class GetRecordParams(BaseModel):
    """Parameters for retrieving a single record by sys_id from any table."""

    table: str = Field(..., description="ServiceNow table name (e.g. 'incident', 'u_my_custom_table')")
    sys_id: str = Field(..., description="sys_id of the record to retrieve")
    fields: Optional[str] = Field(
        None,
        description="Comma-separated list of field names to return. If omitted, returns default field set.",
    )
    display_value: Optional[bool] = Field(True, description="Return display values for reference fields")


class CreateRecordParams(BaseModel):
    """Parameters for creating a new record in any ServiceNow table."""

    table: str = Field(..., description="ServiceNow table name (e.g. 'incident', 'u_my_custom_table')")
    fields: Dict[str, Any] = Field(
        ...,
        description=(
            "Dictionary of field names → values to set on the new record. "
            "Example: {\"short_description\": \"Test\", \"priority\": \"2\"}"
        ),
    )
    return_fields: Optional[str] = Field(
        None,
        description=(
            "Comma-separated list of fields to include in the returned record. "
            "If omitted, ServiceNow returns its default field set."
        ),
    )


class UpdateRecordParams(BaseModel):
    """Parameters for updating an existing record in any ServiceNow table."""

    table: str = Field(..., description="ServiceNow table name (e.g. 'incident', 'u_my_custom_table')")
    sys_id: str = Field(..., description="sys_id of the record to update")
    fields: Dict[str, Any] = Field(
        ...,
        description=(
            "Dictionary of field names → new values. Only supplied fields are changed. "
            "Example: {\"state\": \"2\", \"assigned_to\": \"<user_sys_id>\"}"
        ),
    )
    return_fields: Optional[str] = Field(
        None,
        description="Comma-separated list of fields to include in the returned record.",
    )


class DeleteRecordParams(BaseModel):
    """Parameters for deleting a record from any ServiceNow table."""

    table: str = Field(..., description="ServiceNow table name (e.g. 'incident', 'u_my_custom_table')")
    sys_id: str = Field(..., description="sys_id of the record to delete")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def list_records(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List records from any ServiceNow table.

    Supports arbitrary sysparm_query strings, field selection, pagination,
    and sort ordering. Useful for custom tables or any standard table not
    covered by a dedicated tool.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListRecordsParams.

    Returns:
        Dictionary with ``success``, ``records`` (list), ``count``, and
        optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListRecordsParams, required_fields=["table"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    display_val = "true" if validated.display_value else "false"
    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=validated.query,
        exclude_reference_link=True,
        order_by=validated.order_by,
        fields=validated.fields,
    )
    query_params["sysparm_display_value"] = display_val

    url = f"{instance_url}/api/now/table/{validated.table}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        records: List[Dict] = response.json().get("result", [])
        return _paginated_list_response(records, validated.limit, validated.offset, "records")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing records from {validated.table}: {e}")
        return {
            "success": False,
            "message": f"Error listing records from '{validated.table}': {_format_http_error(e)}",
        }


def get_record(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single record by sys_id from any ServiceNow table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetRecordParams.

    Returns:
        Dictionary with ``success`` and ``record`` keys, or an error message.
    """
    result = _unwrap_and_validate_params(params, GetRecordParams, required_fields=["table", "sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    display_val = "true" if validated.display_value else "false"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": display_val,
        "sysparm_exclude_reference_link": "true",
    }
    if validated.fields:
        query_params["sysparm_fields"] = validated.fields

    url = f"{instance_url}/api/now/table/{validated.table}/{validated.sys_id}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {
                "success": False,
                "message": f"Record not found in '{validated.table}': {validated.sys_id}",
            }
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {
                "success": False,
                "message": f"Record not found in '{validated.table}': {validated.sys_id}",
            }
        return {"success": True, "record": record}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving record from {validated.table}: {e}")
        return {
            "success": False,
            "message": f"Error retrieving record from '{validated.table}': {_format_http_error(e)}",
        }


def create_record(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new record in any ServiceNow table.

    Accepts an arbitrary dictionary of field → value pairs. Field names must
    match the internal ServiceNow field names on the target table (e.g.
    ``short_description``, not ``Short description``).

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateRecordParams.

    Returns:
        Dictionary with ``success``, ``record`` (created record), and
        ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, CreateRecordParams, required_fields=["table", "fields"])
    if not result["success"]:
        return result
    validated = result["params"]

    if not validated.fields:
        return {"success": False, "message": "No fields provided — cannot create an empty record"}

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }
    if validated.return_fields:
        query_params["sysparm_fields"] = validated.return_fields

    url = f"{instance_url}/api/now/table/{validated.table}"
    try:
        response = _make_request("POST", url, headers=headers, params=query_params, json=validated.fields)
        response.raise_for_status()
        record = response.json().get("result", {})
        sys_id = record.get("sys_id", "")
        return {
            "success": True,
            "message": f"Record created in '{validated.table}' with sys_id '{sys_id}'",
            "record": record,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating record in {validated.table}: {e}")
        return {
            "success": False,
            "message": f"Error creating record in '{validated.table}': {_format_http_error(e)}",
        }


def update_record(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing record in any ServiceNow table.

    Only the fields supplied in the ``fields`` dictionary are changed; all
    other fields are left untouched (PATCH semantics).

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdateRecordParams.

    Returns:
        Dictionary with ``success``, ``record`` (updated record), and
        ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, UpdateRecordParams, required_fields=["table", "sys_id", "fields"])
    if not result["success"]:
        return result
    validated = result["params"]

    if not validated.fields:
        return {"success": False, "message": "No fields provided — nothing to update"}

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }
    if validated.return_fields:
        query_params["sysparm_fields"] = validated.return_fields

    url = f"{instance_url}/api/now/table/{validated.table}/{validated.sys_id}"
    try:
        response = _make_request("PATCH", url, headers=headers, params=query_params, json=validated.fields)
        if response.status_code == 404:
            return {
                "success": False,
                "message": f"Record not found in '{validated.table}': {validated.sys_id}",
            }
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Record '{validated.sys_id}' in '{validated.table}' updated successfully",
            "record": record,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating record in {validated.table}: {e}")
        return {
            "success": False,
            "message": f"Error updating record in '{validated.table}': {_format_http_error(e)}",
        }


def delete_record(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete a record from any ServiceNow table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeleteRecordParams.

    Returns:
        Dictionary with ``success`` and ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, DeleteRecordParams, required_fields=["table", "sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}/api/now/table/{validated.table}/{validated.sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {
                "success": False,
                "message": f"Record not found in '{validated.table}': {validated.sys_id}",
            }
        if response.status_code in (200, 204):
            return {
                "success": True,
                "message": f"Record '{validated.sys_id}' deleted from '{validated.table}'",
            }
        response.raise_for_status()
        return {
            "success": True,
            "message": f"Record '{validated.sys_id}' deleted from '{validated.table}'",
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting record from {validated.table}: {e}")
        return {
            "success": False,
            "message": f"Error deleting record from '{validated.table}': {_format_http_error(e)}",
        }
