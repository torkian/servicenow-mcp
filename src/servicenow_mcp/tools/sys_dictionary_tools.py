"""
System dictionary tools for the ServiceNow MCP server.

Provides tools for inspecting table schema via the sys_dictionary table,
which stores field definitions for every table in the instance.
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

SYS_DICTIONARY_TABLE = "sys_dictionary"

SYS_DICTIONARY_FIELDS = ",".join([
    "sys_id",
    "name",
    "element",
    "internal_type",
    "column_label",
    "comments",
    "mandatory",
    "read_only",
    "default_value",
    "max_length",
    "reference",
    "reference_qual",
    "array",
    "choice",
    "active",
    "sys_created_on",
    "sys_updated_on",
])


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListTableFieldsParams(BaseModel):
    """Parameters for listing field definitions for a table."""

    table_name: str = Field(
        ...,
        description=(
            "The name of the table to inspect (e.g. 'incident', 'change_request'). "
            "Returned fields include all columns defined directly on this table."
        ),
    )
    include_inherited: Optional[bool] = Field(
        False,
        description=(
            "When true, include fields inherited from parent tables "
            "(e.g. task fields on incident). Default false returns only "
            "fields defined directly on this table."
        ),
    )
    field_type: Optional[str] = Field(
        None,
        description=(
            "Filter by internal_type (e.g. 'string', 'integer', 'boolean', "
            "'reference', 'glide_date_time', 'choice'). Substring match."
        ),
    )
    mandatory_only: Optional[bool] = Field(
        False,
        description="When true, return only mandatory fields.",
    )
    limit: Optional[int] = Field(50, description="Maximum number of fields to return (default 50).")
    offset: Optional[int] = Field(0, description="Offset for pagination.")


class GetFieldDefinitionParams(BaseModel):
    """Parameters for retrieving a single field definition."""

    table_name: str = Field(
        ...,
        description="The table that owns the field (e.g. 'incident').",
    )
    field_name: str = Field(
        ...,
        description=(
            "The column/element name of the field to retrieve (e.g. 'priority', 'assignment_group'). "
            "Exact match."
        ),
    )


class UpdateFieldDefinitionParams(BaseModel):
    """Parameters for updating a sys_dictionary field definition record."""

    sys_id: Optional[str] = Field(
        None,
        description=(
            "The sys_id of the sys_dictionary record to update. "
            "Supply this OR both table_name + field_name."
        ),
    )
    table_name: Optional[str] = Field(
        None,
        description="Table name used to look up the record when sys_id is not provided.",
    )
    field_name: Optional[str] = Field(
        None,
        description="Element/column name used to look up the record when sys_id is not provided.",
    )
    column_label: Optional[str] = Field(None, description="New display label for the field.")
    mandatory: Optional[bool] = Field(None, description="Set field as mandatory (true) or optional (false).")
    read_only: Optional[bool] = Field(None, description="Set field as read-only (true) or editable (false).")
    default_value: Optional[str] = Field(None, description="New default value for the field.")
    max_length: Optional[int] = Field(None, description="New maximum length for string fields.")
    comments: Optional[str] = Field(None, description="New comment/tooltip text for the field.")
    active: Optional[bool] = Field(None, description="Set field as active (true) or inactive (false).")
    reference_qual: Optional[str] = Field(None, description="New reference qualifier filter for reference fields.")


class DeleteFieldDefinitionParams(BaseModel):
    """Parameters for deleting a sys_dictionary field definition record."""

    sys_id: Optional[str] = Field(
        None,
        description=(
            "The sys_id of the sys_dictionary record to delete. "
            "Supply this OR both table_name + field_name."
        ),
    )
    table_name: Optional[str] = Field(
        None,
        description="Table name used to look up the record when sys_id is not provided.",
    )
    field_name: Optional[str] = Field(
        None,
        description="Element/column name used to look up the record when sys_id is not provided.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_field(record: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a sys_dictionary record."""

    def _val(field: str) -> Any:
        v = record.get(field, "")
        if isinstance(v, dict):
            return v.get("value") or v.get("display_value") or ""
        return v

    result: Dict[str, Any] = {
        "sys_id": _val("sys_id"),
        "table_name": _val("name"),
        "field_name": _val("element"),
        "field_type": _val("internal_type"),
        "label": _val("column_label"),
        "mandatory": _val("mandatory") in ("true", True, "1", 1),
        "read_only": _val("read_only") in ("true", True, "1", 1),
        "max_length": _val("max_length"),
        "default_value": _val("default_value"),
        "active": _val("active") in ("true", True, "1", 1),
        "comments": _val("comments"),
    }

    ref = _val("reference")
    if ref:
        result["reference_table"] = ref

    ref_qual = _val("reference_qual")
    if ref_qual:
        result["reference_qualifier"] = ref_qual

    choice = _val("choice")
    if choice not in ("", "0", 0, None):
        result["choice"] = choice

    return result


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def list_table_fields(
    params: Dict[str, Any],
    server_config: ServerConfig,
    auth_manager: AuthManager,
) -> Dict[str, Any]:
    """List field definitions for a ServiceNow table from sys_dictionary."""

    result = _unwrap_and_validate_params(params, ListTableFieldsParams)
    if not result["success"]:
        return {"error": result["message"]}
    p: ListTableFieldsParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"error": "No instance URL configured"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"error": "Failed to obtain authentication headers"}

    url = f"{instance_url}/api/now/table/{SYS_DICTIONARY_TABLE}"

    query_parts: List[str] = [f"name={p.table_name}"]

    if p.mandatory_only:
        query_parts.append("mandatory=true")

    if p.field_type:
        query_parts.append(f"internal_typeLIKE{p.field_type}")

    sysparm_query = _join_query_parts(query_parts)

    sysparm_params = _build_sysparm_params(
        limit=p.limit,
        offset=p.offset,
        query=sysparm_query,
        fields=SYS_DICTIONARY_FIELDS,
    )

    try:
        resp = _make_request(
            method="GET",
            url=url,
            headers=headers,
            params=sysparm_params,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": _format_http_error(exc)}
    except requests.RequestException as exc:
        return {"error": str(exc)}

    data = resp.json().get("result", [])
    fields = [_format_field(r) for r in data]

    return _paginated_list_response(
        items=fields,
        result_key="fields",
        limit=p.limit,
        offset=p.offset,
        extra={"table_name": p.table_name},
    )


def get_field_definition(
    params: Dict[str, Any],
    server_config: ServerConfig,
    auth_manager: AuthManager,
) -> Dict[str, Any]:
    """Retrieve the sys_dictionary definition for a specific table field."""

    result = _unwrap_and_validate_params(
        params, GetFieldDefinitionParams, required_fields=["table_name", "field_name"]
    )
    if not result["success"]:
        return {"error": result["message"]}
    p: GetFieldDefinitionParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"error": "No instance URL configured"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"error": "Failed to obtain authentication headers"}

    url = f"{instance_url}/api/now/table/{SYS_DICTIONARY_TABLE}"

    sysparm_params = _build_sysparm_params(
        limit=1,
        offset=0,
        query=f"name={p.table_name}^element={p.field_name}",
        fields=SYS_DICTIONARY_FIELDS,
    )

    try:
        resp = _make_request(
            method="GET",
            url=url,
            headers=headers,
            params=sysparm_params,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": _format_http_error(exc)}
    except requests.RequestException as exc:
        return {"error": str(exc)}

    results = resp.json().get("result", [])
    if not results:
        return {
            "error": f"Field '{p.field_name}' not found on table '{p.table_name}'",
        }

    return {"field": _format_field(results[0])}


def _resolve_field_sys_id(
    sys_id: Optional[str],
    table_name: Optional[str],
    field_name: Optional[str],
    instance_url: str,
    headers: Dict[str, Any],
) -> Dict[str, Any]:
    """Return {"sys_id": ...} or {"error": ...}."""
    if sys_id:
        return {"sys_id": sys_id}
    if not table_name or not field_name:
        return {"error": "Provide sys_id or both table_name and field_name"}

    url = f"{instance_url}/api/now/table/{SYS_DICTIONARY_TABLE}"
    sysparm_params = _build_sysparm_params(
        limit=1,
        offset=0,
        query=f"name={table_name}^element={field_name}",
        fields="sys_id",
    )
    try:
        resp = _make_request(method="GET", url=url, headers=headers, params=sysparm_params)
        resp.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": _format_http_error(exc)}
    except requests.RequestException as exc:
        return {"error": str(exc)}

    results = resp.json().get("result", [])
    if not results:
        return {"error": f"Field '{field_name}' not found on table '{table_name}'"}
    record = results[0]
    resolved = record.get("sys_id", "")
    if isinstance(resolved, dict):
        resolved = resolved.get("value") or resolved.get("display_value") or ""
    return {"sys_id": resolved}


def update_field_definition(
    params: Dict[str, Any],
    server_config: ServerConfig,
    auth_manager: AuthManager,
) -> Dict[str, Any]:
    """Update a sys_dictionary field definition record."""

    result = _unwrap_and_validate_params(params, UpdateFieldDefinitionParams)
    if not result["success"]:
        return {"error": result["message"]}
    p: UpdateFieldDefinitionParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"error": "No instance URL configured"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"error": "Failed to obtain authentication headers"}

    resolved = _resolve_field_sys_id(p.sys_id, p.table_name, p.field_name, instance_url, headers)
    if "error" in resolved:
        return resolved
    record_sys_id = resolved["sys_id"]

    body: Dict[str, Any] = {}
    if p.column_label is not None:
        body["column_label"] = p.column_label
    if p.mandatory is not None:
        body["mandatory"] = "true" if p.mandatory else "false"
    if p.read_only is not None:
        body["read_only"] = "true" if p.read_only else "false"
    if p.default_value is not None:
        body["default_value"] = p.default_value
    if p.max_length is not None:
        body["max_length"] = str(p.max_length)
    if p.comments is not None:
        body["comments"] = p.comments
    if p.active is not None:
        body["active"] = "true" if p.active else "false"
    if p.reference_qual is not None:
        body["reference_qual"] = p.reference_qual

    if not body:
        return {
            "error": (
                "No fields to update — provide at least one of: "
                "column_label, mandatory, read_only, default_value, "
                "max_length, comments, active, reference_qual"
            )
        }

    url = f"{instance_url}/api/now/table/{SYS_DICTIONARY_TABLE}/{record_sys_id}"

    try:
        resp = _make_request(method="PATCH", url=url, headers=headers, json=body)
        resp.raise_for_status()
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"error": f"Field definition '{record_sys_id}' not found"}
        return {"error": _format_http_error(exc)}
    except requests.RequestException as exc:
        return {"error": str(exc)}

    updated = resp.json().get("result", {})
    return {
        "success": True,
        "field": _format_field(updated),
        "message": f"Field definition '{record_sys_id}' updated successfully",
    }


def delete_field_definition(
    params: Dict[str, Any],
    server_config: ServerConfig,
    auth_manager: AuthManager,
) -> Dict[str, Any]:
    """Delete a sys_dictionary field definition record."""

    result = _unwrap_and_validate_params(params, DeleteFieldDefinitionParams)
    if not result["success"]:
        return {"error": result["message"]}
    p: DeleteFieldDefinitionParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"error": "No instance URL configured"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"error": "Failed to obtain authentication headers"}

    resolved = _resolve_field_sys_id(p.sys_id, p.table_name, p.field_name, instance_url, headers)
    if "error" in resolved:
        return resolved
    record_sys_id = resolved["sys_id"]

    url = f"{instance_url}/api/now/table/{SYS_DICTIONARY_TABLE}/{record_sys_id}"

    try:
        resp = _make_request(method="DELETE", url=url, headers=headers)
        if resp.status_code == 404:
            return {"error": f"Field definition '{record_sys_id}' not found"}
        resp.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": _format_http_error(exc)}
    except requests.RequestException as exc:
        return {"error": str(exc)}

    return {
        "success": True,
        "sys_id": record_sys_id,
        "message": f"Field definition '{record_sys_id}' deleted successfully",
    }
