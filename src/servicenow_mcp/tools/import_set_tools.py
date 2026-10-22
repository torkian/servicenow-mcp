"""
Import set management tools for the ServiceNow MCP server.

Provides tools for listing, retrieving, and cleaning up sys_import_set records.
Import sets are staging collections created when a data source is loaded;
each import set groups the raw rows that will be processed by a transform map.
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

IMPORT_SET_TABLE = "sys_import_set"

IMPORT_SET_FIELDS = [
    "sys_id",
    "label",
    "table_name",
    "state",
    "import_count",
    "error_count",
    "skip_count",
    "complete_source",
    "data_source",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
    "sys_updated_by",
]


def _format_import_set(record: Dict) -> Dict:
    """Normalise a raw sys_import_set record."""
    data_source = record.get("data_source")
    if isinstance(data_source, dict):
        data_source = data_source.get("display_value") or data_source.get("value")
    complete_source = record.get("complete_source")
    if isinstance(complete_source, str):
        complete_source = complete_source.lower() == "true"
    return {
        "sys_id": record.get("sys_id"),
        "label": record.get("label"),
        "table_name": record.get("table_name"),
        "state": record.get("state"),
        "import_count": record.get("import_count"),
        "error_count": record.get("error_count"),
        "skip_count": record.get("skip_count"),
        "complete_source": complete_source,
        "data_source": data_source,
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
        "updated_by": record.get("sys_updated_by"),
    }


def _resolve_import_set_sys_id(
    import_set_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Return the sys_id for an import set given a sys_id or exact label."""
    if len(import_set_id) == 32 and all(c in "0123456789abcdef" for c in import_set_id.lower()):
        return import_set_id
    url = f"{instance_url}/api/now/table/{IMPORT_SET_TABLE}"
    params: Dict[str, Any] = {
        "sysparm_query": f"label={import_set_id}",
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


# ---------------------------------------------------------------------------
# Pydantic parameter models
# ---------------------------------------------------------------------------


class ListImportSetsParams(BaseModel):
    """Parameters for listing sys_import_set records."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    label: Optional[str] = Field(None, description="Filter by label (LIKE match)")
    table_name: Optional[str] = Field(None, description="Filter by staging table name (exact match)")
    state: Optional[str] = Field(None, description="Filter by state (e.g. loaded, complete, error)")
    data_source: Optional[str] = Field(
        None, description="Filter by data source name or sys_id"
    )


class GetImportSetParams(BaseModel):
    """Parameters for retrieving a single sys_import_set record."""

    import_set_id: str = Field(..., description="sys_id (32-char hex) or exact label of the import set")


class CleanupImportSetParams(BaseModel):
    """Parameters for deleting (cleaning up) a sys_import_set record."""

    import_set_id: str = Field(..., description="sys_id (32-char hex) or exact label of the import set to delete")


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def list_import_sets(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List import set records from the sys_import_set table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListImportSetsParams.

    Returns:
        Dictionary with ``success``, ``import_sets``, ``total``, ``has_more``,
        and ``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListImportSetsParams)
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
    if validated.label:
        query_parts.append(f"labelLIKE{validated.label}")
    if validated.table_name:
        query_parts.append(f"table_name={validated.table_name}")
    if validated.state:
        query_parts.append(f"state={validated.state}")
    if validated.data_source:
        query_parts.append(f"data_source.nameLIKE{validated.data_source}")

    sysparm_query = _join_query_parts(query_parts)
    api_params = _build_sysparm_params(
        limit=validated.limit,
        offset=validated.offset,
        fields=IMPORT_SET_FIELDS,
        query=sysparm_query,
    )
    api_params["sysparm_exclude_reference_link"] = "true"

    url = f"{instance_url}/api/now/table/{IMPORT_SET_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=api_params)
        response.raise_for_status()
        raw_records = response.json().get("result", [])
        import_sets = [_format_import_set(r) for r in raw_records]
        return _paginated_list_response(
            import_sets, validated.limit, validated.offset, "import_sets"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing import sets: {e}")
        return {"success": False, "message": f"Error listing import sets: {_format_http_error(e)}"}


def get_import_set(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single sys_import_set record.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetImportSetParams.

    Returns:
        Dictionary with ``success`` and ``import_set`` keys.
    """
    result = _unwrap_and_validate_params(params, GetImportSetParams, required_fields=["import_set_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_import_set_sys_id(validated.import_set_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Import set not found: {validated.import_set_id}"}

    url = f"{instance_url}/api/now/table/{IMPORT_SET_TABLE}/{sys_id}"
    api_params = {
        "sysparm_fields": ",".join(IMPORT_SET_FIELDS),
        "sysparm_display_value": "all",
        "sysparm_exclude_reference_link": "true",
    }
    try:
        response = _make_request("GET", url, headers=headers, params=api_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Import set not found: {validated.import_set_id}"}
        response.raise_for_status()
        record = response.json().get("result")
        if not record:
            return {"success": False, "message": f"Import set not found: {validated.import_set_id}"}
        return {"success": True, "import_set": _format_import_set(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving import set: {e}")
        return {"success": False, "message": f"Error retrieving import set: {_format_http_error(e)}"}


def cleanup_import_set(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete (clean up) a sys_import_set record and its staging data.

    Removing an import set frees storage used by its raw staging rows.
    The operation is permanent and cannot be undone.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CleanupImportSetParams.

    Returns:
        Dictionary with ``success`` and ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, CleanupImportSetParams, required_fields=["import_set_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_import_set_sys_id(validated.import_set_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Import set not found: {validated.import_set_id}"}

    url = f"{instance_url}/api/now/table/{IMPORT_SET_TABLE}/{sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {"success": False, "message": f"Import set not found: {validated.import_set_id}"}
        if response.status_code in (200, 204):
            return {
                "success": True,
                "message": f"Import set '{validated.import_set_id}' deleted successfully",
            }
        response.raise_for_status()
        return {
            "success": True,
            "message": f"Import set '{validated.import_set_id}' deleted successfully",
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting import set: {e}")
        return {"success": False, "message": f"Error deleting import set: {_format_http_error(e)}"}
