"""
Performance Analytics tools for the ServiceNow MCP server.

Provides tools for querying and creating Performance Analytics indicators
(pa_indicator), their collected scores (pa_score), and PA dashboards
(pa_home_page).  PA indicators are formula-driven KPIs that sit on top of
ServiceNow data and are distinct from the field-level sys_metric gauges.
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
PA_DASHBOARD_TABLE = "pa_home_page"
PA_WIDGET_TABLE = "pa_widget"
PA_BREAKDOWN_TABLE = "pa_breakdown"

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

PA_DASHBOARD_FIELDS = [
    "sys_id",
    "title",
    "description",
    "owner",
    "active",
    "order",
    "sys_created_on",
    "sys_updated_on",
]

PA_WIDGET_FIELDS = [
    "sys_id",
    "name",
    "description",
    "indicator",
    "widget_type",
    "active",
    "home_page",
    "breakdown",
    "color",
    "sys_created_on",
    "sys_updated_on",
]

PA_BREAKDOWN_FIELDS = [
    "sys_id",
    "name",
    "active",
    "table",
    "field",
    "filter_condition",
    "calculated_from",
    "sys_created_on",
    "sys_updated_on",
]

PA_JOB_TABLE = "pa_job"
PA_TARGET_TABLE = "pa_target"

PA_JOB_FIELDS = [
    "sys_id",
    "name",
    "active",
    "run_type",
    "run_time",
    "last_run_time",
    "next_run_time",
    "last_run_status",
    "indicator",
    "breakdown",
    "sys_created_on",
    "sys_updated_on",
]

PA_TARGET_FIELDS = [
    "sys_id",
    "indicator",
    "target",
    "minimum",
    "maximum",
    "period",
    "active",
    "sys_created_on",
    "sys_updated_on",
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


class CreatePAIndicatorParams(BaseModel):
    """Parameters for creating a new Performance Analytics indicator."""

    name: str = Field(..., description="Unique display name for the indicator")
    description: Optional[str] = Field(None, description="Free-text description of the indicator")
    table: Optional[str] = Field(
        None,
        description="ServiceNow table the indicator draws data from (e.g. 'incident')",
    )
    condition: Optional[str] = Field(
        None,
        description="Encoded query string that filters records before aggregation",
    )
    formula: Optional[str] = Field(
        None,
        description="Aggregation formula (e.g. 'count', 'sum(field)', 'avg(field)')",
    )
    frequency: Optional[str] = Field(
        None,
        description=(
            "Collection frequency. Common values: daily, weekly, monthly, quarterly, yearly"
        ),
    )
    direction: Optional[str] = Field(
        None,
        description=(
            "Optimisation direction. "
            "Use '1' (or 'maximize') to indicate higher is better; "
            "'2' (or 'minimize') for lower is better."
        ),
    )
    active: Optional[bool] = Field(True, description="Whether the indicator is active (default true)")
    unit: Optional[str] = Field(
        None,
        description="sys_id or display name of the unit record (pa_unit table)",
    )
    indicator_group: Optional[str] = Field(
        None,
        description="sys_id or display name of the indicator group (pa_indicator_group table)",
    )


class ListPADashboardsParams(BaseModel):
    """Parameters for listing Performance Analytics dashboards."""

    limit: Optional[int] = Field(20, description="Maximum number of dashboards to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    title: Optional[str] = Field(None, description="Filter by dashboard title (substring match)")
    active: Optional[bool] = Field(None, description="Filter by active flag (true=active only)")
    owner: Optional[str] = Field(
        None,
        description="Filter by owner user name (substring match on user_name field)",
    )


class GetPADashboardParams(BaseModel):
    """Parameters for retrieving a single Performance Analytics dashboard."""

    dashboard_id: str = Field(
        ...,
        description=(
            "sys_id of the PA dashboard, or its exact title. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a title= lookup on pa_home_page."
        ),
    )


class ListPAWidgetsParams(BaseModel):
    """Parameters for listing Performance Analytics widgets."""

    limit: Optional[int] = Field(20, description="Maximum number of widgets to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    name: Optional[str] = Field(None, description="Filter by widget name (substring match)")
    active: Optional[bool] = Field(None, description="Filter by active flag (true=active only)")
    widget_type: Optional[str] = Field(
        None,
        description="Filter by widget type (e.g. 'chart', 'scorecard', 'breakdown')",
    )
    indicator_id: Optional[str] = Field(
        None,
        description=(
            "Filter by PA indicator; accepts sys_id or exact name of the indicator "
            "(auto-resolved to sys_id)."
        ),
    )
    dashboard_id: Optional[str] = Field(
        None,
        description=(
            "Filter by PA dashboard (home_page); accepts sys_id or exact title "
            "(auto-resolved to sys_id)."
        ),
    )


class GetPAWidgetParams(BaseModel):
    """Parameters for retrieving a single Performance Analytics widget."""

    widget_id: str = Field(
        ...,
        description=(
            "sys_id of the PA widget, or its exact name. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a name= lookup on pa_widget."
        ),
    )


class ListPABreakdownsParams(BaseModel):
    """Parameters for listing Performance Analytics breakdowns."""

    limit: Optional[int] = Field(20, description="Maximum number of breakdowns to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    name: Optional[str] = Field(None, description="Filter by breakdown name (substring match)")
    active: Optional[bool] = Field(None, description="Filter by active flag (true=active only)")
    table: Optional[str] = Field(
        None,
        description="Filter by the source table the breakdown operates on (e.g. 'incident')",
    )
    field: Optional[str] = Field(
        None,
        description="Filter by the field name used as the breakdown dimension",
    )


class GetPABreakdownParams(BaseModel):
    """Parameters for retrieving a single Performance Analytics breakdown."""

    breakdown_id: str = Field(
        ...,
        description=(
            "sys_id of the PA breakdown, or its exact name. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a name= lookup on pa_breakdown."
        ),
    )


class ListPAJobsParams(BaseModel):
    """Parameters for listing Performance Analytics collection jobs."""

    limit: Optional[int] = Field(20, description="Maximum number of jobs to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    name: Optional[str] = Field(None, description="Filter by job name (substring match)")
    active: Optional[bool] = Field(None, description="Filter by active flag (true=active only)")
    run_type: Optional[str] = Field(
        None,
        description=(
            "Filter by run type. Common values: daily, weekly, monthly, on_demand"
        ),
    )
    last_run_status: Optional[str] = Field(
        None,
        description=(
            "Filter by the status of the most recent run. "
            "Common values: success, failed, running"
        ),
    )
    indicator_id: Optional[str] = Field(
        None,
        description=(
            "Filter by PA indicator; accepts sys_id or exact name (auto-resolved to sys_id)."
        ),
    )


class GetPAJobParams(BaseModel):
    """Parameters for retrieving a single Performance Analytics collection job."""

    job_id: str = Field(
        ...,
        description=(
            "sys_id of the PA job, or its exact name. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a name= lookup on pa_job."
        ),
    )


class TriggerPACollectionParams(BaseModel):
    """Parameters for triggering a Performance Analytics data collection job."""

    job_id: str = Field(
        ...,
        description=(
            "sys_id of the PA job to trigger, or its exact name. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a name= lookup on pa_job."
        ),
    )


class UpdatePAIndicatorParams(BaseModel):
    """Parameters for updating an existing Performance Analytics indicator."""

    indicator_id: str = Field(
        ...,
        description=(
            "sys_id of the PA indicator to update, or its exact name. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a name= lookup on pa_indicator."
        ),
    )
    name: Optional[str] = Field(None, description="New display name for the indicator")
    description: Optional[str] = Field(None, description="Updated free-text description")
    table: Optional[str] = Field(
        None,
        description="ServiceNow table the indicator draws data from (e.g. 'incident')",
    )
    condition: Optional[str] = Field(
        None,
        description="Encoded query string that filters records before aggregation",
    )
    formula: Optional[str] = Field(
        None,
        description="Aggregation formula (e.g. 'count', 'sum(field)', 'avg(field)')",
    )
    frequency: Optional[str] = Field(
        None,
        description=(
            "Collection frequency. Common values: daily, weekly, monthly, quarterly, yearly"
        ),
    )
    direction: Optional[str] = Field(
        None,
        description=(
            "Optimisation direction. "
            "Use '1' (or 'maximize') to indicate higher is better; "
            "'2' (or 'minimize') for lower is better."
        ),
    )
    active: Optional[bool] = Field(None, description="Whether the indicator is active")
    unit: Optional[str] = Field(
        None,
        description="sys_id or display name of the unit record (pa_unit table)",
    )
    indicator_group: Optional[str] = Field(
        None,
        description="sys_id or display name of the indicator group (pa_indicator_group table)",
    )


class DeletePAIndicatorParams(BaseModel):
    """Parameters for deleting a Performance Analytics indicator."""

    indicator_id: str = Field(
        ...,
        description=(
            "sys_id of the PA indicator to delete, or its exact name. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a name= lookup on pa_indicator."
        ),
    )


class UpdatePADashboardParams(BaseModel):
    """Parameters for updating an existing Performance Analytics dashboard."""

    dashboard_id: str = Field(
        ...,
        description=(
            "sys_id of the PA dashboard to update, or its exact title. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a title= lookup on pa_home_page."
        ),
    )
    title: Optional[str] = Field(None, description="New display title for the dashboard")
    description: Optional[str] = Field(None, description="Updated free-text description")
    active: Optional[bool] = Field(None, description="Whether the dashboard is active")
    order: Optional[int] = Field(None, description="Display order for the dashboard")
    owner: Optional[str] = Field(
        None,
        description="sys_id or user_name of the new dashboard owner",
    )


class DeletePADashboardParams(BaseModel):
    """Parameters for deleting a Performance Analytics dashboard."""

    dashboard_id: str = Field(
        ...,
        description=(
            "sys_id of the PA dashboard to delete, or its exact title. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a title= lookup on pa_home_page."
        ),
    )


class UpdatePABreakdownParams(BaseModel):
    """Parameters for updating an existing Performance Analytics breakdown."""

    breakdown_id: str = Field(
        ...,
        description=(
            "sys_id of the PA breakdown to update, or its exact name. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a name= lookup on pa_breakdown."
        ),
    )
    name: Optional[str] = Field(None, description="New display name for the breakdown")
    active: Optional[bool] = Field(None, description="Whether the breakdown is active")
    table: Optional[str] = Field(
        None,
        description="Source table the breakdown dimension is drawn from (e.g. 'incident')",
    )
    field: Optional[str] = Field(
        None,
        description="Field on the source table used as the breakdown dimension",
    )
    filter_condition: Optional[str] = Field(
        None,
        description="Encoded query string that pre-filters records before grouping",
    )


class DeletePABreakdownParams(BaseModel):
    """Parameters for deleting a Performance Analytics breakdown."""

    breakdown_id: str = Field(
        ...,
        description=(
            "sys_id of the PA breakdown to delete, or its exact name. "
            "A 32-character hex string is treated as a sys_id; anything else is "
            "resolved via a name= lookup on pa_breakdown."
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


class ListPATargetsParams(BaseModel):
    """Parameters for listing Performance Analytics targets."""

    limit: Optional[int] = Field(20, description="Maximum number of targets to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    indicator_id: Optional[str] = Field(
        None,
        description=(
            "sys_id or exact name of the PA indicator to filter by. "
            "Names are resolved to a sys_id automatically."
        ),
    )
    active: Optional[bool] = Field(None, description="Filter by active flag (true=active only)")
    created_after: Optional[str] = Field(
        None,
        description="Return targets created on or after this date (YYYY-MM-DD)",
    )
    created_before: Optional[str] = Field(
        None,
        description="Return targets created on or before this date (YYYY-MM-DD)",
    )

    @field_validator("created_after", "created_before", mode="before")
    @classmethod
    def _validate_date_fields(cls, v):
        return validate_servicenow_date(v)


class GetPATargetParams(BaseModel):
    """Parameters for retrieving a single Performance Analytics target."""

    target_id: str = Field(
        ...,
        description="sys_id of the PA target record.",
    )


class CreatePATargetParams(BaseModel):
    """Parameters for creating a new Performance Analytics target record."""

    indicator_id: str = Field(
        ...,
        description=(
            "sys_id or exact name of the PA indicator this target is associated with. "
            "Names are resolved to a sys_id automatically."
        ),
    )
    target: Optional[str] = Field(None, description="Desired KPI value for the target period")
    minimum: Optional[str] = Field(None, description="Minimum acceptable KPI value")
    maximum: Optional[str] = Field(None, description="Maximum acceptable KPI value")
    period: Optional[str] = Field(
        None,
        description="sys_id or display name of the period record (pa_period table)",
    )
    active: Optional[bool] = Field(True, description="Whether the target is active (default true)")


class UpdatePATargetParams(BaseModel):
    """Parameters for updating an existing Performance Analytics target record."""

    target_id: str = Field(
        ...,
        description=(
            "sys_id of the PA target record to update. "
            "A 32-character hex string is treated as a sys_id."
        ),
    )
    indicator_id: Optional[str] = Field(
        None,
        description=(
            "sys_id or exact name of the PA indicator to reassign this target to. "
            "Names are resolved to a sys_id automatically."
        ),
    )
    target: Optional[str] = Field(None, description="New desired KPI value")
    minimum: Optional[str] = Field(None, description="New minimum acceptable KPI value")
    maximum: Optional[str] = Field(None, description="New maximum acceptable KPI value")
    period: Optional[str] = Field(
        None,
        description="sys_id or display name of the new period record",
    )
    active: Optional[bool] = Field(None, description="Whether the target should be active")


class DeletePATargetParams(BaseModel):
    """Parameters for deleting a Performance Analytics target record."""

    target_id: str = Field(
        ...,
        description="sys_id of the PA target record to delete.",
    )


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


def _format_pa_dashboard(record: Dict) -> Dict:
    """Normalise a raw pa_home_page record."""
    return {
        "sys_id": record.get("sys_id"),
        "title": record.get("title"),
        "description": record.get("description"),
        "owner": _ref_display(record.get("owner")),
        "active": record.get("active"),
        "order": record.get("order"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _format_pa_widget(record: Dict) -> Dict:
    """Normalise a raw pa_widget record."""
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "description": record.get("description"),
        "indicator": _ref_display(record.get("indicator")),
        "widget_type": record.get("widget_type"),
        "active": record.get("active"),
        "home_page": _ref_display(record.get("home_page")),
        "breakdown": _ref_display(record.get("breakdown")),
        "color": record.get("color"),
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


def _format_pa_breakdown(record: Dict) -> Dict:
    """Normalise a raw pa_breakdown record."""
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "active": record.get("active"),
        "table": _ref_display(record.get("table")),
        "field": record.get("field"),
        "filter_condition": record.get("filter_condition"),
        "calculated_from": _ref_display(record.get("calculated_from")),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _format_pa_job(record: Dict) -> Dict:
    """Normalise a raw pa_job record."""
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "active": record.get("active"),
        "run_type": record.get("run_type"),
        "run_time": record.get("run_time"),
        "last_run_time": record.get("last_run_time"),
        "next_run_time": record.get("next_run_time"),
        "last_run_status": record.get("last_run_status"),
        "indicator": _ref_display(record.get("indicator")),
        "breakdown": _ref_display(record.get("breakdown")),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _format_pa_target(record: Dict) -> Dict:
    """Normalise a raw pa_target record."""
    return {
        "sys_id": record.get("sys_id"),
        "indicator": _ref_display(record.get("indicator")),
        "target": record.get("target"),
        "minimum": record.get("minimum"),
        "maximum": record.get("maximum"),
        "period": _ref_display(record.get("period")),
        "active": record.get("active"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


# ---------------------------------------------------------------------------
# Resolver helper
# ---------------------------------------------------------------------------


def _resolve_pa_dashboard_sys_id(
    dashboard_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a PA dashboard title to its sys_id.

    If *dashboard_id* is a 32-character hex string it is returned unchanged.
    Otherwise a GET against pa_home_page with ``title=<value>`` is performed
    and the first match's sys_id returned.  Returns ``None`` when not found.
    """
    if len(dashboard_id) == 32 and all(c in "0123456789abcdefABCDEF" for c in dashboard_id):
        return dashboard_id
    url = f"{instance_url}/api/now/table/{PA_DASHBOARD_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"title={dashboard_id}",
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


def _resolve_pa_widget_sys_id(
    widget_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a PA widget name to its sys_id.

    If *widget_id* is a 32-character hex string it is returned unchanged.
    Otherwise a GET against pa_widget with ``name=<value>`` is performed
    and the first match's sys_id returned.  Returns ``None`` when not found.
    """
    if len(widget_id) == 32 and all(c in "0123456789abcdefABCDEF" for c in widget_id):
        return widget_id
    url = f"{instance_url}/api/now/table/{PA_WIDGET_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={widget_id}",
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


def _resolve_pa_breakdown_sys_id(
    breakdown_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a PA breakdown name to its sys_id.

    If *breakdown_id* is a 32-character hex string it is returned unchanged.
    Otherwise a GET against pa_breakdown with ``name=<value>`` is performed
    and the first match's sys_id returned.  Returns ``None`` when not found.
    """
    if len(breakdown_id) == 32 and all(c in "0123456789abcdefABCDEF" for c in breakdown_id):
        return breakdown_id
    url = f"{instance_url}/api/now/table/{PA_BREAKDOWN_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={breakdown_id}",
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


def _resolve_pa_job_sys_id(
    job_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a PA job name to its sys_id.

    If *job_id* is a 32-character hex string it is returned unchanged.
    Otherwise a GET against pa_job with ``name=<value>`` is performed
    and the first match's sys_id returned.  Returns ``None`` when not found.
    """
    if len(job_id) == 32 and all(c in "0123456789abcdefABCDEF" for c in job_id):
        return job_id
    url = f"{instance_url}/api/now/table/{PA_JOB_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={job_id}",
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


def _resolve_pa_target_sys_id(
    target_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Resolve a PA target identifier to its sys_id.

    If *target_id* is a 32-character hex string it is returned unchanged.
    Otherwise a GET against pa_target with ``sys_id=<value>`` lookup is
    attempted and the first match's sys_id returned.  Returns ``None``
    when not found.
    """
    if len(target_id) == 32 and all(c in "0123456789abcdefABCDEF" for c in target_id):
        return target_id
    # For non-hex values try a direct lookup by sys_id query
    url = f"{instance_url}/api/now/table/{PA_TARGET_TABLE}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"sys_id={target_id}",
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


def create_pa_indicator(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new Performance Analytics indicator in the pa_indicator table.

    A PA indicator defines a KPI: the source table, filter condition, aggregation
    formula, collection frequency, and optimisation direction.  The indicator
    must be collected (manually or via a scheduled PA job) before scores appear.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreatePAIndicatorParams.

    Returns:
        Dictionary with ``success``, ``indicator`` (the created record), and
        ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, CreatePAIndicatorParams, required_fields=["name"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    # Normalise direction aliases
    direction_map = {"maximize": "1", "minimise": "2", "minimize": "2", "maximise": "1"}
    direction_value = validated.direction
    if direction_value is not None:
        direction_value = direction_map.get(direction_value.lower(), direction_value)

    body: Dict[str, Any] = {
        "name": validated.name,
        "active": "true" if validated.active else "false",
    }
    if validated.description is not None:
        body["description"] = validated.description
    if validated.table is not None:
        body["table"] = validated.table
    if validated.condition is not None:
        body["condition"] = validated.condition
    if validated.formula is not None:
        body["formula"] = validated.formula
    if validated.frequency is not None:
        body["frequency"] = validated.frequency
    if direction_value is not None:
        body["direction"] = direction_value
    if validated.unit is not None:
        body["unit"] = validated.unit
    if validated.indicator_group is not None:
        body["indicator_group"] = validated.indicator_group

    url = f"{instance_url}/api/now/table/{PA_INDICATOR_TABLE}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "all",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(PA_INDICATOR_FIELDS),
    }
    try:
        response = _make_request("POST", url, headers=headers, params=query_params, json=body)
        response.raise_for_status()
        data = response.json().get("result", {})
        return {
            "success": True,
            "indicator": _format_pa_indicator(data),
            "message": f"PA indicator '{validated.name}' created successfully",
        }
    except requests.exceptions.HTTPError as exc:
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def list_pa_dashboards(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List Performance Analytics dashboards from the pa_home_page table.

    PA dashboards aggregate widgets and indicator tiles into a single view.
    Each dashboard has an owner, an optional order for display sorting, and
    an active flag.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListPADashboardsParams.

    Returns:
        Dictionary with ``success``, ``dashboards`` (list), ``count``,
        and optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListPADashboardsParams)
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
    if validated.title:
        query_parts.append(f"titleLIKE{validated.title}")
    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")
    if validated.owner:
        query_parts.append(f"owner.user_nameLIKE{validated.owner}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=False,
        order_by="title",
        fields=",".join(PA_DASHBOARD_FIELDS),
    )
    query_params["sysparm_display_value"] = "all"

    url = f"{instance_url}/api/now/table/{PA_DASHBOARD_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        dashboards = [_format_pa_dashboard(r) for r in response.json().get("result", [])]
        return _paginated_list_response(dashboards, validated.limit, validated.offset, "dashboards")
    except requests.exceptions.HTTPError as exc:
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def get_pa_dashboard(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single Performance Analytics dashboard by sys_id or exact title.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetPADashboardParams.

    Returns:
        Dictionary with ``success`` and ``dashboard`` keys, or an error message.
    """
    result = _unwrap_and_validate_params(params, GetPADashboardParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_pa_dashboard_sys_id(validated.dashboard_id, instance_url, headers)
    if not sys_id:
        return {
            "success": False,
            "message": f"PA dashboard not found: {validated.dashboard_id}",
        }

    url = f"{instance_url}/api/now/table/{PA_DASHBOARD_TABLE}/{sys_id}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_fields": ",".join(PA_DASHBOARD_FIELDS),
                "sysparm_display_value": "all",
            },
        )
        response.raise_for_status()
        data = response.json().get("result")
        if not data:
            return {"success": False, "message": f"PA dashboard not found: {sys_id}"}
        return {"success": True, "dashboard": _format_pa_dashboard(data)}
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA dashboard not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def list_pa_widgets(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List Performance Analytics widgets from the pa_widget table.

    PA widgets are the individual visualisation elements (charts, scorecards,
    breakdowns) that sit on a PA dashboard.  Each widget is tied to one PA
    indicator and optionally a breakdown.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListPAWidgetsParams.

    Returns:
        Dictionary with ``success``, ``widgets`` (list), ``count``,
        and optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListPAWidgetsParams)
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
    if validated.widget_type:
        query_parts.append(f"widget_type={validated.widget_type}")
    if validated.indicator_id:
        ind_sys_id = _resolve_pa_indicator_sys_id(validated.indicator_id, instance_url, headers)
        if not ind_sys_id:
            return {
                "success": False,
                "message": f"PA indicator not found: {validated.indicator_id}",
            }
        query_parts.append(f"indicator={ind_sys_id}")
    if validated.dashboard_id:
        dash_sys_id = _resolve_pa_dashboard_sys_id(validated.dashboard_id, instance_url, headers)
        if not dash_sys_id:
            return {
                "success": False,
                "message": f"PA dashboard not found: {validated.dashboard_id}",
            }
        query_parts.append(f"home_page={dash_sys_id}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=False,
        order_by="name",
        fields=",".join(PA_WIDGET_FIELDS),
    )
    query_params["sysparm_display_value"] = "all"

    url = f"{instance_url}/api/now/table/{PA_WIDGET_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        widgets = [_format_pa_widget(r) for r in response.json().get("result", [])]
        return _paginated_list_response(widgets, validated.limit, validated.offset, "widgets")
    except requests.exceptions.HTTPError as exc:
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def get_pa_widget(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single Performance Analytics widget by sys_id or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetPAWidgetParams.

    Returns:
        Dictionary with ``success`` and ``widget`` keys, or an error message.
    """
    result = _unwrap_and_validate_params(params, GetPAWidgetParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_pa_widget_sys_id(validated.widget_id, instance_url, headers)
    if not sys_id:
        return {
            "success": False,
            "message": f"PA widget not found: {validated.widget_id}",
        }

    url = f"{instance_url}/api/now/table/{PA_WIDGET_TABLE}/{sys_id}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_fields": ",".join(PA_WIDGET_FIELDS),
                "sysparm_display_value": "all",
            },
        )
        response.raise_for_status()
        data = response.json().get("result")
        if not data:
            return {"success": False, "message": f"PA widget not found: {sys_id}"}
        return {"success": True, "widget": _format_pa_widget(data)}
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA widget not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def list_pa_breakdowns(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List Performance Analytics breakdowns from the pa_breakdown table.

    PA breakdowns are dimension definitions that segment indicator scores
    into categories (e.g. by Priority, Category, Assignment Group).  Each
    breakdown references a source table and a field used as the grouping key.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListPABreakdownsParams.

    Returns:
        Dictionary with ``success``, ``breakdowns`` (list), ``count``,
        and optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListPABreakdownsParams)
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
    if validated.table:
        query_parts.append(f"table={validated.table}")
    if validated.field:
        query_parts.append(f"fieldLIKE{validated.field}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=False,
        order_by="name",
        fields=",".join(PA_BREAKDOWN_FIELDS),
    )
    query_params["sysparm_display_value"] = "all"

    url = f"{instance_url}/api/now/table/{PA_BREAKDOWN_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        breakdowns = [_format_pa_breakdown(r) for r in response.json().get("result", [])]
        return _paginated_list_response(breakdowns, validated.limit, validated.offset, "breakdowns")
    except requests.exceptions.HTTPError as exc:
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def get_pa_breakdown(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single Performance Analytics breakdown by sys_id or exact name.

    PA breakdowns define how indicator scores are segmented into categories.
    Pass the sys_id directly for a guaranteed single-record lookup, or supply
    the exact breakdown name which is resolved to a sys_id automatically.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetPABreakdownParams.

    Returns:
        Dictionary with ``success`` and ``breakdown`` keys, or an error message.
    """
    result = _unwrap_and_validate_params(params, GetPABreakdownParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_pa_breakdown_sys_id(validated.breakdown_id, instance_url, headers)
    if not sys_id:
        return {
            "success": False,
            "message": f"PA breakdown not found: {validated.breakdown_id}",
        }

    url = f"{instance_url}/api/now/table/{PA_BREAKDOWN_TABLE}/{sys_id}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_fields": ",".join(PA_BREAKDOWN_FIELDS),
                "sysparm_display_value": "all",
            },
        )
        response.raise_for_status()
        data = response.json().get("result")
        if not data:
            return {"success": False, "message": f"PA breakdown not found: {sys_id}"}
        return {"success": True, "breakdown": _format_pa_breakdown(data)}
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA breakdown not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def list_pa_jobs(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List Performance Analytics data collection jobs from the pa_job table.

    PA jobs are the scheduled or on-demand processes that collect indicator scores.
    Each job is linked to one or more indicators and optionally a breakdown, and
    records its last and next scheduled run times.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListPAJobsParams.

    Returns:
        Dictionary with ``success``, ``jobs`` (list), ``count``,
        and optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListPAJobsParams)
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
    if validated.run_type:
        query_parts.append(f"run_type={validated.run_type}")
    if validated.last_run_status:
        query_parts.append(f"last_run_status={validated.last_run_status}")
    if validated.indicator_id:
        ind_sys_id = _resolve_pa_indicator_sys_id(validated.indicator_id, instance_url, headers)
        if not ind_sys_id:
            return {
                "success": False,
                "message": f"PA indicator not found: {validated.indicator_id}",
            }
        query_parts.append(f"indicator={ind_sys_id}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=False,
        order_by="name",
        fields=",".join(PA_JOB_FIELDS),
    )
    query_params["sysparm_display_value"] = "all"

    url = f"{instance_url}/api/now/table/{PA_JOB_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        jobs = [_format_pa_job(r) for r in response.json().get("result", [])]
        return _paginated_list_response(jobs, validated.limit, validated.offset, "jobs")
    except requests.exceptions.HTTPError as exc:
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def get_pa_job(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single Performance Analytics collection job by sys_id or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetPAJobParams.

    Returns:
        Dictionary with ``success`` and ``job`` keys, or an error message.
    """
    result = _unwrap_and_validate_params(params, GetPAJobParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_pa_job_sys_id(validated.job_id, instance_url, headers)
    if not sys_id:
        return {
            "success": False,
            "message": f"PA job not found: {validated.job_id}",
        }

    url = f"{instance_url}/api/now/table/{PA_JOB_TABLE}/{sys_id}"
    try:
        response = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_fields": ",".join(PA_JOB_FIELDS),
                "sysparm_display_value": "all",
            },
        )
        response.raise_for_status()
        data = response.json().get("result")
        if not data:
            return {"success": False, "message": f"PA job not found: {sys_id}"}
        return {"success": True, "job": _format_pa_job(data)}
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA job not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def update_pa_indicator(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing Performance Analytics indicator.

    Issues a PATCH to pa_indicator/{sys_id} with only the fields supplied in
    *params*.  Empty-body calls (no updatable field provided) are rejected
    before reaching the API.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdatePAIndicatorParams.

    Returns:
        Dictionary with ``success``, ``indicator``, and ``message`` keys,
        or an error message.
    """
    result = _unwrap_and_validate_params(params, UpdatePAIndicatorParams)
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

    # Normalise direction aliases
    direction_map = {"maximize": "1", "minimise": "2", "minimize": "2", "maximise": "1"}
    direction_value = validated.direction
    if direction_value is not None:
        direction_value = direction_map.get(direction_value.lower(), direction_value)

    body: Dict[str, Any] = {}
    if validated.name is not None:
        body["name"] = validated.name
    if validated.description is not None:
        body["description"] = validated.description
    if validated.table is not None:
        body["table"] = validated.table
    if validated.condition is not None:
        body["condition"] = validated.condition
    if validated.formula is not None:
        body["formula"] = validated.formula
    if validated.frequency is not None:
        body["frequency"] = validated.frequency
    if direction_value is not None:
        body["direction"] = direction_value
    if validated.active is not None:
        body["active"] = "true" if validated.active else "false"
    if validated.unit is not None:
        body["unit"] = validated.unit
    if validated.indicator_group is not None:
        body["indicator_group"] = validated.indicator_group

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    url = f"{instance_url}/api/now/table/{PA_INDICATOR_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "all",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(PA_INDICATOR_FIELDS),
    }
    try:
        response = _make_request("PATCH", url, headers=headers, params=query_params, json=body)
        response.raise_for_status()
        data = response.json().get("result", {})
        return {
            "success": True,
            "indicator": _format_pa_indicator(data),
            "message": f"PA indicator '{sys_id}' updated successfully",
        }
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA indicator not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def delete_pa_indicator(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete a Performance Analytics indicator by sys_id or exact name.

    Issues a DELETE to pa_indicator/{sys_id}.  Returns success on HTTP 204
    (no content) or 200.  Returns a 404 error when the indicator is not found.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeletePAIndicatorParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``indicator_sys_id`` keys,
        or an error message.
    """
    result = _unwrap_and_validate_params(params, DeletePAIndicatorParams)
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
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code in (200, 204):
            return {
                "success": True,
                "message": f"PA indicator '{sys_id}' deleted successfully",
                "indicator_sys_id": sys_id,
            }
        response.raise_for_status()
        return {
            "success": True,
            "message": f"PA indicator '{sys_id}' deleted successfully",
            "indicator_sys_id": sys_id,
        }
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA indicator not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def trigger_pa_collection(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Trigger an immediate Performance Analytics data collection run.

    Issues a PATCH to the pa_job record setting run_now=true, which ServiceNow
    interprets as a manual collection trigger.  The job is identified by sys_id
    or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching TriggerPACollectionParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``job_sys_id`` keys.
    """
    result = _unwrap_and_validate_params(params, TriggerPACollectionParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_pa_job_sys_id(validated.job_id, instance_url, headers)
    if not sys_id:
        return {
            "success": False,
            "message": f"PA job not found: {validated.job_id}",
        }

    url = f"{instance_url}/api/now/table/{PA_JOB_TABLE}/{sys_id}"
    try:
        response = _make_request(
            "PATCH",
            url,
            headers=headers,
            json={"run_now": "true"},
        )
        response.raise_for_status()
        return {
            "success": True,
            "message": f"PA collection job triggered successfully: {sys_id}",
            "job_sys_id": sys_id,
        }
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA job not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def update_pa_dashboard(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing Performance Analytics dashboard.

    Issues a PATCH to pa_home_page/{sys_id} with only the fields supplied in
    *params*.  Empty-body calls (no updatable field provided) are rejected
    before reaching the API.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdatePADashboardParams.

    Returns:
        Dictionary with ``success``, ``dashboard``, and ``message`` keys,
        or an error message.
    """
    result = _unwrap_and_validate_params(params, UpdatePADashboardParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_pa_dashboard_sys_id(validated.dashboard_id, instance_url, headers)
    if not sys_id:
        return {
            "success": False,
            "message": f"PA dashboard not found: {validated.dashboard_id}",
        }

    body: Dict[str, Any] = {}
    if validated.title is not None:
        body["title"] = validated.title
    if validated.description is not None:
        body["description"] = validated.description
    if validated.active is not None:
        body["active"] = "true" if validated.active else "false"
    if validated.order is not None:
        body["order"] = str(validated.order)
    if validated.owner is not None:
        body["owner"] = validated.owner

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    url = f"{instance_url}/api/now/table/{PA_DASHBOARD_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "all",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(PA_DASHBOARD_FIELDS),
    }
    try:
        response = _make_request("PATCH", url, headers=headers, params=query_params, json=body)
        response.raise_for_status()
        data = response.json().get("result", {})
        return {
            "success": True,
            "dashboard": _format_pa_dashboard(data),
            "message": f"PA dashboard '{sys_id}' updated successfully",
        }
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA dashboard not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def delete_pa_dashboard(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete a Performance Analytics dashboard by sys_id or exact title.

    Issues a DELETE to pa_home_page/{sys_id}.  Returns success on HTTP 204
    (no content) or 200.  Returns a 404 error when the dashboard is not found.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeletePADashboardParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``dashboard_sys_id`` keys,
        or an error message.
    """
    result = _unwrap_and_validate_params(params, DeletePADashboardParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_pa_dashboard_sys_id(validated.dashboard_id, instance_url, headers)
    if not sys_id:
        return {
            "success": False,
            "message": f"PA dashboard not found: {validated.dashboard_id}",
        }

    url = f"{instance_url}/api/now/table/{PA_DASHBOARD_TABLE}/{sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code in (200, 204):
            return {
                "success": True,
                "message": f"PA dashboard '{sys_id}' deleted successfully",
                "dashboard_sys_id": sys_id,
            }
        response.raise_for_status()
        return {
            "success": True,
            "message": f"PA dashboard '{sys_id}' deleted successfully",
            "dashboard_sys_id": sys_id,
        }
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA dashboard not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def update_pa_breakdown(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing Performance Analytics breakdown.

    Issues a PATCH to pa_breakdown/{sys_id} with only the fields supplied in
    *params*.  Empty-body calls (no updatable field provided) are rejected
    before reaching the API.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdatePABreakdownParams.

    Returns:
        Dictionary with ``success``, ``breakdown``, and ``message`` keys,
        or an error message.
    """
    result = _unwrap_and_validate_params(params, UpdatePABreakdownParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_pa_breakdown_sys_id(validated.breakdown_id, instance_url, headers)
    if not sys_id:
        return {
            "success": False,
            "message": f"PA breakdown not found: {validated.breakdown_id}",
        }

    body: Dict[str, Any] = {}
    if validated.name is not None:
        body["name"] = validated.name
    if validated.active is not None:
        body["active"] = "true" if validated.active else "false"
    if validated.table is not None:
        body["table"] = validated.table
    if validated.field is not None:
        body["field"] = validated.field
    if validated.filter_condition is not None:
        body["filter_condition"] = validated.filter_condition

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    url = f"{instance_url}/api/now/table/{PA_BREAKDOWN_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "all",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(PA_BREAKDOWN_FIELDS),
    }
    try:
        response = _make_request("PATCH", url, headers=headers, params=query_params, json=body)
        response.raise_for_status()
        data = response.json().get("result", {})
        return {
            "success": True,
            "breakdown": _format_pa_breakdown(data),
            "message": f"PA breakdown '{sys_id}' updated successfully",
        }
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA breakdown not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def delete_pa_breakdown(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete a Performance Analytics breakdown by sys_id or exact name.

    Issues a DELETE to pa_breakdown/{sys_id}.  Returns success on HTTP 204
    (no content) or 200.  Returns a 404 error when the breakdown is not found.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeletePABreakdownParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``breakdown_sys_id`` keys,
        or an error message.
    """
    result = _unwrap_and_validate_params(params, DeletePABreakdownParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_pa_breakdown_sys_id(validated.breakdown_id, instance_url, headers)
    if not sys_id:
        return {
            "success": False,
            "message": f"PA breakdown not found: {validated.breakdown_id}",
        }

    url = f"{instance_url}/api/now/table/{PA_BREAKDOWN_TABLE}/{sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code in (200, 204):
            return {
                "success": True,
                "message": f"PA breakdown '{sys_id}' deleted successfully",
                "breakdown_sys_id": sys_id,
            }
        response.raise_for_status()
        return {
            "success": True,
            "message": f"PA breakdown '{sys_id}' deleted successfully",
            "breakdown_sys_id": sys_id,
        }
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA breakdown not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}

def list_pa_targets(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List Performance Analytics target records from the pa_target table.

    PA targets define the desired, minimum, and maximum values for a PA
    indicator over a given period.  They can be filtered by indicator
    (name or sys_id), active state, and creation date range.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListPATargetsParams.

    Returns:
        Dictionary with ``success``, ``targets`` (list), ``count``,
        and optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListPATargetsParams)
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

    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")

    if validated.created_after:
        query_parts.append(f"sys_created_on>={validated.created_after}")
    if validated.created_before:
        query_parts.append(f"sys_created_on<={validated.created_before}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=False,
        fields=",".join(PA_TARGET_FIELDS),
    )
    query_params["sysparm_display_value"] = "all"

    url = f"{instance_url}/api/now/table/{PA_TARGET_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        targets = [_format_pa_target(r) for r in response.json().get("result", [])]
        return _paginated_list_response(targets, validated.limit, validated.offset, "targets")
    except requests.exceptions.HTTPError as exc:
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def get_pa_target(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single Performance Analytics target by sys_id.

    PA targets store desired, minimum, and maximum KPI values for a given
    indicator and time period.  Pass the sys_id of the target record to
    retrieve its full details.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetPATargetParams.

    Returns:
        Dictionary with ``success`` and ``target`` on success,
        or ``success=False`` and ``message`` on failure.
    """
    result = _unwrap_and_validate_params(params, GetPATargetParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}/api/now/table/{PA_TARGET_TABLE}/{validated.target_id}"
    query_params = {
        "sysparm_display_value": "all",
        "sysparm_fields": ",".join(PA_TARGET_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        data = response.json().get("result")
        if not data:
            return {"success": False, "message": f"PA target not found: {validated.target_id}"}
        return {"success": True, "target": _format_pa_target(data)}
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA target not found: {validated.target_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}

def create_pa_target(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new Performance Analytics target record in the pa_target table.

    A PA target stores the desired, minimum, and maximum KPI values for an
    indicator over a given period.  The indicator is resolved from name or
    sys_id automatically.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreatePATargetParams.

    Returns:
        Dictionary with ``success``, ``target`` (the created record), and
        ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, CreatePATargetParams, required_fields=["indicator_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    indicator_sys_id = _resolve_pa_indicator_sys_id(validated.indicator_id, instance_url, headers)
    if not indicator_sys_id:
        return {
            "success": False,
            "message": f"PA indicator not found: {validated.indicator_id}",
        }

    body: Dict[str, Any] = {
        "indicator": indicator_sys_id,
        "active": "true" if validated.active else "false",
    }
    if validated.target is not None:
        body["target"] = validated.target
    if validated.minimum is not None:
        body["minimum"] = validated.minimum
    if validated.maximum is not None:
        body["maximum"] = validated.maximum
    if validated.period is not None:
        body["period"] = validated.period

    url = f"{instance_url}/api/now/table/{PA_TARGET_TABLE}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "all",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(PA_TARGET_FIELDS),
    }
    try:
        response = _make_request("POST", url, headers=headers, params=query_params, json=body)
        response.raise_for_status()
        data = response.json().get("result", {})
        return {
            "success": True,
            "target": _format_pa_target(data),
            "message": "PA target created successfully",
        }
    except requests.exceptions.HTTPError as exc:
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def update_pa_target(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing Performance Analytics target record.

    Issues a PATCH to pa_target/{sys_id} with only the fields supplied in
    *params*.  Empty-body calls (no updatable field provided) are rejected
    before reaching the API.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdatePATargetParams.

    Returns:
        Dictionary with ``success``, ``target``, and ``message`` keys,
        or an error message.
    """
    result = _unwrap_and_validate_params(params, UpdatePATargetParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = validated.target_id

    body: Dict[str, Any] = {}
    if validated.indicator_id is not None:
        indicator_sys_id = _resolve_pa_indicator_sys_id(validated.indicator_id, instance_url, headers)
        if not indicator_sys_id:
            return {
                "success": False,
                "message": f"PA indicator not found: {validated.indicator_id}",
            }
        body["indicator"] = indicator_sys_id
    if validated.target is not None:
        body["target"] = validated.target
    if validated.minimum is not None:
        body["minimum"] = validated.minimum
    if validated.maximum is not None:
        body["maximum"] = validated.maximum
    if validated.period is not None:
        body["period"] = validated.period
    if validated.active is not None:
        body["active"] = "true" if validated.active else "false"

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    url = f"{instance_url}/api/now/table/{PA_TARGET_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "all",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(PA_TARGET_FIELDS),
    }
    try:
        response = _make_request("PATCH", url, headers=headers, params=query_params, json=body)
        response.raise_for_status()
        data = response.json().get("result", {})
        return {
            "success": True,
            "target": _format_pa_target(data),
            "message": f"PA target '{sys_id}' updated successfully",
        }
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA target not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}


def delete_pa_target(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete a Performance Analytics target record by sys_id.

    Issues a DELETE to pa_target/{sys_id}.  Returns success on HTTP 204
    (no content) or 200.  Returns a 404 error when the target is not found.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeletePATargetParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``target_sys_id`` keys,
        or an error message.
    """
    result = _unwrap_and_validate_params(params, DeletePATargetParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = validated.target_id

    url = f"{instance_url}/api/now/table/{PA_TARGET_TABLE}/{sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code in (200, 204):
            return {
                "success": True,
                "message": f"PA target '{sys_id}' deleted successfully",
                "target_sys_id": sys_id,
            }
        response.raise_for_status()
        return {
            "success": True,
            "message": f"PA target '{sys_id}' deleted successfully",
            "target_sys_id": sys_id,
        }
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"success": False, "message": f"PA target not found: {sys_id}"}
        return {"success": False, "message": _format_http_error(exc)}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "message": str(exc)}
