"""
User preference tools for the ServiceNow MCP server.

Provides tools for reading, writing, and deleting user preferences stored in
the sys_user_preference table.  Preferences are key-value pairs tied to a
specific user and an optional application scope.
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

USER_PREFERENCE_TABLE = "sys_user_preference"

USER_PREFERENCE_FIELDS = [
    "sys_id",
    "user",
    "name",
    "value",
    "type",
    "system",
    "description",
    "sys_created_on",
    "sys_updated_on",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class GetUserPreferenceParams(BaseModel):
    """Parameters for retrieving a single user preference."""

    user_id: str = Field(
        ...,
        description=(
            "sys_id or user_name of the user whose preference to retrieve. "
            "A 32-character hex string is treated as a sys_id; otherwise resolved "
            "via user_name lookup on sys_user."
        ),
    )
    name: str = Field(
        ...,
        description=(
            "The preference key name (e.g. 'rowcount', 'theme', 'com.glide.ui.date_format')."
        ),
    )


class SetUserPreferenceParams(BaseModel):
    """Parameters for creating or updating a user preference."""

    user_id: str = Field(
        ...,
        description=(
            "sys_id or user_name of the user whose preference to set. "
            "A 32-character hex string is treated as a sys_id; otherwise resolved "
            "via user_name lookup on sys_user."
        ),
    )
    name: str = Field(
        ...,
        description="The preference key name (e.g. 'rowcount', 'theme').",
    )
    value: str = Field(
        ...,
        description="The preference value to store.",
    )
    description: Optional[str] = Field(
        None,
        description="Optional human-readable description of the preference.",
    )
    system: Optional[bool] = Field(
        None,
        description=(
            "Mark the preference as a system-level preference (true) or user-level (false). "
            "Defaults to false (user-level)."
        ),
    )


class DeleteUserPreferenceParams(BaseModel):
    """Parameters for deleting a user preference."""

    user_id: str = Field(
        ...,
        description=(
            "sys_id or user_name of the user whose preference to delete. "
            "A 32-character hex string is treated as a sys_id; otherwise resolved "
            "via user_name lookup on sys_user."
        ),
    )
    name: str = Field(
        ...,
        description="The preference key name to delete.",
    )


class ListUserPreferencesParams(BaseModel):
    """Parameters for listing user preferences."""

    user_id: Optional[str] = Field(
        None,
        description=(
            "sys_id or user_name of the user whose preferences to list. "
            "When omitted, preferences for all users are returned (admin use)."
        ),
    )
    name: Optional[str] = Field(
        None,
        description="Filter by preference key name (substring match).",
    )
    limit: Optional[int] = Field(20, description="Maximum number of preferences to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_user_sys_id(
    user_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a user_name to its sys_id.

    A 32-character hex string is returned unchanged.  Otherwise a lookup
    against sys_user by user_name is performed.

    Returns ``None`` when the user cannot be found.
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


def _find_preference_sys_id(
    user_sys_id: str,
    name: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Look up the sys_id of an existing user preference by user and key name."""
    url = f"{instance_url}/api/now/table/{USER_PREFERENCE_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"user={user_sys_id}^name={name}",
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


def _format_user_preference(record: Dict) -> Dict:
    """Normalise a raw sys_user_preference record."""
    user = record.get("user")
    if isinstance(user, dict):
        user = user.get("display_value") or user.get("value")
    return {
        "sys_id": record.get("sys_id"),
        "user": user,
        "name": record.get("name"),
        "value": record.get("value"),
        "type": record.get("type"),
        "system": record.get("system"),
        "description": record.get("description"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def get_user_preference(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single user preference by user and key name.

    Looks up the preference in sys_user_preference using the supplied
    ``user_id`` (sys_id or user_name) and the preference ``name``.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetUserPreferenceParams.

    Returns:
        Dictionary with ``success`` and ``preference`` keys on success.
    """
    result = _unwrap_and_validate_params(
        params, GetUserPreferenceParams, required_fields=["user_id", "name"]
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

    user_sys_id = _resolve_user_sys_id(validated.user_id, instance_url, headers)
    if not user_sys_id:
        return {"success": False, "message": f"User not found: {validated.user_id}"}

    url = f"{instance_url}/api/now/table/{USER_PREFERENCE_TABLE}"
    query_params: Dict[str, Any] = {
        "sysparm_query": f"user={user_sys_id}^name={validated.name}",
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(USER_PREFERENCE_FIELDS),
        "sysparm_limit": "1",
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        results = response.json().get("result", [])
        if not results:
            return {
                "success": False,
                "message": f"Preference '{validated.name}' not found for user '{validated.user_id}'",
            }
        return {"success": True, "preference": _format_user_preference(results[0])}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving user preference: {e}")
        return {"success": False, "message": f"Error retrieving user preference: {_format_http_error(e)}"}


def set_user_preference(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create or update a user preference.

    If a preference with the given ``name`` already exists for the user it is
    updated (PATCH); otherwise a new record is created (POST).

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching SetUserPreferenceParams.

    Returns:
        Dictionary with ``success``, ``preference``, and ``action`` ('created'
        or 'updated') keys on success.
    """
    result = _unwrap_and_validate_params(
        params, SetUserPreferenceParams, required_fields=["user_id", "name", "value"]
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

    user_sys_id = _resolve_user_sys_id(validated.user_id, instance_url, headers)
    if not user_sys_id:
        return {"success": False, "message": f"User not found: {validated.user_id}"}

    # Build the preference body
    body: Dict[str, Any] = {
        "user": user_sys_id,
        "name": validated.name,
        "value": validated.value,
    }
    if validated.description is not None:
        body["description"] = validated.description
    if validated.system is not None:
        body["system"] = "true" if validated.system else "false"

    # Check if a preference with this name already exists for the user
    existing_sys_id = _find_preference_sys_id(user_sys_id, validated.name, instance_url, headers)

    try:
        if existing_sys_id:
            # Update existing preference
            url = f"{instance_url}/api/now/table/{USER_PREFERENCE_TABLE}/{existing_sys_id}"
            response = _make_request("PATCH", url, headers=headers, json=body)
            if response.status_code == 404:
                return {"success": False, "message": f"Preference not found during update: {validated.name}"}
            response.raise_for_status()
            record = response.json().get("result", {})
            return {
                "success": True,
                "action": "updated",
                "preference": _format_user_preference(record),
            }
        else:
            # Create new preference
            url = f"{instance_url}/api/now/table/{USER_PREFERENCE_TABLE}"
            response = _make_request("POST", url, headers=headers, json=body)
            response.raise_for_status()
            record = response.json().get("result", {})
            return {
                "success": True,
                "action": "created",
                "preference": _format_user_preference(record),
            }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error setting user preference: {e}")
        return {"success": False, "message": f"Error setting user preference: {_format_http_error(e)}"}


def delete_user_preference(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete a user preference by user and key name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeleteUserPreferenceParams.

    Returns:
        Dictionary with ``success`` and ``message`` keys.
    """
    result = _unwrap_and_validate_params(
        params, DeleteUserPreferenceParams, required_fields=["user_id", "name"]
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

    user_sys_id = _resolve_user_sys_id(validated.user_id, instance_url, headers)
    if not user_sys_id:
        return {"success": False, "message": f"User not found: {validated.user_id}"}

    pref_sys_id = _find_preference_sys_id(user_sys_id, validated.name, instance_url, headers)
    if not pref_sys_id:
        return {
            "success": False,
            "message": f"Preference '{validated.name}' not found for user '{validated.user_id}'",
        }

    url = f"{instance_url}/api/now/table/{USER_PREFERENCE_TABLE}/{pref_sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {
                "success": False,
                "message": f"Preference '{validated.name}' not found for user '{validated.user_id}'",
            }
        if response.status_code not in (200, 204):
            response.raise_for_status()
        return {
            "success": True,
            "message": f"Preference '{validated.name}' deleted for user '{validated.user_id}'",
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting user preference: {e}")
        return {"success": False, "message": f"Error deleting user preference: {_format_http_error(e)}"}


def list_user_preferences(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List user preferences from the sys_user_preference table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListUserPreferencesParams.

    Returns:
        Dictionary with ``success``, ``preferences`` (list), ``count``, and
        optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListUserPreferencesParams)
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

    if validated.name:
        query_parts.append(f"nameLIKE{validated.name}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="name",
        fields=",".join(USER_PREFERENCE_FIELDS),
    )
    query_params["sysparm_display_value"] = "true"

    url = f"{instance_url}/api/now/table/{USER_PREFERENCE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        prefs = [_format_user_preference(r) for r in response.json().get("result", [])]
        return _paginated_list_response(prefs, validated.limit, validated.offset, "preferences")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing user preferences: {e}")
        return {"success": False, "message": f"Error listing user preferences: {_format_http_error(e)}"}
