"""
Problem management tools for the ServiceNow MCP server.

Provides tools for listing, retrieving, creating, updating, closing, and
managing workarounds for problem records via the /api/now/table/problem endpoint.
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
INCIDENT_TABLE = "/api/now/table/incident"

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


class CloseProblemParams(BaseModel):
    """Parameters for closing a problem."""

    problem_id: str = Field(
        ...,
        description="Problem number (e.g. PRB0001234) or sys_id (32-char hex)",
    )
    close_notes: Optional[str] = Field(None, description="Closure notes explaining how the problem was resolved")
    fix_notes: Optional[str] = Field(None, description="Description of the fix that was applied")
    cause_notes: Optional[str] = Field(None, description="Root-cause analysis notes")
    work_notes: Optional[str] = Field(None, description="Additional work notes to append on closure")


class CreateProblemWorkaroundParams(BaseModel):
    """Parameters for creating/setting a workaround on a problem."""

    problem_id: str = Field(
        ...,
        description="Problem number (e.g. PRB0001234) or sys_id (32-char hex)",
    )
    workaround: str = Field(
        ...,
        description="Workaround description — steps users can follow to avoid or mitigate the problem",
    )
    known_error: Optional[bool] = Field(
        None,
        description="If True, also mark the problem as a known error (sets known_error=true)",
    )
    work_notes: Optional[str] = Field(
        None,
        description="Optional work notes to append when recording the workaround",
    )


class GetProblemWorkaroundParams(BaseModel):
    """Parameters for retrieving the workaround of a problem."""

    problem_id: str = Field(
        ...,
        description="Problem number (e.g. PRB0001234) or sys_id (32-char hex)",
    )


class SetProblemRootCauseParams(BaseModel):
    """Parameters for setting root cause analysis fields on a problem."""

    problem_id: str = Field(
        ...,
        description="Problem number (e.g. PRB0001234) or sys_id (32-char hex)",
    )
    cause_notes: Optional[str] = Field(None, description="Root cause analysis notes describing why the problem occurred")
    fix_notes: Optional[str] = Field(None, description="Fix implementation notes")
    corrective_actions: Optional[str] = Field(None, description="Corrective actions to prevent recurrence")
    resolution_code: Optional[str] = Field(
        None,
        description="Resolution code: fix_applied, risk_accepted, canceled, or duplicate",
    )
    problem_state: Optional[str] = Field(
        None,
        description="Problem state: '2' (Root Cause Analysis), '3' (Fix in Progress), '4' (Resolved)",
    )
    work_notes: Optional[str] = Field(None, description="Internal work notes to attach to the problem")


class GetProblemRootCauseParams(BaseModel):
    """Parameters for retrieving root cause analysis details from a problem."""

    problem_id: str = Field(
        ...,
        description="Problem number (e.g. PRB0001234) or sys_id (32-char hex)",
    )


class LinkIncidentToProblemParams(BaseModel):
    """Parameters for linking an incident to a problem."""

    incident_id: str = Field(
        ...,
        description="Incident number (e.g. INC0001234) or sys_id (32-char hex)",
    )
    problem_id: str = Field(
        ...,
        description="Problem number (e.g. PRB0001234) or sys_id (32-char hex)",
    )
    work_notes: Optional[str] = Field(None, description="Optional work note to attach to the incident")


class ListProblemRelatedIncidentsParams(BaseModel):
    """Parameters for listing incidents linked to a problem."""

    problem_id: str = Field(
        ...,
        description="Problem number (e.g. PRB0001234) or sys_id (32-char hex)",
    )
    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    state: Optional[str] = Field(None, description="Filter by incident state value")


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


def close_problem(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Close a problem record by setting its state to Closed (4).

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CloseProblemParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, ``number``, and ``problem`` keys.
    """
    result = _unwrap_and_validate_params(
        params, CloseProblemParams, required_fields=["problem_id"]
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

    body: Dict[str, Any] = {"state": "4"}
    if validated.close_notes is not None:
        body["close_notes"] = validated.close_notes
    if validated.fix_notes is not None:
        body["fix_notes"] = validated.fix_notes
    if validated.cause_notes is not None:
        body["cause_notes"] = validated.cause_notes
    if validated.work_notes is not None:
        body["work_notes"] = validated.work_notes

    url = f"{instance_url}{PROBLEM_TABLE}/{sys_id}"
    try:
        response = _make_request("PATCH", url, headers=headers, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"Problem not found: {validated.problem_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": "Problem closed successfully",
            "sys_id": record.get("sys_id") or sys_id,
            "number": record.get("number"),
            "problem": _format_problem(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error closing problem: {e}")
        return {"success": False, "message": f"Error closing problem: {_format_http_error(e)}"}


def create_problem_workaround(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Set a workaround on a problem record in ServiceNow.

    PATCHes the problem's ``workaround`` field and optionally marks it as a
    known error.  Use this when a workaround is found during root-cause
    analysis so it is recorded on the problem for users and service desk staff.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateProblemWorkaroundParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, ``number``, and ``problem`` keys.
    """
    result = _unwrap_and_validate_params(
        params, CreateProblemWorkaroundParams, required_fields=["problem_id", "workaround"]
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

    body: Dict[str, Any] = {"workaround": validated.workaround}
    if validated.known_error is not None:
        body["known_error"] = "true" if validated.known_error else "false"
    if validated.work_notes is not None:
        body["work_notes"] = validated.work_notes

    url = f"{instance_url}{PROBLEM_TABLE}/{sys_id}"
    try:
        response = _make_request("PATCH", url, headers=headers, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"Problem not found: {validated.problem_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": "Problem workaround recorded successfully",
            "sys_id": record.get("sys_id") or sys_id,
            "number": record.get("number"),
            "problem": _format_problem(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error setting problem workaround: {e}")
        return {"success": False, "message": f"Error setting problem workaround: {_format_http_error(e)}"}


def get_problem_workaround(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve the workaround details for a problem record.

    Returns the ``workaround`` text and related fields (``known_error``,
    ``state``, ``problem_state``) so callers can quickly check whether a
    workaround is available without fetching the full problem record.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetProblemWorkaroundParams.

    Returns:
        Dictionary with ``success`` and ``workaround_info`` keys.
        ``workaround_info`` includes ``sys_id``, ``number``,
        ``short_description``, ``workaround``, ``known_error``,
        ``state``, and ``problem_state``.
    """
    result = _unwrap_and_validate_params(
        params, GetProblemWorkaroundParams, required_fields=["problem_id"]
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

    workaround_fields = "sys_id,number,short_description,workaround,known_error,state,problem_state"

    # Direct sys_id fetch
    if len(validated.problem_id) == 32 and all(c in "0123456789abcdef" for c in validated.problem_id):
        url = f"{instance_url}{PROBLEM_TABLE}/{validated.problem_id}"
        try:
            response = _make_request(
                "GET",
                url,
                headers=headers,
                params={
                    "sysparm_fields": workaround_fields,
                    "sysparm_display_value": "true",
                    "sysparm_exclude_reference_link": "true",
                },
            )
            if response.status_code == 404:
                return {"success": False, "message": f"Problem not found: {validated.problem_id}"}
            response.raise_for_status()
            record = response.json().get("result", {})
            if not record:
                return {"success": False, "message": f"Problem not found: {validated.problem_id}"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving problem workaround: {e}")
            return {"success": False, "message": f"Error retrieving problem workaround: {_format_http_error(e)}"}
    else:
        # Number-based lookup
        url = f"{instance_url}{PROBLEM_TABLE}"
        try:
            response = _make_request(
                "GET",
                url,
                headers=headers,
                params={
                    "sysparm_query": f"number={validated.problem_id}",
                    "sysparm_limit": 1,
                    "sysparm_fields": workaround_fields,
                    "sysparm_display_value": "true",
                    "sysparm_exclude_reference_link": "true",
                },
            )
            response.raise_for_status()
            records = response.json().get("result", [])
            if not records:
                return {"success": False, "message": f"Problem not found: {validated.problem_id}"}
            record = records[0]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving problem workaround: {e}")
            return {"success": False, "message": f"Error retrieving problem workaround: {_format_http_error(e)}"}

    known_error_raw = record.get("known_error", "false")
    known_error_bool = known_error_raw in (True, "true", "1")

    return {
        "success": True,
        "workaround_info": {
            "sys_id": record.get("sys_id"),
            "number": record.get("number"),
            "short_description": record.get("short_description"),
            "workaround": record.get("workaround") or "",
            "has_workaround": bool(record.get("workaround")),
            "known_error": known_error_bool,
            "state": record.get("state"),
            "problem_state": record.get("problem_state"),
        },
    }


def set_problem_root_cause(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Record root cause analysis findings on a problem record.

    PATCHes root-cause-specific fields (cause_notes, fix_notes,
    corrective_actions, resolution_code, problem_state) so analysts can
    capture RCA details without touching unrelated problem fields.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching SetProblemRootCauseParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, ``number``, and ``problem`` keys.
    """
    result = _unwrap_and_validate_params(
        params, SetProblemRootCauseParams, required_fields=["problem_id"]
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
    if validated.cause_notes is not None:
        body["cause_notes"] = validated.cause_notes
    if validated.fix_notes is not None:
        body["fix_notes"] = validated.fix_notes
    if validated.corrective_actions is not None:
        body["additional_assignee_list"] = validated.corrective_actions
    if validated.resolution_code is not None:
        body["resolution_code"] = validated.resolution_code
    if validated.problem_state is not None:
        body["problem_state"] = validated.problem_state
    if validated.work_notes is not None:
        body["work_notes"] = validated.work_notes

    if not body:
        return {"success": False, "message": "No root cause fields provided to update"}

    url = f"{instance_url}{PROBLEM_TABLE}/{sys_id}"
    try:
        response = _make_request("PATCH", url, headers=headers, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"Problem not found: {validated.problem_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": "Problem root cause analysis updated successfully",
            "sys_id": record.get("sys_id") or sys_id,
            "number": record.get("number"),
            "problem": _format_problem(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error setting problem root cause: {e}")
        return {"success": False, "message": f"Error setting problem root cause: {_format_http_error(e)}"}


def get_problem_root_cause(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve root cause analysis details for a problem record.

    Returns RCA-specific fields so callers can quickly assess the current
    investigation state without fetching the full problem record.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetProblemRootCauseParams.

    Returns:
        Dictionary with ``success`` and ``rca_info`` keys.
    """
    result = _unwrap_and_validate_params(
        params, GetProblemRootCauseParams, required_fields=["problem_id"]
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

    rca_fields = (
        "sys_id,number,short_description,state,problem_state,"
        "cause_notes,fix_notes,workaround,known_error,"
        "resolution_code,resolved_at,closed_at,assigned_to,assignment_group"
    )

    if len(validated.problem_id) == 32 and all(c in "0123456789abcdef" for c in validated.problem_id):
        url = f"{instance_url}{PROBLEM_TABLE}/{validated.problem_id}"
        try:
            response = _make_request(
                "GET",
                url,
                headers=headers,
                params={
                    "sysparm_fields": rca_fields,
                    "sysparm_display_value": "true",
                    "sysparm_exclude_reference_link": "true",
                },
            )
            if response.status_code == 404:
                return {"success": False, "message": f"Problem not found: {validated.problem_id}"}
            response.raise_for_status()
            record = response.json().get("result", {})
            if not record:
                return {"success": False, "message": f"Problem not found: {validated.problem_id}"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving problem root cause: {e}")
            return {"success": False, "message": f"Error retrieving problem root cause: {_format_http_error(e)}"}
    else:
        url = f"{instance_url}{PROBLEM_TABLE}"
        try:
            response = _make_request(
                "GET",
                url,
                headers=headers,
                params={
                    "sysparm_query": f"number={validated.problem_id}",
                    "sysparm_limit": 1,
                    "sysparm_fields": rca_fields,
                    "sysparm_display_value": "true",
                    "sysparm_exclude_reference_link": "true",
                },
            )
            response.raise_for_status()
            records = response.json().get("result", [])
            if not records:
                return {"success": False, "message": f"Problem not found: {validated.problem_id}"}
            record = records[0]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving problem root cause: {e}")
            return {"success": False, "message": f"Error retrieving problem root cause: {_format_http_error(e)}"}

    def _display(val):
        if isinstance(val, dict):
            return val.get("display_value") or val.get("value") or ""
        return val or ""

    known_error_raw = record.get("known_error", "false")
    known_error_bool = known_error_raw in (True, "true", "1")

    problem_state_map = {
        "1": "Open",
        "2": "Root Cause Analysis",
        "3": "Fix in Progress",
        "4": "Resolved",
        "5": "Closed",
        "107": "Known Error",
    }
    problem_state_raw = _display(record.get("problem_state", ""))
    problem_state_label = problem_state_map.get(problem_state_raw, problem_state_raw)

    return {
        "success": True,
        "rca_info": {
            "sys_id": record.get("sys_id"),
            "number": record.get("number"),
            "short_description": _display(record.get("short_description")),
            "state": _display(record.get("state")),
            "problem_state": problem_state_label,
            "cause_notes": record.get("cause_notes") or "",
            "has_root_cause": bool(record.get("cause_notes")),
            "fix_notes": record.get("fix_notes") or "",
            "workaround": record.get("workaround") or "",
            "known_error": known_error_bool,
            "resolution_code": _display(record.get("resolution_code")),
            "resolved_at": _display(record.get("resolved_at")),
            "closed_at": _display(record.get("closed_at")),
            "assigned_to": _display(record.get("assigned_to")),
            "assignment_group": _display(record.get("assignment_group")),
        },
    }


def link_incident_to_problem(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Link an incident to a problem record.

    PATCHes the incident's ``problem_id`` field so the incident appears in
    the problem's related-incidents list.  Useful during root-cause analysis
    to associate impacted incidents with the underlying problem.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching LinkIncidentToProblemParams.

    Returns:
        Dictionary with ``success``, ``incident_sys_id``, ``problem_sys_id``, and ``message`` keys.
    """
    result = _unwrap_and_validate_params(
        params, LinkIncidentToProblemParams, required_fields=["incident_id", "problem_id"]
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

    # Resolve problem sys_id
    prob_resolve = _resolve_problem_sys_id(validated.problem_id, instance_url, headers)
    if not prob_resolve["success"]:
        return prob_resolve
    problem_sys_id = prob_resolve["sys_id"]

    # Resolve incident sys_id
    if len(validated.incident_id) == 32 and all(c in "0123456789abcdef" for c in validated.incident_id):
        incident_sys_id = validated.incident_id
    else:
        inc_url = f"{instance_url}{INCIDENT_TABLE}"
        try:
            inc_response = _make_request(
                "GET",
                inc_url,
                headers=headers,
                params={
                    "sysparm_query": f"number={validated.incident_id}",
                    "sysparm_limit": 1,
                    "sysparm_fields": "sys_id",
                },
            )
            inc_response.raise_for_status()
            inc_records = inc_response.json().get("result", [])
            if not inc_records:
                return {"success": False, "message": f"Incident not found: {validated.incident_id}"}
            incident_sys_id = inc_records[0]["sys_id"]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error resolving incident: {e}")
            return {"success": False, "message": f"Error resolving incident: {_format_http_error(e)}"}

    # Patch incident with problem_id
    body: Dict[str, Any] = {"problem_id": problem_sys_id}
    if validated.work_notes is not None:
        body["work_notes"] = validated.work_notes

    inc_patch_url = f"{instance_url}{INCIDENT_TABLE}/{incident_sys_id}"
    try:
        response = _make_request("PATCH", inc_patch_url, headers=headers, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"Incident not found: {validated.incident_id}"}
        response.raise_for_status()
        return {
            "success": True,
            "message": "Incident linked to problem successfully",
            "incident_sys_id": incident_sys_id,
            "problem_sys_id": problem_sys_id,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error linking incident to problem: {e}")
        return {"success": False, "message": f"Error linking incident to problem: {_format_http_error(e)}"}


def list_problem_related_incidents(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List incidents linked to a problem record.

    Queries the incident table for records whose ``problem_id`` field
    references the given problem.  Useful for assessing the blast radius
    during root-cause analysis.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListProblemRelatedIncidentsParams.

    Returns:
        Dictionary with ``success``, ``incidents``, ``total``, ``has_more``,
        and ``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(
        params, ListProblemRelatedIncidentsParams, required_fields=["problem_id"]
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

    # Resolve problem sys_id
    prob_resolve = _resolve_problem_sys_id(validated.problem_id, instance_url, headers)
    if not prob_resolve["success"]:
        return prob_resolve
    problem_sys_id = prob_resolve["sys_id"]

    query_parts = [f"problem_id={problem_sys_id}"]
    if validated.state is not None:
        query_parts.append(f"state={validated.state}")

    inc_url = f"{instance_url}{INCIDENT_TABLE}"
    query_params = _build_sysparm_params(
        query=_join_query_parts(query_parts),
        limit=validated.limit,
        offset=validated.offset,
        fields="sys_id,number,short_description,state,priority,assigned_to,assignment_group,sys_created_on,sys_updated_on,resolved_at",
        display_value="true",
        exclude_reference_link=True,
    )

    try:
        response = _make_request("GET", inc_url, headers=headers, params=query_params)
        response.raise_for_status()
        records = response.json().get("result", [])

        def _display(val):
            if isinstance(val, dict):
                return val.get("display_value") or val.get("value") or ""
            return val or ""

        incidents = [
            {
                "sys_id": r.get("sys_id"),
                "number": r.get("number"),
                "short_description": _display(r.get("short_description")),
                "state": _display(r.get("state")),
                "priority": _display(r.get("priority")),
                "assigned_to": _display(r.get("assigned_to")),
                "assignment_group": _display(r.get("assignment_group")),
                "sys_created_on": _display(r.get("sys_created_on")),
                "sys_updated_on": _display(r.get("sys_updated_on")),
                "resolved_at": _display(r.get("resolved_at")),
            }
            for r in records
        ]

        return _paginated_list_response(
            incidents, validated.limit, validated.offset, result_key="incidents"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing problem related incidents: {e}")
        return {"success": False, "message": f"Error listing problem related incidents: {_format_http_error(e)}"}
