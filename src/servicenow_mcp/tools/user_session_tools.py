"""
User session tools for the ServiceNow MCP server.

Provides tools for inspecting active and recent user sessions stored in the
sys_user_session table.
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

USER_SESSION_TABLE = "sys_user_session"

USER_SESSION_FIELDS = [
    "sys_id",
    "user",
    "session_id",
    "logged_in",
    "last_request",
    "ip_address",
    "user_agent",
    "browser",
    "os_type",
    "screen_size",
    "sys_created_on",
    "sys_updated_on",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListUserSessionsParams(BaseModel):
    """Parameters for listing user sessions."""

    user_id: Optional[str] = Field(
        None,
        description=(
            "sys_id or user_name of the user whose sessions to list. "
            "A 32-character hex string is treated as a sys_id; otherwise resolved "
            "via user_name lookup on sys_user."
        ),
    )
    ip_address: Optional[str] = Field(
        None,
        description="Filter sessions by IP address (exact match).",
    )
    logged_in_after: Optional[str] = Field(
        None,
        description=(
            "Return only sessions with logged_in >= this datetime "
            "(format: YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)."
        ),
    )
    limit: Optional[int] = Field(20, description="Maximum number of sessions to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")


class GetUserSessionParams(BaseModel):
    """Parameters for retrieving a single user session."""

    session_id: str = Field(
        ...,
        description="sys_id of the session record to retrieve.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_user_sys_id_for_session(
    user_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a user_name to its sys_id for session lookup.

    A 32-character hex string is returned unchanged.  Otherwise a lookup
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


def _format_user_session(record: Dict) -> Dict:
    """Normalise a raw sys_user_session record."""
    user = record.get("user")
    if isinstance(user, dict):
        user = user.get("display_value") or user.get("value")
    return {
        "sys_id": record.get("sys_id"),
        "user": user,
        "session_id": record.get("session_id"),
        "logged_in": record.get("logged_in"),
        "last_request": record.get("last_request"),
        "ip_address": record.get("ip_address"),
        "user_agent": record.get("user_agent"),
        "browser": record.get("browser"),
        "os_type": record.get("os_type"),
        "screen_size": record.get("screen_size"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def list_user_sessions(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List user session records from sys_user_session.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListUserSessionsParams.

    Returns:
        Dictionary with ``success``, ``sessions`` (list), ``count``, and
        optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListUserSessionsParams)
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
        user_sys_id = _resolve_user_sys_id_for_session(validated.user_id, instance_url, headers)
        if not user_sys_id:
            return {"success": False, "message": f"User not found: {validated.user_id}"}
        query_parts.append(f"user={user_sys_id}")

    if validated.ip_address:
        query_parts.append(f"ip_address={validated.ip_address}")

    if validated.logged_in_after:
        query_parts.append(f"logged_in>={validated.logged_in_after}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="logged_in",
        fields=",".join(USER_SESSION_FIELDS),
    )
    query_params["sysparm_display_value"] = "true"

    url = f"{instance_url}/api/now/table/{USER_SESSION_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        sessions = [_format_user_session(r) for r in response.json().get("result", [])]
        return _paginated_list_response(sessions, validated.limit, validated.offset, "sessions")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing user sessions: {e}")
        return {"success": False, "message": f"Error listing user sessions: {_format_http_error(e)}"}


def get_user_session(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single user session record by sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetUserSessionParams.

    Returns:
        Dictionary with ``success`` and ``session`` keys on success.
    """
    result = _unwrap_and_validate_params(
        params, GetUserSessionParams, required_fields=["session_id"]
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

    url = f"{instance_url}/api/now/table/{USER_SESSION_TABLE}/{validated.session_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(USER_SESSION_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Session not found: {validated.session_id}"}
        response.raise_for_status()
        result_data = response.json().get("result")
        if not result_data:
            return {"success": False, "message": f"Session not found: {validated.session_id}"}
        return {"success": True, "session": _format_user_session(result_data)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving user session: {e}")
        return {"success": False, "message": f"Error retrieving user session: {_format_http_error(e)}"}
