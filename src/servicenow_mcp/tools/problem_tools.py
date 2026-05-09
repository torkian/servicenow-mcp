"""
Problem management tools for the ServiceNow MCP server.

Provides tools for listing, retrieving, creating, and updating problem records
via the /api/now/table/problem endpoint.
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

PROBLEM_TABLE = "/api/now/table/problem"

PROBLEM_FIELDS = [
    "sys_id",
    "number",
    "short_description",
    "description",
    "state",
    "problem_state",
    "priority",
    "impact",
    "urgency",
    "category",
    "subcategory",
    "assigned_to",
    "assignment_group",
    "cause_notes",
    "fix_notes",
    "workaround",
    "known_error",
    "sys_created_on",
    "sys_updated_on",
    "resolved_at",
    "closed_at",
]


class ListProblemsParams(BaseModel):
    """Parameters for listing problems."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    state: Optional[str] = Field(None, description="Filter by problem state value (e.g. '1' for Open)")
    assigned_to: Optional[str] = Field(None, description="Filter by assigned user name or sys_id")
    assignment_group: Optional[str] = Field(None, description="Filter by assignment group name or sys_id")
    category: Optional[str] = Field(None, description="Filter by category")
    known_error: Optional[bool] = Field(None, description="If True, return only known-error problems")
    query: Optional[str] = Field(None, description="Free-text search on short_description and description")


class GetProblemParams(BaseModel):
    """Parameters for retrieving a single problem."""

    problem_id: str = Field(
        ...,
        description="Problem number (e.g. PRB0001234) or sys_id (32-char hex)",
    )


class CreateProblemParams(BaseModel):
    """Parameters for creating a new problem."""

    short_description: str = Field(..., description="Short description of the problem")
    description: Optional[str] = Field(None, description="Detailed description of the problem")
    category: Optional[str] = Field(None, description="Category of the problem")
    subcategory: Optional[str] = Field(None, description="Subcategory of the problem")
    priority: Optional[str] = Field(None, description="Priority (1=Critical, 2=High, 3=Moderate, 4=Low)")
    impact: Optional[str] = Field(None, description="Impact (1=High, 2=Medium, 3=Low)")
    urgency: Optional[str] = Field(None, description="Urgency (1=High, 2=Medium, 3=Low)")
    assigned_to: Optional[str] = Field(None, description="User name or sys_id to assign the problem to")
    assignment_group: Optional[str] = Field(None, description="Group name or sys_id for the assignment")
    workaround: Optional[str] = Field(None, description="Workaround description")
    known_error: Optional[bool] = Field(None, description="Mark as a known error")


class UpdateProblemParams(BaseModel):
    """Parameters for updating an existing problem."""

    problem_id: str = Field(
        ...,
        description="Problem number (e.g. PRB0001234) or sys_id (32-char hex)",
    )
    short_description: Optional[str] = Field(None, description="Updated short description")
    description: Optional[str] = Field(None, description="Updated detailed description")
    state: Optional[str] = Field(None, description="Updated state value")
    category: Optional[str] = Field(None, description="Updated category")
    subcategory: Optional[str] = Field(None, description="Updated subcategory")
    priority: Optional[str] = Field(None, description="Updated priority")
    impact: Optional[str] = Field(None, description="Updated impact")
    urgency: Optional[str] = Field(None, description="Updated urgency")
    assigned_to: Optional[str] = Field(None, description="Updated assignee user name or sys_id")
    assignment_group: Optional[str] = Field(None, description="Updated assignment group name or sys_id")
    workaround: Optional[str] = Field(None, description="Updated workaround description")
    known_error: Optional[bool] = Field(None, description="Update known-error flag")
    cause_notes: Optional[str] = Field(None, description="Root-cause analysis notes")
    fix_notes: Optional[str] = Field(None, description="Fix notes")
    work_notes: Optional[str] = Field(None, description="Work notes to append")
    close_notes: Optional[str] = Field(None, description="Closure notes")


def _format_problem(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw problem API record."""
    assigned_to = record.get("assigned_to")
    if isinstance(assigned_to, dict):
        assigned_to = assigned_to.get("display_value")

    assignment_group = record.get("assignment_group")
    if isinstance(assignment_group, dict):
        assignment_group = assignment_group.get("display_value")

    return {
        "sys_id": record.get("sys_id"),
        "number": record.get("number"),
        "short_description": record.get("short_description"),
        "description": record.get("description"),
        "state": record.get("state"),
        "priority": record.get("priority"),
        "impact": record.get("impact"),
        "urgency": record.get("urgency"),
        "category": record.get("category"),
        "subcategory": record.get("subcategory"),
        "assigned_to": assigned_to,
        "assignment_group": assignment_group,
        "cause_notes": record.get("cause_notes"),
        "fix_notes": record.get("fix_notes"),
        "workaround": record.get("workaround"),
        "known_error": record.get("known_error"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "resolved_at": record.get("resolved_at"),
        "closed_at": record.get("closed_at"),
    }


def _resolve_problem_sys_id(
    problem_id: str,
    instance_url: str,
    headers: Dict,
) -> Dict[str, Any]:
    """Return the sys_id for a problem number or pass through a sys_id unchanged."""
    # 32-char hex string -> treat as sys_id
    if len(problem_id) == 32 and all(c in "0123456789abcdef" for c in problem_id):
        return {"success": True, "sys_id": problem_id}

    url = f"{instance_url}{PROBLEM_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={"sysparm_query": f"number={problem_id}", "sysparm_limit": 1},
        )
        response.raise_for_status()
        result = response.json().get("result", [])
        if not result:
            return {"success": False, "message": f"Problem not found: {problem_id}"}
        return {"success": True, "sys_id": result[0]["sys_id"]}
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Error looking up problem: {_format_http_error(e)}"}


def list_problems(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List problem records from ServiceNow.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListProblemsParams.

    Returns:
        Dictionary with ``success``, ``problems`` (list), ``count``, and
        pagination keys.
    """
    result = _unwrap_and_validate_params(params, ListProblemsParams)
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
    if validated.state is not None:
        filters.append(f"state={validated.state}")
    if validated.assigned_to:
        filters.append(f"assigned_to={validated.assigned_to}")
    if validated.assignment_group:
        filters.append(f"assignment_group={validated.assignment_group}")
    if validated.category:
        filters.append(f"category={validated.category}")
    if validated.known_error is not None:
        filters.append(f"known_error={'true' if validated.known_error else 'false'}")
    if validated.query:
        filters.append(
            f"short_descriptionLIKE{validated.query}^ORdescriptionLIKE{validated.query}"
        )

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(filters),
        exclude_reference_link=True,
        fields=",".join(PROBLEM_FIELDS),
    )

    url = f"{instance_url}{PROBLEM_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        problems = [_format_problem(r) for r in response.json().get("result", [])]
        return _paginated_list_response(problems, validated.limit, validated.offset, "problems")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing problems: {e}")
        return {"success": False, "message": f"Error listing problems: {_format_http_error(e)}"}


def get_problem(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single problem record by number or sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetProblemParams.

    Returns:
        Dictionary with ``success`` and ``problem`` keys.
    """
    result = _unwrap_and_validate_params(params, GetProblemParams, required_fields=["problem_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    # Decide between direct sys_id fetch and number lookup
    if len(validated.problem_id) == 32 and all(c in "0123456789abcdef" for c in validated.problem_id):
        url = f"{instance_url}{PROBLEM_TABLE}/{validated.problem_id}"
        try:
            response = _make_request(
                "GET", url, headers=headers,
                params={"sysparm_display_value": "true", "sysparm_exclude_reference_link": "true"},
            )
            if response.status_code == 404:
                return {"success": False, "message": f"Problem not found: {validated.problem_id}"}
            response.raise_for_status()
            record = response.json().get("result", {})
            if not record:
                return {"success": False, "message": f"Problem not found: {validated.problem_id}"}
            return {"success": True, "problem": _format_problem(record)}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving problem: {e}")
            return {"success": False, "message": f"Error retrieving problem: {_format_http_error(e)}"}
    else:
        url = f"{instance_url}{PROBLEM_TABLE}"
        try:
            response = _make_request(
                "GET", url, headers=headers,
                params={
                    "sysparm_query": f"number={validated.problem_id}",
                    "sysparm_limit": 1,
                    "sysparm_display_value": "true",
                    "sysparm_exclude_reference_link": "true",
                },
            )
            response.raise_for_status()
            records = response.json().get("result", [])
            if not records:
                return {"success": False, "message": f"Problem not found: {validated.problem_id}"}
            return {"success": True, "problem": _format_problem(records[0])}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving problem: {e}")
            return {"success": False, "message": f"Error retrieving problem: {_format_http_error(e)}"}


def create_problem(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new problem record in ServiceNow.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateProblemParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, and ``number`` keys.
    """
    result = _unwrap_and_validate_params(
        params, CreateProblemParams, required_fields=["short_description"]
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

    body: Dict[str, Any] = {"short_description": validated.short_description}
    if validated.description is not None:
        body["description"] = validated.description
    if validated.category is not None:
        body["category"] = validated.category
    if validated.subcategory is not None:
        body["subcategory"] = validated.subcategory
    if validated.priority is not None:
        body["priority"] = validated.priority
    if validated.impact is not None:
        body["impact"] = validated.impact
    if validated.urgency is not None:
        body["urgency"] = validated.urgency
    if validated.assigned_to is not None:
        body["assigned_to"] = validated.assigned_to
    if validated.assignment_group is not None:
        body["assignment_group"] = validated.assignment_group
    if validated.workaround is not None:
        body["workaround"] = validated.workaround
    if validated.known_error is not None:
        body["known_error"] = "true" if validated.known_error else "false"

    url = f"{instance_url}{PROBLEM_TABLE}"
    try:
        response = _make_request("POST", url, headers=headers, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": "Problem created successfully",
            "sys_id": record.get("sys_id"),
            "number": record.get("number"),
            "problem": _format_problem(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating problem: {e}")
        return {"success": False, "message": f"Error creating problem: {_format_http_error(e)}"}


def update_problem(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing problem record in ServiceNow.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdateProblemParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, and ``number`` keys.
    """
    result = _unwrap_and_validate_params(
        params, UpdateProblemParams, required_fields=["problem_id"]
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

    resolve = _resolve_problem_sys_id(validated.problem_id, instance_url, headers)
    if not resolve["success"]:
        return resolve
    sys_id = resolve["sys_id"]

    body: Dict[str, Any] = {}
    if validated.short_description is not None:
        body["short_description"] = validated.short_description
    if validated.description is not None:
        body["description"] = validated.description
    if validated.state is not None:
        body["state"] = validated.state
    if validated.category is not None:
        body["category"] = validated.category
    if validated.subcategory is not None:
        body["subcategory"] = validated.subcategory
    if validated.priority is not None:
        body["priority"] = validated.priority
    if validated.impact is not None:
        body["impact"] = validated.impact
    if validated.urgency is not None:
        body["urgency"] = validated.urgency
    if validated.assigned_to is not None:
        body["assigned_to"] = validated.assigned_to
    if validated.assignment_group is not None:
        body["assignment_group"] = validated.assignment_group
    if validated.workaround is not None:
        body["workaround"] = validated.workaround
    if validated.known_error is not None:
        body["known_error"] = "true" if validated.known_error else "false"
    if validated.cause_notes is not None:
        body["cause_notes"] = validated.cause_notes
    if validated.fix_notes is not None:
        body["fix_notes"] = validated.fix_notes
    if validated.work_notes is not None:
        body["work_notes"] = validated.work_notes
    if validated.close_notes is not None:
        body["close_notes"] = validated.close_notes

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    url = f"{instance_url}{PROBLEM_TABLE}/{sys_id}"
    try:
        response = _make_request("PATCH", url, headers=headers, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": "Problem updated successfully",
            "sys_id": record.get("sys_id") or sys_id,
            "number": record.get("number"),
            "problem": _format_problem(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating problem: {e}")
        return {"success": False, "message": f"Error updating problem: {_format_http_error(e)}"}
