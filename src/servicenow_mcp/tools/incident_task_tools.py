"""
Incident Task tools for the ServiceNow MCP server.

Manages sc_task records whose parent_incident field links them to an incident.
"""

import logging
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.helpers import (
    _format_http_error,
    _get_headers,
    _get_instance_url,
    _unwrap_and_validate_params,
    _make_request,
)

logger = logging.getLogger(__name__)


class CreateIncidentTaskParams(BaseModel):
    """Parameters for creating a task linked to an incident."""

    incident_id: str = Field(
        ...,
        description="Incident sys_id or number (e.g. INC0010001) to attach the task to",
    )
    short_description: str = Field(..., description="Short description of the task")
    description: Optional[str] = Field(None, description="Detailed description of the task")
    assigned_to: Optional[str] = Field(None, description="Username or sys_id of the assignee")
    assignment_group: Optional[str] = Field(None, description="Name or sys_id of the assignment group")
    priority: Optional[str] = Field(
        None,
        description="Priority (1=Critical, 2=High, 3=Moderate, 4=Low, 5=Planning)",
    )
    state: Optional[str] = Field(
        None,
        description="Initial state (1=Open, 2=Work In Progress). Defaults to Open.",
    )
    work_notes: Optional[str] = Field(None, description="Initial work notes")


class ListIncidentTasksParams(BaseModel):
    """Parameters for listing tasks linked to an incident."""

    incident_id: str = Field(
        ...,
        description="Incident sys_id or number whose tasks should be listed",
    )
    limit: int = Field(10, description="Maximum number of tasks to return")
    offset: int = Field(0, description="Pagination offset")
    state: Optional[str] = Field(None, description="Filter by task state")


def _resolve_incident_sys_id(
    instance_url: str,
    headers: Dict[str, str],
    incident_id: str,
) -> Optional[str]:
    """Return the sys_id for an incident number or passthrough if already a sys_id."""
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        return incident_id

    url = f"{instance_url}/api/now/table/incident"
    try:
        resp = _make_request(
            "GET",
            url,
            headers=headers,
            params={"sysparm_query": f"number={incident_id}", "sysparm_limit": 1, "sysparm_fields": "sys_id"},
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        if not results:
            return None
        return results[0].get("sys_id")
    except requests.exceptions.RequestException:
        return None


def create_incident_task(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a task (sc_task) linked to an incident via parent_incident."""
    result = _unwrap_and_validate_params(
        params, CreateIncidentTaskParams, required_fields=["incident_id", "short_description"]
    )
    if not result["success"]:
        return result

    validated: CreateIncidentTaskParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}

    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}
    headers["Content-Type"] = "application/json"

    incident_sys_id = _resolve_incident_sys_id(instance_url, headers, validated.incident_id)
    if not incident_sys_id:
        return {"success": False, "message": f"Incident not found: {validated.incident_id}"}

    body: Dict[str, Any] = {
        "short_description": validated.short_description,
        "parent_incident": incident_sys_id,
    }
    if validated.description is not None:
        body["description"] = validated.description
    if validated.assigned_to is not None:
        body["assigned_to"] = validated.assigned_to
    if validated.assignment_group is not None:
        body["assignment_group"] = validated.assignment_group
    if validated.priority is not None:
        body["priority"] = validated.priority
    if validated.state is not None:
        body["state"] = validated.state
    if validated.work_notes is not None:
        body["work_notes"] = validated.work_notes

    url = f"{instance_url}/api/now/table/sc_task"
    try:
        resp = _make_request("POST", url, json=body, headers=headers)
        resp.raise_for_status()
        task = resp.json().get("result", {})
        return {
            "success": True,
            "message": f"Incident task created: {task.get('number')}",
            "task": {
                "sys_id": task.get("sys_id"),
                "number": task.get("number"),
                "short_description": task.get("short_description"),
                "state": task.get("state"),
                "priority": task.get("priority"),
                "assigned_to": task.get("assigned_to"),
                "assignment_group": task.get("assignment_group"),
                "parent_incident": incident_sys_id,
            },
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating incident task: {e}")
        return {"success": False, "message": f"Error creating incident task: {_format_http_error(e)}"}


def list_incident_tasks(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List sc_task records linked to a specific incident."""
    result = _unwrap_and_validate_params(
        params, ListIncidentTasksParams, required_fields=["incident_id"]
    )
    if not result["success"]:
        return result

    validated: ListIncidentTasksParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}

    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    incident_sys_id = _resolve_incident_sys_id(instance_url, headers, validated.incident_id)
    if not incident_sys_id:
        return {"success": False, "message": f"Incident not found: {validated.incident_id}"}

    query_parts = [f"parent_incident={incident_sys_id}"]
    if validated.state:
        query_parts.append(f"state={validated.state}")

    url = f"{instance_url}/api/now/table/sc_task"
    query_params = {
        "sysparm_query": "^".join(query_parts),
        "sysparm_limit": validated.limit,
        "sysparm_offset": validated.offset,
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        resp = _make_request("GET", url, headers=headers, params=query_params)
        resp.raise_for_status()
        tasks = resp.json().get("result", [])
        return {
            "success": True,
            "tasks": tasks,
            "count": len(tasks),
            "has_more": len(tasks) == validated.limit,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing incident tasks: {e}")
        return {"success": False, "message": f"Error listing incident tasks: {_format_http_error(e)}"}
