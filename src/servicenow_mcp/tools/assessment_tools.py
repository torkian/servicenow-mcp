"""
Survey and assessment tools for the ServiceNow MCP server.

Provides tools for managing assessment instances, metric types, and results
stored in the asmt_assessment_instance, asmt_metric_type, and
asmt_assessment_instance_v2 tables.
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

ASSESSMENT_INSTANCE_TABLE = "asmt_assessment_instance"
ASSESSMENT_METRIC_TYPE_TABLE = "asmt_metric_type"

ASSESSMENT_INSTANCE_FIELDS = [
    "sys_id",
    "metric_type",
    "source_id",
    "source_table",
    "state",
    "user",
    "assigned_to",
    "due_date",
    "completion_date",
    "score",
    "percent_answered",
    "definition",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]

ASSESSMENT_METRIC_TYPE_FIELDS = [
    "sys_id",
    "name",
    "description",
    "active",
    "type",
    "category",
    "roles",
    "related_table",
    "related_filter",
    "frequency",
    "due_period",
    "sys_created_on",
    "sys_updated_on",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _ref(value: Any) -> Any:
    """Normalise a reference field to its display value."""
    if isinstance(value, dict):
        return value.get("display_value") or value.get("value")
    return value


def _format_assessment_instance(record: Dict) -> Dict:
    """Extract and normalise fields from a raw asmt_assessment_instance record."""
    return {
        "sys_id": record.get("sys_id"),
        "metric_type": _ref(record.get("metric_type")),
        "source_id": record.get("source_id"),
        "source_table": record.get("source_table"),
        "state": record.get("state"),
        "user": _ref(record.get("user")),
        "assigned_to": _ref(record.get("assigned_to")),
        "due_date": record.get("due_date"),
        "completion_date": record.get("completion_date"),
        "score": record.get("score"),
        "percent_answered": record.get("percent_answered"),
        "definition": _ref(record.get("definition")),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
    }


def _format_assessment_metric_type(record: Dict) -> Dict:
    """Extract and normalise fields from a raw asmt_metric_type record."""
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "description": record.get("description"),
        "active": record.get("active"),
        "type": record.get("type"),
        "category": _ref(record.get("category")),
        "roles": record.get("roles"),
        "related_table": record.get("related_table"),
        "related_filter": record.get("related_filter"),
        "frequency": record.get("frequency"),
        "due_period": record.get("due_period"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _resolve_metric_type_sys_id(
    instance_url: str,
    headers: Dict,
    metric_type_id: str,
) -> Optional[str]:
    """Return a metric_type sys_id from a name or passthrough if already a sys_id."""
    if len(metric_type_id) == 32 and all(c in "0123456789abcdef" for c in metric_type_id):
        return metric_type_id
    url = f"{instance_url}/api/now/table/{ASSESSMENT_METRIC_TYPE_TABLE}"
    try:
        resp = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"name={metric_type_id}",
                "sysparm_limit": 1,
                "sysparm_fields": "sys_id",
            },
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        if not results:
            return None
        return results[0].get("sys_id")
    except requests.exceptions.RequestException:
        return None


# ---------------------------------------------------------------------------
# list_assessment_instances
# ---------------------------------------------------------------------------


class ListAssessmentInstancesParams(BaseModel):
    """Parameters for listing assessment instances."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    state: Optional[str] = Field(
        None,
        description=(
            "Filter by instance state. Common values: 'draft', 'pending', 'in_progress', "
            "'complete', 'cancelled'."
        ),
    )
    metric_type: Optional[str] = Field(
        None,
        description="Filter by metric type name or sys_id (the survey/assessment definition).",
    )
    user: Optional[str] = Field(
        None,
        description="Filter by user sys_id or user_name (the respondent).",
    )
    source_table: Optional[str] = Field(
        None,
        description="Filter by the source table the assessment is attached to (e.g. 'incident').",
    )
    source_id: Optional[str] = Field(
        None,
        description="Filter by the source record sys_id the assessment is attached to.",
    )


def list_assessment_instances(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List assessment instances from the ServiceNow asmt_assessment_instance table.

    Supports filtering by state, metric type, user, and source record.
    Results are ordered by sys_created_on descending (newest first).

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListAssessmentInstancesParams.

    Returns:
        Dictionary with ``success``, ``instances`` (list), ``count``,
        ``has_more``, and ``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListAssessmentInstancesParams)
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
    if validated.state:
        query_parts.append(f"state={validated.state}")
    if validated.source_table:
        query_parts.append(f"source_table={validated.source_table}")
    if validated.source_id:
        query_parts.append(f"source_id={validated.source_id}")
    if validated.user:
        if len(validated.user) == 32 and all(c in "0123456789abcdef" for c in validated.user):
            query_parts.append(f"user={validated.user}")
        else:
            query_parts.append(f"user.user_name={validated.user}")
    if validated.metric_type:
        mt_sys_id = _resolve_metric_type_sys_id(instance_url, headers, validated.metric_type)
        if mt_sys_id:
            query_parts.append(f"metric_type={mt_sys_id}")
        else:
            query_parts.append(f"metric_type.nameLIKE{validated.metric_type}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="sys_created_on",
        fields=",".join(ASSESSMENT_INSTANCE_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{ASSESSMENT_INSTANCE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        instances = [_format_assessment_instance(r) for r in response.json().get("result", [])]
        return _paginated_list_response(instances, validated.limit, validated.offset, "instances")
    except requests.exceptions.RequestException as e:
        logger.error("Error listing assessment instances: %s", e)
        return {
            "success": False,
            "message": f"Error listing assessment instances: {_format_http_error(e)}",
        }


# ---------------------------------------------------------------------------
# get_assessment_instance
# ---------------------------------------------------------------------------


class GetAssessmentInstanceParams(BaseModel):
    """Parameters for retrieving a single assessment instance."""

    instance_id: str = Field(
        ...,
        description="The sys_id of the assessment instance to retrieve.",
    )


def get_assessment_instance(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single asmt_assessment_instance record by sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetAssessmentInstanceParams.

    Returns:
        Dictionary with ``success`` and ``instance`` keys on success.
    """
    result = _unwrap_and_validate_params(params, GetAssessmentInstanceParams, required_fields=["instance_id"])
    if not result["success"]:
        return result
    validated: GetAssessmentInstanceParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}/api/now/table/{ASSESSMENT_INSTANCE_TABLE}/{validated.instance_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(ASSESSMENT_INSTANCE_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Assessment instance not found: {validated.instance_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Assessment instance not found: {validated.instance_id}"}
        return {"success": True, "instance": _format_assessment_instance(record)}
    except requests.exceptions.RequestException as e:
        logger.error("Error retrieving assessment instance: %s", e)
        return {"success": False, "message": f"Error retrieving assessment instance: {_format_http_error(e)}"}


# ---------------------------------------------------------------------------
# list_assessment_metric_types
# ---------------------------------------------------------------------------


class ListAssessmentMetricTypesParams(BaseModel):
    """Parameters for listing assessment metric types (survey definitions)."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Offset for pagination")
    name: Optional[str] = Field(
        None,
        description="Filter by name (case-insensitive substring match).",
    )
    active: Optional[bool] = Field(
        None,
        description="Filter by active state. True returns only active types.",
    )
    assessment_type: Optional[str] = Field(
        None,
        alias="type",
        description="Filter by assessment type (e.g. 'survey', 'assessment', 'certification').",
    )
    related_table: Optional[str] = Field(
        None,
        description="Filter by related_table (the table the assessment is attached to).",
    )


def list_assessment_metric_types(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List assessment metric types (survey/assessment definitions) from asmt_metric_type.

    Supports filtering by name, active state, type, and related table.
    Results are ordered by name ascending.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListAssessmentMetricTypesParams.

    Returns:
        Dictionary with ``success``, ``metric_types`` (list), ``count``,
        ``has_more``, and ``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListAssessmentMetricTypesParams)
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
    if validated.assessment_type:
        query_parts.append(f"type={validated.assessment_type}")
    if validated.related_table:
        query_parts.append(f"related_table={validated.related_table}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="name",
        fields=",".join(ASSESSMENT_METRIC_TYPE_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{ASSESSMENT_METRIC_TYPE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        metric_types = [_format_assessment_metric_type(r) for r in response.json().get("result", [])]
        return _paginated_list_response(metric_types, validated.limit, validated.offset, "metric_types")
    except requests.exceptions.RequestException as e:
        logger.error("Error listing assessment metric types: %s", e)
        return {
            "success": False,
            "message": f"Error listing assessment metric types: {_format_http_error(e)}",
        }


# ---------------------------------------------------------------------------
# get_assessment_metric_type
# ---------------------------------------------------------------------------


class GetAssessmentMetricTypeParams(BaseModel):
    """Parameters for retrieving a single assessment metric type."""

    metric_type_id: str = Field(
        ...,
        description="The sys_id or exact name of the assessment metric type to retrieve.",
    )


def get_assessment_metric_type(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single asmt_metric_type record by sys_id or name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetAssessmentMetricTypeParams.

    Returns:
        Dictionary with ``success`` and ``metric_type`` keys on success.
    """
    result = _unwrap_and_validate_params(
        params, GetAssessmentMetricTypeParams, required_fields=["metric_type_id"]
    )
    if not result["success"]:
        return result
    validated: GetAssessmentMetricTypeParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_metric_type_sys_id(instance_url, headers, validated.metric_type_id)
    if not sys_id:
        return {"success": False, "message": f"Assessment metric type not found: {validated.metric_type_id}"}

    url = f"{instance_url}/api/now/table/{ASSESSMENT_METRIC_TYPE_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(ASSESSMENT_METRIC_TYPE_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {
                "success": False,
                "message": f"Assessment metric type not found: {validated.metric_type_id}",
            }
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {
                "success": False,
                "message": f"Assessment metric type not found: {validated.metric_type_id}",
            }
        return {"success": True, "metric_type": _format_assessment_metric_type(record)}
    except requests.exceptions.RequestException as e:
        logger.error("Error retrieving assessment metric type: %s", e)
        return {
            "success": False,
            "message": f"Error retrieving assessment metric type: {_format_http_error(e)}",
        }


# ---------------------------------------------------------------------------
# create_assessment_instance
# ---------------------------------------------------------------------------


class CreateAssessmentInstanceParams(BaseModel):
    """Parameters for creating a new assessment instance."""

    metric_type: str = Field(
        ...,
        description=(
            "The sys_id or exact name of the assessment metric type (survey definition) "
            "to use for this instance."
        ),
    )
    source_table: str = Field(
        ...,
        description=(
            "The ServiceNow table that the source record belongs to (e.g. 'incident', "
            "'change_request', 'sys_user')."
        ),
    )
    source_id: str = Field(
        ...,
        description="The sys_id of the source record that this assessment is attached to.",
    )
    user: Optional[str] = Field(
        None,
        description=(
            "The sys_id or user_name of the respondent. When omitted ServiceNow uses "
            "the authenticated user."
        ),
    )
    assigned_to: Optional[str] = Field(
        None,
        description="The sys_id or user_name of the user responsible for completing the assessment.",
    )
    due_date: Optional[str] = Field(
        None,
        description="Due date for the assessment in YYYY-MM-DD format.",
    )
    state: Optional[str] = Field(
        None,
        description=(
            "Initial state of the instance. Typical values: 'draft', 'pending', 'in_progress'. "
            "Defaults to ServiceNow's platform default when omitted."
        ),
    )

    @field_validator("due_date", mode="before")
    @classmethod
    def validate_due_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate due_date as YYYY-MM-DD."""
        if v is None:
            return v
        return validate_servicenow_date(v)


def _resolve_user_sys_id(
    instance_url: str,
    headers: Dict,
    user_value: str,
) -> Optional[str]:
    """Return a sys_user sys_id from a user_name or passthrough if already a sys_id."""
    if len(user_value) == 32 and all(c in "0123456789abcdef" for c in user_value):
        return user_value
    url = f"{instance_url}/api/now/table/sys_user"
    try:
        resp = _make_request(
            "GET",
            url,
            headers=headers,
            params={
                "sysparm_query": f"user_name={user_value}",
                "sysparm_limit": 1,
                "sysparm_fields": "sys_id",
            },
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        if not results:
            return None
        return results[0].get("sys_id")
    except requests.exceptions.RequestException:
        return None


def create_assessment_instance(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new assessment instance in asmt_assessment_instance.

    Assigns a metric type (survey definition) to a source record and optionally
    specifies the respondent (user), the person responsible (assigned_to), and a
    due date.  The metric_type may be supplied as a sys_id or as its exact name;
    user and assigned_to may be supplied as sys_ids or as user_name values.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateAssessmentInstanceParams.

    Returns:
        Dictionary with ``success`` and ``instance`` keys on success.
    """
    result = _unwrap_and_validate_params(
        params,
        CreateAssessmentInstanceParams,
        required_fields=["metric_type", "source_table", "source_id"],
    )
    if not result["success"]:
        return result
    validated: CreateAssessmentInstanceParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    # Resolve metric_type to a sys_id.
    mt_sys_id = _resolve_metric_type_sys_id(instance_url, headers, validated.metric_type)
    if not mt_sys_id:
        return {
            "success": False,
            "message": f"Assessment metric type not found: {validated.metric_type}",
        }

    # Build the request body.
    body: Dict[str, Any] = {
        "metric_type": mt_sys_id,
        "source_table": validated.source_table,
        "source_id": validated.source_id,
    }

    if validated.user:
        user_sys_id = _resolve_user_sys_id(instance_url, headers, validated.user)
        if not user_sys_id:
            return {"success": False, "message": f"User not found: {validated.user}"}
        body["user"] = user_sys_id

    if validated.assigned_to:
        assigned_sys_id = _resolve_user_sys_id(instance_url, headers, validated.assigned_to)
        if not assigned_sys_id:
            return {"success": False, "message": f"User not found: {validated.assigned_to}"}
        body["assigned_to"] = assigned_sys_id

    if validated.due_date:
        body["due_date"] = validated.due_date

    if validated.state:
        body["state"] = validated.state

    url = f"{instance_url}/api/now/table/{ASSESSMENT_INSTANCE_TABLE}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }
    try:
        response = _make_request("POST", url, headers=headers, json=body, params=query_params)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {"success": True, "instance": _format_assessment_instance(record)}
    except requests.exceptions.RequestException as e:
        logger.error("Error creating assessment instance: %s", e)
        return {
            "success": False,
            "message": f"Error creating assessment instance: {_format_http_error(e)}",
        }
