"""
Catalog Item Delivery Plan tools for the ServiceNow MCP server.

Provides tools for managing approval/delivery policies attached to catalog items:
  - sc_cat_item_delivery_plan  — delivery plans
  - sc_cat_item_delivery_task  — tasks within a delivery plan
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

_PLAN_TABLE = "sc_cat_item_delivery_plan"
_TASK_TABLE = "sc_cat_item_delivery_task"

_PLAN_FIELDS = [
    "sys_id",
    "name",
    "description",
    "active",
    "cat_item",
    "workflow",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
]

_TASK_FIELDS = [
    "sys_id",
    "name",
    "description",
    "active",
    "order",
    "delivery_plan",
    "approval_group",
    "assigned_to",
    "mandatory",
    "sys_created_on",
    "sys_updated_on",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListDeliveryPlansParams(BaseModel):
    """Parameters for listing catalog item delivery plans."""

    limit: int = Field(20, description="Maximum number of records to return")
    offset: int = Field(0, description="Pagination offset")
    name: Optional[str] = Field(None, description="Filter by plan name (substring)")
    cat_item_id: Optional[str] = Field(None, description="Filter by catalog item sys_id or name")
    active: Optional[bool] = Field(None, description="Filter by active state")
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetDeliveryPlanParams(BaseModel):
    """Parameters for retrieving a single delivery plan."""

    plan_id: str = Field(..., description="Delivery plan sys_id or exact name")


class CreateDeliveryPlanParams(BaseModel):
    """Parameters for creating a new catalog item delivery plan."""

    name: str = Field(..., description="Name of the delivery plan")
    cat_item_id: str = Field(..., description="sys_id of the catalog item this plan applies to")
    description: Optional[str] = Field(None, description="Description of the plan")
    workflow: Optional[str] = Field(None, description="sys_id of an associated workflow")
    active: bool = Field(True, description="Whether the plan is active")


class UpdateDeliveryPlanParams(BaseModel):
    """Parameters for updating an existing catalog item delivery plan."""

    plan_id: str = Field(..., description="Delivery plan sys_id or exact name")
    name: Optional[str] = Field(None, description="New name for the plan")
    description: Optional[str] = Field(None, description="New description")
    workflow: Optional[str] = Field(None, description="sys_id of an associated workflow")
    active: Optional[bool] = Field(None, description="Whether the plan is active")


class DeleteDeliveryPlanParams(BaseModel):
    """Parameters for deleting a catalog item delivery plan."""

    plan_id: str = Field(..., description="Delivery plan sys_id or exact name")


class ListDeliveryTasksParams(BaseModel):
    """Parameters for listing tasks within a delivery plan."""

    plan_id: str = Field(..., description="Delivery plan sys_id or name")
    limit: int = Field(20, description="Maximum number of records to return")
    offset: int = Field(0, description="Pagination offset")
    active: Optional[bool] = Field(None, description="Filter by active state")


class CreateDeliveryTaskParams(BaseModel):
    """Parameters for creating a task within a delivery plan."""

    plan_id: str = Field(..., description="Delivery plan sys_id or name")
    name: str = Field(..., description="Name of the delivery task")
    description: Optional[str] = Field(None, description="Description of the task")
    order: Optional[int] = Field(None, description="Execution order (lower = earlier)")
    approval_group: Optional[str] = Field(None, description="sys_id of the approval group")
    assigned_to: Optional[str] = Field(None, description="sys_id of the user assigned to this task")
    mandatory: bool = Field(True, description="Whether this task must complete for the plan to proceed")
    active: bool = Field(True, description="Whether the task is active")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _ref_val(field: Any) -> Optional[str]:
    """Return display_value from a reference dict, or the value itself."""
    if isinstance(field, dict):
        return field.get("display_value") or field.get("value")
    return field or None


def _format_plan(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "sys_id": raw.get("sys_id"),
        "name": raw.get("name"),
        "description": raw.get("description"),
        "active": raw.get("active"),
        "cat_item": _ref_val(raw.get("cat_item")),
        "workflow": _ref_val(raw.get("workflow")),
        "sys_created_on": raw.get("sys_created_on"),
        "sys_updated_on": raw.get("sys_updated_on"),
        "sys_created_by": raw.get("sys_created_by"),
    }


def _format_task(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "sys_id": raw.get("sys_id"),
        "name": raw.get("name"),
        "description": raw.get("description"),
        "active": raw.get("active"),
        "order": raw.get("order"),
        "delivery_plan": _ref_val(raw.get("delivery_plan")),
        "approval_group": _ref_val(raw.get("approval_group")),
        "assigned_to": _ref_val(raw.get("assigned_to")),
        "mandatory": raw.get("mandatory"),
        "sys_created_on": raw.get("sys_created_on"),
        "sys_updated_on": raw.get("sys_updated_on"),
    }


def _resolve_plan_sys_id(base_url: str, headers: Dict[str, str], plan_id: str) -> Optional[str]:
    """Return the sys_id for a plan given a sys_id or exact name."""
    if len(plan_id) == 32 and all(c in "0123456789abcdef" for c in plan_id):
        return plan_id
    url = f"{base_url}/api/now/table/{_PLAN_TABLE}"
    try:
        resp = requests.get(
            url,
            headers=headers,
            params={"sysparm_query": f"name={plan_id}", "sysparm_fields": "sys_id", "sysparm_limit": 1},
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        return results[0]["sys_id"] if results else None
    except Exception:
        return None


def _resolve_cat_item_sys_id(base_url: str, headers: Dict[str, str], cat_item_id: str) -> Optional[str]:
    """Return the sys_id for a catalog item given a sys_id or name."""
    if len(cat_item_id) == 32 and all(c in "0123456789abcdef" for c in cat_item_id):
        return cat_item_id
    url = f"{base_url}/api/now/table/sc_cat_item"
    try:
        resp = requests.get(
            url,
            headers=headers,
            params={"sysparm_query": f"nameLIKE{cat_item_id}", "sysparm_fields": "sys_id", "sysparm_limit": 1},
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        return results[0]["sys_id"] if results else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def list_delivery_plans(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListDeliveryPlansParams,
) -> Dict[str, Any]:
    """List catalog item delivery plan records from sc_cat_item_delivery_plan.

    Supports filtering by name, catalog item, and active state. Returns a
    paginated list with has_more and next_offset for cursor navigation.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")
    url = f"{base_url}/api/now/table/{_PLAN_TABLE}"

    parts: List[str] = []
    if params.name:
        parts.append(f"nameLIKE{params.name}")
    if params.active is not None:
        parts.append(f"active={'true' if params.active else 'false'}")
    if params.cat_item_id:
        cat_sys_id = _resolve_cat_item_sys_id(base_url, headers, params.cat_item_id)
        if cat_sys_id:
            parts.append(f"cat_item={cat_sys_id}")
    if params.query:
        parts.append(params.query)
    query = "^".join(parts)

    request_params: Dict[str, Any] = {
        "sysparm_fields": ",".join(_PLAN_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_orderby": "name",
    }
    if query:
        request_params["sysparm_query"] = query

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    data = response.json().get("result", [])
    records = [_format_plan(r) for r in data]
    has_more = len(records) == params.limit
    return {
        "records": records,
        "count": len(records),
        "has_more": has_more,
        "next_offset": params.offset + len(records) if has_more else None,
    }


def get_delivery_plan(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetDeliveryPlanParams,
) -> Dict[str, Any]:
    """Retrieve a single catalog item delivery plan by sys_id or exact name.

    Returns 404 error when no matching plan is found.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")

    sys_id = _resolve_plan_sys_id(base_url, headers, params.plan_id)
    if not sys_id:
        return {"error": f"Delivery plan not found: {params.plan_id}"}

    url = f"{base_url}/api/now/table/{_PLAN_TABLE}/{sys_id}"
    request_params = {
        "sysparm_fields": ",".join(_PLAN_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        if response.status_code == 404:
            return {"error": f"Delivery plan not found: {params.plan_id}"}
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    result = response.json().get("result")
    if not result:
        return {"error": f"Delivery plan not found: {params.plan_id}"}

    return {"plan": _format_plan(result)}


def create_delivery_plan(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateDeliveryPlanParams,
) -> Dict[str, Any]:
    """Create a new catalog item delivery plan in sc_cat_item_delivery_plan.

    Links the plan to a catalog item by sys_id. Optionally attaches an
    existing workflow to drive the approval flow.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")
    url = f"{base_url}/api/now/table/{_PLAN_TABLE}"

    cat_sys_id = _resolve_cat_item_sys_id(base_url, headers, params.cat_item_id)
    if not cat_sys_id:
        return {"error": f"Catalog item not found: {params.cat_item_id}"}

    body: Dict[str, Any] = {
        "name": params.name,
        "cat_item": cat_sys_id,
        "active": "true" if params.active else "false",
    }
    if params.description is not None:
        body["description"] = params.description
    if params.workflow is not None:
        body["workflow"] = params.workflow

    try:
        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    result = response.json().get("result", {})
    return {
        "success": True,
        "message": f"Delivery plan '{params.name}' created successfully.",
        "plan": _format_plan(result),
    }


def update_delivery_plan(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateDeliveryPlanParams,
) -> Dict[str, Any]:
    """Update an existing catalog item delivery plan.

    Issues a PATCH request with only the supplied fields. Returns 404 error
    when the plan is not found, and rejects calls with no updatable fields.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")

    sys_id = _resolve_plan_sys_id(base_url, headers, params.plan_id)
    if not sys_id:
        return {"error": f"Delivery plan not found: {params.plan_id}"}

    body: Dict[str, Any] = {}
    if params.name is not None:
        body["name"] = params.name
    if params.description is not None:
        body["description"] = params.description
    if params.workflow is not None:
        body["workflow"] = params.workflow
    if params.active is not None:
        body["active"] = "true" if params.active else "false"

    if not body:
        return {"error": "No fields provided to update."}

    url = f"{base_url}/api/now/table/{_PLAN_TABLE}/{sys_id}"

    try:
        response = requests.patch(url, headers=headers, json=body, timeout=30)
        if response.status_code == 404:
            return {"error": f"Delivery plan not found: {params.plan_id}"}
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    result = response.json().get("result", {})
    return {
        "success": True,
        "message": "Delivery plan updated successfully.",
        "plan": _format_plan(result),
    }


def delete_delivery_plan(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DeleteDeliveryPlanParams,
) -> Dict[str, Any]:
    """Delete a catalog item delivery plan by sys_id or name.

    Returns 404 error when the plan is not found. Deleting a plan also
    removes its associated delivery tasks (ServiceNow cascade).
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")

    sys_id = _resolve_plan_sys_id(base_url, headers, params.plan_id)
    if not sys_id:
        return {"error": f"Delivery plan not found: {params.plan_id}"}

    url = f"{base_url}/api/now/table/{_PLAN_TABLE}/{sys_id}"

    try:
        response = requests.delete(url, headers=headers, timeout=30)
        if response.status_code == 404:
            return {"error": f"Delivery plan not found: {params.plan_id}"}
        if response.status_code not in (200, 204):
            response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    return {"success": True, "message": f"Delivery plan '{params.plan_id}' deleted successfully."}


def list_delivery_tasks(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListDeliveryTasksParams,
) -> Dict[str, Any]:
    """List tasks belonging to a catalog item delivery plan.

    Tasks are ordered by their execution order field. Supports optional
    active filter and pagination.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")
    url = f"{base_url}/api/now/table/{_TASK_TABLE}"

    plan_sys_id = _resolve_plan_sys_id(base_url, headers, params.plan_id)
    if not plan_sys_id:
        return {"error": f"Delivery plan not found: {params.plan_id}"}

    parts: List[str] = [f"delivery_plan={plan_sys_id}"]
    if params.active is not None:
        parts.append(f"active={'true' if params.active else 'false'}")
    query = "^".join(parts)

    request_params: Dict[str, Any] = {
        "sysparm_fields": ",".join(_TASK_FIELDS),
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_orderby": "order",
        "sysparm_query": query,
    }

    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=30)
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    data = response.json().get("result", [])
    records = [_format_task(r) for r in data]
    has_more = len(records) == params.limit
    return {
        "records": records,
        "count": len(records),
        "has_more": has_more,
        "next_offset": params.offset + len(records) if has_more else None,
    }


def create_delivery_task(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateDeliveryTaskParams,
) -> Dict[str, Any]:
    """Create a task within a catalog item delivery plan.

    Tasks define individual approval or work steps. The order field controls
    execution sequence — lower values run first.
    """
    headers = auth_manager.get_headers()
    base_url = config.instance_url.rstrip("/")

    plan_sys_id = _resolve_plan_sys_id(base_url, headers, params.plan_id)
    if not plan_sys_id:
        return {"error": f"Delivery plan not found: {params.plan_id}"}

    url = f"{base_url}/api/now/table/{_TASK_TABLE}"

    body: Dict[str, Any] = {
        "name": params.name,
        "delivery_plan": plan_sys_id,
        "mandatory": "true" if params.mandatory else "false",
        "active": "true" if params.active else "false",
    }
    if params.description is not None:
        body["description"] = params.description
    if params.order is not None:
        body["order"] = str(params.order)
    if params.approval_group is not None:
        body["approval_group"] = params.approval_group
    if params.assigned_to is not None:
        body["assigned_to"] = params.assigned_to

    try:
        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {exc}"}

    result = response.json().get("result", {})
    return {
        "success": True,
        "message": f"Delivery task '{params.name}' created successfully.",
        "task": _format_task(result),
    }
