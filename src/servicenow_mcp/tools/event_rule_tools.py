"""
Event rule management tools for the ServiceNow MCP server.

Provides tools for managing sysevent_rule records — the server-side scripts
that run when a named business event fires.
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

EVENT_RULE_TABLE = "sysevent_rule"

EVENT_RULE_FIELDS = [
    "sys_id",
    "name",
    "description",
    "active",
    "order",
    "condition",
    "script",
    "filter_fields",
    "queue",
    "application",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
    "sys_updated_by",
]


def _format_event_rule(record: Dict) -> Dict:
    """Normalise a raw sysevent_rule record."""
    active = record.get("active")
    if isinstance(active, str):
        active = active.lower() == "true"
    application = record.get("application")
    if isinstance(application, dict):
        application = application.get("display_value") or application.get("value")
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "description": record.get("description"),
        "active": active,
        "order": record.get("order"),
        "condition": record.get("condition"),
        "script": record.get("script"),
        "filter_fields": record.get("filter_fields"),
        "queue": record.get("queue"),
        "application": application,
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
        "updated_by": record.get("sys_updated_by"),
    }


def _resolve_event_rule_sys_id(
    rule_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Return the sys_id for a rule given a sys_id or exact name."""
    if len(rule_id) == 32 and all(c in "0123456789abcdef" for c in rule_id.lower()):
        return rule_id
    url = f"{instance_url}/api/now/table/{EVENT_RULE_TABLE}"
    params: Dict[str, Any] = {
        "sysparm_query": f"name={rule_id}",
        "sysparm_limit": "1",
        "sysparm_fields": "sys_id",
        "sysparm_exclude_reference_link": "true",
    }
    try:
        resp = _make_request("GET", url, headers=headers, params=params)
        resp.raise_for_status()
        results = resp.json().get("result", [])
        return results[0]["sys_id"] if results else None
    except requests.exceptions.RequestException:
        return None


class ListEventRulesParams(BaseModel):
    """Parameters for listing sysevent_rule records."""

    limit: Optional[int] = Field(20, description="Maximum number of rules to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    name: Optional[str] = Field(None, description="Filter by event name pattern (LIKE match)")
    active: Optional[bool] = Field(None, description="Filter by active state")
    queue: Optional[str] = Field(None, description="Filter by queue name (LIKE match)")
    application: Optional[str] = Field(None, description="Filter by application scope sys_id or display name (LIKE match)")


class GetEventRuleParams(BaseModel):
    """Parameters for retrieving a single sysevent_rule."""

    rule_id: str = Field(
        ...,
        description="sys_id (32-char hex) or exact name of the event rule to retrieve",
    )


class CreateEventRuleParams(BaseModel):
    """Parameters for creating a new sysevent_rule."""

    name: str = Field(..., description="Event name pattern this rule reacts to (e.g. 'incident.created')")
    script: str = Field(..., description="Server-side JavaScript executed when the event fires")
    description: Optional[str] = Field(None, description="Human-readable description of what the rule does")
    active: Optional[bool] = Field(True, description="Whether the rule is active (default true)")
    order: Optional[int] = Field(None, description="Execution order relative to other rules for the same event")
    condition: Optional[str] = Field(None, description="Optional condition script; rule runs only when this evaluates to true")
    filter_fields: Optional[str] = Field(None, description="Comma-separated list of event fields to pass to the script")
    queue: Optional[str] = Field(None, description="Queue name (leave blank for the default queue)")


class UpdateEventRuleParams(BaseModel):
    """Parameters for updating an existing sysevent_rule."""

    rule_id: str = Field(..., description="sys_id (32-char hex) or exact name of the rule to update")
    name: Optional[str] = Field(None, description="New event name pattern")
    script: Optional[str] = Field(None, description="New server-side script")
    description: Optional[str] = Field(None, description="New description")
    active: Optional[bool] = Field(None, description="Enable or disable the rule")
    order: Optional[int] = Field(None, description="New execution order")
    condition: Optional[str] = Field(None, description="New condition script")
    filter_fields: Optional[str] = Field(None, description="New filter_fields value")
    queue: Optional[str] = Field(None, description="New queue name")


class DeleteEventRuleParams(BaseModel):
    """Parameters for deleting a sysevent_rule."""

    rule_id: str = Field(..., description="sys_id (32-char hex) or exact name of the rule to delete")


def list_event_rules(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List event rules from the ServiceNow sysevent_rule table.

    Supports filtering by event name pattern, active state, queue, and
    application scope.  Results are ordered by name ascending.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListEventRulesParams.

    Returns:
        Dictionary with ``success``, ``event_rules`` (list), ``count``, and
        optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListEventRulesParams)
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
    if validated.queue:
        query_parts.append(f"queueLIKE{validated.queue}")
    if validated.application:
        query_parts.append(f"applicationLIKE{validated.application}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="name",
        fields=",".join(EVENT_RULE_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{EVENT_RULE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        rules = [_format_event_rule(r) for r in response.json().get("result", [])]
        return _paginated_list_response(rules, validated.limit, validated.offset, "event_rules")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing event rules: {e}")
        return {"success": False, "message": f"Error listing event rules: {_format_http_error(e)}"}


def get_event_rule(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single sysevent_rule record by sys_id or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetEventRuleParams.

    Returns:
        Dictionary with ``success`` and ``event_rule`` keys.
    """
    result = _unwrap_and_validate_params(params, GetEventRuleParams, required_fields=["rule_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_event_rule_sys_id(validated.rule_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Event rule not found: {validated.rule_id}"}

    url = f"{instance_url}/api/now/table/{EVENT_RULE_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(EVENT_RULE_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Event rule not found: {validated.rule_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Event rule not found: {validated.rule_id}"}
        return {"success": True, "event_rule": _format_event_rule(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving event rule: {e}")
        return {"success": False, "message": f"Error retrieving event rule: {_format_http_error(e)}"}


def create_event_rule(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new event rule in the ServiceNow sysevent_rule table.

    The new rule fires its script whenever an event whose name matches the
    ``name`` field is processed by the ServiceNow event queue.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateEventRuleParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``event_rule`` keys.
    """
    result = _unwrap_and_validate_params(params, CreateEventRuleParams, required_fields=["name", "script"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    body: Dict[str, Any] = {
        "name": validated.name,
        "script": validated.script,
        "active": "true" if validated.active else "false",
    }
    if validated.description is not None:
        body["description"] = validated.description
    if validated.order is not None:
        body["order"] = str(validated.order)
    if validated.condition is not None:
        body["condition"] = validated.condition
    if validated.filter_fields is not None:
        body["filter_fields"] = validated.filter_fields
    if validated.queue is not None:
        body["queue"] = validated.queue

    url = f"{instance_url}/api/now/table/{EVENT_RULE_TABLE}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(EVENT_RULE_FIELDS),
    }
    try:
        response = _make_request("POST", url, headers=headers, params=query_params, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Event rule '{validated.name}' created successfully",
            "event_rule": _format_event_rule(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating event rule: {e}")
        return {"success": False, "message": f"Error creating event rule: {_format_http_error(e)}"}


def update_event_rule(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing sysevent_rule record.

    Accepts a sys_id or exact event rule name.  Only fields that are
    explicitly provided are sent in the PATCH body.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdateEventRuleParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``event_rule`` keys.
    """
    result = _unwrap_and_validate_params(params, UpdateEventRuleParams, required_fields=["rule_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_event_rule_sys_id(validated.rule_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Event rule not found: {validated.rule_id}"}

    body: Dict[str, Any] = {}
    if validated.name is not None:
        body["name"] = validated.name
    if validated.script is not None:
        body["script"] = validated.script
    if validated.description is not None:
        body["description"] = validated.description
    if validated.active is not None:
        body["active"] = "true" if validated.active else "false"
    if validated.order is not None:
        body["order"] = str(validated.order)
    if validated.condition is not None:
        body["condition"] = validated.condition
    if validated.filter_fields is not None:
        body["filter_fields"] = validated.filter_fields
    if validated.queue is not None:
        body["queue"] = validated.queue

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    url = f"{instance_url}/api/now/table/{EVENT_RULE_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(EVENT_RULE_FIELDS),
    }
    try:
        response = _make_request("PATCH", url, headers=headers, params=query_params, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"Event rule not found: {validated.rule_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Event rule '{validated.rule_id}' updated successfully",
            "event_rule": _format_event_rule(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating event rule: {e}")
        return {"success": False, "message": f"Error updating event rule: {_format_http_error(e)}"}


def delete_event_rule(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete a sysevent_rule record.

    Accepts a sys_id or exact event rule name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeleteEventRuleParams.

    Returns:
        Dictionary with ``success`` and ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, DeleteEventRuleParams, required_fields=["rule_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_event_rule_sys_id(validated.rule_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Event rule not found: {validated.rule_id}"}

    url = f"{instance_url}/api/now/table/{EVENT_RULE_TABLE}/{sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {"success": False, "message": f"Event rule not found: {validated.rule_id}"}
        if response.status_code in (200, 204):
            return {"success": True, "message": f"Event rule '{validated.rule_id}' deleted successfully"}
        response.raise_for_status()
        return {"success": True, "message": f"Event rule '{validated.rule_id}' deleted successfully"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting event rule: {e}")
        return {"success": False, "message": f"Error deleting event rule: {_format_http_error(e)}"}
