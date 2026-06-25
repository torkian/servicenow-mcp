"""
Change management tools for the ServiceNow MCP server.

This module provides tools for managing change requests in ServiceNow.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field, field_validator

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
    validate_servicenow_datetime,
)

logger = logging.getLogger(__name__)


class CreateChangeRequestParams(BaseModel):
    """Parameters for creating a change request."""

    short_description: str = Field(..., description="Short description of the change request")
    description: Optional[str] = Field(None, description="Detailed description of the change request")
    type: str = Field(..., description="Type of change (normal, standard, emergency)")
    risk: Optional[str] = Field(None, description="Risk level of the change")
    impact: Optional[str] = Field(None, description="Impact of the change")
    category: Optional[str] = Field(None, description="Category of the change")
    requested_by: Optional[str] = Field(None, description="User who requested the change")
    assignment_group: Optional[str] = Field(None, description="Group assigned to the change")
    start_date: Optional[str] = Field(None, description="Planned start date (YYYY-MM-DD HH:MM:SS)")
    end_date: Optional[str] = Field(None, description="Planned end date (YYYY-MM-DD HH:MM:SS)")

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _validate_dates(cls, v):
        return validate_servicenow_datetime(v)


class UpdateChangeRequestParams(BaseModel):
    """Parameters for updating a change request."""

    change_id: str = Field(..., description="Change request ID or sys_id")
    short_description: Optional[str] = Field(None, description="Short description of the change request")
    description: Optional[str] = Field(None, description="Detailed description of the change request")
    state: Optional[str] = Field(None, description="State of the change request")
    risk: Optional[str] = Field(None, description="Risk level of the change")
    impact: Optional[str] = Field(None, description="Impact of the change")
    category: Optional[str] = Field(None, description="Category of the change")
    assignment_group: Optional[str] = Field(None, description="Group assigned to the change")
    start_date: Optional[str] = Field(None, description="Planned start date (YYYY-MM-DD HH:MM:SS)")
    end_date: Optional[str] = Field(None, description="Planned end date (YYYY-MM-DD HH:MM:SS)")
    work_notes: Optional[str] = Field(None, description="Work notes to add to the change request")

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _validate_dates(cls, v):
        return validate_servicenow_datetime(v)


class ListChangeRequestsParams(BaseModel):
    """Parameters for listing change requests."""

    limit: Optional[int] = Field(10, description="Maximum number of records to return")
    offset: Optional[int] = Field(0, description="Offset to start from")
    state: Optional[str] = Field(None, description="Filter by state")
    type: Optional[str] = Field(None, description="Filter by type (normal, standard, emergency)")
    category: Optional[str] = Field(None, description="Filter by category")
    assignment_group: Optional[str] = Field(None, description="Filter by assignment group")
    timeframe: Optional[str] = Field(None, description="Filter by timeframe (upcoming, in-progress, completed)")
    query: Optional[str] = Field(None, description="Additional query string")


class GetChangeRequestDetailsParams(BaseModel):
    """Parameters for getting change request details."""

    change_id: str = Field(..., description="Change request ID or sys_id")


class AddChangeTaskParams(BaseModel):
    """Parameters for adding a task to a change request."""

    change_id: str = Field(..., description="Change request ID or sys_id")
    short_description: str = Field(..., description="Short description of the task")
    description: Optional[str] = Field(None, description="Detailed description of the task")
    assigned_to: Optional[str] = Field(None, description="User assigned to the task")
    planned_start_date: Optional[str] = Field(None, description="Planned start date (YYYY-MM-DD HH:MM:SS)")
    planned_end_date: Optional[str] = Field(None, description="Planned end date (YYYY-MM-DD HH:MM:SS)")

    @field_validator("planned_start_date", "planned_end_date", mode="before")
    @classmethod
    def _validate_dates(cls, v):
        return validate_servicenow_datetime(v)


class SubmitChangeForApprovalParams(BaseModel):
    """Parameters for submitting a change request for approval."""

    change_id: str = Field(..., description="Change request ID or sys_id")
    approval_comments: Optional[str] = Field(None, description="Comments for the approval request")


class ApproveChangeParams(BaseModel):
    """Parameters for approving a change request."""

    change_id: str = Field(..., description="Change request ID or sys_id")
    approver_id: Optional[str] = Field(None, description="ID of the approver")
    approval_comments: Optional[str] = Field(None, description="Comments for the approval")


class RejectChangeParams(BaseModel):
    """Parameters for rejecting a change request."""

    change_id: str = Field(..., description="Change request ID or sys_id")
    approver_id: Optional[str] = Field(None, description="ID of the approver")
    rejection_reason: str = Field(..., description="Reason for rejection")


def create_change_request(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a new change request in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for creating the change request.

    Returns:
        The created change request.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        CreateChangeRequestParams, 
        required_fields=["short_description", "type"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Prepare the request data
    data = {
        "short_description": validated_params.short_description,
        "type": validated_params.type,
    }
    
    # Add optional fields if provided
    if validated_params.description:
        data["description"] = validated_params.description
    if validated_params.risk:
        data["risk"] = validated_params.risk
    if validated_params.impact:
        data["impact"] = validated_params.impact
    if validated_params.category:
        data["category"] = validated_params.category
    if validated_params.requested_by:
        data["requested_by"] = validated_params.requested_by
    if validated_params.assignment_group:
        data["assignment_group"] = validated_params.assignment_group
    if validated_params.start_date:
        data["start_date"] = validated_params.start_date
    if validated_params.end_date:
        data["end_date"] = validated_params.end_date
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Add Content-Type header
    headers["Content-Type"] = "application/json"
    
    # Make the API request
    url = f"{instance_url}/api/now/table/change_request"
    
    try:
        response = _make_request("POST", url, json=data, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        return {
            "success": True,
            "message": "Change request created successfully",
            "change_request": result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating change request: {e}")
        return {
            "success": False,
            "message": f"Error creating change request: {_format_http_error(e)}",
        }


def update_change_request(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Update an existing change request in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for updating the change request.

    Returns:
        The updated change request.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        UpdateChangeRequestParams, 
        required_fields=["change_id"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Prepare the request data
    data = {}
    
    # Add fields if provided
    if validated_params.short_description:
        data["short_description"] = validated_params.short_description
    if validated_params.description:
        data["description"] = validated_params.description
    if validated_params.state:
        data["state"] = validated_params.state
    if validated_params.risk:
        data["risk"] = validated_params.risk
    if validated_params.impact:
        data["impact"] = validated_params.impact
    if validated_params.category:
        data["category"] = validated_params.category
    if validated_params.assignment_group:
        data["assignment_group"] = validated_params.assignment_group
    if validated_params.start_date:
        data["start_date"] = validated_params.start_date
    if validated_params.end_date:
        data["end_date"] = validated_params.end_date
    if validated_params.work_notes:
        data["work_notes"] = validated_params.work_notes
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Add Content-Type header
    headers["Content-Type"] = "application/json"
    
    # Make the API request
    url = f"{instance_url}/api/now/table/change_request/{validated_params.change_id}"
    
    try:
        response = _make_request("PUT", url, json=data, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        return {
            "success": True,
            "message": "Change request updated successfully",
            "change_request": result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating change request: {e}")
        return {
            "success": False,
            "message": f"Error updating change request: {_format_http_error(e)}",
        }


def list_change_requests(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    List change requests from ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for listing change requests.

    Returns:
        A list of change requests.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        ListChangeRequestsParams
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Build the query
    query_parts = []
    
    if validated_params.state:
        query_parts.append(f"state={validated_params.state}")
    if validated_params.type:
        query_parts.append(f"type={validated_params.type}")
    if validated_params.category:
        query_parts.append(f"category={validated_params.category}")
    if validated_params.assignment_group:
        query_parts.append(f"assignment_group={validated_params.assignment_group}")
    
    # Handle timeframe filtering
    if validated_params.timeframe:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if validated_params.timeframe == "upcoming":
            query_parts.append(f"start_date>{now}")
        elif validated_params.timeframe == "in-progress":
            query_parts.append(f"start_date<{now}^end_date>{now}")
        elif validated_params.timeframe == "completed":
            query_parts.append(f"end_date<{now}")
    
    # Add any additional query string
    if validated_params.query:
        query_parts.append(validated_params.query)
    
    # Combine query parts
    query = "^".join(query_parts) if query_parts else ""
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Make the API request
    url = f"{instance_url}/api/now/table/change_request"
    
    params = {
        "sysparm_limit": validated_params.limit,
        "sysparm_offset": validated_params.offset,
        "sysparm_query": query,
        "sysparm_display_value": "true",
    }
    
    try:
        response = _make_request("GET", url, headers=headers, params=params)
        response.raise_for_status()
        
        result = response.json()
        
        # Handle the case where result["result"] is a list
        change_requests = result.get("result", [])
        count = len(change_requests)
        
        return {
            "success": True,
            "change_requests": change_requests,
            "count": count,
            "total": count,  # Use count as total if total is not provided
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing change requests: {e}")
        return {
            "success": False,
            "message": f"Error listing change requests: {_format_http_error(e)}",
        }


def get_change_request_details(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Get details of a change request from ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for getting change request details.

    Returns:
        The change request details.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        GetChangeRequestDetailsParams,
        required_fields=["change_id"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Make the API request
    url = f"{instance_url}/api/now/table/change_request/{validated_params.change_id}"
    
    params = {
        "sysparm_display_value": "true",
    }
    
    try:
        response = _make_request("GET", url, headers=headers, params=params)
        response.raise_for_status()
        
        result = response.json()
        
        # Get tasks associated with this change request
        tasks_url = f"{instance_url}/api/now/table/change_task"
        tasks_params = {
            "sysparm_query": f"change_request={validated_params.change_id}",
            "sysparm_display_value": "true",
        }
        
        tasks_response = _make_request("GET", tasks_url, headers=headers, params=tasks_params)
        tasks_response.raise_for_status()
        
        tasks_result = tasks_response.json()
        
        return {
            "success": True,
            "change_request": result["result"],
            "tasks": tasks_result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting change request details: {e}")
        return {
            "success": False,
            "message": f"Error getting change request details: {_format_http_error(e)}",
        }


def add_change_task(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Add a task to a change request in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for adding a change task.

    Returns:
        The created change task.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        AddChangeTaskParams,
        required_fields=["change_id", "short_description"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Prepare the request data
    data = {
        "change_request": validated_params.change_id,
        "short_description": validated_params.short_description,
    }
    
    # Add optional fields if provided
    if validated_params.description:
        data["description"] = validated_params.description
    if validated_params.assigned_to:
        data["assigned_to"] = validated_params.assigned_to
    if validated_params.planned_start_date:
        data["planned_start_date"] = validated_params.planned_start_date
    if validated_params.planned_end_date:
        data["planned_end_date"] = validated_params.planned_end_date
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Add Content-Type header
    headers["Content-Type"] = "application/json"
    
    # Make the API request
    url = f"{instance_url}/api/now/table/change_task"
    
    try:
        response = _make_request("POST", url, json=data, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        return {
            "success": True,
            "message": "Change task added successfully",
            "change_task": result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error adding change task: {e}")
        return {
            "success": False,
            "message": f"Error adding change task: {_format_http_error(e)}",
        }


def submit_change_for_approval(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Submit a change request for approval in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for submitting a change request for approval.

    Returns:
        The result of the submission.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        SubmitChangeForApprovalParams,
        required_fields=["change_id"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Prepare the request data
    data = {
        "state": "assess",  # Set state to "assess" to submit for approval
    }
    
    # Add approval comments if provided
    if validated_params.approval_comments:
        data["work_notes"] = validated_params.approval_comments
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Add Content-Type header
    headers["Content-Type"] = "application/json"
    
    # Make the API request
    url = f"{instance_url}/api/now/table/change_request/{validated_params.change_id}"
    
    try:
        response = _make_request("PATCH", url, json=data, headers=headers)
        response.raise_for_status()
        
        # Now, create an approval request
        approval_url = f"{instance_url}/api/now/table/sysapproval_approver"
        approval_data = {
            "document_id": validated_params.change_id,
            "source_table": "change_request",
            "state": "requested",
        }
        
        approval_response = _make_request("POST", approval_url, json=approval_data, headers=headers)
        approval_response.raise_for_status()
        
        approval_result = approval_response.json()
        
        return {
            "success": True,
            "message": "Change request submitted for approval successfully",
            "approval": approval_result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error submitting change for approval: {e}")
        return {
            "success": False,
            "message": f"Error submitting change for approval: {_format_http_error(e)}",
        }


def approve_change(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Approve a change request in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for approving a change request.

    Returns:
        The result of the approval.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        ApproveChangeParams,
        required_fields=["change_id"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # First, find the approval record
    approval_query_url = f"{instance_url}/api/now/table/sysapproval_approver"
    
    query_params = {
        "sysparm_query": f"document_id={validated_params.change_id}",
        "sysparm_limit": 1,
    }
    
    try:
        approval_response = _make_request("GET", approval_query_url, headers=headers, params=query_params)
        approval_response.raise_for_status()
        
        approval_result = approval_response.json()
        
        if not approval_result.get("result") or len(approval_result["result"]) == 0:
            return {
                "success": False,
                "message": "No approval record found for this change request",
            }
        
        approval_id = approval_result["result"][0]["sys_id"]
        
        # Now, update the approval record to approved
        approval_update_url = f"{instance_url}/api/now/table/sysapproval_approver/{approval_id}"
        headers["Content-Type"] = "application/json"
        
        approval_data = {
            "state": "approved",
        }
        
        if validated_params.approval_comments:
            approval_data["comments"] = validated_params.approval_comments
        
        approval_update_response = _make_request("PATCH", approval_update_url, json=approval_data, headers=headers)
        approval_update_response.raise_for_status()
        
        # Finally, update the change request state to "implement"
        change_url = f"{instance_url}/api/now/table/change_request/{validated_params.change_id}"
        
        change_data = {
            "state": "implement",  # This may vary depending on ServiceNow configuration
        }
        
        change_response = _make_request("PATCH", change_url, json=change_data, headers=headers)
        change_response.raise_for_status()
        
        return {
            "success": True,
            "message": "Change request approved successfully",
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error approving change: {e}")
        return {
            "success": False,
            "message": f"Error approving change: {_format_http_error(e)}",
        }


CHANGE_TASK_FIELDS = [
    "sys_id",
    "number",
    "short_description",
    "description",
    "state",
    "assigned_to",
    "assignment_group",
    "change_request",
    "planned_start_date",
    "planned_end_date",
    "close_notes",
    "work_notes",
    "priority",
    "order",
    "sys_created_on",
    "sys_updated_on",
]


class GetChangeTaskParams(BaseModel):
    """Parameters for retrieving a single change task by sys_id or CTASK number."""

    task_id: str = Field(
        ...,
        description=(
            "The change task sys_id (32-char hex) or task number (e.g. CTASK0001234)"
        ),
    )


def _format_change_task(record: Dict) -> Dict:
    """Normalise a raw change_task record into a clean dict."""

    def _display(val):
        if isinstance(val, dict):
            return val.get("display_value") or val.get("value")
        return val

    return {
        "sys_id": record.get("sys_id"),
        "number": record.get("number"),
        "short_description": record.get("short_description"),
        "description": record.get("description"),
        "state": _display(record.get("state")),
        "priority": _display(record.get("priority")),
        "assigned_to": _display(record.get("assigned_to")),
        "assignment_group": _display(record.get("assignment_group")),
        "change_request": _display(record.get("change_request")),
        "planned_start_date": record.get("planned_start_date"),
        "planned_end_date": record.get("planned_end_date"),
        "close_notes": record.get("close_notes"),
        "order": record.get("order"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _resolve_change_task_sys_id(
    instance_url: str,
    headers: dict,
    task_id: str,
) -> Optional[str]:
    """Return the sys_id for a CTASK number or passthrough if already a sys_id."""
    if len(task_id) == 32 and all(c in "0123456789abcdef" for c in task_id):
        return task_id
    url = f"{instance_url}/api/now/table/change_task"
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


def get_change_task(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single change_task record by its sys_id or CTASK number.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetChangeTaskParams.

    Returns:
        Dictionary with ``success`` and ``task`` keys on success.
    """
    result = _unwrap_and_validate_params(params, GetChangeTaskParams, required_fields=["task_id"])
    if not result["success"]:
        return result
    validated: GetChangeTaskParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    task_sys_id = _resolve_change_task_sys_id(instance_url, headers, validated.task_id)
    if not task_sys_id:
        return {"success": False, "message": f"Change task not found: {validated.task_id}"}

    url = f"{instance_url}/api/now/table/change_task/{task_sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(CHANGE_TASK_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Change task not found: {validated.task_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Change task not found: {validated.task_id}"}
        return {"success": True, "task": _format_change_task(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving change task: {e}")
        return {"success": False, "message": f"Error retrieving change task: {_format_http_error(e)}"}


class ListChangeTasksParams(BaseModel):
    """Parameters for listing tasks linked to a change request."""

    change_request_id: str = Field(
        ...,
        description="Change request sys_id or number (e.g. CHG0001234) whose tasks should be listed",
    )
    limit: int = Field(10, description="Maximum number of tasks to return")
    offset: int = Field(0, description="Pagination offset")
    state: Optional[str] = Field(None, description="Filter by task state (e.g. -5=Pending, 1=Open, 2=Work In Progress, 3=Closed Complete)")


class CreateChangeTaskParams(BaseModel):
    """Parameters for creating a task linked to a change request."""

    change_request_id: str = Field(
        ...,
        description="Change request sys_id or number (e.g. CHG0001234) to attach the task to",
    )
    short_description: str = Field(..., description="Short description of the task")
    description: Optional[str] = Field(None, description="Detailed description of the task")
    assigned_to: Optional[str] = Field(None, description="Username or sys_id of the assignee")
    assignment_group: Optional[str] = Field(None, description="Name or sys_id of the assignment group")
    state: Optional[str] = Field(None, description="Initial state. Defaults to Open (-5=Pending, 1=Open, 2=Work In Progress)")
    planned_start_date: Optional[str] = Field(None, description="Planned start date (YYYY-MM-DD HH:MM:SS)")
    planned_end_date: Optional[str] = Field(None, description="Planned end date (YYYY-MM-DD HH:MM:SS)")
    work_notes: Optional[str] = Field(None, description="Initial work notes")

    @field_validator("planned_start_date", "planned_end_date", mode="before")
    @classmethod
    def _validate_dates(cls, v):
        return validate_servicenow_datetime(v)


def _resolve_change_request_sys_id(
    instance_url: str,
    headers: dict,
    change_request_id: str,
) -> Optional[str]:
    """Return the sys_id for a change request number or passthrough if already a sys_id."""
    if len(change_request_id) == 32 and all(c in "0123456789abcdef" for c in change_request_id):
        return change_request_id

    url = f"{instance_url}/api/now/table/change_request"
    try:
        resp = _make_request(
            "GET",
            url,
            headers=headers,
            params={"sysparm_query": f"number={change_request_id}", "sysparm_limit": 1, "sysparm_fields": "sys_id"},
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        if not results:
            return None
        return results[0].get("sys_id")
    except requests.exceptions.RequestException:
        return None


def list_change_tasks(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List change_task records linked to a specific change request."""
    result = _unwrap_and_validate_params(
        params, ListChangeTasksParams, required_fields=["change_request_id"]
    )
    if not result["success"]:
        return result

    validated: ListChangeTasksParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}

    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    change_sys_id = _resolve_change_request_sys_id(instance_url, headers, validated.change_request_id)
    if not change_sys_id:
        return {"success": False, "message": f"Change request not found: {validated.change_request_id}"}

    query_parts = [f"change_request={change_sys_id}"]
    if validated.state:
        query_parts.append(f"state={validated.state}")

    url = f"{instance_url}/api/now/table/change_task"
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
        logger.error(f"Error listing change tasks: {e}")
        return {"success": False, "message": f"Error listing change tasks: {_format_http_error(e)}"}


def create_change_task(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a change_task record linked to a specific change request."""
    result = _unwrap_and_validate_params(
        params, CreateChangeTaskParams, required_fields=["change_request_id", "short_description"]
    )
    if not result["success"]:
        return result

    validated: CreateChangeTaskParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}

    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}
    headers["Content-Type"] = "application/json"

    change_sys_id = _resolve_change_request_sys_id(instance_url, headers, validated.change_request_id)
    if not change_sys_id:
        return {"success": False, "message": f"Change request not found: {validated.change_request_id}"}

    body: Dict[str, Any] = {
        "change_request": change_sys_id,
        "short_description": validated.short_description,
    }
    if validated.description is not None:
        body["description"] = validated.description
    if validated.assigned_to is not None:
        body["assigned_to"] = validated.assigned_to
    if validated.assignment_group is not None:
        body["assignment_group"] = validated.assignment_group
    if validated.state is not None:
        body["state"] = validated.state
    if validated.planned_start_date is not None:
        body["planned_start_date"] = validated.planned_start_date
    if validated.planned_end_date is not None:
        body["planned_end_date"] = validated.planned_end_date
    if validated.work_notes is not None:
        body["work_notes"] = validated.work_notes

    url = f"{instance_url}/api/now/table/change_task"
    try:
        resp = _make_request("POST", url, json=body, headers=headers)
        resp.raise_for_status()
        task = resp.json().get("result", {})
        return {
            "success": True,
            "message": f"Change task created: {task.get('number')}",
            "task": {
                "sys_id": task.get("sys_id"),
                "number": task.get("number"),
                "short_description": task.get("short_description"),
                "state": task.get("state"),
                "assigned_to": task.get("assigned_to"),
                "assignment_group": task.get("assignment_group"),
                "change_request": change_sys_id,
            },
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating change task: {e}")
        return {"success": False, "message": f"Error creating change task: {_format_http_error(e)}"}


class UpdateChangeTaskParams(BaseModel):
    """Parameters for updating an existing change task."""

    task_id: str = Field(
        ...,
        description="Change task sys_id (32-char hex) or task number (e.g. CTASK0001234)",
    )
    short_description: Optional[str] = Field(None, description="Updated short description")
    description: Optional[str] = Field(None, description="Updated detailed description")
    state: Optional[str] = Field(
        None,
        description="New state value (-5=Pending, 1=Open, 2=Work In Progress, 3=Closed Complete, 4=Closed Incomplete, 7=Closed Skipped)",
    )
    assigned_to: Optional[str] = Field(None, description="Username or sys_id of the new assignee")
    assignment_group: Optional[str] = Field(None, description="Name or sys_id of the new assignment group")
    planned_start_date: Optional[str] = Field(None, description="Planned start date (YYYY-MM-DD HH:MM:SS)")
    planned_end_date: Optional[str] = Field(None, description="Planned end date (YYYY-MM-DD HH:MM:SS)")
    work_notes: Optional[str] = Field(None, description="Work notes to append to the task")
    close_notes: Optional[str] = Field(None, description="Closure notes (used when closing the task)")

    @field_validator("planned_start_date", "planned_end_date", mode="before")
    @classmethod
    def _validate_dates(cls, v):
        return validate_servicenow_datetime(v)


def update_change_task(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing change_task record (state, assignee, dates, notes, etc.).

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdateChangeTaskParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``task`` keys on success.
    """
    result = _unwrap_and_validate_params(params, UpdateChangeTaskParams, required_fields=["task_id"])
    if not result["success"]:
        return result
    validated: UpdateChangeTaskParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    task_sys_id = _resolve_change_task_sys_id(instance_url, headers, validated.task_id)
    if not task_sys_id:
        return {"success": False, "message": f"Change task not found: {validated.task_id}"}

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
    if validated.planned_start_date is not None:
        body["planned_start_date"] = validated.planned_start_date
    if validated.planned_end_date is not None:
        body["planned_end_date"] = validated.planned_end_date
    if validated.work_notes is not None:
        body["work_notes"] = validated.work_notes
    if validated.close_notes is not None:
        body["close_notes"] = validated.close_notes

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    headers["Content-Type"] = "application/json"
    url = f"{instance_url}/api/now/table/change_task/{task_sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(CHANGE_TASK_FIELDS),
    }
    try:
        response = _make_request("PATCH", url, json=body, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Change task not found: {validated.task_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Change task updated: {validated.task_id}",
            "task": _format_change_task(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating change task: {e}")
        return {"success": False, "message": f"Error updating change task: {_format_http_error(e)}"}


class CloseChangeTaskParams(BaseModel):
    """Parameters for closing a change task."""

    task_id: str = Field(
        ...,
        description="Change task sys_id (32-char hex) or task number (e.g. CTASK0001234)",
    )
    state: str = Field(
        "3",
        description="Closed state value: 3=Closed Complete (default), 4=Closed Incomplete, 7=Closed Skipped",
    )
    close_notes: Optional[str] = Field(None, description="Closure notes")
    work_notes: Optional[str] = Field(None, description="Work notes to add when closing")


def close_change_task(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Close a change_task record by setting its state to Closed Complete (or another closed state).

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CloseChangeTaskParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``task`` keys on success.
    """
    result = _unwrap_and_validate_params(params, CloseChangeTaskParams, required_fields=["task_id"])
    if not result["success"]:
        return result
    validated: CloseChangeTaskParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}
    headers["Content-Type"] = "application/json"

    task_sys_id = _resolve_change_task_sys_id(instance_url, headers, validated.task_id)
    if not task_sys_id:
        return {"success": False, "message": f"Change task not found: {validated.task_id}"}

    body: Dict[str, Any] = {"state": validated.state}
    if validated.close_notes is not None:
        body["close_notes"] = validated.close_notes
    if validated.work_notes is not None:
        body["work_notes"] = validated.work_notes

    url = f"{instance_url}/api/now/table/change_task/{task_sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(CHANGE_TASK_FIELDS),
    }
    try:
        response = _make_request("PATCH", url, json=body, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Change task not found: {validated.task_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Change task {validated.task_id} closed successfully",
            "task": _format_change_task(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error closing change task: {e}")
        return {"success": False, "message": f"Error closing change task: {_format_http_error(e)}"}


class CancelChangeRequestParams(BaseModel):
    """Parameters for cancelling a change request."""

    change_id: str = Field(
        ...,
        description="Change request sys_id or number (e.g. CHG0001234) to cancel",
    )
    cancellation_reason: Optional[str] = Field(
        None, description="Reason for cancellation (added as work notes)"
    )


class ReopenChangeRequestParams(BaseModel):
    """Parameters for reopening a cancelled or closed change request."""

    change_id: str = Field(
        ...,
        description="Change request sys_id or number (e.g. CHG0001234) to reopen",
    )
    state: str = Field(
        "-5",
        description="Target state to reopen to: '-5' = New (default), '-4' = Assess",
    )
    work_notes: Optional[str] = Field(
        None, description="Work notes to add when reopening"
    )


def cancel_change_request(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Cancel a change request by setting its state to Cancelled."""
    result = _unwrap_and_validate_params(
        params, CancelChangeRequestParams, required_fields=["change_id"]
    )
    if not result["success"]:
        return result

    validated: CancelChangeRequestParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}

    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}
    headers["Content-Type"] = "application/json"

    change_sys_id = _resolve_change_request_sys_id(instance_url, headers, validated.change_id)
    if not change_sys_id:
        return {"success": False, "message": f"Change request not found: {validated.change_id}"}

    body: Dict[str, Any] = {"state": "-1"}
    if validated.cancellation_reason:
        body["work_notes"] = validated.cancellation_reason

    url = f"{instance_url}/api/now/table/change_request/{change_sys_id}"
    try:
        resp = _make_request("PATCH", url, json=body, headers=headers)
        resp.raise_for_status()
        record = resp.json().get("result", {})
        return {
            "success": True,
            "message": f"Change request cancelled: {record.get('number', change_sys_id)}",
            "change_request": {
                "sys_id": record.get("sys_id"),
                "number": record.get("number"),
                "state": record.get("state"),
            },
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error cancelling change request: {e}")
        return {"success": False, "message": f"Error cancelling change request: {_format_http_error(e)}"}


def reopen_change_request(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Reopen a cancelled or closed change request by setting its state back to New or Assess."""
    result = _unwrap_and_validate_params(
        params, ReopenChangeRequestParams, required_fields=["change_id"]
    )
    if not result["success"]:
        return result

    validated: ReopenChangeRequestParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}

    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}
    headers["Content-Type"] = "application/json"

    change_sys_id = _resolve_change_request_sys_id(instance_url, headers, validated.change_id)
    if not change_sys_id:
        return {"success": False, "message": f"Change request not found: {validated.change_id}"}

    body: Dict[str, Any] = {"state": validated.state}
    if validated.work_notes:
        body["work_notes"] = validated.work_notes

    url = f"{instance_url}/api/now/table/change_request/{change_sys_id}"
    try:
        resp = _make_request("PATCH", url, json=body, headers=headers)
        resp.raise_for_status()
        record = resp.json().get("result", {})
        state_label = "New" if validated.state == "-5" else "Assess"
        return {
            "success": True,
            "message": f"Change request reopened (state → {state_label}): {record.get('number', change_sys_id)}",
            "change_request": {
                "sys_id": record.get("sys_id"),
                "number": record.get("number"),
                "state": record.get("state"),
            },
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error reopening change request: {e}")
        return {"success": False, "message": f"Error reopening change request: {_format_http_error(e)}"}


def reject_change(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Reject a change request in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for rejecting a change request.

    Returns:
        The result of the rejection.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        RejectChangeParams,
        required_fields=["change_id", "rejection_reason"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # First, find the approval record
    approval_query_url = f"{instance_url}/api/now/table/sysapproval_approver"
    
    query_params = {
        "sysparm_query": f"document_id={validated_params.change_id}",
        "sysparm_limit": 1,
    }
    
    try:
        approval_response = _make_request("GET", approval_query_url, headers=headers, params=query_params)
        approval_response.raise_for_status()
        
        approval_result = approval_response.json()
        
        if not approval_result.get("result") or len(approval_result["result"]) == 0:
            return {
                "success": False,
                "message": "No approval record found for this change request",
            }
        
        approval_id = approval_result["result"][0]["sys_id"]
        
        # Now, update the approval record to rejected
        approval_update_url = f"{instance_url}/api/now/table/sysapproval_approver/{approval_id}"
        headers["Content-Type"] = "application/json"
        
        approval_data = {
            "state": "rejected",
            "comments": validated_params.rejection_reason,
        }
        
        approval_update_response = _make_request("PATCH", approval_update_url, json=approval_data, headers=headers)
        approval_update_response.raise_for_status()
        
        # Finally, update the change request state to "canceled"
        change_url = f"{instance_url}/api/now/table/change_request/{validated_params.change_id}"
        
        change_data = {
            "state": "canceled",  # This may vary depending on ServiceNow configuration
            "work_notes": f"Change request rejected: {validated_params.rejection_reason}",
        }
        
        change_response = _make_request("PATCH", change_url, json=change_data, headers=headers)
        change_response.raise_for_status()
        
        return {
            "success": True,
            "message": "Change request rejected successfully",
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error rejecting change: {e}")
        return {
            "success": False,
            "message": f"Error rejecting change: {_format_http_error(e)}",
        } 

APPROVAL_TABLE = "/api/now/table/sysapproval_approver"

APPROVAL_FIELDS = [
    "sys_id",
    "document_id",
    "source_table",
    "approver",
    "state",
    "comments",
    "due_date",
    "sys_created_on",
    "sys_updated_on",
]


class ApproveChangeApprovalParams(BaseModel):
    """Parameters for approving a specific sysapproval_approver record by sys_id."""

    sys_id: str = Field(..., description="The sys_id of the sysapproval_approver record to approve")
    comments: Optional[str] = Field(None, description="Optional approval comments")


class RejectChangeApprovalParams(BaseModel):
    """Parameters for rejecting a specific sysapproval_approver record by sys_id."""

    sys_id: str = Field(..., description="The sys_id of the sysapproval_approver record to reject")
    rejection_reason: str = Field(..., description="Reason for rejecting the approval")


class GetChangeApprovalParams(BaseModel):
    """Parameters for retrieving a single approval record by sys_id."""

    sys_id: str = Field(..., description="The sys_id of the sysapproval_approver record to retrieve")


class ListChangeApprovalsParams(BaseModel):
    """Parameters for listing approval records for change requests."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    change_id: Optional[str] = Field(
        None,
        description="Filter by change request sys_id (32-char hex) or CHG number",
    )
    state: Optional[str] = Field(
        None,
        description=(
            "Filter by approval state. Values: 'requested', 'approved', "
            "'rejected', 'not_yet_requested', 'cancelled'"
        ),
    )
    approver: Optional[str] = Field(
        None,
        description="Filter by approver user name (exact match on approver.name)",
    )


def get_change_approval(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single sysapproval_approver record by its sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetChangeApprovalParams.

    Returns:
        Dictionary with ``success`` and ``approval`` keys on success.
    """
    result = _unwrap_and_validate_params(params, GetChangeApprovalParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}{APPROVAL_TABLE}/{validated.sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(APPROVAL_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Approval record not found: {validated.sys_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Approval record not found: {validated.sys_id}"}
        return {"success": True, "approval": _format_approval(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving change approval: {e}")
        return {"success": False, "message": f"Error retrieving change approval: {_format_http_error(e)}"}


def _format_approval(record: Dict) -> Dict:
    """Normalise a raw sysapproval_approver record into a clean dict."""

    def _display(val):
        if isinstance(val, dict):
            return val.get("display_value") or val.get("value")
        return val

    return {
        "sys_id": record.get("sys_id"),
        "change_request": _display(record.get("document_id")),
        "approver": _display(record.get("approver")),
        "state": record.get("state"),
        "comments": record.get("comments"),
        "due_date": record.get("due_date"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _resolve_change_sys_id(
    change_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Return the sys_id for a change request given a CHG number or sys_id.

    Returns None on network errors or when the record is not found.
    """
    if len(change_id) == 32 and all(c in "0123456789abcdef" for c in change_id):
        return change_id
    lookup_url = f"{instance_url}/api/now/table/change_request"
    try:
        resp = _make_request(
            "GET",
            lookup_url,
            headers=headers,
            params={"sysparm_query": f"number={change_id}", "sysparm_limit": 1},
        )
        resp.raise_for_status()
        records = resp.json().get("result", [])
        if not records:
            return None
        return records[0].get("sys_id")
    except requests.exceptions.RequestException:
        return None


def list_change_approvals(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List approval records for change requests from the sysapproval_approver table.

    Always scopes results to ``source_table=change_request``.  Optionally
    filter by a specific change request (number or sys_id), approval state,
    or approver user name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListChangeApprovalsParams.

    Returns:
        Dictionary with ``success``, ``approvals`` (list), ``count``, and
        pagination keys (``has_more``, ``next_offset``).
    """
    result = _unwrap_and_validate_params(params, ListChangeApprovalsParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    filters = ["source_table=change_request"]

    if validated.change_id:
        sys_id = _resolve_change_sys_id(validated.change_id, instance_url, headers)
        if sys_id is None:
            return {
                "success": False,
                "message": f"Change request not found: {validated.change_id}",
            }
        filters.append(f"document_id={sys_id}")

    if validated.state:
        filters.append(f"state={validated.state}")

    if validated.approver:
        filters.append(f"approver.name={validated.approver}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(filters),
        exclude_reference_link=True,
        fields=",".join(APPROVAL_FIELDS),
    )

    url = f"{instance_url}{APPROVAL_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        approvals = [_format_approval(r) for r in response.json().get("result", [])]
        return _paginated_list_response(approvals, validated.limit, validated.offset, "approvals")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing change approvals: {e}")
        return {
            "success": False,
            "message": f"Error listing change approvals: {_format_http_error(e)}",
        }


def approve_change_approval(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Approve a specific sysapproval_approver record by its sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ApproveChangeApprovalParams.

    Returns:
        Dictionary with ``success`` and ``approval`` keys on success.
    """
    result = _unwrap_and_validate_params(params, ApproveChangeApprovalParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}{APPROVAL_TABLE}/{validated.sys_id}"
    body: Dict[str, Any] = {"state": "approved"}
    if validated.comments:
        body["comments"] = validated.comments

    try:
        response = _make_request("PATCH", url, headers=headers, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"Approval record not found: {validated.sys_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": "Approval record approved successfully",
            "approval": _format_approval(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error approving change approval: {e}")
        return {"success": False, "message": f"Error approving change approval: {_format_http_error(e)}"}


def reject_change_approval(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Reject a specific sysapproval_approver record by its sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching RejectChangeApprovalParams.

    Returns:
        Dictionary with ``success`` and ``approval`` keys on success.
    """
    result = _unwrap_and_validate_params(params, RejectChangeApprovalParams, required_fields=["sys_id", "rejection_reason"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}{APPROVAL_TABLE}/{validated.sys_id}"
    body: Dict[str, Any] = {"state": "rejected", "comments": validated.rejection_reason}

    try:
        response = _make_request("PATCH", url, headers=headers, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"Approval record not found: {validated.sys_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": "Approval record rejected successfully",
            "approval": _format_approval(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error rejecting change approval: {e}")
        return {"success": False, "message": f"Error rejecting change approval: {_format_http_error(e)}"}


RISK_ASSESSMENT_TABLE = "/api/now/table/risk_assessment"

RISK_ASSESSMENT_FIELDS = [
    "sys_id",
    "source",
    "source_table",
    "questionnaire",
    "result",
    "state",
    "risk",
    "sys_created_by",
    "sys_created_on",
    "sys_updated_on",
]


class ListChangeRiskAssessmentsParams(BaseModel):
    """Parameters for listing risk assessments linked to a change request."""

    change_id: Optional[str] = Field(
        None,
        description=(
            "Filter by change request sys_id (32-char hex) or CHG number. "
            "When omitted, returns risk assessments for all change requests."
        ),
    )
    state: Optional[str] = Field(
        None,
        description="Filter by assessment state (e.g. 'draft', 'pending', 'complete')",
    )
    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")


def _format_risk_assessment(record: Dict) -> Dict:
    """Normalise a raw risk_assessment record into a clean dict."""

    def _display(val):
        if isinstance(val, dict):
            return val.get("display_value") or val.get("value")
        return val

    return {
        "sys_id": record.get("sys_id"),
        "change_request": _display(record.get("source")),
        "questionnaire": _display(record.get("questionnaire")),
        "result": _display(record.get("result")),
        "state": _display(record.get("state")),
        "risk": _display(record.get("risk")),
        "created_by": record.get("sys_created_by"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def list_change_risk_assessments(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List risk_assessment records scoped to change requests.

    Queries the ``risk_assessment`` table with ``source_table=change_request``.
    Optionally filter by a specific change request (CHG number or sys_id) and
    by assessment state.  Returns a paginated list with ``has_more`` /
    ``next_offset`` fields.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListChangeRiskAssessmentsParams.

    Returns:
        Dictionary with ``success``, ``risk_assessments`` (list), ``count``,
        ``has_more``, and ``next_offset``.
    """
    result = _unwrap_and_validate_params(params, ListChangeRiskAssessmentsParams)
    if not result["success"]:
        return result
    validated: ListChangeRiskAssessmentsParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    filters = ["source_table=change_request"]

    if validated.change_id:
        sys_id = _resolve_change_sys_id(validated.change_id, instance_url, headers)
        if sys_id is None:
            return {
                "success": False,
                "message": f"Change request not found: {validated.change_id}",
            }
        filters.append(f"source={sys_id}")

    if validated.state:
        filters.append(f"state={validated.state}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(filters),
        exclude_reference_link=True,
        fields=",".join(RISK_ASSESSMENT_FIELDS),
    )

    url = f"{instance_url}{RISK_ASSESSMENT_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        assessments = [_format_risk_assessment(r) for r in response.json().get("result", [])]
        return _paginated_list_response(assessments, validated.limit, validated.offset, "risk_assessments")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing change risk assessments: {e}")
        return {
            "success": False,
            "message": f"Error listing change risk assessments: {_format_http_error(e)}",
        }


# ---------------------------------------------------------------------------
# list_change_schedules
# ---------------------------------------------------------------------------

CHANGE_SCHEDULE_TABLE = "/api/now/table/cmn_schedule"

CHANGE_SCHEDULE_FIELDS = [
    "sys_id",
    "name",
    "description",
    "type",
    "time_zone",
    "active",
    "parent",
    "sys_created_by",
    "sys_created_on",
    "sys_updated_on",
]


class ListChangeSchedulesParams(BaseModel):
    """Parameters for listing cmn_schedule records (change windows)."""

    name_query: Optional[str] = Field(
        None,
        description="Substring search on the schedule name (case-insensitive LIKE match).",
    )
    schedule_type: Optional[str] = Field(
        None,
        description=(
            "Filter by schedule type value (e.g. 'change_window', "
            "'on_call_rotation', 'holiday_schedule')."
        ),
    )
    active: Optional[bool] = Field(
        None,
        description="When True, return only active schedules; False returns only inactive.",
    )
    time_zone: Optional[str] = Field(
        None,
        description="Filter by exact time_zone value (e.g. 'US/Eastern', 'UTC').",
    )
    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")


def _format_change_schedule(record: Dict) -> Dict:
    """Normalise a raw cmn_schedule record into a clean dict."""

    def _display(val):
        if isinstance(val, dict):
            return val.get("display_value") or val.get("value")
        return val

    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "description": record.get("description"),
        "type": _display(record.get("type")),
        "time_zone": record.get("time_zone"),
        "active": record.get("active"),
        "parent": _display(record.get("parent")),
        "created_by": record.get("sys_created_by"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def list_change_schedules(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List cmn_schedule records, optionally scoped to change windows.

    Queries the ``cmn_schedule`` table with optional filters for schedule type,
    name, active state, and time zone.  Returns a paginated list with
    ``has_more`` / ``next_offset`` fields.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListChangeSchedulesParams.

    Returns:
        Dictionary with ``success``, ``schedules`` (list), ``count``,
        ``has_more``, and ``next_offset``.
    """
    result = _unwrap_and_validate_params(params, ListChangeSchedulesParams)
    if not result["success"]:
        return result
    validated: ListChangeSchedulesParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    filters: list = []

    if validated.name_query:
        filters.append(f"nameLIKE{validated.name_query}")

    if validated.schedule_type:
        filters.append(f"type={validated.schedule_type}")

    if validated.active is not None:
        filters.append(f"active={'true' if validated.active else 'false'}")

    if validated.time_zone:
        filters.append(f"time_zone={validated.time_zone}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(filters) if filters else None,
        exclude_reference_link=True,
        fields=",".join(CHANGE_SCHEDULE_FIELDS),
    )

    url = f"{instance_url}{CHANGE_SCHEDULE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        schedules = [_format_change_schedule(r) for r in response.json().get("result", [])]
        return _paginated_list_response(schedules, validated.limit, validated.offset, "schedules")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing change schedules: {e}")
        return {
            "success": False,
            "message": f"Error listing change schedules: {_format_http_error(e)}",
        }


# ---------------------------------------------------------------------------
# get_change_schedule
# ---------------------------------------------------------------------------


class GetChangeScheduleParams(BaseModel):
    """Parameters for retrieving a single cmn_schedule record."""

    schedule_id: str = Field(
        ...,
        description=(
            "The cmn_schedule sys_id (32-char hex) or exact schedule name "
            "(e.g. 'Change Window - Weekend')."
        ),
    )


def _resolve_change_schedule_sys_id(
    instance_url: str,
    headers: dict,
    schedule_id: str,
) -> Optional[str]:
    """Return the sys_id for a schedule name or passthrough if already a sys_id."""
    if len(schedule_id) == 32 and all(c in "0123456789abcdef" for c in schedule_id):
        return schedule_id
    url = f"{instance_url}{CHANGE_SCHEDULE_TABLE}"
    try:
        resp = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={schedule_id}",
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


def get_change_schedule(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single cmn_schedule record by sys_id or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetChangeScheduleParams.

    Returns:
        Dictionary with ``success`` and ``schedule`` keys on success.
    """
    result = _unwrap_and_validate_params(params, GetChangeScheduleParams, required_fields=["schedule_id"])
    if not result["success"]:
        return result
    validated: GetChangeScheduleParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    schedule_sys_id = _resolve_change_schedule_sys_id(instance_url, headers, validated.schedule_id)
    if not schedule_sys_id:
        return {"success": False, "message": f"Change schedule not found: {validated.schedule_id}"}

    url = f"{instance_url}{CHANGE_SCHEDULE_TABLE}/{schedule_sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(CHANGE_SCHEDULE_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Change schedule not found: {validated.schedule_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Change schedule not found: {validated.schedule_id}"}
        return {"success": True, "schedule": _format_change_schedule(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving change schedule: {e}")
        return {"success": False, "message": f"Error retrieving change schedule: {_format_http_error(e)}"}


# ---------------------------------------------------------------------------
# create_change_schedule
# ---------------------------------------------------------------------------


class CreateChangeScheduleParams(BaseModel):
    """Parameters for creating a new cmn_schedule record."""

    name: str = Field(
        ...,
        description="Display name for the new schedule (e.g. 'Change Window - Saturday Night').",
    )
    schedule_type: Optional[str] = Field(
        None,
        description=(
            "Schedule type value (e.g. 'change_window', 'on_call_rotation', "
            "'holiday_schedule'). Leave unset to create a generic schedule."
        ),
    )
    time_zone: Optional[str] = Field(
        None,
        description="IANA time zone string (e.g. 'US/Eastern', 'UTC'). Defaults to instance time zone when omitted.",
    )
    active: Optional[bool] = Field(
        True,
        description="Whether the schedule is active. Defaults to True.",
    )
    parent: Optional[str] = Field(
        None,
        description="Parent schedule sys_id (32-char hex) or exact name.",
    )
    description: Optional[str] = Field(
        None,
        description="Free-text description of the schedule.",
    )


def create_change_schedule(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new cmn_schedule record.

    POSTs to the ``cmn_schedule`` table with the supplied fields.  If a
    ``parent`` schedule name/sys_id is provided it is resolved to a sys_id
    before the request is sent.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateChangeScheduleParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``schedule`` on success.
    """
    result = _unwrap_and_validate_params(params, CreateChangeScheduleParams, required_fields=["name"])
    if not result["success"]:
        return result
    validated: CreateChangeScheduleParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}
    headers["Content-Type"] = "application/json"

    # Resolve parent to sys_id if supplied
    parent_sys_id: Optional[str] = None
    if validated.parent is not None:
        parent_sys_id = _resolve_change_schedule_sys_id(instance_url, headers, validated.parent)
        if not parent_sys_id:
            return {"success": False, "message": f"Parent schedule not found: {validated.parent}"}

    body: Dict[str, Any] = {"name": validated.name}
    if validated.schedule_type is not None:
        body["type"] = validated.schedule_type
    if validated.time_zone is not None:
        body["time_zone"] = validated.time_zone
    if validated.active is not None:
        body["active"] = "true" if validated.active else "false"
    if parent_sys_id is not None:
        body["parent"] = parent_sys_id
    if validated.description is not None:
        body["description"] = validated.description

    url = f"{instance_url}{CHANGE_SCHEDULE_TABLE}"
    try:
        response = _make_request("POST", url, json=body, headers=headers)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Change schedule created: {record.get('name')}",
            "schedule": _format_change_schedule(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating change schedule: {e}")
        return {"success": False, "message": f"Error creating change schedule: {_format_http_error(e)}"}


# ---------------------------------------------------------------------------
# update_change_schedule
# ---------------------------------------------------------------------------


class UpdateChangeScheduleParams(BaseModel):
    """Parameters for updating an existing cmn_schedule record."""

    schedule_id: str = Field(
        ...,
        description=(
            "The cmn_schedule sys_id (32-char hex) or exact schedule name "
            "to update."
        ),
    )
    name: Optional[str] = Field(
        None,
        description="New display name for the schedule.",
    )
    schedule_type: Optional[str] = Field(
        None,
        description=(
            "New schedule type value (e.g. 'change_window', 'on_call_rotation', "
            "'holiday_schedule')."
        ),
    )
    time_zone: Optional[str] = Field(
        None,
        description="New IANA time zone string (e.g. 'US/Eastern', 'UTC').",
    )
    active: Optional[bool] = Field(
        None,
        description="Set to True to activate the schedule or False to deactivate it.",
    )
    parent: Optional[str] = Field(
        None,
        description="New parent schedule sys_id (32-char hex) or exact name.",
    )
    description: Optional[str] = Field(
        None,
        description="New free-text description for the schedule.",
    )


def update_change_schedule(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing cmn_schedule record.

    PATCHes the ``cmn_schedule`` table record identified by ``schedule_id``
    (sys_id or name).  At least one optional field must be supplied; an
    empty-body call is rejected before any HTTP request is made.  If a
    ``parent`` schedule name/sys_id is provided it is resolved to a sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdateChangeScheduleParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``schedule`` on success.
    """
    result = _unwrap_and_validate_params(params, UpdateChangeScheduleParams, required_fields=["schedule_id"])
    if not result["success"]:
        return result
    validated: UpdateChangeScheduleParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    schedule_sys_id = _resolve_change_schedule_sys_id(instance_url, headers, validated.schedule_id)
    if not schedule_sys_id:
        return {"success": False, "message": f"Change schedule not found: {validated.schedule_id}"}

    body: Dict[str, Any] = {}
    if validated.name is not None:
        body["name"] = validated.name
    if validated.schedule_type is not None:
        body["type"] = validated.schedule_type
    if validated.time_zone is not None:
        body["time_zone"] = validated.time_zone
    if validated.active is not None:
        body["active"] = "true" if validated.active else "false"
    if validated.description is not None:
        body["description"] = validated.description

    # Resolve parent to sys_id if supplied
    if validated.parent is not None:
        parent_sys_id = _resolve_change_schedule_sys_id(instance_url, headers, validated.parent)
        if not parent_sys_id:
            return {"success": False, "message": f"Parent schedule not found: {validated.parent}"}
        body["parent"] = parent_sys_id

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    headers["Content-Type"] = "application/json"
    url = f"{instance_url}{CHANGE_SCHEDULE_TABLE}/{schedule_sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }
    try:
        response = _make_request("PATCH", url, json=body, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Change schedule not found: {validated.schedule_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Change schedule updated: {validated.schedule_id}",
            "schedule": _format_change_schedule(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating change schedule: {e}")
        return {"success": False, "message": f"Error updating change schedule: {_format_http_error(e)}"}
