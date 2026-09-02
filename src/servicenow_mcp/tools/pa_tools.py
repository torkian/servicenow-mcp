"""
Performance Analytics tools for the ServiceNow MCP server.

Provides tools for querying Performance Analytics indicators (pa_indicator)
and their collected scores (pa_score).  PA indicators are formula-driven KPIs
that sit on top of ServiceNow data and are distinct from the field-level
sys_metric gauges.
"""

import logging
from typing import Any, Dict, List, Optional

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

PA_INDICATOR_TABLE = "pa_indicator"
PA_SCORE_TABLE = "pa_score"

PA_INDICATOR_FIELDS = [
    "sys_id",
    "name",
    "description",
    "indicator_group",
    "unit",
    "direction",
    "frequency",
    "active",
    "formula",
    "condition",
    "table",
    "sys_created_on",
    "sys_updated_on",
]

PA_SCORE_FIELDS = [
    "sys_id",
    "indicator",
    "period",
    "value",
    "breakdownvalue",
    "sys_created_on",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListPAIndicatorsParams(BaseModel):
    """Parameters for listing Performance Analytics indicators."""

    limit: Optional[int] = Field(20, description="Maximum number of indicators to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    name: Optional[str] = Field(None, description="Filter by indicator name (substring match)")
    active: Optional[bool] = Field(None, description="Filter by active flag (true=active only)")
    frequency: Optional[str] = Field(
        None,
        description=(
            "Filter by collection frequency. Common values: daily, weekly, monthly, quarterly, yearly"
        ),
    )
    indicator_group: Optional[str] = Field(
        None,
        description="Filter by indicator group name (substring match)",
    )


class GetPAIndicatorParams(BaseModel):
    """Parameters for retrieving a single Performance Analytics indicator."""

    indicator_id: str = Field(
        ...,
        description=(
            "sys_id of the PA indicator, or its exact name. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a name= lookup on pa_indicator."
        ),
    )


class ListPAScoresParams(BaseModel):
    """Parameters for listing Performance Analytics scores."""

    limit: Optional[int] = Field(20, description="Maximum number of scores to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    indicator_id: Optional[str] = Field(
        None,
        description=(
            "sys_id or exact name of the PA indicator to filter by. "
            "Names are resolved to a sys_id automatically."
        ),
    )
    period_start: Optional[str] = Field(
        None,
        description="Return scores for periods on or after this date (YYYY-MM-DD)",
    )
    period_end: Optional[str] = Field(
        None,
        description="Return scores for periods on or before this date (YYYY-MM-DD)",
    )

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def _validate_date_fields(cls, v):
        return validate_servicenow_date(v)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _ref_display(field) -> Optional[str]:
    """Extract display_value from a reference dict, or return the string as-is."""
    if isinstance(field, dict):
        return field.get("display_value") or field.get("value")
    return field


def _format_pa_indicator(record: Dict) -> Dict:
    """Normalise a raw pa_indicator record."""
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "description": record.get("description"),
        "indicator_group": _ref_display(record.get("indicator_group")),
        "unit": _ref_display(record.get("unit")),
        "direction": record.get("direction"),
        "frequency": record.get("frequency"),
        "active": record.get("active"),
        "formula": record.get("formula"),
        "condition": record.get("condition"),
        "table": _ref_display(record.get("table")),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _format_pa_score(record: Dict) -> Dict:
    """Normalise a raw pa_score record."""
    return {
        "sys_id": record.get("sys_id"),
        "indicator": _ref_display(record.get("indicator")),
        "period": _ref_display(record.get("period")),
        "value": record.get("value"),
        "breakdown_value": _ref_display(record.get("breakdownvalue")),
        "created_on": record.get("sys_created_on"),
    }


# ---------------------------------------------------------------------------
# Resolver helper
# ---------------------------------------------------------------------------


def _resolve_pa_indicator_sys_id(
    indicator_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a PA indicator name to its sys_id.

    If *indicator_id* is a 32-character hex string it is returned unchanged.
    Otherwise a GET against pa_indicator with ``name=<value>`` is performed
    and the first match's sys_id returned.  Returns ``None`` when not found.
    """
    if len(indicator_id) == 32 and all(c in "0123456789abcdefABCDEF" for c in indicator_id):
        return indicator_id
    url = f"{instance_url}/api/now/table/{PA_INDICATOR_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={indicator_id}",
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


def list_pa_indicators(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List Performance Analytics indicators from the pa_indicator table.

    PA indicators are KPI definitions used by ServiceNow Performance Analytics.
    Each indicator specifies a data source, an aggregation formula, a direction
    (maximise/minimise), and a collection frequency.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListPAIndicatorsParams.

    Returns:
        Dictionary with ``success``, ``indicators`` (list), ``count``,
        and optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListPAIndicatorsParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    query_parts: List[str] = []
    if validated.name:
        query_parts.append(f"nameLIKE{validated.name}")
    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")
    if validated.frequency:
        query_parts.append(f"frequency={validated.frequency}")
    if validated.indicator_group:
        query_parts.append(f"indicator_group.nameLIKE{validated.indicator_group}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=False,
        order_by="name",
        fields=",".join(PA_INDICATOR_FIELDS),
    )
    query_params["sysparm_display_value"] = "all"

    url = f"{instance_url}/api/now/table/{PA_INDICATOR_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        indicators = [_format_pa_indicator(r) for r in response.json().get("result", [])]
        return _paginated_list_response(indicators, validated.limit, validated.offset, "indicators")
    except requests.exceptions.HTTPError as exc:
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def get_pa_indicator(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single Performance Analytics indicator by sys_id or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetPAIndicatorParams.

    Returns:
        Dictionary with ``success`` and ``indicator`` keys, or an error message.
    """
    result = _unwrap_and_validate_params(params, GetPAIndicatorParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_pa_indicator_sys_id(validated.indicator_id, instance_url, headers)
    if not sys_id:
        return {
            "success": False,
            "message": f"PA indicator not found: {validated.indicator_id}",
        }

    url = f"{instance_url}/api/now/table/{PA_INDICATOR_TABLE}/{sys_id}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_fields": ",".join(PA_INDICATOR_FIELDS),
                "sysparm_display_value": "all",
            },
        )
        response.raise_for_status()
        data = response.json().get("result")
        if not data:
            return {"success": False, "message": f"PA indicator not found: {sys_id}"}
        return {"success": True, "indicator": _format_pa_indicator(data)}
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA indicator not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def list_pa_scores(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List Performance Analytics score records from the pa_score table.

    PA scores are the collected values for a given indicator over a given time
    period.  They can be filtered by indicator (name or sys_id) and by the
    date of the period.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListPAScoresParams.

    Returns:
        Dictionary with ``success``, ``scores`` (list), ``count``,
        and optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListPAScoresParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    query_parts: List[str] = []

    if validated.indicator_id:
        sys_id = _resolve_pa_indicator_sys_id(validated.indicator_id, instance_url, headers)
        if not sys_id:
            return {
                "success": False,
                "message": f"PA indicator not found: {validated.indicator_id}",
            }
        query_parts.append(f"indicator={sys_id}")

    if validated.period_start:
        query_parts.append(f"sys_created_on>={validated.period_start}")
    if validated.period_end:
        query_parts.append(f"sys_created_on<={validated.period_end}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=False,
        order_by="DESCsys_created_on",
        fields=",".join(PA_SCORE_FIELDS),
    )
    query_params["sysparm_display_value"] = "all"

    url = f"{instance_url}/api/now/table/{PA_SCORE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        scores = [_format_pa_score(r) for r in response.json().get("result", [])]
        return _paginated_list_response(scores, validated.limit, validated.offset, "scores")
    except requests.exceptions.HTTPError as exc:
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}
