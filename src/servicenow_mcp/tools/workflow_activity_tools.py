"""
Flow Designer workflow activity tools for the ServiceNow MCP server.

Provides a tool for listing action type definitions (sys_hub_action_type_base)
that are used in Flow Designer workflows.  When a flow_id is supplied the
results are scoped to the application scope of that flow; otherwise all
matching action types across the instance are returned.
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

_ACTION_TYPE_TABLE = "sys_hub_action_type_base"
_FLOW_TABLE = "sys_hub_flow"

_ACTION_TYPE_FIELDS = [
    "sys_id",
    "name",
    "label",
    "description",
    "category",
    "active",
    "sys_scope",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]


def _format_action_type(record: Dict) -> Dict:
    """Extract and normalise fields from a sys_hub_action_type_base record."""

    def _ref(value):
        if isinstance(value, dict):
            return value.get("display_value") or value.get("value")
        return value

    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "label": record.get("label"),
        "description": record.get("description"),
        "category": record.get("category"),
        "active": record.get("active"),
        "scope": _ref(record.get("sys_scope")),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def _resolve_flow_scope(instance_url: str, headers: Dict, flow_id: str) -> Optional[str]:
    """Return the sys_scope sys_id for a Flow Designer flow.

    Accepts either a raw sys_id (32-char hex) or any value that can be matched
    against the flow's name field.  Returns None when the flow cannot be found.
    """
    if len(flow_id) == 32 and all(c in "0123456789abcdef" for c in flow_id):
        query = f"sys_id={flow_id}"
    else:
        query = f"nameLIKE{flow_id}"

    url = f"{instance_url}/api/now/table/{_FLOW_TABLE}"
    try:
        resp = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": query,
                "sysparm_limit": 1,
                "sysparm_fields": "sys_id,sys_scope",
                "sysparm_display_value": "false",
                "sysparm_exclude_reference_link": "true",
            },
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        if not results:
            return None
        scope = results[0].get("sys_scope")
        if isinstance(scope, dict):
            return scope.get("value")
        return scope
    except requests.exceptions.RequestException:
        return None


class ListWorkflowActivitiesParams(BaseModel):
    """Parameters for listing Flow Designer action type definitions."""

    flow_id: Optional[str] = Field(
        None,
        description=(
            "Scope results to the application containing this flow. "
            "Accepts a sys_hub_flow sys_id or a name substring."
        ),
    )
    name: Optional[str] = Field(
        None,
        description="Filter by action type name (case-insensitive substring match)",
    )
    category: Optional[str] = Field(
        None,
        description="Filter by action type category (exact match)",
    )
    active: Optional[bool] = Field(
        None,
        description="Filter by active status. True returns only active action types.",
    )
    limit: Optional[int] = Field(20, description="Maximum records to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")


def list_workflow_activities(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List Flow Designer action type definitions from sys_hub_action_type_base.

    When *flow_id* is provided the results are filtered to the application scope
    that owns that flow, effectively showing which action types are available
    within that workflow's scope.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListWorkflowActivitiesParams.

    Returns:
        Dictionary with ``success``, ``activities`` (list), ``count``,
        ``has_more``, and ``next_offset`` keys on success.
    """
    result = _unwrap_and_validate_params(params, ListWorkflowActivitiesParams)
    if not result["success"]:
        return result
    validated: ListWorkflowActivitiesParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    query_parts = []

    if validated.flow_id:
        scope_sys_id = _resolve_flow_scope(instance_url, headers, validated.flow_id)
        if not scope_sys_id:
            return {
                "success": False,
                "message": f"Flow not found: {validated.flow_id}",
            }
        query_parts.append(f"sys_scope={scope_sys_id}")

    if validated.name:
        query_parts.append(f"nameLIKE{validated.name}")
    if validated.category:
        query_parts.append(f"category={validated.category}")
    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="name",
        fields=",".join(_ACTION_TYPE_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{_ACTION_TYPE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        activities = [_format_action_type(r) for r in response.json().get("result", [])]
        return _paginated_list_response(
            activities, validated.limit, validated.offset, "activities"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing workflow activities: {e}")
        return {
            "success": False,
            "message": f"Error listing workflow activities: {_format_http_error(e)}",
        }
