"""
Event management tools for the ServiceNow MCP server.

Provides tools for querying and creating business events via the ServiceNow
sysevent table.
"""

import logging
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

EVENT_TABLE = "sysevent"

EVENT_FIELDS = [
    "sys_id",
    "name",
    "parm1",
    "parm2",
    "state",
    "queue",
    "process_on",
    "processed",
    "claimed_by",
    "fired_by",
    "instance",
    "table",
    "record",
    "error_string",
    "sys_created_on",
    "sys_created_by",
]

_STATE_LABELS = {
    "0": "pending",
    "1": "processed",
    "2": "error",
    "3": "cancelled",
}


class ListEventsParams(BaseModel):
    """Parameters for listing sysevent entries."""

    limit: Optional[int] = Field(20, description="Maximum number of events to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    name: Optional[str] = Field(None, description="Filter by event name (substring match, e.g. 'incident.created')")
    state: Optional[str] = Field(
        None,
        description="Filter by event state: 0=pending, 1=processed, 2=error, 3=cancelled",
    )
    queue: Optional[str] = Field(None, description="Filter by queue name")
    fired_by: Optional[str] = Field(None, description="Filter by the user who fired the event (sys_id or username)")
    created_after: Optional[str] = Field(
        None,
        description="Return events created after this datetime (format: YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)",
    )
    created_before: Optional[str] = Field(
        None,
        description="Return events created before this datetime (format: YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)",
    )
    order_by: Optional[str] = Field(
        "DESCsys_created_on",
        description="Sort order. Use 'DESCsys_created_on' for newest first (default) or 'sys_created_on' for oldest first",
    )

    @field_validator("created_after", "created_before", mode="before")
    @classmethod
    def _validate_datetime_fields(cls, v):
        return validate_servicenow_datetime(v)


class GetEventParams(BaseModel):
    """Parameters for retrieving a single sysevent by sys_id."""

    sys_id: str = Field(..., description="sys_id of the sysevent record to retrieve")


class CreateEventParams(BaseModel):
    """Parameters for creating a new sysevent entry."""

    name: str = Field(..., description="Event name (e.g. 'incident.created', 'task.completed')")
    parm1: Optional[str] = Field(None, description="First event parameter (often a record sys_id or descriptive value)")
    parm2: Optional[str] = Field(None, description="Second event parameter")
    queue: Optional[str] = Field(None, description="Event queue name (default: 'default')")
    process_on: Optional[str] = Field(
        None,
        description="Datetime when the event should be processed (format: YYYY-MM-DD HH:MM:SS). Leave blank to process immediately.",
    )
    table: Optional[str] = Field(None, description="Related table name (e.g. 'incident')")
    record: Optional[str] = Field(None, description="Related record sys_id")
    fired_by: Optional[str] = Field(None, description="sys_id of the user firing the event")

    @field_validator("process_on", mode="before")
    @classmethod
    def _validate_process_on(cls, v):
        return validate_servicenow_datetime(v)


def _format_event(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw sysevent record."""
    raw_state = record.get("state", "")
    state_label = _STATE_LABELS.get(str(raw_state), str(raw_state))
    fired_by = record.get("fired_by")
    if isinstance(fired_by, dict):
        fired_by = fired_by.get("display_value") or fired_by.get("value")
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "parm1": record.get("parm1"),
        "parm2": record.get("parm2"),
        "state": state_label,
        "queue": record.get("queue"),
        "process_on": record.get("process_on"),
        "processed": record.get("processed"),
        "claimed_by": record.get("claimed_by"),
        "fired_by": fired_by,
        "instance": record.get("instance"),
        "table": record.get("table"),
        "record": record.get("record"),
        "error_string": record.get("error_string"),
        "created_on": record.get("sys_created_on"),
        "created_by": record.get("sys_created_by"),
    }


def list_events(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List sysevent entries from the ServiceNow sysevent table.

    Supports filtering by event name, state, queue, fired_by, and date range.
    Results are ordered newest-first by default.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListEventsParams.

    Returns:
        Dictionary with ``success``, ``events`` (list), ``count``, and
        optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListEventsParams)
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
    if validated.state:
        query_parts.append(f"state={validated.state}")
    if validated.queue:
        query_parts.append(f"queueLIKE{validated.queue}")
    if validated.fired_by:
        query_parts.append(f"fired_by={validated.fired_by}")
    if validated.created_after:
        query_parts.append(f"sys_created_on>={validated.created_after}")
    if validated.created_before:
        query_parts.append(f"sys_created_on<={validated.created_before}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by=validated.order_by or "DESCsys_created_on",
        fields=",".join(EVENT_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{EVENT_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        events = [_format_event(r) for r in response.json().get("result", [])]
        return _paginated_list_response(events, validated.limit, validated.offset, "events")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing events: {e}")
        return {"success": False, "message": f"Error listing events: {_format_http_error(e)}"}


def get_event(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single sysevent record by its sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetEventParams.

    Returns:
        Dictionary with ``success`` and ``event`` keys.
    """
    result = _unwrap_and_validate_params(params, GetEventParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}/api/now/table/{EVENT_TABLE}/{validated.sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(EVENT_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Event not found: {validated.sys_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Event not found: {validated.sys_id}"}
        return {"success": True, "event": _format_event(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving event: {e}")
        return {"success": False, "message": f"Error retrieving event: {_format_http_error(e)}"}


def create_event(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new business event in the ServiceNow sysevent table.

    Inserting a record into sysevent queues the event for processing by the
    ServiceNow event management subsystem.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateEventParams.

    Returns:
        Dictionary with ``success``, ``event`` (the created record), and
        ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, CreateEventParams, required_fields=["name"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    body: Dict[str, Any] = {"name": validated.name}
    if validated.parm1 is not None:
        body["parm1"] = validated.parm1
    if validated.parm2 is not None:
        body["parm2"] = validated.parm2
    if validated.queue is not None:
        body["queue"] = validated.queue
    if validated.process_on is not None:
        body["process_on"] = validated.process_on
    if validated.table is not None:
        body["table"] = validated.table
    if validated.record is not None:
        body["record"] = validated.record
    if validated.fired_by is not None:
        body["fired_by"] = validated.fired_by

    url = f"{instance_url}/api/now/table/{EVENT_TABLE}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(EVENT_FIELDS),
    }
    try:
        response = _make_request("POST", url, headers=headers, params=query_params, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Event '{validated.name}' created successfully",
            "event": _format_event(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating event: {e}")
        return {"success": False, "message": f"Error creating event: {_format_http_error(e)}"}
