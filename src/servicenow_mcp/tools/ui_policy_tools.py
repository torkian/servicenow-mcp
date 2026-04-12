"""
UI Policy tools for the ServiceNow MCP server.

This module provides tools for managing UI policies and UI policy actions in ServiceNow.
UI policies control the behavior of form fields (mandatory, visible, read-only) based
on configurable conditions.
"""

import logging
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


class CreateUIPolicyParams(BaseModel):
    """Parameters for creating a UI policy in ServiceNow."""

    name: str = Field(..., description="The name of the UI policy")
    table_name: str = Field(
        ...,
        description=(
            "The name of the table this policy applies to "
            "(e.g., 'incident', 'sc_cat_item', 'change_request')"
        ),
    )
    active: bool = Field(True, description="Whether the UI policy is active")
    on_load: bool = Field(
        True,
        description="Whether to run the policy when the form first loads",
    )
    reverse_if_false: bool = Field(
        True,
        description=(
            "When true, reverses the policy's field actions when the condition "
            "evaluates to false"
        ),
    )
    conditions: Optional[str] = Field(
        None,
        description=(
            "Encoded query string that acts as the trigger condition "
            "(e.g., 'priority=1^state=2'). Leave empty for the policy to always apply."
        ),
    )
    short_description: Optional[str] = Field(
        None, description="Short description or purpose of the UI policy"
    )
    catalog_item_id: Optional[str] = Field(
        None,
        description=(
            "For catalog UI policies, the sys_id of the catalog item "
            "(sc_cat_item) this policy is scoped to"
        ),
    )
    run_scripts: bool = Field(
        False,
        description="Whether this policy also executes scripts (requires script fields)",
    )


class UIPolicyResponse(BaseModel):
    """Response from UI policy operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")
    policy_id: Optional[str] = Field(None, description="The sys_id of the created UI policy")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional details returned by ServiceNow"
    )


def create_ui_policy(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateUIPolicyParams,
) -> UIPolicyResponse:
    """
    Create a new UI policy in ServiceNow.

    UI policies define dynamic form behaviour: they evaluate a condition and then
    apply a set of field-level actions (mandatory / visible / read-only) managed
    via the companion ``create_ui_policy_action`` tool.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for creating the UI policy.

    Returns:
        Response with information about the created UI policy.
    """
    api_url = f"{config.instance_url}/api/now/table/sys_ui_policy"

    data: Dict[str, Any] = {
        "name": params.name,
        "table_name": params.table_name,
        "active": str(params.active).lower(),
        "on_load": str(params.on_load).lower(),
        "reverse_if_false": str(params.reverse_if_false).lower(),
        "run_scripts": str(params.run_scripts).lower(),
    }

    if params.conditions:
        data["conditions"] = params.conditions
    if params.short_description:
        data["short_description"] = params.short_description
    if params.catalog_item_id:
        data["catalog_item"] = params.catalog_item_id

    try:
        response = requests.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return UIPolicyResponse(
            success=True,
            message=f"UI policy '{params.name}' created successfully",
            policy_id=result.get("sys_id"),
            details=result,
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create UI policy: {e}")
        return UIPolicyResponse(
            success=False,
            message=f"Failed to create UI policy: {str(e)}",
        )
