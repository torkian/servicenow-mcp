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
