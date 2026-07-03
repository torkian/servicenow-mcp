"""
Scheduled Job tools for the ServiceNow MCP server.

Provides tools for querying scheduled script execution jobs from the
sysauto_script table.
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

SCHEDULED_JOB_TABLE = "sysauto_script"

SCHEDULED_JOB_FIELDS = [
    "sys_id",
    "name",
    "active",
    "run_as",
    "run_type",
    "run_period",
    "run_start",
    "run_time",
    "run_dayofmonth",
    "run_dayofweek",
    "run_at",
    "script",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]


class ListScheduledJobsParams(BaseModel):
    """Parameters for listing scheduled jobs."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    name: Optional[str] = Field(
        None,
        description="Filter by job name (case-insensitive substring match)",
    )
    active: Optional[bool] = Field(
        None,
        description="Filter by active state. True returns only active jobs, False only inactive.",
    )
    run_as: Optional[str] = Field(
        None,
        description="Filter by the user name or sys_id of the run-as account",
    )
    run_type: Optional[str] = Field(
        None,
        description=(
            "Filter by run type (e.g. 'daily', 'weekly', 'monthly', 'once', 'periodically')"
        ),
    )


def _format_scheduled_job(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw sysauto_script record."""

    def _ref(value):
        if isinstance(value, dict):
            return value.get("display_value") or value.get("value")
        return value

    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "active": record.get("active"),
        "run_as": _ref(record.get("run_as")),
        "run_type": record.get("run_type"),
        "run_period": record.get("run_period"),
        "run_start": record.get("run_start"),
        "run_time": record.get("run_time"),
        "run_dayofmonth": record.get("run_dayofmonth"),
        "run_dayofweek": record.get("run_dayofweek"),
        "run_at": record.get("run_at"),
        "script": record.get("script"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def list_scheduled_jobs(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List scheduled script jobs from the ServiceNow sysauto_script table.

    Supports filtering by name substring, active state, run_as user, and
    run_type. Results are ordered by name ascending by default.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListScheduledJobsParams.

    Returns:
        Dictionary with ``success``, ``jobs`` (list), ``count``, ``has_more``,
        and ``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListScheduledJobsParams)
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
    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")
    if validated.run_as:
        query_parts.append(f"run_as.nameLIKE{validated.run_as}")
    if validated.run_type:
        query_parts.append(f"run_type={validated.run_type}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="name",
        fields=",".join(SCHEDULED_JOB_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{SCHEDULED_JOB_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        jobs = [_format_scheduled_job(r) for r in response.json().get("result", [])]
        return _paginated_list_response(
            jobs, validated.limit, validated.offset, "jobs",
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing scheduled jobs: {e}")
        return {"success": False, "message": f"Error listing scheduled jobs: {_format_http_error(e)}"}
