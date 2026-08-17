"""
Metric and gauge tools for the ServiceNow MCP server.

Provides tools for querying metric definitions (sys_metric_base) and metric
values (sys_metric), which record quantitative measurements gathered from
ServiceNow table fields over time.
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
    validate_servicenow_date,
)

logger = logging.getLogger(__name__)

METRIC_BASE_TABLE = "sys_metric_base"
METRIC_VALUE_TABLE = "sys_metric"

METRIC_BASE_FIELDS = [
    "sys_id",
    "name",
    "description",
    "table",
    "field",
    "type",
    "condition",
    "active",
    "sys_created_on",
    "sys_updated_on",
]

METRIC_VALUE_FIELDS = [
    "sys_id",
    "metric_definition",
    "table_name",
    "id",
    "value",
    "date",
    "starts",
    "ends",
    "sum_of_squares",
    "count",
    "sys_created_on",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListMetricDefinitionsParams(BaseModel):
    """Parameters for listing metric definitions."""

    limit: Optional[int] = Field(20, description="Maximum number of definitions to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    name: Optional[str] = Field(None, description="Filter by metric name (substring match)")
    table: Optional[str] = Field(None, description="Filter by the table the metric applies to (e.g. 'incident')")
    metric_type: Optional[str] = Field(
        None,
        description=(
            "Filter by metric type. Common values: avg, sum, count, max, min, "
            "percentage, custom"
        ),
    )
    active: Optional[bool] = Field(None, description="Filter by active flag (true=active only, false=inactive only)")


class GetMetricDefinitionParams(BaseModel):
    """Parameters for retrieving a single metric definition."""

    metric_id: str = Field(
        ...,
        description=(
            "sys_id of the metric definition, or its exact name. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a name= lookup on sys_metric_base."
        ),
    )


class ListMetricValuesParams(BaseModel):
    """Parameters for listing metric value records."""

    limit: Optional[int] = Field(20, description="Maximum number of metric values to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    metric_definition_id: Optional[str] = Field(
        None,
        description=(
            "sys_id or name of the metric definition to filter by. "
            "Names are resolved to a sys_id automatically."
        ),
    )
    table_name: Optional[str] = Field(
        None,
        description="Filter by the table the metric was collected from (e.g. 'incident')",
    )
    record_id: Optional[str] = Field(
        None,
        description="Filter by the sys_id of the specific record that was measured",
    )
    date_on_or_after: Optional[str] = Field(
        None,
        description="Return values on or after this date (format: YYYY-MM-DD)",
    )
    date_on_or_before: Optional[str] = Field(
        None,
        description="Return values on or before this date (format: YYYY-MM-DD)",
    )
    order_by: Optional[str] = Field(
        "DESCdate",
        description="Sort order. Use 'DESCdate' for newest first (default) or 'date' for oldest first",
    )

    @field_validator("date_on_or_after", "date_on_or_before", mode="before")
    @classmethod
    def _validate_date_fields(cls, v):
        return validate_servicenow_date(v)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _format_metric_definition(record: Dict) -> Dict:
    """Normalise a raw sys_metric_base record."""
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "description": record.get("description"),
        "table": record.get("table"),
        "field": record.get("field"),
        "type": record.get("type"),
        "condition": record.get("condition"),
        "active": record.get("active"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _format_metric_value(record: Dict) -> Dict:
    """Normalise a raw sys_metric record."""
    metric_def = record.get("metric_definition")
    if isinstance(metric_def, dict):
        metric_def = metric_def.get("display_value") or metric_def.get("value")
    return {
        "sys_id": record.get("sys_id"),
        "metric_definition": metric_def,
        "table_name": record.get("table_name"),
        "record_id": record.get("id"),
        "value": record.get("value"),
        "date": record.get("date"),
        "period_starts": record.get("starts"),
        "period_ends": record.get("ends"),
        "sum_of_squares": record.get("sum_of_squares"),
        "count": record.get("count"),
        "created_on": record.get("sys_created_on"),
    }


# ---------------------------------------------------------------------------
# Resolver helper
# ---------------------------------------------------------------------------


def _resolve_metric_definition_sys_id(
    metric_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a metric definition name to its sys_id.

    If *metric_id* looks like a 32-character hex sys_id it is returned
    unchanged.  Otherwise a GET against sys_metric_base with ``name=<value>``
    is performed and the first match's sys_id returned.

    Returns ``None`` when no matching definition is found.
    """
    if len(metric_id) == 32 and all(c in "0123456789abcdefABCDEF" for c in metric_id):
        return metric_id
    url = f"{instance_url}/api/now/table/{METRIC_BASE_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={metric_id}",
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


def list_metric_definitions(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List metric definitions from the ServiceNow sys_metric_base table.

    Metric definitions describe *what* is being measured: the source table,
    the field, the aggregation type, and an optional filter condition.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListMetricDefinitionsParams.

    Returns:
        Dictionary with ``success``, ``metric_definitions`` (list), ``count``,
        and optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListMetricDefinitionsParams)
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
    if validated.table:
        query_parts.append(f"table={validated.table}")
    if validated.metric_type:
        query_parts.append(f"type={validated.metric_type}")
    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="name",
        fields=",".join(METRIC_BASE_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{METRIC_BASE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        definitions = [_format_metric_definition(r) for r in response.json().get("result", [])]
        return _paginated_list_response(definitions, validated.limit, validated.offset, "metric_definitions")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing metric definitions: {e}")
        return {"success": False, "message": f"Error listing metric definitions: {_format_http_error(e)}"}


def get_metric_definition(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single metric definition by sys_id or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetMetricDefinitionParams.

    Returns:
        Dictionary with ``success`` and ``metric_definition`` keys.
    """
    result = _unwrap_and_validate_params(params, GetMetricDefinitionParams, required_fields=["metric_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    # Resolve name → sys_id when necessary
    sys_id = _resolve_metric_definition_sys_id(validated.metric_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Metric definition not found: {validated.metric_id}"}

    url = f"{instance_url}/api/now/table/{METRIC_BASE_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(METRIC_BASE_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Metric definition not found: {validated.metric_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Metric definition not found: {validated.metric_id}"}
        return {"success": True, "metric_definition": _format_metric_definition(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving metric definition: {e}")
        return {"success": False, "message": f"Error retrieving metric definition: {_format_http_error(e)}"}


def list_metric_values(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List metric value records from the ServiceNow sys_metric table.

    Metric values are the time-stamped measurements gathered by a metric
    definition.  Results can be filtered by metric definition, source table,
    specific record, and date range.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListMetricValuesParams.

    Returns:
        Dictionary with ``success``, ``metric_values`` (list), ``count``,
        and optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListMetricValuesParams)
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

    # Resolve metric definition identifier if supplied
    if validated.metric_definition_id:
        def_sys_id = _resolve_metric_definition_sys_id(
            validated.metric_definition_id, instance_url, headers
        )
        if not def_sys_id:
            return {
                "success": False,
                "message": f"Metric definition not found: {validated.metric_definition_id}",
            }
        query_parts.append(f"metric_definition={def_sys_id}")

    if validated.table_name:
        query_parts.append(f"table_name={validated.table_name}")
    if validated.record_id:
        query_parts.append(f"id={validated.record_id}")
    if validated.date_on_or_after:
        query_parts.append(f"date>={validated.date_on_or_after}")
    if validated.date_on_or_before:
        query_parts.append(f"date<={validated.date_on_or_before}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by=validated.order_by or "DESCdate",
        fields=",".join(METRIC_VALUE_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{METRIC_VALUE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        values = [_format_metric_value(r) for r in response.json().get("result", [])]
        return _paginated_list_response(values, validated.limit, validated.offset, "metric_values")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing metric values: {e}")
        return {"success": False, "message": f"Error listing metric values: {_format_http_error(e)}"}
