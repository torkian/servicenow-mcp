"""
On-call rotation tools for the ServiceNow MCP server.

Provides tools for querying on-call rotation schedules from the
cmn_rota table and rotation members from the cmn_rota_member table.
"""

import logging
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, ConfigDict, Field

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
ON_CALL_ROTA_MEMBER_TABLE = "cmn_rota_member"

ON_CALL_ROTA_MEMBER_FIELDS = [
    "sys_id",
    "rota",
    "member",
    "order",
    "active",
    "skills",
    "override_on_call_rota",
    "catch_all",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]

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


class GetOnCallRotationParams(BaseModel):
    """Parameters for retrieving a single on-call rotation."""

    rotation_id: str = Field(
        ...,
        description="The sys_id or exact name of the on-call rotation to retrieve.",
    )


def _resolve_on_call_rotation_sys_id(
    instance_url: str,
    headers: Dict,
    rotation_id: str,
) -> Optional[str]:
    """Return the sys_id for a rotation name or passthrough if already a sys_id."""
    if len(rotation_id) == 32 and all(c in "0123456789abcdef" for c in rotation_id):
        return rotation_id
    url = f"{instance_url}/api/now/table/{ON_CALL_ROTA_TABLE}"
    try:
        resp = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={rotation_id}",
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


def get_on_call_rotation(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single cmn_rota record by sys_id or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetOnCallRotationParams.

    Returns:
        Dictionary with ``success`` and ``rotation`` keys on success.
    """
    result = _unwrap_and_validate_params(params, GetOnCallRotationParams, required_fields=["rotation_id"])
    if not result["success"]:
        return result
    validated: GetOnCallRotationParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_on_call_rotation_sys_id(instance_url, headers, validated.rotation_id)
    if not sys_id:
        return {"success": False, "message": f"On-call rotation not found: {validated.rotation_id}"}

    url = f"{instance_url}/api/now/table/{ON_CALL_ROTA_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(ON_CALL_ROTA_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"On-call rotation not found: {validated.rotation_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"On-call rotation not found: {validated.rotation_id}"}
        return {"success": True, "rotation": _format_on_call_rotation(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving on-call rotation: {e}")
        return {"success": False, "message": f"Error retrieving on-call rotation: {_format_http_error(e)}"}


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


# ---------------------------------------------------------------------------
# Create / update on-call rotation tools
# ---------------------------------------------------------------------------


class CreateOnCallRotationParams(BaseModel):
    """Parameters for creating a new on-call rotation."""

    name: str = Field(..., description="Name of the on-call rotation")
    group: Optional[str] = Field(
        None,
        description="Group name or sys_id that owns this rotation",
    )
    active: Optional[bool] = Field(True, description="Whether the rotation is active (default True)")
    description: Optional[str] = Field(None, description="Description of the rotation")
    manager: Optional[str] = Field(
        None,
        description="User name or sys_id of the rotation manager",
    )
    schedule: Optional[str] = Field(
        None,
        description="Schedule name or sys_id that defines on-call windows",
    )
    escalation: Optional[str] = Field(
        None,
        description="Escalation policy name or sys_id",
    )
    rotation_type: Optional[str] = Field(
        None,
        alias="type",
        description="Rotation type (e.g. 'primary', 'secondary')",
    )

    model_config = ConfigDict(populate_by_name=True)


def create_on_call_rotation(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new on-call rotation record in the ServiceNow cmn_rota table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateOnCallRotationParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, and ``rotation`` keys on success.
    """
    result = _unwrap_and_validate_params(params, CreateOnCallRotationParams, required_fields=["name"])
    if not result["success"]:
        return result
    validated: CreateOnCallRotationParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    body: Dict[str, Any] = {"name": validated.name}
    if validated.group is not None:
        body["group"] = validated.group
    if validated.active is not None:
        body["active"] = "true" if validated.active else "false"
    if validated.description is not None:
        body["description"] = validated.description
    if validated.manager is not None:
        body["manager"] = validated.manager
    if validated.schedule is not None:
        body["schedule"] = validated.schedule
    if validated.escalation is not None:
        body["escalation"] = validated.escalation
    if validated.rotation_type is not None:
        body["type"] = validated.rotation_type

    url = f"{instance_url}/api/now/table/{ON_CALL_ROTA_TABLE}"
    try:
        response = _make_request("POST", url, headers=headers, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": "On-call rotation created successfully",
            "sys_id": record.get("sys_id"),
            "rotation": _format_on_call_rotation(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating on-call rotation: {e}")
        return {"success": False, "message": f"Error creating on-call rotation: {_format_http_error(e)}"}


# ---------------------------------------------------------------------------
# On-call rotation member tools
# ---------------------------------------------------------------------------


class ListOnCallRotationMembersParams(BaseModel):
    """Parameters for listing members of an on-call rotation."""

    rotation_id: str = Field(
        ...,
        description="The sys_id or exact name of the on-call rotation whose members to list.",
    )
    active: Optional[bool] = Field(
        None,
        description="Filter by active state. True returns only active members, False only inactive.",
    )
    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")


def _format_on_call_rotation_member(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw cmn_rota_member record."""

    def _ref(value):
        if isinstance(value, dict):
            return value.get("display_value") or value.get("value")
        return value

    return {
        "sys_id": record.get("sys_id"),
        "rota": _ref(record.get("rota")),
        "member": _ref(record.get("member")),
        "order": record.get("order"),
        "active": record.get("active"),
        "skills": _ref(record.get("skills")),
        "override_on_call_rota": record.get("override_on_call_rota"),
        "catch_all": record.get("catch_all"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def list_on_call_rotation_members(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List members of an on-call rotation from the cmn_rota_member table.

    Accepts the rotation by sys_id or exact name. Supports optional active
    filter and pagination.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListOnCallRotationMembersParams.

    Returns:
        Dictionary with ``success``, ``members`` (list), ``count``,
        ``has_more``, and ``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(
        params, ListOnCallRotationMembersParams, required_fields=["rotation_id"]
    )
    if not result["success"]:
        return result
    validated: ListOnCallRotationMembersParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    rotation_sys_id = _resolve_on_call_rotation_sys_id(
        instance_url, headers, validated.rotation_id
    )
    if not rotation_sys_id:
        return {
            "success": False,
            "message": f"On-call rotation not found: {validated.rotation_id}",
        }

    query_parts = [f"rota={rotation_sys_id}"]
    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="order",
        fields=",".join(ON_CALL_ROTA_MEMBER_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{ON_CALL_ROTA_MEMBER_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        members = [
            _format_on_call_rotation_member(r)
            for r in response.json().get("result", [])
        ]
        return _paginated_list_response(
            members, validated.limit, validated.offset, "members"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing on-call rotation members: {e}")
        return {
            "success": False,
            "message": f"Error listing on-call rotation members: {_format_http_error(e)}",
        }
