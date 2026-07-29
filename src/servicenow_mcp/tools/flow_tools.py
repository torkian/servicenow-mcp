"""
Flow Designer flow tools for the ServiceNow MCP server.

Provides tools for listing and retrieving Flow Designer flows
(sys_hub_flow table).  Complements workflow_activity_tools.py which
covers action type definitions (sys_hub_action_type_base).
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

_FLOW_TABLE = "sys_hub_flow"

_FLOW_FIELDS = [
    "sys_id",
    "name",
    "description",
    "active",
    "status",
    "category",
    "sys_scope",
    "trigger_type",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
    "sys_updated_by",
]


def _format_flow(record: Dict) -> Dict:
    """Extract and normalise fields from a sys_hub_flow record."""

    def _ref(value):
        if isinstance(value, dict):
            return value.get("display_value") or value.get("value")
        return value

    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "description": record.get("description"),
        "active": record.get("active"),
        "status": record.get("status"),
        "category": record.get("category"),
        "scope": _ref(record.get("sys_scope")),
        "trigger_type": record.get("trigger_type"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
        "updated_by": record.get("sys_updated_by"),
    }


def _resolve_flow_sys_id(
    instance_url: str,
    headers: Dict,
    flow_id: str,
) -> Optional[str]:
    """Return a sys_hub_flow sys_id from a sys_id passthrough or name lookup."""
    if len(flow_id) == 32 and all(c in "0123456789abcdef" for c in flow_id):
        return flow_id
    url = f"{instance_url}/api/now/table/{_FLOW_TABLE}"
    try:
        resp = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={flow_id}",
                "sysparm_limit": 1,
                "sysparm_fields": "sys_id",
            },
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        if not results:
            return None
        return results[0].get("sys_id")
    except requests.exceptions.RequestException:
        return None


class ListFlowsParams(BaseModel):
    """Parameters for listing Flow Designer flows."""

    name: Optional[str] = Field(
        None,
        description="Filter by flow name (case-insensitive substring match)",
    )
    active: Optional[bool] = Field(
        None,
        description="Filter by active status. True returns only active flows.",
    )
    status: Optional[str] = Field(
        None,
        description=(
            "Filter by publication status.  Common values: 'published', 'draft'."
        ),
    )
    category: Optional[str] = Field(
        None,
        description=(
            "Filter by flow category.  Common values: 'flow', 'subflow', 'action'."
        ),
    )
    scope: Optional[str] = Field(
        None,
        description=(
            "Filter by application scope name (case-insensitive substring match). "
            "E.g. 'Global', 'ServiceNow ITSM'."
        ),
    )
    limit: Optional[int] = Field(20, description="Maximum records to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")


def list_flows(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List Flow Designer flows from the sys_hub_flow table.

    Supports filtering by name, active state, publication status, category,
    and application scope.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListFlowsParams.

    Returns:
        Dictionary with ``success``, ``flows`` (list), ``count``,
        ``has_more``, and ``next_offset`` keys on success.
    """
    result = _unwrap_and_validate_params(params, ListFlowsParams)
    if not result["success"]:
        return result
    validated: ListFlowsParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    query_parts = []
    if validated.name:
        query_parts.append(f"nameLIKE{validated.name}")
    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")
    if validated.status:
        query_parts.append(f"status={validated.status}")
    if validated.category:
        query_parts.append(f"category={validated.category}")
    if validated.scope:
        query_parts.append(f"sys_scope.nameLIKE{validated.scope}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="name",
        fields=",".join(_FLOW_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{_FLOW_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        flows = [_format_flow(r) for r in response.json().get("result", [])]
        return _paginated_list_response(flows, validated.limit, validated.offset, "flows")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing flows: {e}")
        return {
            "success": False,
            "message": f"Error listing flows: {_format_http_error(e)}",
        }


class GetFlowParams(BaseModel):
    """Parameters for retrieving a single Flow Designer flow."""

    flow_id: str = Field(
        ...,
        description=(
            "The sys_id or exact name of the flow (sys_hub_flow) to retrieve."
        ),
    )


def get_flow(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single Flow Designer flow by sys_id or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetFlowParams.

    Returns:
        Dictionary with ``success`` and ``flow`` keys on success.
    """
    result = _unwrap_and_validate_params(
        params, GetFlowParams, required_fields=["flow_id"]
    )
    if not result["success"]:
        return result
    validated: GetFlowParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_flow_sys_id(instance_url, headers, validated.flow_id)
    if not sys_id:
        return {
            "success": False,
            "message": f"Flow not found: {validated.flow_id}",
        }

    url = f"{instance_url}/api/now/table/{_FLOW_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(_FLOW_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {
                "success": False,
                "message": f"Flow not found: {validated.flow_id}",
            }
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {
                "success": False,
                "message": f"Flow not found: {validated.flow_id}",
            }
        return {"success": True, "flow": _format_flow(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving flow: {e}")
        return {
            "success": False,
            "message": f"Error retrieving flow: {_format_http_error(e)}",
        }
