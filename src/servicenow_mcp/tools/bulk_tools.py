"""
Bulk operations tools for the ServiceNow MCP server.

Wraps the ServiceNow Batch API (POST /api/now/v1/batch) so multiple
Table API calls can be executed in a single HTTP round-trip.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from pydantic import BaseModel, Field, field_validator

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.helpers import _format_http_error, _make_request

logger = logging.getLogger(__name__)

_SYS_ID_CHARS = frozenset("0123456789abcdefABCDEF")


def _is_sys_id(value: str) -> bool:
    return len(value) == 32 and all(c in _SYS_ID_CHARS for c in value)

_ALLOWED_METHODS = frozenset({"DELETE", "GET", "PATCH", "POST", "PUT"})


class BulkOperationRequest(BaseModel):
    """A single API call within a bulk batch request."""

    id: str = Field(..., description="Unique identifier for this request within the batch")
    method: str = Field(..., description="HTTP method: GET, POST, PUT, PATCH, or DELETE")
    url: str = Field(
        ...,
        description=(
            "Relative API path starting with /api/ "
            "(e.g. /api/now/v2/table/incident). "
            "Full URLs are accepted; the scheme and host are stripped automatically."
        ),
    )
    body: Optional[Dict[str, Any]] = Field(
        None,
        description="Request body for POST/PUT/PATCH operations; omit or set null for GET/DELETE",
    )

    @field_validator("method", mode="before")
    @classmethod
    def normalize_method(cls, v: str) -> str:
        upper = v.upper()
        if upper not in _ALLOWED_METHODS:
            raise ValueError(
                f"Invalid HTTP method '{v}'. Allowed: {sorted(_ALLOWED_METHODS)}"
            )
        return upper

    @field_validator("url", mode="before")
    @classmethod
    def ensure_relative_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme:
            path = parsed.path
            if parsed.query:
                path = f"{path}?{parsed.query}"
            return path
        return v


class BulkOperationsParams(BaseModel):
    """Parameters for executing a batch of ServiceNow API calls."""

    requests: List[BulkOperationRequest] = Field(
        ...,
        description="API calls to execute as one batch (1–100 requests).",
    )


def execute_bulk_operations(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: BulkOperationsParams,
) -> Dict[str, Any]:
    """Execute up to 100 ServiceNow API calls in a single batch HTTP request.

    Uses POST /api/now/v1/batch. Responses are returned in the same order as
    the input requests. Each result includes the original request id, HTTP
    status code, a boolean ok flag, and the parsed response body.
    """
    if not params.requests:
        return {"success": False, "message": "No requests provided"}

    if len(params.requests) > 100:
        return {
            "success": False,
            "message": f"Too many requests: {len(params.requests)} (maximum 100)",
        }

    # Build the batch payload; sub-request bodies must be JSON strings
    batch_payload: Dict[str, Any] = {
        "requests": [
            {
                "id": req.id,
                "method": req.method,
                "url": req.url,
                "headers": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Accept", "value": "application/json"},
                ],
                "body": json.dumps(req.body) if req.body is not None else "",
            }
            for req in params.requests
        ]
    }

    batch_url = f"{config.api_url}/v1/batch"

    try:
        response = _make_request("POST", 
            batch_url,
            json=batch_payload,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Batch request failed: %s", e)
        return {
            "success": False,
            "message": f"Batch request failed: {_format_http_error(e)}",
        }

    data = response.json()
    serviced = data.get("servicedRequests", [])

    results = []
    all_ok = True
    for item in serviced:
        status_code = item.get("statusCode", 0)
        ok = 200 <= status_code < 300

        raw_body = item.get("body", "")
        try:
            parsed_body = json.loads(raw_body) if raw_body else None
        except (json.JSONDecodeError, TypeError):
            parsed_body = raw_body

        if not ok:
            all_ok = False

        results.append(
            {
                "id": item.get("id"),
                "status_code": status_code,
                "status_text": item.get("statusText", ""),
                "ok": ok,
                "body": parsed_body,
            }
        )

    total = len(results)
    succeeded = sum(1 for r in results if r["ok"])

    return {
        "success": all_ok,
        "message": f"Batch completed: {succeeded}/{total} requests succeeded",
        "total": total,
        "succeeded": succeeded,
        "failed": total - succeeded,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Bulk update incidents
# ---------------------------------------------------------------------------

_INCIDENT_UPDATE_FIELDS = (
    "short_description",
    "description",
    "state",
    "category",
    "subcategory",
    "priority",
    "impact",
    "urgency",
    "assigned_to",
    "assignment_group",
    "work_notes",
    "close_notes",
    "close_code",
)


class IncidentUpdate(BaseModel):
    """One incident update within a bulk request."""

    incident_id: str = Field(
        ...,
        description="Incident number (e.g. INC0010001) or 32-character sys_id",
    )
    short_description: Optional[str] = Field(None, description="Short description")
    description: Optional[str] = Field(None, description="Detailed description")
    state: Optional[str] = Field(None, description="Incident state code (e.g. '2' = In Progress)")
    category: Optional[str] = Field(None, description="Category")
    subcategory: Optional[str] = Field(None, description="Subcategory")
    priority: Optional[str] = Field(None, description="Priority code")
    impact: Optional[str] = Field(None, description="Impact code")
    urgency: Optional[str] = Field(None, description="Urgency code")
    assigned_to: Optional[str] = Field(None, description="Assigned-to user name or sys_id")
    assignment_group: Optional[str] = Field(None, description="Assignment group name or sys_id")
    work_notes: Optional[str] = Field(None, description="Work notes to append")
    close_notes: Optional[str] = Field(None, description="Close notes")
    close_code: Optional[str] = Field(None, description="Close code")


class BulkUpdateIncidentsParams(BaseModel):
    """Parameters for bulk-updating multiple incidents in one batch call."""

    updates: List[IncidentUpdate] = Field(
        ...,
        description="List of incident updates (1–100 items). Each entry must include incident_id plus at least one field to change.",
    )


def _resolve_incident_numbers(
    config: ServerConfig,
    auth_manager: AuthManager,
    numbers: List[str],
) -> Dict[str, str]:
    """Resolve a list of incident numbers to sys_ids via a single GET.

    Returns a dict mapping number → sys_id for every number found.
    Raises requests.RequestException on HTTP failure.
    """
    query = "numberIN" + ",".join(numbers)
    response = _make_request(
        "GET",
        f"{config.api_url}/table/incident",
        params={
            "sysparm_query": query,
            "sysparm_fields": "sys_id,number",
            "sysparm_limit": len(numbers),
        },
        headers=auth_manager.get_headers(),
        timeout=config.timeout,
    )
    response.raise_for_status()
    return {r["number"]: r["sys_id"] for r in response.json().get("result", [])}


def bulk_update_incidents(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: BulkUpdateIncidentsParams,
) -> Dict[str, Any]:
    """PATCH multiple incidents in ServiceNow using a single Batch API call.

    Incident numbers are resolved to sys_ids with one preliminary GET request
    before the batch PATCH is issued. Up to 100 incidents can be updated per call.
    Each result entry reports the incident_id, ok flag, HTTP status, and response body.
    """
    if not params.updates:
        return {"success": False, "message": "No updates provided"}

    if len(params.updates) > 100:
        return {
            "success": False,
            "message": f"Too many updates: {len(params.updates)} (maximum 100)",
        }

    # Split: collect numbers that need resolution
    numbers_to_resolve: List[str] = [
        u.incident_id for u in params.updates if not _is_sys_id(u.incident_id)
    ]

    # Batch-resolve numbers → sys_ids
    number_to_sys_id: Dict[str, str] = {}
    if numbers_to_resolve:
        try:
            number_to_sys_id = _resolve_incident_numbers(
                config, auth_manager, numbers_to_resolve
            )
        except requests.RequestException as e:
            logger.error("Failed to resolve incident numbers: %s", e)
            return {
                "success": False,
                "message": f"Failed to resolve incident numbers: {_format_http_error(e)}",
            }

    # Build batch PATCH sub-requests
    batch_requests: List[BulkOperationRequest] = []
    unresolved: List[str] = []

    for idx, update in enumerate(params.updates):
        if _is_sys_id(update.incident_id):
            sys_id = update.incident_id
        else:
            sys_id = number_to_sys_id.get(update.incident_id)
            if sys_id is None:
                unresolved.append(update.incident_id)
                continue

        body = {
            field: getattr(update, field)
            for field in _INCIDENT_UPDATE_FIELDS
            if getattr(update, field) is not None
        }

        batch_requests.append(
            BulkOperationRequest(
                id=str(idx),
                method="PATCH",
                url=f"/api/now/v2/table/incident/{sys_id}",
                body=body if body else None,
            )
        )

    if unresolved:
        return {
            "success": False,
            "message": f"Incident(s) not found: {', '.join(unresolved)}",
            "unresolved": unresolved,
        }

    if not batch_requests:
        return {"success": False, "message": "No valid updates to execute"}

    bulk_params = BulkOperationsParams(requests=batch_requests)
    result = execute_bulk_operations(config, auth_manager, bulk_params)

    # Re-attach original incident_id to each result entry
    enriched = []
    for entry in result.get("results", []):
        original_idx = int(entry["id"])
        original_update = params.updates[original_idx]
        enriched.append({**entry, "incident_id": original_update.incident_id})

    result["results"] = enriched
    return result


# ---------------------------------------------------------------------------
# Bulk update change requests
# ---------------------------------------------------------------------------

_CHANGE_REQUEST_UPDATE_FIELDS = (
    "short_description",
    "description",
    "state",
    "type",
    "category",
    "risk",
    "impact",
    "priority",
    "assignment_group",
    "assigned_to",
    "start_date",
    "end_date",
    "work_notes",
)


class ChangeRequestUpdate(BaseModel):
    """One change request update within a bulk batch request."""

    change_id: str = Field(
        ...,
        description="Change request number (e.g. CHG0010001) or 32-character sys_id",
    )
    short_description: Optional[str] = Field(None, description="Short description")
    description: Optional[str] = Field(None, description="Detailed description")
    state: Optional[str] = Field(None, description="State code (e.g. '-1'=Draft, '0'=Open, '1'=Scheduled)")
    type: Optional[str] = Field(None, description="Change type: normal, standard, or emergency")
    category: Optional[str] = Field(None, description="Category")
    risk: Optional[str] = Field(None, description="Risk level: low, moderate, high, or very_high")
    impact: Optional[str] = Field(None, description="Impact code")
    priority: Optional[str] = Field(None, description="Priority code")
    assignment_group: Optional[str] = Field(None, description="Assignment group name or sys_id")
    assigned_to: Optional[str] = Field(None, description="Assigned-to user name or sys_id")
    start_date: Optional[str] = Field(None, description="Planned start date (YYYY-MM-DD HH:MM:SS)")
    end_date: Optional[str] = Field(None, description="Planned end date (YYYY-MM-DD HH:MM:SS)")
    work_notes: Optional[str] = Field(None, description="Work notes to append")


class BulkUpdateChangeRequestsParams(BaseModel):
    """Parameters for bulk-updating multiple change requests in one batch call."""

    updates: List[ChangeRequestUpdate] = Field(
        ...,
        description="List of change request updates (1–100 items). Each entry must include change_id plus at least one field to change.",
    )


def _resolve_change_request_numbers(
    config: ServerConfig,
    auth_manager: AuthManager,
    numbers: List[str],
) -> Dict[str, str]:
    """Resolve change request numbers to sys_ids via a single GET.

    Returns a dict mapping number → sys_id for every number found.
    Raises requests.RequestException on HTTP failure.
    """
    query = "numberIN" + ",".join(numbers)
    response = _make_request(
        "GET",
        f"{config.api_url}/table/change_request",
        params={
            "sysparm_query": query,
            "sysparm_fields": "sys_id,number",
            "sysparm_limit": len(numbers),
        },
        headers=auth_manager.get_headers(),
        timeout=config.timeout,
    )
    response.raise_for_status()
    return {r["number"]: r["sys_id"] for r in response.json().get("result", [])}


def bulk_update_change_requests(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: BulkUpdateChangeRequestsParams,
) -> Dict[str, Any]:
    """PATCH multiple change requests in ServiceNow using a single Batch API call.

    Change request numbers are resolved to sys_ids with one preliminary GET
    before the batch PATCH is issued. Up to 100 change requests per call.
    Each result entry reports the change_id, ok flag, HTTP status, and response body.
    """
    if not params.updates:
        return {"success": False, "message": "No updates provided"}

    if len(params.updates) > 100:
        return {
            "success": False,
            "message": f"Too many updates: {len(params.updates)} (maximum 100)",
        }

    numbers_to_resolve: List[str] = [
        u.change_id for u in params.updates if not _is_sys_id(u.change_id)
    ]

    number_to_sys_id: Dict[str, str] = {}
    if numbers_to_resolve:
        try:
            number_to_sys_id = _resolve_change_request_numbers(
                config, auth_manager, numbers_to_resolve
            )
        except requests.RequestException as e:
            logger.error("Failed to resolve change request numbers: %s", e)
            return {
                "success": False,
                "message": f"Failed to resolve change request numbers: {_format_http_error(e)}",
            }

    batch_requests: List[BulkOperationRequest] = []
    unresolved: List[str] = []

    for idx, update in enumerate(params.updates):
        if _is_sys_id(update.change_id):
            sys_id = update.change_id
        else:
            sys_id = number_to_sys_id.get(update.change_id)
            if sys_id is None:
                unresolved.append(update.change_id)
                continue

        body = {
            field: getattr(update, field)
            for field in _CHANGE_REQUEST_UPDATE_FIELDS
            if getattr(update, field) is not None
        }

        batch_requests.append(
            BulkOperationRequest(
                id=str(idx),
                method="PATCH",
                url=f"/api/now/v2/table/change_request/{sys_id}",
                body=body if body else None,
            )
        )

    if unresolved:
        return {
            "success": False,
            "message": f"Change request(s) not found: {', '.join(unresolved)}",
            "unresolved": unresolved,
        }

    if not batch_requests:
        return {"success": False, "message": "No valid updates to execute"}

    bulk_params = BulkOperationsParams(requests=batch_requests)
    result = execute_bulk_operations(config, auth_manager, bulk_params)

    enriched = []
    for entry in result.get("results", []):
        original_idx = int(entry["id"])
        original_update = params.updates[original_idx]
        enriched.append({**entry, "change_id": original_update.change_id})

    result["results"] = enriched
    return result


# ---------------------------------------------------------------------------
# Bulk update problems
# ---------------------------------------------------------------------------

_PROBLEM_UPDATE_FIELDS = (
    "short_description",
    "description",
    "state",
    "priority",
    "impact",
    "urgency",
    "assigned_to",
    "assignment_group",
    "work_notes",
    "known_error",
    "cause_notes",
    "fix_notes",
    "category",
)


class ProblemUpdate(BaseModel):
    """One problem update within a bulk batch request."""

    problem_id: str = Field(
        ...,
        description="Problem number (e.g. PRB0001234) or 32-character sys_id",
    )
    short_description: Optional[str] = Field(None, description="Short description")
    description: Optional[str] = Field(None, description="Detailed description")
    state: Optional[str] = Field(
        None, description="State code (e.g. '1'=Open, '2'=Known Error, '3'=Pending Change, '4'=Closed/Resolved)"
    )
    priority: Optional[str] = Field(None, description="Priority code")
    impact: Optional[str] = Field(None, description="Impact code")
    urgency: Optional[str] = Field(None, description="Urgency code")
    assigned_to: Optional[str] = Field(None, description="Assigned-to user name or sys_id")
    assignment_group: Optional[str] = Field(None, description="Assignment group name or sys_id")
    work_notes: Optional[str] = Field(None, description="Work notes to append")
    known_error: Optional[str] = Field(
        None, description="Mark as known error: 'true' or 'false'"
    )
    cause_notes: Optional[str] = Field(None, description="Root cause notes")
    fix_notes: Optional[str] = Field(None, description="Fix / workaround notes")
    category: Optional[str] = Field(None, description="Category")


class BulkUpdateProblemsParams(BaseModel):
    """Parameters for bulk-updating multiple problems in one batch call."""

    updates: List[ProblemUpdate] = Field(
        ...,
        description="List of problem updates (1–100 items). Each entry must include problem_id plus at least one field to change.",
    )


def _resolve_problem_numbers(
    config: ServerConfig,
    auth_manager: AuthManager,
    numbers: List[str],
) -> Dict[str, str]:
    """Resolve a list of problem numbers to sys_ids via a single GET.

    Returns a dict mapping number → sys_id for every number found.
    Raises requests.RequestException on HTTP failure.
    """
    query = "numberIN" + ",".join(numbers)
    response = _make_request(
        "GET",
        f"{config.api_url}/table/problem",
        params={
            "sysparm_query": query,
            "sysparm_fields": "sys_id,number",
            "sysparm_limit": len(numbers),
        },
        headers=auth_manager.get_headers(),
        timeout=config.timeout,
    )
    response.raise_for_status()
    return {r["number"]: r["sys_id"] for r in response.json().get("result", [])}


def bulk_update_problems(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: BulkUpdateProblemsParams,
) -> Dict[str, Any]:
    """PATCH multiple problems in ServiceNow using a single Batch API call.

    Problem numbers are resolved to sys_ids with one preliminary GET request
    before the batch PATCH is issued. Up to 100 problems can be updated per call.
    Each result entry reports the problem_id, ok flag, HTTP status, and response body.
    """
    if not params.updates:
        return {"success": False, "message": "No updates provided"}

    if len(params.updates) > 100:
        return {
            "success": False,
            "message": f"Too many updates: {len(params.updates)} (maximum 100)",
        }

    numbers_to_resolve: List[str] = [
        u.problem_id for u in params.updates if not _is_sys_id(u.problem_id)
    ]

    number_to_sys_id: Dict[str, str] = {}
    if numbers_to_resolve:
        try:
            number_to_sys_id = _resolve_problem_numbers(
                config, auth_manager, numbers_to_resolve
            )
        except requests.RequestException as e:
            logger.error("Failed to resolve problem numbers: %s", e)
            return {
                "success": False,
                "message": f"Failed to resolve problem numbers: {_format_http_error(e)}",
            }

    batch_requests: List[BulkOperationRequest] = []
    unresolved: List[str] = []

    for idx, update in enumerate(params.updates):
        if _is_sys_id(update.problem_id):
            sys_id = update.problem_id
        else:
            sys_id = number_to_sys_id.get(update.problem_id)
            if sys_id is None:
                unresolved.append(update.problem_id)
                continue

        body = {
            field: getattr(update, field)
            for field in _PROBLEM_UPDATE_FIELDS
            if getattr(update, field) is not None
        }

        batch_requests.append(
            BulkOperationRequest(
                id=str(idx),
                method="PATCH",
                url=f"/api/now/v2/table/problem/{sys_id}",
                body=body if body else None,
            )
        )

    if unresolved:
        return {
            "success": False,
            "message": f"Problem(s) not found: {', '.join(unresolved)}",
            "unresolved": unresolved,
        }

    if not batch_requests:
        return {"success": False, "message": "No valid updates to execute"}

    bulk_params = BulkOperationsParams(requests=batch_requests)
    result = execute_bulk_operations(config, auth_manager, bulk_params)

    enriched = []
    for entry in result.get("results", []):
        original_idx = int(entry["id"])
        original_update = params.updates[original_idx]
        enriched.append({**entry, "problem_id": original_update.problem_id})

    result["results"] = enriched
    return result


# ---------------------------------------------------------------------------
# Bulk update change tasks
# ---------------------------------------------------------------------------

_CHANGE_TASK_UPDATE_FIELDS = (
    "short_description",
    "description",
    "state",
    "assigned_to",
    "assignment_group",
    "planned_start_date",
    "planned_end_date",
    "work_notes",
    "close_notes",
)


class ChangeTaskUpdate(BaseModel):
    """One change task update within a bulk batch request."""

    task_id: str = Field(
        ...,
        description="Change task number (e.g. CTASK0001234) or 32-character sys_id",
    )
    short_description: Optional[str] = Field(None, description="Short description")
    description: Optional[str] = Field(None, description="Detailed description")
    state: Optional[str] = Field(
        None,
        description="State code (-5=Pending, 1=Open, 2=Work In Progress, 3=Closed Complete, 4=Closed Incomplete, 7=Closed Skipped)",
    )
    assigned_to: Optional[str] = Field(None, description="Assigned-to user name or sys_id")
    assignment_group: Optional[str] = Field(None, description="Assignment group name or sys_id")
    planned_start_date: Optional[str] = Field(None, description="Planned start date (YYYY-MM-DD HH:MM:SS)")
    planned_end_date: Optional[str] = Field(None, description="Planned end date (YYYY-MM-DD HH:MM:SS)")
    work_notes: Optional[str] = Field(None, description="Work notes to append")
    close_notes: Optional[str] = Field(None, description="Closure notes")


class BulkUpdateChangeTasksParams(BaseModel):
    """Parameters for bulk-updating multiple change tasks in one batch call."""

    updates: List[ChangeTaskUpdate] = Field(
        ...,
        description="List of change task updates (1–100 items). Each entry must include task_id plus at least one field to change.",
    )


def _resolve_change_task_numbers(
    config: ServerConfig,
    auth_manager: AuthManager,
    numbers: List[str],
) -> Dict[str, str]:
    """Resolve a list of CTASK numbers to sys_ids via a single GET.

    Returns a dict mapping number → sys_id for every number found.
    Raises requests.RequestException on HTTP failure.
    """
    query = "numberIN" + ",".join(numbers)
    response = _make_request(
        "GET",
        f"{config.api_url}/table/change_task",
        params={
            "sysparm_query": query,
            "sysparm_fields": "sys_id,number",
            "sysparm_limit": len(numbers),
        },
        headers=auth_manager.get_headers(),
        timeout=config.timeout,
    )
    response.raise_for_status()
    return {r["number"]: r["sys_id"] for r in response.json().get("result", [])}


def bulk_update_change_tasks(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: BulkUpdateChangeTasksParams,
) -> Dict[str, Any]:
    """PATCH multiple change tasks in ServiceNow using a single Batch API call.

    CTASK numbers are resolved to sys_ids with one preliminary GET request
    before the batch PATCH is issued. Up to 100 tasks can be updated per call.
    Each result entry reports the task_id, ok flag, HTTP status, and response body.
    """
    if not params.updates:
        return {"success": False, "message": "No updates provided"}

    if len(params.updates) > 100:
        return {
            "success": False,
            "message": f"Too many updates: {len(params.updates)} (maximum 100)",
        }

    numbers_to_resolve: List[str] = [
        u.task_id for u in params.updates if not _is_sys_id(u.task_id)
    ]

    number_to_sys_id: Dict[str, str] = {}
    if numbers_to_resolve:
        try:
            number_to_sys_id = _resolve_change_task_numbers(
                config, auth_manager, numbers_to_resolve
            )
        except requests.RequestException as e:
            logger.error("Failed to resolve change task numbers: %s", e)
            return {
                "success": False,
                "message": f"Failed to resolve change task numbers: {_format_http_error(e)}",
            }

    batch_requests: List[BulkOperationRequest] = []
    unresolved: List[str] = []

    for idx, update in enumerate(params.updates):
        if _is_sys_id(update.task_id):
            sys_id = update.task_id
        else:
            sys_id = number_to_sys_id.get(update.task_id)
            if sys_id is None:
                unresolved.append(update.task_id)
                continue

        body = {
            field: getattr(update, field)
            for field in _CHANGE_TASK_UPDATE_FIELDS
            if getattr(update, field) is not None
        }

        batch_requests.append(
            BulkOperationRequest(
                id=str(idx),
                method="PATCH",
                url=f"/api/now/v2/table/change_task/{sys_id}",
                body=body if body else None,
            )
        )

    if unresolved:
        return {
            "success": False,
            "message": f"Change task(s) not found: {', '.join(unresolved)}",
            "unresolved": unresolved,
        }

    if not batch_requests:
        return {"success": False, "message": "No valid updates to execute"}

    bulk_params = BulkOperationsParams(requests=batch_requests)
    result = execute_bulk_operations(config, auth_manager, bulk_params)

    enriched = []
    for entry in result.get("results", []):
        original_idx = int(entry["id"])
        original_update = params.updates[original_idx]
        enriched.append({**entry, "task_id": original_update.task_id})

    result["results"] = enriched
    return result
