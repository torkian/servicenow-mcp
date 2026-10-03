"""
SLA breach notification tools for the ServiceNow MCP server.

Provides tools for monitoring at-risk SLAs (approaching breach) and
triggering or listing SLA breach notification events via the sysevent table.
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
)

logger = logging.getLogger(__name__)

TASK_SLA_TABLE = "/api/now/table/task_sla"
SYSEVENT_TABLE = "/api/now/table/sysevent"

TASK_SLA_FIELDS = [
    "sys_id",
    "task",
    "sla",
    "stage",
    "has_breached",
    "percentage",
    "business_percentage",
    "business_time_left",
    "time_left",
    "breach_time",
    "start_time",
    "end_time",
    "table_name",
    "sys_updated_on",
]

SYSEVENT_FIELDS = [
    "sys_id",
    "name",
    "parm1",
    "parm2",
    "source",
    "state",
    "processed",
    "process_on",
    "sys_created_on",
    "sys_updated_on",
]


def _format_task_sla(record: Dict[str, Any]) -> Dict[str, Any]:
    def _val(v):
        if isinstance(v, dict):
            return v.get("display_value") or v.get("value", "")
        return v

    return {
        "sys_id": _val(record.get("sys_id", "")),
        "task": _val(record.get("task", "")),
        "sla": _val(record.get("sla", "")),
        "stage": _val(record.get("stage", "")),
        "has_breached": _val(record.get("has_breached", "false")) in ("true", True),
        "percentage": _val(record.get("percentage", "")),
        "business_percentage": _val(record.get("business_percentage", "")),
        "business_time_left": _val(record.get("business_time_left", "")),
        "time_left": _val(record.get("time_left", "")),
        "breach_time": _val(record.get("breach_time", "")),
        "start_time": _val(record.get("start_time", "")),
        "end_time": _val(record.get("end_time", "")),
        "table_name": _val(record.get("table_name", "")),
        "sys_updated_on": _val(record.get("sys_updated_on", "")),
    }


def _format_sysevent(record: Dict[str, Any]) -> Dict[str, Any]:
    def _val(v):
        if isinstance(v, dict):
            return v.get("display_value") or v.get("value", "")
        return v

    return {
        "sys_id": _val(record.get("sys_id", "")),
        "name": _val(record.get("name", "")),
        "parm1": _val(record.get("parm1", "")),
        "parm2": _val(record.get("parm2", "")),
        "source": _val(record.get("source", "")),
        "state": _val(record.get("state", "")),
        "processed": _val(record.get("processed", "")),
        "process_on": _val(record.get("process_on", "")),
        "sys_created_on": _val(record.get("sys_created_on", "")),
        "sys_updated_on": _val(record.get("sys_updated_on", "")),
    }


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListAtRiskSLAsParams(BaseModel):
    """Parameters for listing task_sla records approaching breach."""

    threshold: Optional[int] = Field(
        80,
        ge=1,
        le=99,
        description="Minimum elapsed percentage (default 80). Records with "
        "percentage >= threshold and has_breached=false are returned.",
    )
    table_name: Optional[str] = Field(
        None,
        description="Scope to a specific task table, e.g. 'incident' or 'change_request'.",
    )
    stage: Optional[str] = Field(
        None,
        description="Filter by SLA stage, e.g. 'In Progress'.",
    )
    limit: Optional[int] = Field(20, description="Maximum records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")


class CreateSLABreachNotificationParams(BaseModel):
    """Parameters for creating an SLA breach notification event."""

    task_sys_id: str = Field(
        ...,
        description="sys_id of the task record (e.g. incident sys_id) that breached its SLA.",
    )
    sla_sys_id: Optional[str] = Field(
        None,
        description="sys_id of the task_sla (breach) record. Stored as parm2 on the event.",
    )
    source: Optional[str] = Field(
        "servicenow-mcp",
        description="Source label for the sysevent record (default 'servicenow-mcp').",
    )
    event_name: Optional[str] = Field(
        "sla.breach",
        description="ServiceNow event name to fire (default 'sla.breach').",
    )

    @field_validator("task_sys_id")
    @classmethod
    def validate_task_sys_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("task_sys_id cannot be empty")
        return v.strip()


class ListSLABreachEventsParams(BaseModel):
    """Parameters for listing SLA breach events from the sysevent table."""

    event_name: Optional[str] = Field(
        "sla.breach",
        description="Event name to filter on (default 'sla.breach').",
    )
    state: Optional[str] = Field(
        None,
        description="Filter by processing state, e.g. 'ready', 'processed', 'error'.",
    )
    source: Optional[str] = Field(
        None,
        description="Filter by event source.",
    )
    limit: Optional[int] = Field(20, description="Maximum records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def list_at_risk_slas(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List task_sla records that are at risk of breaching.

    Queries task_sla for active (not yet breached) records whose elapsed
    percentage is at or above *threshold* (default 80%).  This lets operators
    identify and act on impending breaches before they occur.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListAtRiskSLAsParams.

    Returns:
        Dictionary with ``success``, ``at_risk_slas`` (list), ``count``, and
        pagination keys.
    """
    result = _unwrap_and_validate_params(params, ListAtRiskSLAsParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    threshold = validated.threshold if validated.threshold is not None else 80

    filters = [
        "has_breached=false",
        f"percentage>={threshold}",
    ]
    if validated.table_name:
        filters.append(f"table_name={validated.table_name}")
    if validated.stage:
        filters.append(f"stage={validated.stage}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(filters),
        exclude_reference_link=True,
        fields=",".join(TASK_SLA_FIELDS),
    )

    url = f"{instance_url}{TASK_SLA_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        records = [_format_task_sla(r) for r in response.json().get("result", [])]
        return _paginated_list_response(records, validated.limit, validated.offset, "at_risk_slas")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing at-risk SLAs: {e}")
        return {"success": False, "message": f"Error listing at-risk SLAs: {_format_http_error(e)}"}


def create_sla_breach_notification(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a ServiceNow sysevent record to trigger an SLA breach notification.

    Posts an event (default name ``sla.breach``) to the sysevent table.
    ServiceNow's built-in notification engine picks up matching events and
    dispatches the configured email/push alerts to the task's assignment group.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateSLABreachNotificationParams.

    Returns:
        Dictionary with ``success`` and ``event`` keys.
    """
    result = _unwrap_and_validate_params(
        params, CreateSLABreachNotificationParams, required_fields=["task_sys_id"]
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

    body: Dict[str, Any] = {
        "name": validated.event_name or "sla.breach",
        "parm1": validated.task_sys_id,
        "source": validated.source or "servicenow-mcp",
    }
    if validated.sla_sys_id:
        body["parm2"] = validated.sla_sys_id

    url = f"{instance_url}{SYSEVENT_TABLE}"
    try:
        response = _make_request("POST", url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json().get("result", {})
        return {"success": True, "event": _format_sysevent(data)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating SLA breach notification: {e}")
        return {
            "success": False,
            "message": f"Error creating SLA breach notification: {_format_http_error(e)}",
        }


def list_sla_breach_events(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List SLA breach events from the ServiceNow sysevent table.

    Returns sysevent records whose name matches *event_name* (default
    ``sla.breach``).  Useful for auditing which breach notifications have been
    fired and whether they were processed successfully.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListSLABreachEventsParams.

    Returns:
        Dictionary with ``success``, ``events`` (list), ``count``, and
        pagination keys.
    """
    result = _unwrap_and_validate_params(params, ListSLABreachEventsParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    event_name = validated.event_name if validated.event_name else "sla.breach"
    filters = [f"name={event_name}"]
    if validated.state:
        filters.append(f"state={validated.state}")
    if validated.source:
        filters.append(f"source={validated.source}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(filters),
        exclude_reference_link=True,
        fields=",".join(SYSEVENT_FIELDS),
    )

    url = f"{instance_url}{SYSEVENT_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        events = [_format_sysevent(r) for r in response.json().get("result", [])]
        return _paginated_list_response(events, validated.limit, validated.offset, "events")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing SLA breach events: {e}")
        return {
            "success": False,
            "message": f"Error listing SLA breach events: {_format_http_error(e)}",
        }
