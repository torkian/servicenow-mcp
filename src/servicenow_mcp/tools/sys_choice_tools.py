"""
sys_choice tools for the ServiceNow MCP server.

Provides tools for managing picklist choices via the sys_choice table,
which stores all choice values for choice-type fields across every table.
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

SYS_CHOICE_TABLE = "sys_choice"

SYS_CHOICE_FIELDS = ",".join([
    "sys_id",
    "name",
    "element",
    "value",
    "label",
    "sequence",
    "language",
    "inactive",
    "hint",
    "dependent_value",
    "sys_created_on",
    "sys_updated_on",
])


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListFieldChoicesParams(BaseModel):
    """Parameters for listing picklist choices."""

    table_name: str = Field(
        ...,
        description=(
            "The table that owns the choice field (e.g. 'incident', 'change_request'). "
            "Required."
        ),
    )
    field_name: Optional[str] = Field(
        None,
        description=(
            "The column/element name of the choice field (e.g. 'state', 'priority'). "
            "When omitted all choice fields on the table are returned."
        ),
    )
    language: Optional[str] = Field(
        None,
        description=(
            "Filter by language code (e.g. 'en', 'fr'). "
            "When omitted all languages are returned."
        ),
    )
    include_inactive: Optional[bool] = Field(
        False,
        description="When true, include inactive choices. Default false returns only active choices.",
    )
    limit: Optional[int] = Field(50, description="Maximum number of choices to return (default 50).")
    offset: Optional[int] = Field(0, description="Offset for pagination.")


class CreateFieldChoiceParams(BaseModel):
    """Parameters for creating a new picklist choice."""

    table_name: str = Field(
        ...,
        description="The table that owns the choice field (e.g. 'incident').",
    )
    field_name: str = Field(
        ...,
        description="The column/element name of the choice field (e.g. 'state').",
    )
    value: str = Field(
        ...,
        description="The stored value (code) for the choice (e.g. '1', 'high').",
    )
    label: str = Field(
        ...,
        description="The display label shown to users (e.g. 'Open', 'High').",
    )
    sequence: Optional[int] = Field(
        None,
        description="Display order; lower numbers appear first.",
    )
    language: Optional[str] = Field(
        "en",
        description="Language code for the choice label (default 'en').",
    )
    hint: Optional[str] = Field(
        None,
        description="Tooltip text displayed when a user hovers over the choice.",
    )
    inactive: Optional[bool] = Field(
        False,
        description="When true, the choice is created but not shown in the picker. Default false.",
    )
    dependent_value: Optional[str] = Field(
        None,
        description=(
            "For dependent choice fields: the parent field value that makes this choice visible."
        ),
    )


class UpdateFieldChoiceParams(BaseModel):
    """Parameters for updating an existing picklist choice."""

    sys_id: str = Field(
        ...,
        description="The sys_id of the sys_choice record to update.",
    )
    label: Optional[str] = Field(
        None,
        description="New display label shown to users.",
    )
    sequence: Optional[int] = Field(
        None,
        description="New display order; lower numbers appear first.",
    )
    hint: Optional[str] = Field(
        None,
        description="New tooltip text.",
    )
    inactive: Optional[bool] = Field(
        None,
        description="Set true to hide the choice from the picker, false to show it.",
    )
    dependent_value: Optional[str] = Field(
        None,
        description="New parent field value that makes this choice visible (for dependent fields).",
    )


class DeleteFieldChoiceParams(BaseModel):
    """Parameters for deleting a picklist choice."""

    sys_id: str = Field(
        ...,
        description="The sys_id of the sys_choice record to delete.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_choice(record: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a sys_choice record."""

    def _val(field: str) -> Any:
        v = record.get(field, "")
        if isinstance(v, dict):
            return v.get("value") or v.get("display_value") or ""
        return v

    result: Dict[str, Any] = {
        "sys_id": _val("sys_id"),
        "table_name": _val("name"),
        "field_name": _val("element"),
        "value": _val("value"),
        "label": _val("label"),
        "sequence": _val("sequence"),
        "language": _val("language"),
        "inactive": _val("inactive") in ("true", True, "1", 1),
        "hint": _val("hint"),
    }

    dep = _val("dependent_value")
    if dep:
        result["dependent_value"] = dep

    return result


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def list_field_choices(
    params: Dict[str, Any],
    server_config: ServerConfig,
    auth_manager: AuthManager,
) -> Dict[str, Any]:
    """List picklist choices for a ServiceNow table field from sys_choice."""

    result = _unwrap_and_validate_params(params, ListFieldChoicesParams)
    if not result["success"]:
        return {"error": result["message"]}
    p: ListFieldChoicesParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"error": "No instance URL configured"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"error": "Failed to obtain authentication headers"}

    url = f"{instance_url}/api/now/table/{SYS_CHOICE_TABLE}"

    query_parts: List[str] = [f"name={p.table_name}"]

    if p.field_name:
        query_parts.append(f"element={p.field_name}")

    if p.language:
        query_parts.append(f"language={p.language}")

    if not p.include_inactive:
        query_parts.append("inactive=false")

    sysparm_query = _join_query_parts(query_parts)

    sysparm_params = _build_sysparm_params(
        limit=p.limit,
        offset=p.offset,
        query=sysparm_query,
        fields=SYS_CHOICE_FIELDS,
    )
    sysparm_params["sysparm_orderby"] = "sequence"

    try:
        resp = _make_request(
            method="GET",
            url=url,
            headers=headers,
            params=sysparm_params,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": _format_http_error(exc)}
    except requests.RequestException as exc:
        return {"error": str(exc)}

    data = resp.json().get("result", [])
    choices = [_format_choice(r) for r in data]

    return _paginated_list_response(
        items=choices,
        result_key="choices",
        limit=p.limit,
        offset=p.offset,
        extra={"table_name": p.table_name, "field_name": p.field_name},
    )


def create_field_choice(
    params: Dict[str, Any],
    server_config: ServerConfig,
    auth_manager: AuthManager,
) -> Dict[str, Any]:
    """Create a new picklist choice in sys_choice."""

    result = _unwrap_and_validate_params(
        params,
        CreateFieldChoiceParams,
        required_fields=["table_name", "field_name", "value", "label"],
    )
    if not result["success"]:
        return {"error": result["message"]}
    p: CreateFieldChoiceParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"error": "No instance URL configured"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"error": "Failed to obtain authentication headers"}

    url = f"{instance_url}/api/now/table/{SYS_CHOICE_TABLE}"

    body: Dict[str, Any] = {
        "name": p.table_name,
        "element": p.field_name,
        "value": p.value,
        "label": p.label,
        "language": p.language or "en",
        "inactive": "true" if p.inactive else "false",
    }

    if p.sequence is not None:
        body["sequence"] = str(p.sequence)
    if p.hint:
        body["hint"] = p.hint
    if p.dependent_value:
        body["dependent_value"] = p.dependent_value

    try:
        resp = _make_request(
            method="POST",
            url=url,
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": _format_http_error(exc)}
    except requests.RequestException as exc:
        return {"error": str(exc)}

    created = resp.json().get("result", {})
    return {
        "success": True,
        "choice": _format_choice(created),
        "message": (
            f"Choice '{p.label}' (value='{p.value}') created for "
            f"{p.table_name}.{p.field_name}"
        ),
    }


def update_field_choice(
    params: Dict[str, Any],
    server_config: ServerConfig,
    auth_manager: AuthManager,
) -> Dict[str, Any]:
    """Update an existing picklist choice in sys_choice by sys_id."""

    result = _unwrap_and_validate_params(
        params, UpdateFieldChoiceParams, required_fields=["sys_id"]
    )
    if not result["success"]:
        return {"error": result["message"]}
    p: UpdateFieldChoiceParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"error": "No instance URL configured"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"error": "Failed to obtain authentication headers"}

    body: Dict[str, Any] = {}
    if p.label is not None:
        body["label"] = p.label
    if p.sequence is not None:
        body["sequence"] = str(p.sequence)
    if p.hint is not None:
        body["hint"] = p.hint
    if p.inactive is not None:
        body["inactive"] = "true" if p.inactive else "false"
    if p.dependent_value is not None:
        body["dependent_value"] = p.dependent_value

    if not body:
        return {"error": "No fields to update — provide at least one of: label, sequence, hint, inactive, dependent_value"}

    url = f"{instance_url}/api/now/table/{SYS_CHOICE_TABLE}/{p.sys_id}"

    try:
        resp = _make_request(
            method="PATCH",
            url=url,
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"error": f"Choice '{p.sys_id}' not found"}
        return {"error": _format_http_error(exc)}
    except requests.RequestException as exc:
        return {"error": str(exc)}

    updated = resp.json().get("result", {})
    return {
        "success": True,
        "choice": _format_choice(updated),
        "message": f"Choice '{p.sys_id}' updated successfully",
    }


def delete_field_choice(
    params: Dict[str, Any],
    server_config: ServerConfig,
    auth_manager: AuthManager,
) -> Dict[str, Any]:
    """Delete a picklist choice from sys_choice by sys_id."""

    result = _unwrap_and_validate_params(
        params, DeleteFieldChoiceParams, required_fields=["sys_id"]
    )
    if not result["success"]:
        return {"error": result["message"]}
    p: DeleteFieldChoiceParams = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"error": "No instance URL configured"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"error": "Failed to obtain authentication headers"}

    url = f"{instance_url}/api/now/table/{SYS_CHOICE_TABLE}/{p.sys_id}"

    try:
        resp = _make_request(
            method="DELETE",
            url=url,
            headers=headers,
        )
        if resp.status_code == 404:
            return {"error": f"Choice '{p.sys_id}' not found"}
        resp.raise_for_status()
    except requests.HTTPError as exc:
        return {"error": _format_http_error(exc)}
    except requests.RequestException as exc:
        return {"error": str(exc)}

    return {
        "success": True,
        "sys_id": p.sys_id,
        "message": f"Choice '{p.sys_id}' deleted successfully",
    }
