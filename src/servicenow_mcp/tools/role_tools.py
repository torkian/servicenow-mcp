"""
Role management tools for the ServiceNow MCP server.

Provides tools for listing group roles, assigning/removing roles from groups,
and listing roles assigned to individual users via sys_group_has_role and
sys_user_has_role junction tables.
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
    _make_request,
    _paginated_list_response,
    _unwrap_and_validate_params,
)

logger = logging.getLogger(__name__)

GROUP_ROLE_TABLE = "/api/now/table/sys_group_has_role"
USER_ROLE_TABLE = "/api/now/table/sys_user_has_role"
ROLE_TABLE = "/api/now/table/sys_user_role"
USER_GROUP_TABLE = "/api/now/table/sys_user_group"
SYS_USER_TABLE = "/api/now/table/sys_user"

GROUP_ROLE_FIELDS = ["sys_id", "group", "role", "sys_created_on"]
USER_ROLE_FIELDS = ["sys_id", "user", "role", "inherited", "granted_by", "sys_created_on"]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------

class GetGroupRolesParams(BaseModel):
    """Parameters for listing roles assigned to a group."""

    group_id: str = Field(
        ...,
        description="Group sys_id (32-char hex) or exact group name",
    )
    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")


class AssignRoleToGroupParams(BaseModel):
    """Parameters for assigning a role to a group."""

    group_id: str = Field(..., description="Group sys_id (32-char hex) or exact group name")
    role_id: str = Field(..., description="Role sys_id (32-char hex) or exact role name (e.g. 'itil')")


class RemoveRoleFromGroupParams(BaseModel):
    """Parameters for removing a role from a group (by junction record sys_id)."""

    member_sys_id: str = Field(
        ...,
        description="sys_id of the sys_group_has_role junction record to delete",
    )


class ListUserRolesParams(BaseModel):
    """Parameters for listing roles assigned to a user."""

    user_id: str = Field(..., description="User sys_id (32-char hex) or username")
    include_inherited: Optional[bool] = Field(
        None,
        description="If True return only inherited roles; if False return only direct grants; omit to return all",
    )
    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_group_role(record: Dict) -> Dict:
    """Normalise reference fields from a raw sys_group_has_role API record."""
    role = record.get("role")
    role_name = None
    role_sys_id = None
    if isinstance(role, dict):
        role_name = role.get("display_value")
        role_sys_id = role.get("value")
    else:
        role_name = role
        role_sys_id = role

    group = record.get("group")
    group_name = None
    group_sys_id = None
    if isinstance(group, dict):
        group_name = group.get("display_value")
        group_sys_id = group.get("value")
    else:
        group_name = group
        group_sys_id = group

    return {
        "sys_id": record.get("sys_id"),
        "role_name": role_name,
        "role_sys_id": role_sys_id,
        "group_name": group_name,
        "group_sys_id": group_sys_id,
        "created_on": record.get("sys_created_on"),
    }


def _format_user_role(record: Dict) -> Dict:
    """Normalise reference fields from a raw sys_user_has_role API record."""
    role = record.get("role")
    role_name = None
    role_sys_id = None
    if isinstance(role, dict):
        role_name = role.get("display_value")
        role_sys_id = role.get("value")
    else:
        role_name = role
        role_sys_id = role

    user = record.get("user")
    user_display = None
    user_sys_id = None
    if isinstance(user, dict):
        user_display = user.get("display_value")
        user_sys_id = user.get("value")
    else:
        user_display = user
        user_sys_id = user

    granted_by = record.get("granted_by")
    if isinstance(granted_by, dict):
        granted_by = granted_by.get("display_value")

    return {
        "sys_id": record.get("sys_id"),
        "role_name": role_name,
        "role_sys_id": role_sys_id,
        "user": user_display,
        "user_sys_id": user_sys_id,
        "inherited": record.get("inherited"),
        "granted_by": granted_by,
        "created_on": record.get("sys_created_on"),
    }


def _resolve_group_sys_id(group_id: str, instance_url: str, headers: Dict) -> Dict[str, Any]:
    """Return the sys_id for a group sys_id or exact group name."""
    if len(group_id) == 32 and all(c in "0123456789abcdef" for c in group_id):
        return {"success": True, "sys_id": group_id}

    url = f"{instance_url}{USER_GROUP_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={"sysparm_query": f"name={group_id}", "sysparm_limit": 1},
        )
        response.raise_for_status()
        result = response.json().get("result", [])
        if not result:
            return {"success": False, "message": f"Group not found: {group_id}"}
        return {"success": True, "sys_id": result[0]["sys_id"]}
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Error looking up group: {_format_http_error(e)}"}


def _resolve_user_sys_id(user_id: str, instance_url: str, headers: Dict) -> Dict[str, Any]:
    """Return the sys_id for a user sys_id or username."""
    if len(user_id) == 32 and all(c in "0123456789abcdef" for c in user_id):
        return {"success": True, "sys_id": user_id}

    url = f"{instance_url}{SYS_USER_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={"sysparm_query": f"user_name={user_id}", "sysparm_limit": 1},
        )
        response.raise_for_status()
        result = response.json().get("result", [])
        if not result:
            return {"success": False, "message": f"User not found: {user_id}"}
        return {"success": True, "sys_id": result[0]["sys_id"]}
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Error looking up user: {_format_http_error(e)}"}


def _resolve_role_sys_id(role_id: str, instance_url: str, headers: Dict) -> Dict[str, Any]:
    """Return the sys_id for a role sys_id or exact role name."""
    if len(role_id) == 32 and all(c in "0123456789abcdef" for c in role_id):
        return {"success": True, "sys_id": role_id}

    url = f"{instance_url}{ROLE_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={"sysparm_query": f"name={role_id}", "sysparm_limit": 1},
        )
        response.raise_for_status()
        result = response.json().get("result", [])
        if not result:
            return {"success": False, "message": f"Role not found: {role_id}"}
        return {"success": True, "sys_id": result[0]["sys_id"]}
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Error looking up role: {_format_http_error(e)}"}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def get_group_roles(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List roles assigned to a group from sys_group_has_role.

    Accepts a group sys_id or exact group name. Returns paginated role records
    with role name, role sys_id, and junction record sys_id.
    """
    result = _unwrap_and_validate_params(params, GetGroupRolesParams, required_fields=["group_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    group_result = _resolve_group_sys_id(validated.group_id, instance_url, headers)
    if not group_result["success"]:
        return group_result
    group_sys_id = group_result["sys_id"]

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=f"group={group_sys_id}",
        exclude_reference_link=True,
        fields=",".join(GROUP_ROLE_FIELDS),
    )

    url = f"{instance_url}{GROUP_ROLE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        roles = [_format_group_role(r) for r in response.json().get("result", [])]
        return _paginated_list_response(roles, validated.limit, validated.offset, "roles")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing group roles: {e}")
        return {"success": False, "message": f"Error listing group roles: {_format_http_error(e)}"}


def assign_role_to_group(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Assign a role to a group by creating a sys_group_has_role junction record.

    Accepts group and role as either sys_id or name.
    """
    result = _unwrap_and_validate_params(
        params, AssignRoleToGroupParams, required_fields=["group_id", "role_id"]
    )
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    group_result = _resolve_group_sys_id(validated.group_id, instance_url, headers)
    if not group_result["success"]:
        return group_result
    group_sys_id = group_result["sys_id"]

    role_result = _resolve_role_sys_id(validated.role_id, instance_url, headers)
    if not role_result["success"]:
        return role_result
    role_sys_id = role_result["sys_id"]

    url = f"{instance_url}{GROUP_ROLE_TABLE}"
    try:
        response = _make_request(
            "POST",
            url,
            headers=headers,
            json={"group": group_sys_id, "role": role_sys_id},
        )
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": "Role assigned to group successfully",
            "member_sys_id": record.get("sys_id"),
            "group_sys_id": group_sys_id,
            "role_sys_id": role_sys_id,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error assigning role to group: {e}")
        return {"success": False, "message": f"Error assigning role to group: {_format_http_error(e)}"}


def remove_role_from_group(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Remove a role from a group by deleting the sys_group_has_role junction record.

    Requires the sys_id of the junction record itself (not the role sys_id).
    """
    result = _unwrap_and_validate_params(
        params, RemoveRoleFromGroupParams, required_fields=["member_sys_id"]
    )
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}{GROUP_ROLE_TABLE}/{validated.member_sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {
                "success": False,
                "message": f"Group role record not found: {validated.member_sys_id}",
            }
        if response.status_code in (200, 204):
            return {"success": True, "message": "Role removed from group successfully"}
        response.raise_for_status()
        return {"success": True, "message": "Role removed from group successfully"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error removing role from group: {e}")
        return {"success": False, "message": f"Error removing role from group: {_format_http_error(e)}"}


def list_user_roles(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List roles assigned to a user from sys_user_has_role.

    Accepts a user sys_id or username. Optionally filter by inherited flag.
    Returns paginated role records with role name and inheritance details.
    """
    result = _unwrap_and_validate_params(params, ListUserRolesParams, required_fields=["user_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    user_result = _resolve_user_sys_id(validated.user_id, instance_url, headers)
    if not user_result["success"]:
        return user_result
    user_sys_id = user_result["sys_id"]

    query_parts = [f"user={user_sys_id}"]
    if validated.include_inherited is not None:
        flag = "true" if validated.include_inherited else "false"
        query_parts.append(f"inherited={flag}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query="^".join(query_parts),
        exclude_reference_link=True,
        fields=",".join(USER_ROLE_FIELDS),
    )

    url = f"{instance_url}{USER_ROLE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        roles = [_format_user_role(r) for r in response.json().get("result", [])]
        return _paginated_list_response(roles, validated.limit, validated.offset, "roles")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing user roles: {e}")
        return {"success": False, "message": f"Error listing user roles: {_format_http_error(e)}"}
