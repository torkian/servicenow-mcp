"""
Report tools for the ServiceNow MCP server.

Provides tools for querying and executing ServiceNow reports via the
sys_report table and the reporting REST API.
"""

import logging
from typing import Any, Dict, List, Optional

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

REPORT_TABLE = "sys_report"

REPORT_LIST_FIELDS = [
    "sys_id",
    "title",
    "table",
    "type",
    "description",
    "category",
    "user",
    "active",
    "is_scheduled",
    "sys_created_on",
    "sys_updated_on",
]

REPORT_DETAIL_FIELDS = REPORT_LIST_FIELDS + [
    "field",
    "group_by",
    "order_by",
    "filter",
    "conditions",
    "trend_field",
    "sum_field",
    "count_field",
    "show_query",
    "sys_created_by",
    "sys_updated_by",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListReportsParams(BaseModel):
    """Parameters for listing ServiceNow reports."""

    limit: Optional[int] = Field(20, description="Maximum number of reports to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    title: Optional[str] = Field(None, description="Filter by report title (substring match)")
    table: Optional[str] = Field(
        None,
        description="Filter by the source table the report runs against (e.g. 'incident')",
    )
    report_type: Optional[str] = Field(
        None,
        description=(
            "Filter by report type. Common values: bar, pie, list, trend, "
            "histogram, map, gauge, trendbox, pivot"
        ),
    )
    category: Optional[str] = Field(None, description="Filter by report category (substring match)")
    active: Optional[bool] = Field(None, description="Filter by active flag (true=active only)")


class GetReportParams(BaseModel):
    """Parameters for retrieving a single report."""

    report_id: str = Field(
        ...,
        description=(
            "sys_id of the report, or its exact title. "
            "A 32-character hex string is treated as a sys_id; anything else triggers "
            "a titleSTARTSWITH lookup on sys_report."
        ),
    )


class RunReportParams(BaseModel):
    """Parameters for executing/running a ServiceNow report."""

    report_id: str = Field(
        ...,
        description=(
            "sys_id of the report to execute, or its exact title (auto-resolved). "
            "A 32-character hex string is treated as a sys_id."
        ),
    )
    output_format: Optional[str] = Field(
        "json",
        description=(
            "Desired output format hint. One of: 'json', 'csv', 'pdf', 'excel'. "
            "When 'json', the tool fetches report metadata and returns data rows "
            "by querying the report's source table using its filter conditions. "
            "For other formats the tool returns a download URL pattern."
        ),
    )
    limit: Optional[int] = Field(
        100,
        description="Maximum number of data rows to return when output_format='json' (default 100, max 1000)",
    )


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _normalise_ref(value: Any) -> Any:
    """Return display_value for reference dict fields."""
    if isinstance(value, dict):
        return value.get("display_value") or value.get("value")
    return value


def _format_report(record: Dict, fields: List[str] = REPORT_LIST_FIELDS) -> Dict:
    """Normalise a raw sys_report record."""
    result: Dict[str, Any] = {}
    for f in fields:
        result[f] = _normalise_ref(record.get(f))
    # Rename sys fields for clarity
    result["created_on"] = result.pop("sys_created_on", None)
    result["updated_on"] = result.pop("sys_updated_on", None)
    result["report_type"] = result.pop("type", None)
    return result


# ---------------------------------------------------------------------------
# Resolver helper
# ---------------------------------------------------------------------------


def _resolve_report_sys_id(
    report_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a report title to its sys_id.

    A 32-character hex string is returned unchanged.  Otherwise a GET against
    sys_report with ``titleSTARTSWITH<value>`` returns the first match.
    """
    if len(report_id) == 32 and all(c in "0123456789abcdefABCDEF" for c in report_id):
        return report_id
    url = f"{instance_url}/api/now/table/{REPORT_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"titleSTARTSWITH{report_id}",
                "sysparm_fields": "sys_id",
                "sysparm_limit": "1",
                "sysparm_exclude_reference_link": "true",
            },
        )
        response.raise_for_status()
        results = response.json().get("result", [])
        if results:
            return results[0].get("sys_id")
    except requests.exceptions.RequestException:
        pass
    return None


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def list_reports(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List ServiceNow reports from the sys_report table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListReportsParams.

    Returns:
        Dictionary with ``success``, ``reports`` (list), ``count``, and
        optional ``has_more``/``next_offset`` pagination keys.
    """
    result = _unwrap_and_validate_params(params, ListReportsParams)
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
    if validated.title:
        query_parts.append(f"titleLIKE{validated.title}")
    if validated.table:
        query_parts.append(f"table={validated.table}")
    if validated.report_type:
        query_parts.append(f"type={validated.report_type}")
    if validated.category:
        query_parts.append(f"categoryLIKE{validated.category}")
    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="title",
        fields=",".join(REPORT_LIST_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{REPORT_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        reports = [_format_report(r) for r in response.json().get("result", [])]
        return _paginated_list_response(reports, validated.limit, validated.offset, "reports")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing reports: {e}")
        return {"success": False, "message": f"Error listing reports: {_format_http_error(e)}"}


def get_report(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single ServiceNow report by sys_id or title.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetReportParams.

    Returns:
        Dictionary with ``success`` and ``report`` keys.
    """
    result = _unwrap_and_validate_params(params, GetReportParams, required_fields=["report_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_report_sys_id(validated.report_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Report not found: {validated.report_id}"}

    url = f"{instance_url}/api/now/table/{REPORT_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(REPORT_DETAIL_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Report not found: {validated.report_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Report not found: {validated.report_id}"}
        return {"success": True, "report": _format_report(record, REPORT_DETAIL_FIELDS)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving report: {e}")
        return {"success": False, "message": f"Error retrieving report: {_format_http_error(e)}"}


def run_report(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute a ServiceNow report and return results.

    When output_format is 'json' the tool fetches the report metadata, then
    queries the report's source table using its stored filter conditions and
    returns up to *limit* data rows.

    For non-json formats (csv, pdf, excel) the tool returns a download URL
    pattern that the caller can use to retrieve the file from ServiceNow.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching RunReportParams.

    Returns:
        Dictionary with ``success``, ``report_id``, ``title``, ``table``,
        ``output_format``, and either ``data`` (list) with ``count`` for json
        output or ``download_url`` for file formats.
    """
    result = _unwrap_and_validate_params(params, RunReportParams, required_fields=["report_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    # Resolve report identifier
    sys_id = _resolve_report_sys_id(validated.report_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Report not found: {validated.report_id}"}

    # Fetch report metadata
    meta_url = f"{instance_url}/api/now/table/{REPORT_TABLE}/{sys_id}"
    try:
        meta_resp = _make_request(
            "GET",
            meta_url,
            headers=headers,
            params={
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
                "sysparm_fields": ",".join(REPORT_DETAIL_FIELDS),
            },
        )
        if meta_resp.status_code == 404:
            return {"success": False, "message": f"Report not found: {validated.report_id}"}
        meta_resp.raise_for_status()
        meta = meta_resp.json().get("result", {})
        if not meta:
            return {"success": False, "message": f"Report not found: {validated.report_id}"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching report metadata: {e}")
        return {"success": False, "message": f"Error fetching report metadata: {_format_http_error(e)}"}

    report_title = _normalise_ref(meta.get("title")) or validated.report_id
    source_table = _normalise_ref(meta.get("table")) or ""
    filter_conditions = _normalise_ref(meta.get("filter")) or ""

    output_format = (validated.output_format or "json").lower()

    if output_format != "json":
        fmt_map = {"csv": "csv", "pdf": "pdf", "excel": "xlsx"}
        ext = fmt_map.get(output_format, output_format)
        download_url = (
            f"{instance_url}/sys_report_download.do?sysparm_sys_id={sys_id}"
            f"&sysparm_type={ext}"
        )
        return {
            "success": True,
            "report_id": sys_id,
            "title": report_title,
            "table": source_table,
            "output_format": output_format,
            "download_url": download_url,
            "message": (
                f"Use the download_url to retrieve the report in {output_format.upper()} format. "
                "Requires a valid ServiceNow session cookie or basic-auth credentials in the request."
            ),
        }

    # JSON mode: query the source table using the report's conditions
    if not source_table:
        return {
            "success": False,
            "message": "Report has no source table defined; cannot execute in json mode.",
        }

    row_limit = min(int(validated.limit or 100), 1000)
    data_url = f"{instance_url}/api/now/table/{source_table}"
    data_params: Dict[str, Any] = {
        "sysparm_limit": str(row_limit),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }
    if filter_conditions:
        data_params["sysparm_query"] = filter_conditions

    # Optional order_by from report metadata
    order_by = _normalise_ref(meta.get("order_by"))
    if order_by:
        data_params["sysparm_orderby"] = order_by

    try:
        data_resp = _make_request("GET", data_url, headers=headers, params=data_params)
        data_resp.raise_for_status()
        rows = data_resp.json().get("result", [])
        return {
            "success": True,
            "report_id": sys_id,
            "title": report_title,
            "table": source_table,
            "output_format": "json",
            "count": len(rows),
            "data": rows,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error executing report: {e}")
        return {"success": False, "message": f"Error executing report: {_format_http_error(e)}"}
