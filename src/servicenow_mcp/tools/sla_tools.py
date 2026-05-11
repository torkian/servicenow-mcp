"""
SLA management tools for the ServiceNow MCP server.

Provides tools for listing and retrieving SLA definition records
from the contract_sla table via the /api/now/table/contract_sla endpoint.
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

SLA_TABLE = "/api/now/table/contract_sla"

SLA_FIELDS = [
    "sys_id",
    "name",
    "description",
    "type",
    "duration",
    "active",
    "table",
    "condition",
    "start_condition",
    "pause_condition",
    "stop_condition",
    "sys_created_on",
    "sys_updated_on",
]


class ListSLAsParams(BaseModel):
    """Parameters for listing SLA definitions."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    active: Optional[bool] = Field(None, description="Filter by active status")
    type: Optional[str] = Field(
        None,
        description="Filter by SLA type (e.g. 'SLA', 'OLA', 'UC')",
    )
    table: Optional[str] = Field(
        None,
        description="Filter by the table the SLA applies to (e.g. 'incident')",
    )
    query: Optional[str] = Field(None, description="Free-text search on name and description")


class GetSLAParams(BaseModel):
    """Parameters for retrieving a single SLA definition."""

    sla_id: str = Field(
        ...,
        description="SLA sys_id (32-char hex) or exact name of the SLA definition",
    )


def _format_sla(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw SLA API record."""
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "description": record.get("description"),
        "type": record.get("type"),
        "duration": record.get("duration"),
        "active": record.get("active"),
        "table": record.get("table"),
        "condition": record.get("condition"),
        "start_condition": record.get("start_condition"),
        "pause_condition": record.get("pause_condition"),
        "stop_condition": record.get("stop_condition"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def list_slas(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List SLA definitions from the ServiceNow contract_sla table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListSLAsParams.

    Returns:
        Dictionary with ``success``, ``slas`` (list), ``count``, and
        pagination keys.
    """
    result = _unwrap_and_validate_params(params, ListSLAsParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    filters = []
    if validated.active is not None:
        filters.append(f"active={'true' if validated.active else 'false'}")
    if validated.type:
        filters.append(f"type={validated.type}")
    if validated.table:
        filters.append(f"table={validated.table}")
    if validated.query:
        filters.append(f"nameLIKE{validated.query}^ORdescriptionLIKE{validated.query}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(filters),
        exclude_reference_link=True,
        fields=",".join(SLA_FIELDS),
    )

    url = f"{instance_url}{SLA_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        slas = [_format_sla(r) for r in response.json().get("result", [])]
        return _paginated_list_response(slas, validated.limit, validated.offset, "slas")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing SLAs: {e}")
        return {"success": False, "message": f"Error listing SLAs: {_format_http_error(e)}"}


def get_sla(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single SLA definition by sys_id or name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetSLAParams.

    Returns:
        Dictionary with ``success`` and ``sla`` keys.
    """
    result = _unwrap_and_validate_params(params, GetSLAParams, required_fields=["sla_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sla_params = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(SLA_FIELDS),
    }

    # 32-char hex -> direct sys_id fetch
    if len(validated.sla_id) == 32 and all(c in "0123456789abcdef" for c in validated.sla_id):
        url = f"{instance_url}{SLA_TABLE}/{validated.sla_id}"
        try:
            response = _make_request("GET", url, headers=headers, params=sla_params)
            if response.status_code == 404:
                return {"success": False, "message": f"SLA not found: {validated.sla_id}"}
            response.raise_for_status()
            record = response.json().get("result", {})
            if not record:
                return {"success": False, "message": f"SLA not found: {validated.sla_id}"}
            return {"success": True, "sla": _format_sla(record)}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving SLA: {e}")
            return {"success": False, "message": f"Error retrieving SLA: {_format_http_error(e)}"}
    else:
        # Treat as name lookup
        url = f"{instance_url}{SLA_TABLE}"
        lookup_params = {
            **sla_params,
            "sysparm_query": f"name={validated.sla_id}",
            "sysparm_limit": 1,
        }
        try:
            response = _make_request("GET", url, headers=headers, params=lookup_params)
            response.raise_for_status()
            records = response.json().get("result", [])
            if not records:
                return {"success": False, "message": f"SLA not found: {validated.sla_id}"}
            return {"success": True, "sla": _format_sla(records[0])}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving SLA: {e}")
            return {"success": False, "message": f"Error retrieving SLA: {_format_http_error(e)}"}
