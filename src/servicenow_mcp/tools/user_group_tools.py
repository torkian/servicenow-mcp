"""
User group management tools for the ServiceNow MCP server.

Provides tools for listing, retrieving, and managing sys_user_group records
and sys_user_grmember junction records via the ServiceNow Table API.
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

USER_GROUP_TABLE = "/api/now/table/sys_user_group"
GROUP_MEMBER_TABLE = "/api/now/table/sys_user_grmember"

USER_GROUP_FIELDS = [
    "sys_id",
    "name",
    "description",
    "manager",
    "parent",
    "type",
    "email",
    "active",
    "sys_created_on",
    "sys_updated_on",
]

GROUP_MEMBER_FIELDS = [
    "sys_id",
    "group",
    "user",
    "sys_created_on",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------

class ListUserGroupsParams(BaseModel):
    """Parameters for listing user groups."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    name: Optional[str] = Field(None, description="Filter by group name (partial/LIKE match)")
    manager: Optional[str] = Field(None, description="Filter by manager name or sys_id")
    active: Optional[bool] = Field(None, description="If provided, filter by active status")
    query: Optional[str] = Field(None, description="Free-text search on name and description")


class GetUserGroupParams(BaseModel):
    """Parameters for retrieving a single user group."""

    group_id: str = Field(
        ...,
        description="Group sys_id (32-char hex) or exact group name",
    )


class AddUserToGroupParams(BaseModel):
    """Parameters for adding a user to a group."""

    group_id: str = Field(..., description="Group sys_id (32-char hex) or exact group name")
    user_id: str = Field(..., description="User sys_id (32-char hex) or username")


class RemoveUserFromGroupParams(BaseModel):
    """Parameters for removing a user from a group (by grmember sys_id)."""

    member_sys_id: str = Field(
        ...,
        description="sys_id of the sys_user_grmember junction record to delete",
    )


class ListGroupMembersParams(BaseModel):
    """Parameters for listing members of a group."""

    group_id: str = Field(..., description="Group sys_id (32-char hex) or exact group name")
    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_user_group(record: Dict) -> Dict:
    """Normalise reference fields from a raw sys_user_group API record."""
    manager = record.get("manager")
    if isinstance(manager, dict):
        manager = manager.get("display_value")

    parent = record.get("parent")
    if isinstance(parent, dict):
        parent = parent.get("display_value")

    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "description": record.get("description"),
        "manager": manager,
        "parent": parent,
        "type": record.get("type"),
        "email": record.get("email"),
        "active": record.get("active"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _format_group_member(record: Dict) -> Dict:
    """Normalise reference fields from a raw sys_user_grmember API record."""
    group = record.get("group")
    if isinstance(group, dict):
        group = group.get("display_value")

    user = record.get("user")
    user_display = None
    if isinstance(user, dict):
        user_display = user.get("display_value")
        user_sys_id = user.get("value")
    else:
        user_display = user
        user_sys_id = user

    return {
        "sys_id": record.get("sys_id"),
        "group": group,
        "user": user_display,
        "user_sys_id": user_sys_id,
        "created_on": record.get("sys_created_on"),
    }


def _resolve_group_sys_id(
    group_id: str,
    instance_url: str,
    headers: Dict,
) -> Dict[str, Any]:
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


def _resolve_user_sys_id(
    user_id: str,
    instance_url: str,
    headers: Dict,
) -> Dict[str, Any]:
    """Return the sys_id for a user sys_id or username."""
    if len(user_id) == 32 and all(c in "0123456789abcdef" for c in user_id):
        return {"success": True, "sys_id": user_id}

    url = f"{instance_url}/api/now/table/sys_user"
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


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def list_user_groups(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List user groups from the sys_user_group table.

    Supports filtering by name, manager, active status, or free-text query.
    Returns paginated results with has_more / next_offset.
    """
    result = _unwrap_and_validate_params(params, ListUserGroupsParams)
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
    if validated.name:
        filters.append(f"nameLIKE{validated.name}")
    if validated.manager:
        filters.append(f"manager.name={validated.manager}^ORmanager={validated.manager}")
    if validated.active is not None:
        filters.append(f"active={'true' if validated.active else 'false'}")
    if validated.query:
        filters.append(f"nameLIKE{validated.query}^ORdescriptionLIKE{validated.query}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(filters),
        exclude_reference_link=True,
        fields=",".join(USER_GROUP_FIELDS),
    )

    url = f"{instance_url}{USER_GROUP_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        groups = [_format_user_group(r) for r in response.json().get("result", [])]
        return _paginated_list_response(groups, validated.limit, validated.offset, "groups")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing user groups: {e}")
        return {"success": False, "message": f"Error listing user groups: {_format_http_error(e)}"}


def get_user_group(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single user group by sys_id or exact name.

    Returns 404-style error when the group cannot be found.
    """
    result = _unwrap_and_validate_params(params, GetUserGroupParams, required_fields=["group_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    base_params = {"sysparm_display_value": "true", "sysparm_exclude_reference_link": "true"}

    if len(validated.group_id) == 32 and all(c in "0123456789abcdef" for c in validated.group_id):
        url = f"{instance_url}{USER_GROUP_TABLE}/{validated.group_id}"
        try:
            response = _make_request("GET", url, headers=headers, params=base_params)
            if response.status_code == 404:
                return {"success": False, "message": f"Group not found: {validated.group_id}"}
            response.raise_for_status()
            record = response.json().get("result", {})
            if not record:
                return {"success": False, "message": f"Group not found: {validated.group_id}"}
            return {"success": True, "group": _format_user_group(record)}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving user group: {e}")
            return {"success": False, "message": f"Error retrieving user group: {_format_http_error(e)}"}
    else:
        url = f"{instance_url}{USER_GROUP_TABLE}"
        try:
            response = _make_request(
                "GET",
                url,
                headers=headers,
                params={**base_params, "sysparm_query": f"name={validated.group_id}", "sysparm_limit": 1},
            )
            response.raise_for_status()
            records = response.json().get("result", [])
            if not records:
                return {"success": False, "message": f"Group not found: {validated.group_id}"}
            return {"success": True, "group": _format_user_group(records[0])}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving user group: {e}")
            return {"success": False, "message": f"Error retrieving user group: {_format_http_error(e)}"}


def add_user_to_group(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Add a user to a group by creating a sys_user_grmember junction record.

    Accepts group and user as either sys_id or name/username.
    """
    result = _unwrap_and_validate_params(
        params, AddUserToGroupParams, required_fields=["group_id", "user_id"]
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

    user_result = _resolve_user_sys_id(validated.user_id, instance_url, headers)
    if not user_result["success"]:
        return user_result
    user_sys_id = user_result["sys_id"]

    url = f"{instance_url}{GROUP_MEMBER_TABLE}"
    try:
        response = _make_request(
            "POST",
            url,
            headers=headers,
            json={"group": group_sys_id, "user": user_sys_id},
        )
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": "User added to group successfully",
            "member_sys_id": record.get("sys_id"),
            "group_sys_id": group_sys_id,
            "user_sys_id": user_sys_id,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error adding user to group: {e}")
        return {"success": False, "message": f"Error adding user to group: {_format_http_error(e)}"}


def remove_user_from_group(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Remove a user from a group by deleting the sys_user_grmember junction record.

    Requires the sys_id of the grmember record itself (not the user sys_id).
    """
    result = _unwrap_and_validate_params(
        params, RemoveUserFromGroupParams, required_fields=["member_sys_id"]
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

    url = f"{instance_url}{GROUP_MEMBER_TABLE}/{validated.member_sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {"success": False, "message": f"Group member record not found: {validated.member_sys_id}"}
        if response.status_code in (200, 204):
            return {"success": True, "message": "User removed from group successfully"}
        response.raise_for_status()
        return {"success": True, "message": "User removed from group successfully"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error removing user from group: {e}")
        return {"success": False, "message": f"Error removing user from group: {_format_http_error(e)}"}


def list_group_members(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List members of a group from the sys_user_grmember table.

    Accepts a group sys_id or exact group name and returns paginated grmember records.
    """
    result = _unwrap_and_validate_params(params, ListGroupMembersParams, required_fields=["group_id"])
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
        fields=",".join(GROUP_MEMBER_FIELDS),
    )

    url = f"{instance_url}{GROUP_MEMBER_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        members = [_format_group_member(r) for r in response.json().get("result", [])]
        return _paginated_list_response(members, validated.limit, validated.offset, "members")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing group members: {e}")
        return {"success": False, "message": f"Error listing group members: {_format_http_error(e)}"}
