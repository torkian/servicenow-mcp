"""
Service request management tools for the ServiceNow MCP server.

Provides tools for listing, retrieving, creating, and updating service request
records via the /api/now/table/sc_request endpoint, and listing requested items
(sc_req_item) within a request.
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

REQUEST_TABLE = "/api/now/table/sc_request"
REQUEST_ITEM_TABLE = "/api/now/table/sc_req_item"

REQUEST_ITEM_FIELDS = [
    "sys_id",
    "number",
    "short_description",
    "description",
    "state",
    "stage",
    "cat_item",
    "quantity",
    "price",
    "request",
    "assigned_to",
    "assignment_group",
    "opened_by",
    "sys_created_on",
    "sys_updated_on",
]

REQUEST_FIELDS = [
    "sys_id",
    "number",
    "short_description",
    "description",
    "state",
    "stage",
    "priority",
    "urgency",
    "impact",
    "requested_for",
    "opened_by",
    "assigned_to",
    "assignment_group",
    "approval",
    "comments",
    "work_notes",
    "due_date",
    "opened_at",
    "closed_at",
    "sys_created_on",
    "sys_updated_on",
]


class ListRequestsParams(BaseModel):
    """Parameters for listing service requests."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    state: Optional[str] = Field(
        None,
        description=(
            "Filter by request state value: 1=Draft, 2=Submitted, 3=In Process, "
            "4=Closed Complete, 5=Closed Incomplete, 6=Cancelled, 7=Closed Skipped"
        ),
    )
    requested_for: Optional[str] = Field(
        None, description="Filter by the user the request was made for (user name or sys_id)"
    )
    assigned_to: Optional[str] = Field(
        None, description="Filter by assigned user (user name or sys_id)"
    )
    assignment_group: Optional[str] = Field(
        None, description="Filter by assignment group name or sys_id"
    )
    approval: Optional[str] = Field(
        None,
        description="Filter by approval state: requested, approved, rejected, not_requested",
    )
    query: Optional[str] = Field(
        None, description="Free-text search on short_description and description"
    )


class GetRequestParams(BaseModel):
    """Parameters for retrieving a single service request."""

    request_id: str = Field(
        ...,
        description="Request number (e.g. REQ0010001) or sys_id (32-char hex)",
    )


class CreateRequestParams(BaseModel):
    """Parameters for creating a new service request."""

    short_description: str = Field(..., description="Short description of the request")
    description: Optional[str] = Field(None, description="Detailed description of the request")
    requested_for: Optional[str] = Field(
        None, description="User name or sys_id the request is for (defaults to the caller)"
    )
    assignment_group: Optional[str] = Field(
        None, description="Group name or sys_id to assign the request to"
    )
    assigned_to: Optional[str] = Field(
        None, description="User name or sys_id to assign the request to"
    )
    priority: Optional[str] = Field(
        None, description="Priority: 1=Critical, 2=High, 3=Moderate, 4=Low"
    )
    urgency: Optional[str] = Field(None, description="Urgency: 1=High, 2=Medium, 3=Low")
    impact: Optional[str] = Field(None, description="Impact: 1=High, 2=Medium, 3=Low")
    due_date: Optional[str] = Field(None, description="Due date in YYYY-MM-DD format")
    comments: Optional[str] = Field(None, description="Initial comments to add to the request")


class UpdateRequestParams(BaseModel):
    """Parameters for updating an existing service request."""

    request_id: str = Field(
        ...,
        description="Request number (e.g. REQ0010001) or sys_id (32-char hex)",
    )
    short_description: Optional[str] = Field(None, description="Updated short description")
    description: Optional[str] = Field(None, description="Updated detailed description")
    state: Optional[str] = Field(
        None,
        description=(
            "Updated state value: 1=Draft, 2=Submitted, 3=In Process, "
            "4=Closed Complete, 5=Closed Incomplete, 6=Cancelled, 7=Closed Skipped"
        ),
    )
    assigned_to: Optional[str] = Field(None, description="Updated assignee user name or sys_id")
    assignment_group: Optional[str] = Field(
        None, description="Updated assignment group name or sys_id"
    )
    priority: Optional[str] = Field(None, description="Updated priority")
    urgency: Optional[str] = Field(None, description="Updated urgency")
    impact: Optional[str] = Field(None, description="Updated impact")
    due_date: Optional[str] = Field(None, description="Updated due date in YYYY-MM-DD format")
    work_notes: Optional[str] = Field(None, description="Work notes to append to the request")
    comments: Optional[str] = Field(None, description="Comments to append to the request")
    close_notes: Optional[str] = Field(None, description="Closure notes when closing the request")


def _format_request(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw sc_request API record."""
    requested_for = record.get("requested_for")
    if isinstance(requested_for, dict):
        requested_for = requested_for.get("display_value")

    opened_by = record.get("opened_by")
    if isinstance(opened_by, dict):
        opened_by = opened_by.get("display_value")

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
        "stage": record.get("stage"),
        "priority": record.get("priority"),
        "urgency": record.get("urgency"),
        "impact": record.get("impact"),
        "requested_for": requested_for,
        "opened_by": opened_by,
        "assigned_to": assigned_to,
        "assignment_group": assignment_group,
        "approval": record.get("approval"),
        "due_date": record.get("due_date"),
        "opened_at": record.get("opened_at"),
        "closed_at": record.get("closed_at"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _resolve_request_sys_id(
    request_id: str,
    instance_url: str,
    headers: Dict,
) -> Dict[str, Any]:
    """Return the sys_id for a request number or pass through a sys_id unchanged."""
    if len(request_id) == 32 and all(c in "0123456789abcdef" for c in request_id):
        return {"success": True, "sys_id": request_id}

    url = f"{instance_url}{REQUEST_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={"sysparm_query": f"number={request_id}", "sysparm_limit": 1},
        )
        response.raise_for_status()
        result = response.json().get("result", [])
        if not result:
            return {"success": False, "message": f"Request not found: {request_id}"}
        return {"success": True, "sys_id": result[0]["sys_id"]}
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Error looking up request: {_format_http_error(e)}"}


def list_requests(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List service request records from ServiceNow.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListRequestsParams.

    Returns:
        Dictionary with ``success``, ``requests`` (list), ``count``, and
        pagination keys.
    """
    result = _unwrap_and_validate_params(params, ListRequestsParams)
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
    if validated.requested_for:
        filters.append(f"requested_for={validated.requested_for}")
    if validated.assigned_to:
        filters.append(f"assigned_to={validated.assigned_to}")
    if validated.assignment_group:
        filters.append(f"assignment_group={validated.assignment_group}")
    if validated.approval:
        filters.append(f"approval={validated.approval}")
    if validated.query:
        filters.append(f"short_descriptionLIKE{validated.query}^ORdescriptionLIKE{validated.query}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(filters),
        exclude_reference_link=True,
        fields=",".join(REQUEST_FIELDS),
    )

    url = f"{instance_url}{REQUEST_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        service_requests = [_format_request(r) for r in response.json().get("result", [])]
        return _paginated_list_response(
            service_requests, validated.limit, validated.offset, "requests"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing requests: {e}")
        return {"success": False, "message": f"Error listing requests: {_format_http_error(e)}"}


def get_request(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single service request record by number or sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetRequestParams.

    Returns:
        Dictionary with ``success`` and ``request`` keys.
    """
    result = _unwrap_and_validate_params(params, GetRequestParams, required_fields=["request_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    display_params = {"sysparm_display_value": "true", "sysparm_exclude_reference_link": "true"}

    if len(validated.request_id) == 32 and all(
        c in "0123456789abcdef" for c in validated.request_id
    ):
        url = f"{instance_url}{REQUEST_TABLE}/{validated.request_id}"
        try:
            response = _make_request("GET", url, headers=headers, params=display_params)
            if response.status_code == 404:
                return {"success": False, "message": f"Request not found: {validated.request_id}"}
            response.raise_for_status()
            record = response.json().get("result", {})
            if not record:
                return {"success": False, "message": f"Request not found: {validated.request_id}"}
            return {"success": True, "request": _format_request(record)}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving request: {e}")
            return {
                "success": False,
                "message": f"Error retrieving request: {_format_http_error(e)}",
            }
    else:
        url = f"{instance_url}{REQUEST_TABLE}"
        try:
            response = _make_request(
                "GET",
                url,
                headers=headers,
                params={
                    "sysparm_query": f"number={validated.request_id}",
                    "sysparm_limit": 1,
                    **display_params,
                },
            )
            response.raise_for_status()
            records = response.json().get("result", [])
            if not records:
                return {"success": False, "message": f"Request not found: {validated.request_id}"}
            return {"success": True, "request": _format_request(records[0])}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving request: {e}")
            return {
                "success": False,
                "message": f"Error retrieving request: {_format_http_error(e)}",
            }


def create_request(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new service request record in ServiceNow.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateRequestParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, ``number``, and ``request`` keys.
    """
    result = _unwrap_and_validate_params(
        params, CreateRequestParams, required_fields=["short_description"]
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
    if validated.requested_for is not None:
        body["requested_for"] = validated.requested_for
    if validated.assignment_group is not None:
        body["assignment_group"] = validated.assignment_group
    if validated.assigned_to is not None:
        body["assigned_to"] = validated.assigned_to
    if validated.priority is not None:
        body["priority"] = validated.priority
    if validated.urgency is not None:
        body["urgency"] = validated.urgency
    if validated.impact is not None:
        body["impact"] = validated.impact
    if validated.due_date is not None:
        body["due_date"] = validated.due_date
    if validated.comments is not None:
        body["comments"] = validated.comments

    url = f"{instance_url}{REQUEST_TABLE}"
    try:
        response = _make_request("POST", url, headers=headers, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": "Request created successfully",
            "sys_id": record.get("sys_id"),
            "number": record.get("number"),
            "request": _format_request(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating request: {e}")
        return {"success": False, "message": f"Error creating request: {_format_http_error(e)}"}


def update_request(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing service request record in ServiceNow.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdateRequestParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, ``number``, and ``request`` keys.
    """
    result = _unwrap_and_validate_params(
        params, UpdateRequestParams, required_fields=["request_id"]
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

    resolve = _resolve_request_sys_id(validated.request_id, instance_url, headers)
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
    if validated.assigned_to is not None:
        body["assigned_to"] = validated.assigned_to
    if validated.assignment_group is not None:
        body["assignment_group"] = validated.assignment_group
    if validated.priority is not None:
        body["priority"] = validated.priority
    if validated.urgency is not None:
        body["urgency"] = validated.urgency
    if validated.impact is not None:
        body["impact"] = validated.impact
    if validated.due_date is not None:
        body["due_date"] = validated.due_date
    if validated.work_notes is not None:
        body["work_notes"] = validated.work_notes
    if validated.comments is not None:
        body["comments"] = validated.comments
    if validated.close_notes is not None:
        body["close_notes"] = validated.close_notes

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    url = f"{instance_url}{REQUEST_TABLE}/{sys_id}"
    try:
        response = _make_request("PATCH", url, headers=headers, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": "Request updated successfully",
            "sys_id": record.get("sys_id") or sys_id,
            "number": record.get("number"),
            "request": _format_request(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating request: {e}")
        return {"success": False, "message": f"Error updating request: {_format_http_error(e)}"}


# ---------------------------------------------------------------------------
# Request Item (sc_req_item) helpers and tool
# ---------------------------------------------------------------------------


class ListRequestItemsParams(BaseModel):
    """Parameters for listing requested items within a service request."""

    request_id: str = Field(
        ...,
        description=(
            "Request number (e.g. REQ0010001) or sys_id (32-char hex) whose "
            "requested items (RITM records) should be listed."
        ),
    )
    state: Optional[str] = Field(
        None,
        description=(
            "Filter by item state: 1=Pending Approval, 2=Approved, 3=Rejected, "
            "4=Fulfilled, 6=Cancelled, 7=Staged, 8=Pending, 16=Open, 17=Work In Progress, "
            "18=Closed Complete, 19=Closed Incomplete"
        ),
    )
    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")


def _format_request_item(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw sc_req_item API record."""
    cat_item = record.get("cat_item")
    if isinstance(cat_item, dict):
        cat_item = cat_item.get("display_value")

    request = record.get("request")
    if isinstance(request, dict):
        request = request.get("display_value")

    assigned_to = record.get("assigned_to")
    if isinstance(assigned_to, dict):
        assigned_to = assigned_to.get("display_value")

    assignment_group = record.get("assignment_group")
    if isinstance(assignment_group, dict):
        assignment_group = assignment_group.get("display_value")

    opened_by = record.get("opened_by")
    if isinstance(opened_by, dict):
        opened_by = opened_by.get("display_value")

    return {
        "sys_id": record.get("sys_id"),
        "number": record.get("number"),
        "short_description": record.get("short_description"),
        "description": record.get("description"),
        "state": record.get("state"),
        "stage": record.get("stage"),
        "cat_item": cat_item,
        "quantity": record.get("quantity"),
        "price": record.get("price"),
        "request": request,
        "assigned_to": assigned_to,
        "assignment_group": assignment_group,
        "opened_by": opened_by,
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def list_request_items(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List requested items (sc_req_item / RITM records) within a service request.

    Each service request (sc_request) may contain one or more requested items,
    each representing a specific catalog item ordered as part of that request.
    This tool returns those child records, optionally filtered by state.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListRequestItemsParams.

    Returns:
        Dictionary with ``success``, ``items`` (list), ``count``, and
        pagination keys ``has_more`` / ``next_offset``.
    """
    result = _unwrap_and_validate_params(
        params, ListRequestItemsParams, required_fields=["request_id"]
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

    # Resolve request_id to a sys_id so we can filter sc_req_item.request
    resolve = _resolve_request_sys_id(validated.request_id, instance_url, headers)
    if not resolve["success"]:
        return resolve
    request_sys_id = resolve["sys_id"]

    filters = [f"request={request_sys_id}"]
    if validated.state is not None:
        filters.append(f"state={validated.state}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(filters),
        exclude_reference_link=True,
        fields=",".join(REQUEST_ITEM_FIELDS),
    )

    url = f"{instance_url}{REQUEST_ITEM_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        items = [_format_request_item(r) for r in response.json().get("result", [])]
        return _paginated_list_response(items, validated.limit, validated.offset, "items")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing request items: {e}")
        return {
            "success": False,
            "message": f"Error listing request items: {_format_http_error(e)}",
        }
