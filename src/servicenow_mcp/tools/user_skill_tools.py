"""
User skill tools for the ServiceNow MCP server.

Provides tools for listing and retrieving user skill assignment records from
the sys_user_has_skill table (and skill definitions from sys_skill).
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

USER_HAS_SKILL_TABLE = "sys_user_has_skill"
SKILL_TABLE = "sys_skill"

USER_HAS_SKILL_FIELDS = [
    "sys_id",
    "user",
    "skill",
    "level",
    "sys_created_on",
    "sys_updated_on",
]

SKILL_FIELDS = [
    "sys_id",
    "name",
    "description",
    "active",
    "sys_created_on",
    "sys_updated_on",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListUserSkillsParams(BaseModel):
    """Parameters for listing user skill assignments."""

    user_id: Optional[str] = Field(
        None,
        description=(
            "sys_id or user_name of the user whose skills to list. "
            "A 32-character hex string is treated as a sys_id; otherwise "
            "resolved via user_name lookup on sys_user."
        ),
    )
    skill_id: Optional[str] = Field(
        None,
        description=(
            "Filter by skill sys_id (32-char hex) or exact skill name. "
            "Name is resolved to sys_id via the sys_skill table."
        ),
    )
    level: Optional[str] = Field(
        None,
        description="Filter by proficiency level (exact match, e.g. '1', '2', '3').",
    )
    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")


class GetUserSkillParams(BaseModel):
    """Parameters for retrieving a single user skill assignment."""

    user_skill_id: str = Field(
        ...,
        description="sys_id of the sys_user_has_skill record to retrieve.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_user_sys_id(
    user_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a user_name to its sys_id.

    A 32-character hex string is returned unchanged. Otherwise a lookup
    against sys_user by user_name is performed.
    """
    if len(user_id) == 32 and all(c in "0123456789abcdefABCDEF" for c in user_id):
        return user_id
    url = f"{instance_url}/api/now/table/sys_user"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"user_name={user_id}",
                "sysparm_fields": "sys_id",
                "sysparm_limit": "1",
                "sysparm_exclude_reference_link": "true",
            },
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        if results:
            return results[0].get("sys_id")
    except requests.exceptions.RequestException:
        pass
    return None


def _resolve_skill_sys_id(
    skill_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a skill name to its sys_id.

    A 32-character hex string is returned unchanged. Otherwise a lookup
    against sys_skill by name is performed.
    """
    if len(skill_id) == 32 and all(c in "0123456789abcdefABCDEF" for c in skill_id):
        return skill_id
    url = f"{instance_url}/api/now/table/{SKILL_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={skill_id}",
                "sysparm_fields": "sys_id",
                "sysparm_limit": "1",
                "sysparm_exclude_reference_link": "true",
            },
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        if results:
            return results[0].get("sys_id")
    except requests.exceptions.RequestException:
        pass
    return None


def _format_user_skill(record: Dict) -> Dict:
    """Normalise a raw sys_user_has_skill record."""
    user = record.get("user")
    if isinstance(user, dict):
        user = user.get("display_value") or user.get("value")

    skill = record.get("skill")
    skill_name = None
    skill_sys_id = None
    if isinstance(skill, dict):
        skill_name = skill.get("display_value")
        skill_sys_id = skill.get("value")
    else:
        skill_name = skill
        skill_sys_id = skill

    return {
        "sys_id": record.get("sys_id"),
        "user": user,
        "skill": skill_name,
        "skill_sys_id": skill_sys_id,
        "level": record.get("level"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def list_user_skills(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List user skill assignment records from sys_user_has_skill.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListUserSkillsParams.

    Returns:
        Dictionary with ``success``, ``skills`` (list), ``count``, and
        optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListUserSkillsParams)
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

    if validated.user_id:
        user_sys_id = _resolve_user_sys_id(validated.user_id, instance_url, headers)
        if not user_sys_id:
            return {"success": False, "message": f"User not found: {validated.user_id}"}
        query_parts.append(f"user={user_sys_id}")

    if validated.skill_id:
        skill_sys_id = _resolve_skill_sys_id(validated.skill_id, instance_url, headers)
        if not skill_sys_id:
            return {"success": False, "message": f"Skill not found: {validated.skill_id}"}
        query_parts.append(f"skill={skill_sys_id}")

    if validated.level:
        query_parts.append(f"level={validated.level}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        fields=",".join(USER_HAS_SKILL_FIELDS),
    )
    query_params["sysparm_display_value"] = "true"

    url = f"{instance_url}/api/now/table/{USER_HAS_SKILL_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        skills = [_format_user_skill(r) for r in response.json().get("result", [])]
        return _paginated_list_response(skills, validated.limit, validated.offset, "skills")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing user skills: {e}")
        return {"success": False, "message": f"Error listing user skills: {_format_http_error(e)}"}


def get_user_skill(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single user skill assignment record by sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetUserSkillParams.

    Returns:
        Dictionary with ``success`` and ``skill`` keys on success.
    """
    result = _unwrap_and_validate_params(
        params, GetUserSkillParams, required_fields=["user_skill_id"]
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

    url = f"{instance_url}/api/now/table/{USER_HAS_SKILL_TABLE}/{validated.user_skill_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(USER_HAS_SKILL_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"User skill record not found: {validated.user_skill_id}"}
        response.raise_for_status()
        result_data = response.json().get("result")
        if not result_data:
            return {"success": False, "message": f"User skill record not found: {validated.user_skill_id}"}
        return {"success": True, "skill": _format_user_skill(result_data)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving user skill: {e}")
        return {"success": False, "message": f"Error retrieving user skill: {_format_http_error(e)}"}
