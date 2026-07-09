"""
Incident tools for the ServiceNow MCP server.

This module provides tools for managing incidents in ServiceNow.
"""

import logging
from typing import Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.helpers import (
    _build_sysparm_params,
    _format_http_error,
    _join_query_parts,
    _make_request,
    _paginated_list_response,
)

logger = logging.getLogger(__name__)


class CreateIncidentParams(BaseModel):
    """Parameters for creating an incident."""

    short_description: str = Field(..., description="Short description of the incident")
    description: Optional[str] = Field(None, description="Detailed description of the incident")
    caller_id: Optional[str] = Field(None, description="User who reported the incident")
    category: Optional[str] = Field(None, description="Category of the incident")
    subcategory: Optional[str] = Field(None, description="Subcategory of the incident")
    priority: Optional[str] = Field(None, description="Priority of the incident")
    impact: Optional[str] = Field(None, description="Impact of the incident")
    urgency: Optional[str] = Field(None, description="Urgency of the incident")
    assigned_to: Optional[str] = Field(None, description="User assigned to the incident")
    assignment_group: Optional[str] = Field(None, description="Group assigned to the incident")


class UpdateIncidentParams(BaseModel):
    """Parameters for updating an incident."""

    incident_id: str = Field(..., description="Incident ID or sys_id")
    short_description: Optional[str] = Field(None, description="Short description of the incident")
    description: Optional[str] = Field(None, description="Detailed description of the incident")
    state: Optional[str] = Field(None, description="State of the incident")
    category: Optional[str] = Field(None, description="Category of the incident")
    subcategory: Optional[str] = Field(None, description="Subcategory of the incident")
    priority: Optional[str] = Field(None, description="Priority of the incident")
    impact: Optional[str] = Field(None, description="Impact of the incident")
    urgency: Optional[str] = Field(None, description="Urgency of the incident")
    assigned_to: Optional[str] = Field(None, description="User assigned to the incident")
    assignment_group: Optional[str] = Field(None, description="Group assigned to the incident")
    work_notes: Optional[str] = Field(None, description="Work notes to add to the incident")
    close_notes: Optional[str] = Field(None, description="Close notes to add to the incident")
    close_code: Optional[str] = Field(None, description="Close code for the incident")


class AddCommentParams(BaseModel):
    """Parameters for adding a comment to an incident."""

    incident_id: str = Field(..., description="Incident ID or sys_id")
    comment: str = Field(..., description="Comment to add to the incident")
    is_work_note: bool = Field(False, description="Whether the comment is a work note")


class ResolveIncidentParams(BaseModel):
    """Parameters for resolving an incident."""

    incident_id: str = Field(..., description="Incident ID or sys_id")
    resolution_code: str = Field(..., description="Resolution code for the incident")
    resolution_notes: str = Field(..., description="Resolution notes for the incident")


class ReopenIncidentParams(BaseModel):
    """Parameters for reopening a resolved or closed incident."""

    incident_id: str = Field(..., description="Incident number (e.g. INC0010001) or sys_id")
    state: str = Field(
        "1",
        description="Target state: '1' = New (default), '2' = In Progress",
    )
    work_notes: Optional[str] = Field(None, description="Work notes to add when reopening")


class EscalateIncidentParams(BaseModel):
    """Parameters for escalating an incident's priority and/or assignment group."""

    incident_id: str = Field(..., description="Incident number (e.g. INC0010001) or sys_id")
    priority: str = Field(
        ...,
        description="New priority value: '1' = Critical, '2' = High, '3' = Moderate, '4' = Low, '5' = Planning",
    )
    assignment_group: Optional[str] = Field(
        None, description="Name or sys_id of the group to reassign the incident to"
    )
    audit_note: Optional[str] = Field(
        None, description="Work note documenting the reason for escalation"
    )


class CancelIncidentParams(BaseModel):
    """Parameters for cancelling an incident."""

    incident_id: str = Field(
        ..., description="Incident number (e.g. INC0010001) or sys_id to cancel"
    )
    cancel_reason: Optional[str] = Field(
        None, description="Reason for cancelling the incident (added as a work note)"
    )


class DeleteIncidentParams(BaseModel):
    """Parameters for deleting an incident."""

    incident_id: str = Field(
        ..., description="Incident number (e.g. INC0010001) or sys_id to delete"
    )


class ListIncidentsParams(BaseModel):
    """Parameters for listing incidents."""
    
    limit: int = Field(10, description="Maximum number of incidents to return")
    offset: int = Field(0, description="Offset for pagination")
    state: Optional[str] = Field(None, description="Filter by incident state")
    assigned_to: Optional[str] = Field(None, description="Filter by assigned user")
    category: Optional[str] = Field(None, description="Filter by category")
    query: Optional[str] = Field(None, description="Search query for incidents")


class GetIncidentByNumberParams(BaseModel):
    """Parameters for fetching an incident by its number."""

    incident_number: str = Field(..., description="The number of the incident to fetch")


class IncidentResponse(BaseModel):
    """Response from incident operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")
    incident_id: Optional[str] = Field(None, description="ID of the affected incident")
    incident_number: Optional[str] = Field(None, description="Number of the affected incident")


def create_incident(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateIncidentParams,
) -> IncidentResponse:
    """
    Create a new incident in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for creating the incident.

    Returns:
        Response with the created incident details.
    """
    api_url = f"{config.api_url}/table/incident"

    # Build request data
    data = {
        "short_description": params.short_description,
    }

    if params.description:
        data["description"] = params.description
    if params.caller_id:
        data["caller_id"] = params.caller_id
    if params.category:
        data["category"] = params.category
    if params.subcategory:
        data["subcategory"] = params.subcategory
    if params.priority:
        data["priority"] = params.priority
    if params.impact:
        data["impact"] = params.impact
    if params.urgency:
        data["urgency"] = params.urgency
    if params.assigned_to:
        data["assigned_to"] = params.assigned_to
    if params.assignment_group:
        data["assignment_group"] = params.assignment_group

    # Make request
    try:
        response = _make_request("POST", 
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return IncidentResponse(
            success=True,
            message="Incident created successfully",
            incident_id=result.get("sys_id"),
            incident_number=result.get("number"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create incident: {e}")
        return IncidentResponse(
            success=False,
            message=f"Failed to create incident: {_format_http_error(e)}",
        )


def update_incident(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateIncidentParams,
) -> IncidentResponse:
    """
    Update an existing incident in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for updating the incident.

    Returns:
        Response with the updated incident details.
    """
    # Determine if incident_id is a number or sys_id
    incident_id = params.incident_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        # This is likely a sys_id
        api_url = f"{config.api_url}/table/incident/{incident_id}"
    else:
        # This is likely an incident number
        # First, we need to get the sys_id
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
            }

            response = _make_request("GET", 
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()

            result = response.json().get("result", [])
            if not result:
                return IncidentResponse(
                    success=False,
                    message=f"Incident not found: {incident_id}",
                )

            incident_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{incident_id}"

        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return IncidentResponse(
                success=False,
                message=f"Failed to find incident: {_format_http_error(e)}",
            )

    # Build request data
    data = {}

    if params.short_description:
        data["short_description"] = params.short_description
    if params.description:
        data["description"] = params.description
    if params.state:
        data["state"] = params.state
    if params.category:
        data["category"] = params.category
    if params.subcategory:
        data["subcategory"] = params.subcategory
    if params.priority:
        data["priority"] = params.priority
    if params.impact:
        data["impact"] = params.impact
    if params.urgency:
        data["urgency"] = params.urgency
    if params.assigned_to:
        data["assigned_to"] = params.assigned_to
    if params.assignment_group:
        data["assignment_group"] = params.assignment_group
    if params.work_notes:
        data["work_notes"] = params.work_notes
    if params.close_notes:
        data["close_notes"] = params.close_notes
    if params.close_code:
        data["close_code"] = params.close_code

    # Make request
    try:
        response = _make_request("PUT", 
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return IncidentResponse(
            success=True,
            message="Incident updated successfully",
            incident_id=result.get("sys_id"),
            incident_number=result.get("number"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to update incident: {e}")
        return IncidentResponse(
            success=False,
            message=f"Failed to update incident: {_format_http_error(e)}",
        )


def add_comment(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: AddCommentParams,
) -> IncidentResponse:
    """
    Add a comment to an incident in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for adding the comment.

    Returns:
        Response with the result of the operation.
    """
    # Determine if incident_id is a number or sys_id
    incident_id = params.incident_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        # This is likely a sys_id
        api_url = f"{config.api_url}/table/incident/{incident_id}"
    else:
        # This is likely an incident number
        # First, we need to get the sys_id
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
            }

            response = _make_request("GET", 
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()

            result = response.json().get("result", [])
            if not result:
                return IncidentResponse(
                    success=False,
                    message=f"Incident not found: {incident_id}",
                )

            incident_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{incident_id}"

        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return IncidentResponse(
                success=False,
                message=f"Failed to find incident: {_format_http_error(e)}",
            )

    # Build request data
    data = {}

    if params.is_work_note:
        data["work_notes"] = params.comment
    else:
        data["comments"] = params.comment

    # Make request
    try:
        response = _make_request("PUT", 
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return IncidentResponse(
            success=True,
            message="Comment added successfully",
            incident_id=result.get("sys_id"),
            incident_number=result.get("number"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to add comment: {e}")
        return IncidentResponse(
            success=False,
            message=f"Failed to add comment: {_format_http_error(e)}",
        )


def resolve_incident(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ResolveIncidentParams,
) -> IncidentResponse:
    """
    Resolve an incident in ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for resolving the incident.

    Returns:
        Response with the result of the operation.
    """
    # Determine if incident_id is a number or sys_id
    incident_id = params.incident_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        # This is likely a sys_id
        api_url = f"{config.api_url}/table/incident/{incident_id}"
    else:
        # This is likely an incident number
        # First, we need to get the sys_id
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
            }

            response = _make_request("GET", 
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()

            result = response.json().get("result", [])
            if not result:
                return IncidentResponse(
                    success=False,
                    message=f"Incident not found: {incident_id}",
                )

            incident_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{incident_id}"

        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return IncidentResponse(
                success=False,
                message=f"Failed to find incident: {_format_http_error(e)}",
            )

    # Build request data
    data = {
        "state": "6",  # Resolved
        "close_code": params.resolution_code,
        "close_notes": params.resolution_notes,
        "resolved_at": "now",
    }

    # Make request
    try:
        response = _make_request("PUT", 
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return IncidentResponse(
            success=True,
            message="Incident resolved successfully",
            incident_id=result.get("sys_id"),
            incident_number=result.get("number"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to resolve incident: {e}")
        return IncidentResponse(
            success=False,
            message=f"Failed to resolve incident: {_format_http_error(e)}",
        )


def reopen_incident(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ReopenIncidentParams,
) -> IncidentResponse:
    """
    Reopen a resolved or closed incident by patching its state back to New or In Progress.
    """
    incident_id = params.incident_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        api_url = f"{config.api_url}/table/incident/{incident_id}"
    else:
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
            }
            response = _make_request(
                "GET",
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()
            result = response.json().get("result", [])
            if not result:
                return IncidentResponse(
                    success=False,
                    message=f"Incident not found: {incident_id}",
                )
            incident_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{incident_id}"
        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return IncidentResponse(
                success=False,
                message=f"Failed to find incident: {_format_http_error(e)}",
            )

    data: dict = {"state": params.state}
    if params.work_notes:
        data["work_notes"] = params.work_notes

    try:
        response = _make_request(
            "PATCH",
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        result = response.json().get("result", {})
        state_label = "New" if params.state == "1" else "In Progress"
        return IncidentResponse(
            success=True,
            message=f"Incident reopened successfully (state → {state_label})",
            incident_id=result.get("sys_id"),
            incident_number=result.get("number"),
        )
    except requests.RequestException as e:
        logger.error(f"Failed to reopen incident: {e}")
        return IncidentResponse(
            success=False,
            message=f"Failed to reopen incident: {_format_http_error(e)}",
        )


def escalate_incident(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: EscalateIncidentParams,
) -> IncidentResponse:
    """Escalate an incident by updating its priority and optionally reassigning it.

    Resolves incident number to sys_id when needed, then PATCHes the record.
    Appends an audit work note when provided so the escalation is traceable.
    """
    incident_id = params.incident_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        api_url = f"{config.api_url}/table/incident/{incident_id}"
    else:
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
                "sysparm_fields": "sys_id,number",
            }
            response = _make_request(
                "GET",
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()
            result = response.json().get("result", [])
            if not result:
                return IncidentResponse(
                    success=False,
                    message=f"Incident not found: {incident_id}",
                )
            incident_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{incident_id}"
        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return IncidentResponse(
                success=False,
                message=f"Failed to find incident: {_format_http_error(e)}",
            )

    data: dict = {"priority": params.priority}
    if params.assignment_group:
        data["assignment_group"] = params.assignment_group
    if params.audit_note:
        data["work_notes"] = params.audit_note

    try:
        response = _make_request(
            "PATCH",
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        if response.status_code == 404:
            return IncidentResponse(
                success=False,
                message=f"Incident not found: {params.incident_id}",
            )
        response.raise_for_status()
        result = response.json().get("result", {})
        priority_labels = {"1": "Critical", "2": "High", "3": "Moderate", "4": "Low", "5": "Planning"}
        priority_label = priority_labels.get(params.priority, params.priority)
        msg = f"Incident escalated successfully (priority → {priority_label})"
        if params.assignment_group:
            msg += f", reassigned to {params.assignment_group}"
        return IncidentResponse(
            success=True,
            message=msg,
            incident_id=result.get("sys_id"),
            incident_number=result.get("number"),
        )
    except requests.RequestException as e:
        logger.error(f"Failed to escalate incident: {e}")
        return IncidentResponse(
            success=False,
            message=f"Failed to escalate incident: {_format_http_error(e)}",
        )


def cancel_incident(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CancelIncidentParams,
) -> IncidentResponse:
    """Cancel an incident by setting its state to 8 (Cancelled).

    Resolves incident number to sys_id when needed, then PATCHes state=8.
    An optional cancel_reason is appended as a work note for audit purposes.
    """
    incident_id = params.incident_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        api_url = f"{config.api_url}/table/incident/{incident_id}"
        resolved_sys_id = incident_id
    else:
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
                "sysparm_fields": "sys_id,number",
            }
            response = _make_request(
                "GET",
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()
            result = response.json().get("result", [])
            if not result:
                return IncidentResponse(
                    success=False,
                    message=f"Incident not found: {incident_id}",
                )
            resolved_sys_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{resolved_sys_id}"
        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return IncidentResponse(
                success=False,
                message=f"Failed to find incident: {_format_http_error(e)}",
            )

    data: dict = {"state": "8"}
    if params.cancel_reason:
        data["work_notes"] = params.cancel_reason

    try:
        response = _make_request(
            "PATCH",
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        if response.status_code == 404:
            return IncidentResponse(
                success=False,
                message=f"Incident not found: {params.incident_id}",
            )
        response.raise_for_status()
        result = response.json().get("result", {})
        return IncidentResponse(
            success=True,
            message=f"Incident {params.incident_id} cancelled successfully",
            incident_id=result.get("sys_id"),
            incident_number=result.get("number"),
        )
    except requests.RequestException as e:
        logger.error(f"Failed to cancel incident: {e}")
        return IncidentResponse(
            success=False,
            message=f"Failed to cancel incident: {_format_http_error(e)}",
        )


def delete_incident(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DeleteIncidentParams,
) -> IncidentResponse:
    """Permanently delete an incident record from ServiceNow.

    Resolves incident number to sys_id when needed, then issues DELETE on
    /api/now/table/incident/{sys_id}.  Returns success on 204, failure on 404
    or any HTTP/network error.
    """
    incident_id = params.incident_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        api_url = f"{config.api_url}/table/incident/{incident_id}"
        resolved_sys_id = incident_id
    else:
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
                "sysparm_fields": "sys_id,number",
            }
            response = _make_request(
                "GET",
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()
            result = response.json().get("result", [])
            if not result:
                return IncidentResponse(
                    success=False,
                    message=f"Incident not found: {incident_id}",
                )
            resolved_sys_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{resolved_sys_id}"
        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return IncidentResponse(
                success=False,
                message=f"Failed to find incident: {_format_http_error(e)}",
            )

    try:
        response = _make_request(
            "DELETE",
            api_url,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        if response.status_code == 404:
            return IncidentResponse(
                success=False,
                message=f"Incident not found: {params.incident_id}",
            )
        if response.status_code not in (200, 204):
            response.raise_for_status()
        return IncidentResponse(
            success=True,
            message=f"Incident {params.incident_id} deleted successfully",
            incident_id=resolved_sys_id,
        )
    except requests.RequestException as e:
        logger.error(f"Failed to delete incident: {e}")
        return IncidentResponse(
            success=False,
            message=f"Failed to delete incident: {_format_http_error(e)}",
        )


def list_incidents(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListIncidentsParams,
) -> dict:
    """
    List incidents from ServiceNow.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for listing incidents.

    Returns:
        Dictionary with list of incidents.
    """
    api_url = f"{config.api_url}/table/incident"

    filters = []
    if params.state:
        filters.append(f"state={params.state}")
    if params.assigned_to:
        filters.append(f"assigned_to={params.assigned_to}")
    if params.category:
        filters.append(f"category={params.category}")
    if params.query:
        filters.append(f"short_descriptionLIKE{params.query}^ORdescriptionLIKE{params.query}")

    query_params = _build_sysparm_params(
        params.limit,
        params.offset,
        query=_join_query_parts(filters),
        exclude_reference_link=True,
    )

    try:
        response = _make_request("GET", 
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        incidents = []
        for incident_data in response.json().get("result", []):
            assigned_to = incident_data.get("assigned_to")
            if isinstance(assigned_to, dict):
                assigned_to = assigned_to.get("display_value")
            incidents.append({
                "sys_id": incident_data.get("sys_id"),
                "number": incident_data.get("number"),
                "short_description": incident_data.get("short_description"),
                "description": incident_data.get("description"),
                "state": incident_data.get("state"),
                "priority": incident_data.get("priority"),
                "assigned_to": assigned_to,
                "category": incident_data.get("category"),
                "subcategory": incident_data.get("subcategory"),
                "created_on": incident_data.get("sys_created_on"),
                "updated_on": incident_data.get("sys_updated_on"),
            })

        return _paginated_list_response(
            incidents,
            params.limit,
            params.offset,
            "incidents",
            extra={"message": f"Found {len(incidents)} incidents"},
        )

    except requests.RequestException as e:
        logger.error(f"Failed to list incidents: {e}")
        return {
            "success": False,
            "message": f"Failed to list incidents: {_format_http_error(e)}",
            "incidents": [],
        }


def get_incident_by_number(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetIncidentByNumberParams,
) -> dict:
    """
    Fetch a single incident from ServiceNow by its number.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for fetching the incident.

    Returns:
        Dictionary with the incident details.
    """
    api_url = f"{config.api_url}/table/incident"

    # Build query parameters
    query_params = {
        "sysparm_query": f"number={params.incident_number}",
        "sysparm_limit": 1,
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    # Make request
    try:
        response = _make_request("GET", 
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        data = response.json()
        result = data.get("result", [])

        if not result:
            return {
                "success": False,
                "message": f"Incident not found: {params.incident_number}",
            }

        incident_data = result[0]
        assigned_to = incident_data.get("assigned_to")
        if isinstance(assigned_to, dict):
            assigned_to = assigned_to.get("display_value")

        incident = {
            "sys_id": incident_data.get("sys_id"),
            "number": incident_data.get("number"),
            "short_description": incident_data.get("short_description"),
            "description": incident_data.get("description"),
            "state": incident_data.get("state"),
            "priority": incident_data.get("priority"),
            "assigned_to": assigned_to,
            "category": incident_data.get("category"),
            "subcategory": incident_data.get("subcategory"),
            "created_on": incident_data.get("sys_created_on"),
            "updated_on": incident_data.get("sys_updated_on"),
        }

        return {
            "success": True,
            "message": f"Incident {params.incident_number} found",
            "incident": incident,
        }

    except requests.RequestException as e:
        logger.error(f"Failed to fetch incident: {e}")
        return {
            "success": False,
            "message": f"Failed to fetch incident: {_format_http_error(e)}",
        }
