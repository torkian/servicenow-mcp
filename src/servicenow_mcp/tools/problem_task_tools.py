"""
Problem Task tools for the ServiceNow MCP server.

Manages problem_task records linked to a parent problem record.
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

PROBLEM_TASK_TABLE = "/api/now/table/problem_task"
PROBLEM_TABLE = "/api/now/table/problem"

PROBLEM_TASK_FIELDS = [
    "sys_id",
    "number",
    "short_description",
    "description",
    "state",
    "priority",
    "assigned_to",
    "assignment_group",
    "problem",
    "work_notes",
    "close_notes",
    "sys_created_on",
    "sys_updated_on",
]


class CreateProblemTaskParams(BaseModel):
    """Parameters for creating a task linked to a problem."""

    problem_id: str = Field(
        ...,
        description="Problem sys_id or number (e.g. PRB0001234) to attach the task to",
    )
    short_description: str = Field(..., description="Short description of the task")
    description: Optional[str] = Field(None, description="Detailed description of the task")
    assigned_to: Optional[str] = Field(None, description="Username or sys_id of the assignee")
    assignment_group: Optional[str] = Field(
        None, description="Name or sys_id of the assignment group"
    )
    priority: Optional[str] = Field(
        None,
        description="Priority (1=Critical, 2=High, 3=Moderate, 4=Low)",
    )
    state: Optional[str] = Field(
        None,
        description="Initial state (1=Open, 2=Work In Progress). Defaults to Open.",
    )
    work_notes: Optional[str] = Field(None, description="Initial work notes")


class ListProblemTasksParams(BaseModel):
    """Parameters for listing tasks linked to a problem."""

    problem_id: str = Field(
        ...,
        description="Problem sys_id or number (e.g. PRB0001234) whose tasks should be listed",
    )
    limit: int = Field(20, description="Maximum number of tasks to return")
    offset: int = Field(0, description="Pagination offset")
    state: Optional[str] = Field(None, description="Filter by task state value")


class CloseProblemTaskParams(BaseModel):
    """Parameters for closing a problem task."""

    task_id: str = Field(
        ...,
        description="Problem task number (e.g. PTASK0010001) or sys_id to close",
    )
    close_notes: Optional[str] = Field(None, description="Closure notes")
    work_notes: Optional[str] = Field(None, description="Work notes to add when closing")


def _format_problem_task(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw problem_task API record."""
    assigned_to = record.get("assigned_to")
    if isinstance(assigned_to, dict):
        assigned_to = assigned_to.get("display_value")

    assignment_group = record.get("assignment_group")
    if isinstance(assignment_group, dict):
        assignment_group = assignment_group.get("display_value")

    problem = record.get("problem")
    if isinstance(problem, dict):
        problem = problem.get("display_value")

    return {
        "sys_id": record.get("sys_id"),
        "number": record.get("number"),
        "short_description": record.get("short_description"),
        "description": record.get("description"),
        "state": record.get("state"),
        "priority": record.get("priority"),
        "assigned_to": assigned_to,
        "assignment_group": assignment_group,
        "problem": problem,
        "close_notes": record.get("close_notes"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _resolve_problem_sys_id(
    instance_url: str,
    headers: Dict[str, str],
    problem_id: str,
) -> Optional[str]:
    """Return the sys_id for a problem number or passthrough if already a sys_id."""
    if len(problem_id) == 32 and all(c in "0123456789abcdef" for c in problem_id):
        return problem_id

    url = f"{instance_url}{PROBLEM_TABLE}"
    try:
        resp = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"number={problem_id}",
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


def _resolve_problem_task_sys_id(
    instance_url: str,
    headers: Dict[str, str],
    task_id: str,
) -> Optional[str]:
    """Return the sys_id for a problem_task number or passthrough if already a sys_id."""
    if len(task_id) == 32 and all(c in "0123456789abcdef" for c in task_id):
        return task_id

    url = f"{instance_url}{PROBLEM_TASK_TABLE}"
    try:
        resp = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"number={task_id}",
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


def create_problem_task(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a problem_task record linked to a parent problem.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateProblemTaskParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, ``number``, and ``task`` keys.
    """
    result = _unwrap_and_validate_params(
        params, CreateProblemTaskParams, required_fields=["problem_id", "short_description"]
    )
    if not result["success"]:
        return result
    validated: CreateProblemTaskParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}
    headers["Content-Type"] = "application/json"

    problem_sys_id = _resolve_problem_sys_id(instance_url, headers, validated.problem_id)
    if not problem_sys_id:
        return {"success": False, "message": f"Problem not found: {validated.problem_id}"}

    body: Dict[str, Any] = {
        "short_description": validated.short_description,
        "problem": problem_sys_id,
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

    url = f"{instance_url}{PROBLEM_TASK_TABLE}"
    try:
        resp = _make_request("POST", url, json=body, headers=headers)
        resp.raise_for_status()
        task = resp.json().get("result", {})
        return {
            "success": True,
            "message": f"Problem task created: {task.get('number')}",
            "sys_id": task.get("sys_id"),
            "number": task.get("number"),
            "task": _format_problem_task(task),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating problem task: {e}")
        return {"success": False, "message": f"Error creating problem task: {_format_http_error(e)}"}


def list_problem_tasks(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List problem_task records linked to a specific problem.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListProblemTasksParams.

    Returns:
        Dictionary with ``success``, ``tasks``, ``count``, and pagination keys.
    """
    result = _unwrap_and_validate_params(
        params, ListProblemTasksParams, required_fields=["problem_id"]
    )
    if not result["success"]:
        return result
    validated: ListProblemTasksParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    problem_sys_id = _resolve_problem_sys_id(instance_url, headers, validated.problem_id)
    if not problem_sys_id:
        return {"success": False, "message": f"Problem not found: {validated.problem_id}"}

    query_parts = [f"problem={problem_sys_id}"]
    if validated.state:
        query_parts.append(f"state={validated.state}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query="^".join(query_parts),
        exclude_reference_link=True,
        fields=",".join(PROBLEM_TASK_FIELDS),
    )
    query_params["sysparm_display_value"] = "true"

    url = f"{instance_url}{PROBLEM_TASK_TABLE}"
    try:
        resp = _make_request("GET", url, headers=headers, params=query_params)
        resp.raise_for_status()
        tasks = [_format_problem_task(r) for r in resp.json().get("result", [])]
        return _paginated_list_response(tasks, validated.limit, validated.offset, "tasks")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing problem tasks: {e}")
        return {"success": False, "message": f"Error listing problem tasks: {_format_http_error(e)}"}


def close_problem_task(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Close a problem task by setting its state to Closed Complete (3).

    Accepts a problem task number (e.g. PTASK0010001) or a 32-character sys_id.
    Optionally adds close_notes and work_notes.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CloseProblemTaskParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, ``number``, and ``task`` keys.
    """
    result = _unwrap_and_validate_params(
        params, CloseProblemTaskParams, required_fields=["task_id"]
    )
    if not result["success"]:
        return result
    validated: CloseProblemTaskParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}
    headers["Content-Type"] = "application/json"

    task_sys_id = _resolve_problem_task_sys_id(instance_url, headers, validated.task_id)
    if not task_sys_id:
        return {"success": False, "message": f"Problem task not found: {validated.task_id}"}

    body: Dict[str, Any] = {"state": "3"}
    if validated.close_notes is not None:
        body["close_notes"] = validated.close_notes
    if validated.work_notes is not None:
        body["work_notes"] = validated.work_notes

    url = f"{instance_url}{PROBLEM_TASK_TABLE}/{task_sys_id}"
    try:
        resp = _make_request("PATCH", url, json=body, headers=headers)
        if resp.status_code == 404:
            return {"success": False, "message": f"Problem task not found: {validated.task_id}"}
        resp.raise_for_status()
        task = resp.json().get("result", {})
        return {
            "success": True,
            "message": f"Problem task {validated.task_id} closed successfully",
            "sys_id": task_sys_id,
            "number": task.get("number", validated.task_id),
            "task": _format_problem_task(task),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error closing problem task: {e}")
        return {"success": False, "message": f"Error closing problem task: {_format_http_error(e)}"}
