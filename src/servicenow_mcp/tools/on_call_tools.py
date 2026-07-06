"""
On-call rotation tools for the ServiceNow MCP server.

Provides tools for querying on-call rotation schedules from the
cmn_rota table.
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

ON_CALL_ROTA_TABLE = "cmn_rota"

ON_CALL_ROTA_FIELDS = [
    "sys_id",
    "name",
    "active",
    "description",
    "group",
    "manager",
    "schedule",
    "escalation",
    "type",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]


class ListOnCallRotationsParams(BaseModel):
    """Parameters for listing on-call rotations."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    group: Optional[str] = Field(
        None,
        description="Filter by group name (substring match) or group sys_id",
    )
    active: Optional[bool] = Field(
        None,
        description="Filter by active state. True returns only active rotations, False only inactive.",
    )
    name: Optional[str] = Field(
        None,
        description="Filter by rotation name (case-insensitive substring match)",
    )


def _format_on_call_rotation(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw cmn_rota record."""

    def _ref(value):
        if isinstance(value, dict):
            return value.get("display_value") or value.get("value")
        return value

    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "active": record.get("active"),
        "description": record.get("description"),
        "group": _ref(record.get("group")),
        "manager": _ref(record.get("manager")),
        "schedule": _ref(record.get("schedule")),
        "escalation": _ref(record.get("escalation")),
        "type": record.get("type"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def list_on_call_rotations(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List on-call rotations from the ServiceNow cmn_rota table.

    Supports filtering by group name/sys_id, active state, and rotation name
    substring. Results are ordered by name ascending.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListOnCallRotationsParams.

    Returns:
        Dictionary with ``success``, ``rotations`` (list), ``count``,
        ``has_more``, and ``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListOnCallRotationsParams)
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
    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")
    if validated.group:
        # Accept either a sys_id (32-char hex) or a name substring
        if len(validated.group) == 32 and all(c in "0123456789abcdef" for c in validated.group):
            query_parts.append(f"group={validated.group}")
        else:
            query_parts.append(f"group.nameLIKE{validated.group}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="name",
        fields=",".join(ON_CALL_ROTA_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{ON_CALL_ROTA_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        rotations = [_format_on_call_rotation(r) for r in response.json().get("result", [])]
        return _paginated_list_response(
            rotations, validated.limit, validated.offset, "rotations",
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing on-call rotations: {e}")
        return {
            "success": False,
            "message": f"Error listing on-call rotations: {_format_http_error(e)}",
        }
