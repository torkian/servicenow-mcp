"""
User Criteria tools for the ServiceNow MCP server.

This module provides tools for managing User Criteria records in ServiceNow.
User Criteria restrict access to Service Catalog items, categories, and
catalogs based on user attributes (role, group, department, company,
location) or a custom script.
"""

import logging
from typing import Any, Dict, Literal, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


class CreateUserCriteriaParams(BaseModel):
    """Parameters for creating a User Criteria record in ServiceNow."""

    name: str = Field(..., description="The display name of the user criteria record")
    active: bool = Field(True, description="Whether the user criteria is active")
    match_all: bool = Field(
        False,
        description=(
            "When true, a user must satisfy ALL specified conditions (AND logic). "
            "When false, matching ANY condition grants access (OR logic)."
        ),
    )
    role: Optional[str] = Field(
        None,
        description=(
            "sys_id of a ServiceNow role (sys_user_role). "
            "Users must have this role to match."
        ),
    )
    user: Optional[str] = Field(
        None,
        description=(
            "sys_id of a specific ServiceNow user (sys_user). "
            "Only this user will match."
        ),
    )
    group: Optional[str] = Field(
        None,
        description=(
            "sys_id of a user group (sys_user_group). "
            "Members of this group will match."
        ),
    )
    department: Optional[str] = Field(
        None,
        description=(
            "sys_id of a department (cmn_department). "
            "Users in this department will match."
        ),
    )
    company: Optional[str] = Field(
        None,
        description=(
            "sys_id of a company (core_company). "
            "Users belonging to this company will match."
        ),
    )
    location: Optional[str] = Field(
        None,
        description=(
            "sys_id of a location (cmn_location). "
            "Users at this location will match."
        ),
    )
    script: Optional[str] = Field(
        None,
        description=(
            "Advanced GlideScript that returns true/false to determine access. "
            "Use for conditions that cannot be expressed with the standard fields."
        ),
    )


class UserCriteriaResponse(BaseModel):
    """Response from User Criteria operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")
    criteria_id: Optional[str] = Field(
        None, description="The sys_id of the created User Criteria record"
    )
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional details returned by ServiceNow"
    )


def create_user_criteria(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateUserCriteriaParams,
) -> UserCriteriaResponse:
    """
    Create a new User Criteria record in ServiceNow.

    User Criteria (``user_criteria`` table) define who can see or request
    Service Catalog items, categories, or entire catalogs.  After creating a
    criteria record you link it to a catalog entity via the
    ``sc_cat_item_user_criteria_mtom`` (or equivalent) relationship table.

    Criteria matching is controlled by ``match_all``:

    * ``match_all=False`` (default) — access is granted when the user satisfies
      ANY of the configured conditions (role, group, department, …).
    * ``match_all=True`` — the user must satisfy ALL configured conditions
      simultaneously.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for creating the User Criteria record.

    Returns:
        Response with information about the created User Criteria record.
    """
    api_url = f"{config.instance_url}/api/now/table/user_criteria"

    data: Dict[str, Any] = {
        "name": params.name,
        "active": str(params.active).lower(),
        "match_all": str(params.match_all).lower(),
    }

    optional_fields = {
        "role": params.role,
        "user": params.user,
        "group": params.group,
        "department": params.department,
        "company": params.company,
        "location": params.location,
        "script": params.script,
    }
    for field, value in optional_fields.items():
        if value is not None:
            data[field] = value

    try:
        response = requests.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return UserCriteriaResponse(
            success=True,
            message=f"User criteria '{params.name}' created successfully",
            criteria_id=result.get("sys_id"),
            details=result,
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create user criteria: {e}")
        return UserCriteriaResponse(
            success=False,
            message=f"Failed to create user criteria: {str(e)}",
        )


# ---------------------------------------------------------------------------
# create_user_criteria_condition
# ---------------------------------------------------------------------------

_ENTITY_TABLES = {
    # (entity_type, visibility) -> (table_name, entity_field_name)
    ("catalog_item", "can_see"): ("sc_cat_item_user_criteria_mtom", "sc_cat_item"),
    ("catalog_item", "cannot_see"): ("sc_cat_item_user_criteria_no_mtom", "sc_cat_item"),
    ("category", "can_see"): ("sc_category_user_criteria_mtom", "sc_category"),
    ("category", "cannot_see"): ("sc_category_user_criteria_no_mtom", "sc_category"),
    ("catalog", "can_see"): ("sc_catalog_user_criteria_mtom", "sc_catalog"),
    ("catalog", "cannot_see"): ("sc_catalog_user_criteria_no_mtom", "sc_catalog"),
}


class CreateUserCriteriaConditionParams(BaseModel):
    """Parameters for applying a User Criteria record to a catalog entity."""

    user_criteria_id: str = Field(
        ...,
        description="sys_id of the User Criteria record to apply",
    )
    entity_type: Literal["catalog_item", "category", "catalog"] = Field(
        ...,
        description=(
            "The type of catalog entity to restrict: "
            "'catalog_item' for a specific item (sc_cat_item), "
            "'category' for a catalog category (sc_category), "
            "or 'catalog' for an entire catalog (sc_catalog)"
        ),
    )
    entity_id: str = Field(
        ...,
        description="sys_id of the catalog entity (item, category, or catalog) to restrict",
    )
    visibility: Literal["can_see", "cannot_see"] = Field(
        "can_see",
        description=(
            "'can_see' grants access to users who match the criteria (allow-list); "
            "'cannot_see' blocks access for users who match the criteria (deny-list)"
        ),
    )


class UserCriteriaConditionResponse(BaseModel):
    """Response from User Criteria condition operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")
    condition_id: Optional[str] = Field(
        None, description="The sys_id of the created junction record"
    )
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional details returned by ServiceNow"
    )


def create_user_criteria_condition(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateUserCriteriaConditionParams,
) -> UserCriteriaConditionResponse:
    """
    Apply a User Criteria record to a Service Catalog entity.

    This creates a junction record in the appropriate ServiceNow relationship
    table, linking an existing ``user_criteria`` record to a catalog item,
    category, or catalog.  Two visibility modes are supported:

    * ``can_see`` (default) — users who match the criteria are *allowed* to
      see / request the entity.  Uses the ``*_mtom`` tables:

      - ``sc_cat_item_user_criteria_mtom``
      - ``sc_category_user_criteria_mtom``
      - ``sc_catalog_user_criteria_mtom``

    * ``cannot_see`` — users who match the criteria are *denied* access to
      the entity.  Uses the ``*_no_mtom`` tables:

      - ``sc_cat_item_user_criteria_no_mtom``
      - ``sc_category_user_criteria_no_mtom``
      - ``sc_catalog_user_criteria_no_mtom``

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters identifying the criteria, entity, and visibility.

    Returns:
        Response with the sys_id of the created junction record.
    """
    table_name, entity_field = _ENTITY_TABLES[(params.entity_type, params.visibility)]
    api_url = f"{config.instance_url}/api/now/table/{table_name}"

    data: Dict[str, Any] = {
        "user_criteria": params.user_criteria_id,
        entity_field: params.entity_id,
    }

    try:
        response = requests.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return UserCriteriaConditionResponse(
            success=True,
            message=(
                f"User criteria condition created: criteria '{params.user_criteria_id}' "
                f"applied to {params.entity_type} '{params.entity_id}' "
                f"({params.visibility})"
            ),
            condition_id=result.get("sys_id"),
            details=result,
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create user criteria condition: {e}")
        return UserCriteriaConditionResponse(
            success=False,
            message=f"Failed to create user criteria condition: {str(e)}",
        )
