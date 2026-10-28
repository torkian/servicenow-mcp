"""
sys_db_object tools for the ServiceNow MCP server.

Provides tools for querying table metadata via the sys_db_object table,
which stores the definition of every table registered in the instance.
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

SYS_DB_OBJECT_TABLE = "sys_db_object"

SYS_DB_OBJECT_FIELDS = ",".join([
    "sys_id",
    "name",
    "label",
    "super_class",
    "scope",
    "is_extendable",
    "create_access",
    "read_access",
    "write_access",
    "delete_access",
    "number_ref",
    "sys_created_on",
    "sys_updated_on",
])


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListTablesParams(BaseModel):
    """Parameters for listing table definitions from sys_db_object."""

    name_query: Optional[str] = Field(
        None,
        description=(
            "Substring filter on the internal table name "
            "(e.g. 'incident' returns incident, incident_task, etc.)."
        ),
    )
    label_query: Optional[str] = Field(
        None,
        description=(
            "Substring filter on the table display label "
            "(e.g. 'Change' returns Change Request, Change Task, etc.)."
        ),
    )
    scope: Optional[str] = Field(
        None,
        description=(
            "Filter by application scope name or sys_id "
            "(e.g. 'global', 'x_custom_app')."
        ),
    )
    is_extendable: Optional[bool] = Field(
        None,
        description=(
            "When true, return only extendable (parent) tables. "
            "When false, return only non-extendable tables. "
            "When omitted, both types are returned."
        ),
    )
    limit: Optional[int] = Field(50, description="Maximum number of tables to return (default 50).")
    offset: Optional[int] = Field(0, description="Offset for pagination.")


class GetTableDefinitionParams(BaseModel):
    """Parameters for retrieving a single table definition."""

    table_name: str = Field(
        ...,
        description=(
            "The internal name of the table (e.g. 'incident', 'change_request', 'cmdb_ci'). "
            "Accepts either the exact table name or its sys_id."
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_table(record: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a sys_db_object record."""

    def _val(field: str) -> Any:
        v = record.get(field, "")
        if isinstance(v, dict):
            return v.get("display_value") or v.get("value") or ""
        return v

    def _bool(field: str) -> bool:
        return _val(field) in ("true", True, "1", 1)

    result: Dict[str, Any] = {
        "sys_id": _val("sys_id"),
        "name": _val("name"),
        "label": _val("label"),
        "is_extendable": _bool("is_extendable"),
        "create_access": _bool("create_access"),
        "read_access": _bool("read_access"),
        "write_access": _bool("write_access"),
        "delete_access": _bool("delete_access"),
        "sys_created_on": _val("sys_created_on"),
        "sys_updated_on": _val("sys_updated_on"),
    }

    super_class = _val("super_class")
    if super_class:
        result["super_class"] = super_class

    scope = _val("scope")
    if scope:
        result["scope"] = scope

    number_ref = _val("number_ref")
    if number_ref:
        result["number_ref"] = number_ref

    return result


def _resolve_table_sys_id(
    table_name: str,
    instance_url: str,
    headers: Dict[str, str],
) -> Optional[str]:
    """Resolve a table sys_id by exact name if the input looks like a name, not a sys_id."""
    if len(table_name) == 32 and all(c in "0123456789abcdef" for c in table_name):
        return table_name

    params = _build_sysparm_params(
        limit=1,
        offset=0,
        query=f"name={table_name}",
        fields="sys_id,name",
    )
    url = f"{instance_url}/api/now/table/{SYS_DB_OBJECT_TABLE}"
    try:
        resp = _make_request(method="GET", url=url, headers=headers, params=params)
        resp.raise_for_status()
        results = resp.json().get("result", [])
        if results:
            return results[0].get("sys_id", "")
    except (requests.RequestException, Exception):
        pass
    return None


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def list_tables(
    params: Dict[str, Any],
    server_config: ServerConfig,
    auth_manager: AuthManager,
) -> Dict[str, Any]:
    """List table definitions from the ServiceNow sys_db_object table."""

    result = _unwrap_and_validate_params(params, ListTablesParams)
    if not result["success"]:
        return {"error": result["message"]}
    p: ListTablesParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"error": "No instance URL configured"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"error": "Failed to obtain authentication headers"}

    url = f"{instance_url}/api/now/table/{SYS_DB_OBJECT_TABLE}"

    query_parts: List[str] = []

    if p.name_query:
        query_parts.append(f"nameLIKE{p.name_query}")

    if p.label_query:
        query_parts.append(f"labelLIKE{p.label_query}")

    if p.scope:
        query_parts.append(f"scope.name={p.scope}")

    if p.is_extendable is not None:
        query_parts.append(f"is_extendable={'true' if p.is_extendable else 'false'}")

    sysparm_query = _join_query_parts(query_parts) if query_parts else ""

    sysparm_params = _build_sysparm_params(
        limit=p.limit,
        offset=p.offset,
        query=sysparm_query or None,
        fields=SYS_DB_OBJECT_FIELDS,
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
    tables = [_format_table(r) for r in data]

    return _paginated_list_response(
        items=tables,
        result_key="tables",
        limit=p.limit,
        offset=p.offset,
    )


def get_table_definition(
    params: Dict[str, Any],
    server_config: ServerConfig,
    auth_manager: AuthManager,
) -> Dict[str, Any]:
    """Retrieve the sys_db_object definition for a specific ServiceNow table."""

    result = _unwrap_and_validate_params(
        params,
        GetTableDefinitionParams,
        required_fields=["table_name"],
    )
    if not result["success"]:
        return {"error": result["message"]}
    p: GetTableDefinitionParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"error": "No instance URL configured"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"error": "Failed to obtain authentication headers"}

    url = f"{instance_url}/api/now/table/{SYS_DB_OBJECT_TABLE}"

    is_sys_id = len(p.table_name) == 32 and all(c in "0123456789abcdef" for c in p.table_name)

    if is_sys_id:
        sysparm_params = _build_sysparm_params(
            limit=1,
            offset=0,
            query=f"sys_id={p.table_name}",
            fields=SYS_DB_OBJECT_FIELDS,
        )
    else:
        sysparm_params = _build_sysparm_params(
            limit=1,
            offset=0,
            query=f"name={p.table_name}",
            fields=SYS_DB_OBJECT_FIELDS,
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
        return {"error": f"Table '{p.table_name}' not found in sys_db_object"}

    return {"table": _format_table(results[0])}
