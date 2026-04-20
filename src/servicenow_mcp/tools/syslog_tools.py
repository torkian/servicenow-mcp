"""
Syslog tools for the ServiceNow MCP server.

This module provides tools for querying syslog entries from the ServiceNow
syslog table (sys_log).
"""

import logging
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field, field_validator

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.helpers import (
    _format_http_error,
    _get_headers,
    _get_instance_url,
    _unwrap_and_validate_params,
    validate_servicenow_datetime,
)

logger = logging.getLogger(__name__)

SYSLOG_TABLE = "sys_log"

SYSLOG_FIELDS = [
    "sys_id",
    "level",
    "message",
    "source",
    "type",
    "sys_created_on",
    "sys_created_by",
    "sequence",
]


class ListSyslogEntriesParams(BaseModel):
    """Parameters for listing syslog entries."""

    limit: Optional[int] = Field(20, description="Maximum number of entries to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    level: Optional[str] = Field(
        None,
        description="Filter by log level: debug, info, warning, error",
    )
    source: Optional[str] = Field(None, description="Filter by log source (application or module name)")
    message_contains: Optional[str] = Field(None, description="Filter entries whose message contains this text")
    created_after: Optional[str] = Field(
        None,
        description="Return entries created after this datetime (format: YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)",
    )
    created_before: Optional[str] = Field(
        None,
        description="Return entries created before this datetime (format: YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)",
    )
    order_by: Optional[str] = Field(
        "DESCsys_created_on",
        description="Sort order. Use 'DESCsys_created_on' for newest first (default) or 'sys_created_on' for oldest first",
    )

    @field_validator("created_after", "created_before", mode="before")
    @classmethod
    def _validate_datetime_fields(cls, v):
        return validate_servicenow_datetime(v)


class GetSyslogEntryParams(BaseModel):
    """Parameters for retrieving a single syslog entry by sys_id."""

    sys_id: str = Field(..., description="sys_id of the syslog entry to retrieve")


def _format_syslog_entry(entry: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw syslog record."""
    return {
        "sys_id": entry.get("sys_id"),
        "level": entry.get("level"),
        "message": entry.get("message"),
        "source": entry.get("source"),
        "type": entry.get("type"),
        "created_on": entry.get("sys_created_on"),
        "created_by": entry.get("sys_created_by"),
        "sequence": entry.get("sequence"),
    }


def list_syslog_entries(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List syslog entries from the ServiceNow sys_log table.

    Supports filtering by level, source, message text, and date range.
    Results are ordered newest-first by default.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListSyslogEntriesParams.

    Returns:
        Dictionary with ``success``, ``entries`` (list), and ``count`` keys.
    """
    result = _unwrap_and_validate_params(params, ListSyslogEntriesParams)
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
    if validated.level:
        query_parts.append(f"level={validated.level}")
    if validated.source:
        query_parts.append(f"sourceLIKE{validated.source}")
    if validated.message_contains:
        query_parts.append(f"messageLIKE{validated.message_contains}")
    if validated.created_after:
        query_parts.append(f"sys_created_on>={validated.created_after}")
    if validated.created_before:
        query_parts.append(f"sys_created_on<={validated.created_before}")

    query_params: Dict[str, Any] = {
        "sysparm_limit": validated.limit,
        "sysparm_offset": validated.offset,
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(SYSLOG_FIELDS),
        "sysparm_orderby": validated.order_by or "DESCsys_created_on",
    }
    if query_parts:
        query_params["sysparm_query"] = "^".join(query_parts)

    url = f"{instance_url}/api/now/table/{SYSLOG_TABLE}"
    try:
        response = requests.get(url, headers=headers, params=query_params)
        response.raise_for_status()
        records = response.json().get("result", [])
        entries = [_format_syslog_entry(r) for r in records]
        return {
            "success": True,
            "entries": entries,
            "count": len(entries),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing syslog entries: {e}")
        return {"success": False, "message": f"Error listing syslog entries: {_format_http_error(e)}"}


def get_syslog_entry(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single syslog entry by its sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetSyslogEntryParams.

    Returns:
        Dictionary with ``success`` and ``entry`` keys.
    """
    result = _unwrap_and_validate_params(params, GetSyslogEntryParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}/api/now/table/{SYSLOG_TABLE}/{validated.sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(SYSLOG_FIELDS),
    }
    try:
        response = requests.get(url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Syslog entry not found: {validated.sys_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Syslog entry not found: {validated.sys_id}"}
        return {
            "success": True,
            "entry": _format_syslog_entry(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving syslog entry: {e}")
        return {"success": False, "message": f"Error retrieving syslog entry: {_format_http_error(e)}"}
