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


class CloseIncidentTaskParams(BaseModel):
    """Parameters for closing an incident task."""

    task_id: str = Field(
        ...,
        description="sc_task number (e.g. TASK0010001) or sys_id to close",
    )
    close_notes: Optional[str] = Field(None, description="Closure notes")
    work_notes: Optional[str] = Field(None, description="Work notes to add when closing")


class ListIncidentCommentsParams(BaseModel):
    """Parameters for listing journal entries (comments/work notes) on an incident."""

    incident_id: str = Field(
        ...,
        description="Incident sys_id or number (e.g. INC0010001)",
    )
    entry_type: Optional[str] = Field(
        None,
        description=(
            "Filter by entry type: 'comments' for customer-visible comments, "
            "'work_notes' for internal notes. Omit to return all entries."
        ),
    )
    limit: int = Field(20, description="Maximum number of entries to return")
    offset: int = Field(0, description="Pagination offset")


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


def list_incident_comments(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List journal entries (comments and work notes) for a specific incident.

    Queries the sys_journal_field table filtered to the incident's sys_id.
    Optionally filter to 'comments' (customer-visible) or 'work_notes' (internal).
    """
    result = _unwrap_and_validate_params(
        params, ListIncidentCommentsParams, required_fields=["incident_id"]
    )
    if not result["success"]:
        return result

    validated: ListIncidentCommentsParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}

    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    incident_sys_id = _resolve_incident_sys_id(instance_url, headers, validated.incident_id)
    if not incident_sys_id:
        return {"success": False, "message": f"Incident not found: {validated.incident_id}"}

    query_parts = [
        "name=incident",
        f"element_id={incident_sys_id}",
    ]
    if validated.entry_type:
        query_parts.append(f"element={validated.entry_type}")

    url = f"{instance_url}/api/now/table/sys_journal_field"
    query_params = {
        "sysparm_query": "^".join(query_parts),
        "sysparm_limit": validated.limit,
        "sysparm_offset": validated.offset,
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": "sys_id,element,element_id,value,sys_created_on,sys_created_by",
    }

    try:
        resp = _make_request("GET", url, headers=headers, params=query_params)
        resp.raise_for_status()
        entries = resp.json().get("result", [])
        comments = [
            {
                "sys_id": e.get("sys_id"),
                "type": e.get("element"),
                "value": e.get("value"),
                "created_on": e.get("sys_created_on"),
                "created_by": e.get("sys_created_by"),
            }
            for e in entries
        ]
        return {
            "success": True,
            "comments": comments,
            "count": len(comments),
            "has_more": len(comments) == validated.limit,
            "next_offset": validated.offset + len(comments) if len(comments) == validated.limit else None,
            "incident_id": incident_sys_id,
            "message": f"Found {len(comments)} journal entries",
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing incident comments: {e}")
        return {"success": False, "message": f"Error listing incident comments: {_format_http_error(e)}"}


def _resolve_task_sys_id(
    instance_url: str,
    headers: Dict[str, str],
    task_id: str,
) -> Optional[str]:
    """Return the sys_id for an sc_task number or passthrough if already a sys_id."""
    if len(task_id) == 32 and all(c in "0123456789abcdef" for c in task_id):
        return task_id

    url = f"{instance_url}/api/now/table/sc_task"
    try:
        resp = _make_request(
            "GET",
            url,
            headers=headers,
            params={"sysparm_query": f"number={task_id}", "sysparm_limit": 1, "sysparm_fields": "sys_id"},
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        if not results:
            return None
        return results[0].get("sys_id")
    except requests.exceptions.RequestException:
        return None


def close_incident_task(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Close an incident task by setting its state to Closed Complete (3).

    Accepts an sc_task number (e.g. TASK0010001) or a 32-character sys_id.
    Optionally adds close_notes and work_notes.
    """
    result = _unwrap_and_validate_params(
        params, CloseIncidentTaskParams, required_fields=["task_id"]
    )
    if not result["success"]:
        return result

    validated: CloseIncidentTaskParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}

    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}
    headers["Content-Type"] = "application/json"

    task_sys_id = _resolve_task_sys_id(instance_url, headers, validated.task_id)
    if not task_sys_id:
        return {"success": False, "message": f"Task not found: {validated.task_id}"}

    body: Dict[str, Any] = {"state": "3"}
    if validated.close_notes is not None:
        body["close_notes"] = validated.close_notes
    if validated.work_notes is not None:
        body["work_notes"] = validated.work_notes

    url = f"{instance_url}/api/now/table/sc_task/{task_sys_id}"
    try:
        resp = _make_request("PATCH", url, json=body, headers=headers)
        if resp.status_code == 404:
            return {"success": False, "message": f"Task not found: {validated.task_id}"}
        resp.raise_for_status()
        task = resp.json().get("result", {})
        return {
            "success": True,
            "message": f"Incident task {validated.task_id} closed successfully",
            "task": {
                "sys_id": task_sys_id,
                "number": task.get("number", validated.task_id),
                "state": task.get("state"),
                "close_notes": task.get("close_notes"),
            },
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error closing incident task: {e}")
        return {"success": False, "message": f"Error closing incident task: {_format_http_error(e)}"}
