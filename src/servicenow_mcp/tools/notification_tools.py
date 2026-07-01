"""
Notification history tools for the ServiceNow MCP server.

Provides tools for listing outbound email notification records from the
sysevent_email_log table via the /api/now/table/* endpoint.
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

NOTIFICATION_TABLE = "/api/now/table/sysevent_email_log"

NOTIFICATION_FIELDS = [
    "sys_id",
    "type",
    "source",
    "target",
    "subject",
    "email_address",
    "state",
    "error_string",
    "weight",
    "sys_created_on",
    "sys_updated_on",
]


class ListNotificationsParams(BaseModel):
    """Parameters for listing email notification log entries."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    state: Optional[str] = Field(
        None,
        description="Filter by delivery state (e.g. 'sent', 'failed', 'skipped')",
    )
    type: Optional[str] = Field(
        None,
        description="Filter by notification type/name (LIKE match)",
    )
    email_address: Optional[str] = Field(
        None,
        description="Filter by recipient email address (LIKE match)",
    )
    source: Optional[str] = Field(
        None,
        description="Filter by source record sys_id (32-char hex)",
    )
    created_after: Optional[str] = Field(
        None,
        description="Return records created after this datetime (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)",
    )
    created_before: Optional[str] = Field(
        None,
        description="Return records created before this datetime (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)",
    )


def _format_notification(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw sysevent_email_log record."""

    def _display(val):
        if isinstance(val, dict):
            return val.get("display_value") or val.get("value")
        return val

    return {
        "sys_id": record.get("sys_id"),
        "type": record.get("type"),
        "source": _display(record.get("source")),
        "target": _display(record.get("target")),
        "subject": record.get("subject"),
        "email_address": record.get("email_address"),
        "state": record.get("state"),
        "error_string": record.get("error_string"),
        "weight": record.get("weight"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def list_notifications(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List outbound email notification records from the sysevent_email_log table.

    Useful for auditing notification delivery, diagnosing failed emails, or
    reviewing what notifications were sent for a particular source record.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListNotificationsParams.

    Returns:
        Dictionary with ``success``, ``notifications`` (list), ``count``, and
        pagination keys (``has_more``, ``next_offset``).
    """
    result = _unwrap_and_validate_params(params, ListNotificationsParams)
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
    if validated.state:
        filters.append(f"state={validated.state}")
    if validated.type:
        filters.append(f"typeLIKE{validated.type}")
    if validated.email_address:
        filters.append(f"email_addressLIKE{validated.email_address}")
    if validated.source:
        filters.append(f"source={validated.source}")
    if validated.created_after:
        filters.append(f"sys_created_on>={validated.created_after}")
    if validated.created_before:
        filters.append(f"sys_created_on<={validated.created_before}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(filters),
        exclude_reference_link=True,
        fields=",".join(NOTIFICATION_FIELDS),
    )

    url = f"{instance_url}{NOTIFICATION_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        notifications = [_format_notification(r) for r in response.json().get("result", [])]
        return _paginated_list_response(
            notifications, validated.limit, validated.offset, "notifications"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing notifications: {e}")
        return {
            "success": False,
            "message": f"Error listing notifications: {_format_http_error(e)}",
        }
