"""
Catalog Item Variables tools for the ServiceNow MCP server.

This module provides tools for managing variables (form fields) in ServiceNow catalog items.
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.helpers import _format_http_error, _make_request

logger = logging.getLogger(__name__)


class CreateCatalogItemVariableParams(BaseModel):
    """Parameters for creating a catalog item variable."""

    catalog_item_id: str = Field(..., description="The sys_id of the catalog item")
    name: str = Field(..., description="The name of the variable (internal name)")
    type: str = Field(..., description="The type of variable (e.g., string, integer, boolean, reference)")
    label: str = Field(..., description="The display label for the variable")
    mandatory: bool = Field(False, description="Whether the variable is required")
    help_text: Optional[str] = Field(None, description="Help text to display with the variable")
    default_value: Optional[str] = Field(None, description="Default value for the variable")
    description: Optional[str] = Field(None, description="Description of the variable")
    order: Optional[int] = Field(None, description="Display order of the variable")
    reference_table: Optional[str] = Field(None, description="For reference fields, the table to reference")
    reference_qualifier: Optional[str] = Field(None, description="For reference fields, the query to filter reference options")
    max_length: Optional[int] = Field(None, description="Maximum length for string fields")
    min: Optional[int] = Field(None, description="Minimum value for numeric fields")
    max: Optional[int] = Field(None, description="Maximum value for numeric fields")


class CatalogItemVariableResponse(BaseModel):
    """Response from catalog item variable operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")
    variable_id: Optional[str] = Field(None, description="The sys_id of the created/updated variable")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details about the variable")


class ListCatalogItemVariablesParams(BaseModel):
    """Parameters for listing catalog item variables."""

    catalog_item_id: str = Field(..., description="The sys_id of the catalog item")
    include_details: bool = Field(True, description="Whether to include detailed information about each variable")
    limit: Optional[int] = Field(None, description="Maximum number of variables to return")
    offset: Optional[int] = Field(None, description="Offset for pagination")


class ListCatalogItemVariablesResponse(BaseModel):
    """Response from listing catalog item variables."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")
    variables: List[Dict[str, Any]] = Field([], description="List of variables")
    count: int = Field(0, description="Total number of variables found")


class DeleteCatalogItemVariableParams(BaseModel):
    """Parameters for deleting a catalog item variable."""

    variable_id: str = Field(..., description="The sys_id of the variable to delete")


class UpdateCatalogItemVariableParams(BaseModel):
    """Parameters for updating a catalog item variable."""

    variable_id: str = Field(..., description="The sys_id of the variable to update")
    label: Optional[str] = Field(None, description="The display label for the variable")
    mandatory: Optional[bool] = Field(None, description="Whether the variable is required")
    help_text: Optional[str] = Field(None, description="Help text to display with the variable")
    default_value: Optional[str] = Field(None, description="Default value for the variable")
    description: Optional[str] = Field(None, description="Description of the variable")
    order: Optional[int] = Field(None, description="Display order of the variable")
    reference_qualifier: Optional[str] = Field(None, description="For reference fields, the query to filter reference options")
    max_length: Optional[int] = Field(None, description="Maximum length for string fields")
    min: Optional[int] = Field(None, description="Minimum value for numeric fields")
    max: Optional[int] = Field(None, description="Maximum value for numeric fields")


def create_catalog_item_variable(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateCatalogItemVariableParams,
) -> CatalogItemVariableResponse:
    """
    Create a new variable (form field) for a catalog item.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for creating a catalog item variable.

    Returns:
        Response with information about the created variable.
    """
    api_url = f"{config.instance_url}/api/now/table/item_option_new"

    # Build request data
    data = {
        "cat_item": params.catalog_item_id,
        "name": params.name,
        "type": params.type,
        "question_text": params.label,
        "mandatory": str(params.mandatory).lower(),  # ServiceNow expects "true"/"false" strings
    }

    if params.help_text:
        data["help_text"] = params.help_text
    if params.default_value:
        data["default_value"] = params.default_value
    if params.description:
        data["description"] = params.description
    if params.order is not None:
        data["order"] = params.order
    if params.reference_table:
        data["reference"] = params.reference_table
    if params.reference_qualifier:
        data["reference_qual"] = params.reference_qualifier
    if params.max_length:
        data["max_length"] = params.max_length
    if params.min is not None:
        data["min"] = params.min
    if params.max is not None:
        data["max"] = params.max

    # Make request
    try:
        response = _make_request("POST", 
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return CatalogItemVariableResponse(
            success=True,
            message="Catalog item variable created successfully",
            variable_id=result.get("sys_id"),
            details=result,
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create catalog item variable: {e}")
        return CatalogItemVariableResponse(
            success=False,
            message=f"Failed to create catalog item variable: {_format_http_error(e)}",
        )


def list_catalog_item_variables(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListCatalogItemVariablesParams,
) -> ListCatalogItemVariablesResponse:
    """
    List all variables (form fields) for a catalog item.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for listing catalog item variables.

    Returns:
        Response with a list of variables for the catalog item.
    """
    # Build query parameters
    query_params = {
        "sysparm_query": f"cat_item={params.catalog_item_id}^ORDERBYorder",
    }
    
    if params.limit:
        query_params["sysparm_limit"] = params.limit
    if params.offset:
        query_params["sysparm_offset"] = params.offset
    
    # Include all fields if detailed info is requested
    if params.include_details:
        query_params["sysparm_display_value"] = "true"
        query_params["sysparm_exclude_reference_link"] = "false"
    else:
        query_params["sysparm_fields"] = "sys_id,name,type,question_text,order,mandatory"

    api_url = f"{config.instance_url}/api/now/table/item_option_new"

    # Make request
    try:
        response = _make_request("GET", 
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", [])
        
        return ListCatalogItemVariablesResponse(
            success=True,
            message=f"Retrieved {len(result)} variables for catalog item",
            variables=result,
            count=len(result),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to list catalog item variables: {e}")
        return ListCatalogItemVariablesResponse(
            success=False,
            message=f"Failed to list catalog item variables: {_format_http_error(e)}",
        )


def update_catalog_item_variable(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: UpdateCatalogItemVariableParams,
) -> CatalogItemVariableResponse:
    """
    Update an existing variable (form field) for a catalog item.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for updating a catalog item variable.

    Returns:
        Response with information about the updated variable.
    """
    api_url = f"{config.instance_url}/api/now/table/item_option_new/{params.variable_id}"

    # Build request data with only parameters that are provided
    data = {}
    
    if params.label is not None:
        data["question_text"] = params.label
    if params.mandatory is not None:
        data["mandatory"] = str(params.mandatory).lower()  # ServiceNow expects "true"/"false" strings
    if params.help_text is not None:
        data["help_text"] = params.help_text
    if params.default_value is not None:
        data["default_value"] = params.default_value
    if params.description is not None:
        data["description"] = params.description
    if params.order is not None:
        data["order"] = params.order
    if params.reference_qualifier is not None:
        data["reference_qual"] = params.reference_qualifier
    if params.max_length is not None:
        data["max_length"] = params.max_length
    if params.min is not None:
        data["min"] = params.min
    if params.max is not None:
        data["max"] = params.max

    # If no fields to update, return early
    if not data:
        return CatalogItemVariableResponse(
            success=False,
            message="No update parameters provided",
        )

    # Make request
    try:
        response = _make_request("PATCH", 
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return CatalogItemVariableResponse(
            success=True,
            message="Catalog item variable updated successfully",
            variable_id=params.variable_id,
            details=result,
        )

    except requests.RequestException as e:
        logger.error(f"Failed to update catalog item variable: {e}")
        return CatalogItemVariableResponse(
            success=False,
            message=f"Failed to update catalog item variable: {_format_http_error(e)}",
        )


class CreateCatalogVariableChoiceParams(BaseModel):
    """Parameters for creating a choice option for a catalog item variable."""

    variable_id: str = Field(
        ...,
        description="The sys_id of the catalog item variable (item_option_new) to add the choice to",
    )
    text: str = Field(..., description="The display text shown to the user for this choice")
    value: str = Field(..., description="The internal value stored when this choice is selected")
    order: Optional[int] = Field(None, description="Display order of the choice (lower numbers appear first)")
    price: Optional[str] = Field(None, description="Optional price modifier for this choice (e.g., '10.00')")
    price_type: Optional[str] = Field(
        None,
        description="How the price is applied: 'flat_fee' adds a fixed amount, 'one_time' is a one-time charge",
    )
    inactive: bool = Field(False, description="Whether this choice is inactive/disabled")


class CatalogVariableChoiceResponse(BaseModel):
    """Response from catalog variable choice operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")
    choice_id: Optional[str] = Field(None, description="The sys_id of the created choice")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details about the choice")


def create_catalog_variable_choice(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateCatalogVariableChoiceParams,
) -> CatalogVariableChoiceResponse:
    """
    Create a choice option for a select-type catalog item variable.

    In ServiceNow, select/checkbox/radio variables get their dropdown options
    from the ``question_choice`` table.  Each choice record is linked to a
    variable via the ``question`` field (which holds the sys_id of the
    ``item_option_new`` record).

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for creating the variable choice.

    Returns:
        Response with information about the created choice.
    """
    api_url = f"{config.instance_url}/api/now/table/question_choice"

    data: Dict[str, Any] = {
        "question": params.variable_id,
        "text": params.text,
        "value": params.value,
        "inactive": str(params.inactive).lower(),
    }

    if params.order is not None:
        data["order"] = params.order
    if params.price is not None:
        data["price"] = params.price
    if params.price_type is not None:
        data["price_type"] = params.price_type

    try:
        response = _make_request("POST", 
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return CatalogVariableChoiceResponse(
            success=True,
            message="Catalog variable choice created successfully",
            choice_id=result.get("sys_id"),
            details=result,
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create catalog variable choice: {e}")
        return CatalogVariableChoiceResponse(
            success=False,
            message=f"Failed to create catalog variable choice: {_format_http_error(e)}",
        )


class CreateCatalogItemVariableSetParams(BaseModel):
    """Parameters for creating a catalog item variable set."""

    name: str = Field(..., description="Internal name for the variable set (no spaces)")
    title: str = Field(..., description="Display title shown to users on the request form")
    catalog_item_id: Optional[str] = Field(
        None,
        description="sys_id of the catalog item to link this set to immediately",
    )
    description: Optional[str] = Field(None, description="Description of the variable set")
    order: Optional[int] = Field(
        None,
        description="Display order relative to other variable sets on the catalog item",
    )
    global_set: bool = Field(
        False,
        description="True to create a reusable global set; False for an item-local set",
    )
    active: bool = Field(True, description="Whether the variable set is active")


class CatalogItemVariableSetResponse(BaseModel):
    """Response from catalog item variable set operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Message describing the result")
    variable_set_id: Optional[str] = Field(None, description="sys_id of the created variable set")
    link_id: Optional[str] = Field(
        None,
        description="sys_id of the io_set_item junction record if a catalog item was linked",
    )
    details: Optional[Dict[str, Any]] = Field(None, description="Full response from ServiceNow")


def create_catalog_item_variable_set(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateCatalogItemVariableSetParams,
) -> CatalogItemVariableSetResponse:
    """
    Create a variable set (section) for grouping catalog item variables.

    Variable sets live in the ``item_option_new_set`` table.  When
    ``catalog_item_id`` is provided the set is immediately linked to that item
    via an ``io_set_item`` junction record so variables added to the set appear
    on the request form.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for creating the variable set.

    Returns:
        Response with the sys_id of the new variable set and, when applicable,
        the sys_id of the ``io_set_item`` link record.
    """
    headers = auth_manager.get_headers()

    # Build variable-set payload
    set_data: Dict[str, Any] = {
        "name": params.name,
        "title": params.title,
        "type": "1" if params.global_set else "0",
        "active": str(params.active).lower(),
    }
    if params.description is not None:
        set_data["description"] = params.description

    try:
        set_response = _make_request(
            "POST",
            f"{config.instance_url}/api/now/table/item_option_new_set",
            json=set_data,
            headers=headers,
            timeout=config.timeout,
        )
        set_response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to create catalog item variable set: {e}")
        return CatalogItemVariableSetResponse(
            success=False,
            message=f"Failed to create catalog item variable set: {_format_http_error(e)}",
        )

    set_result = set_response.json().get("result", {})
    variable_set_id = set_result.get("sys_id")

    # Optionally link to a catalog item
    link_id: Optional[str] = None
    if params.catalog_item_id and variable_set_id:
        link_data: Dict[str, Any] = {
            "sc_cat_item": params.catalog_item_id,
            "variable_set": variable_set_id,
        }
        if params.order is not None:
            link_data["order"] = params.order

        try:
            link_response = _make_request(
                "POST",
                f"{config.instance_url}/api/now/table/io_set_item",
                json=link_data,
                headers=headers,
                timeout=config.timeout,
            )
            link_response.raise_for_status()
            link_id = link_response.json().get("result", {}).get("sys_id")
        except requests.RequestException as e:
            logger.error(f"Variable set created but failed to link to catalog item: {e}")
            return CatalogItemVariableSetResponse(
                success=False,
                message=(
                    f"Variable set {variable_set_id} created but failed to link to catalog item: "
                    f"{_format_http_error(e)}"
                ),
                variable_set_id=variable_set_id,
                details=set_result,
            )

    msg = "Catalog item variable set created successfully"
    if link_id:
        msg += " and linked to catalog item"

    return CatalogItemVariableSetResponse(
        success=True,
        message=msg,
        variable_set_id=variable_set_id,
        link_id=link_id,
        details=set_result,
    )


def delete_catalog_item_variable(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: DeleteCatalogItemVariableParams,
) -> CatalogItemVariableResponse:
    """
    Delete a variable (form field) from a catalog item.

    Args:
        config: Server configuration.
        auth_manager: Authentication manager.
        params: Parameters for deleting a catalog item variable.

    Returns:
        Response indicating whether the deletion was successful.
    """
    api_url = f"{config.instance_url}/api/now/table/item_option_new/{params.variable_id}"

    try:
        response = _make_request("DELETE", 
            api_url,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        return CatalogItemVariableResponse(
            success=True,
            message=f"Catalog item variable {params.variable_id} deleted successfully",
            variable_id=params.variable_id,
        )

    except requests.RequestException as e:
        logger.error(f"Failed to delete catalog item variable: {e}")
        return CatalogItemVariableResponse(
            success=False,
            message=f"Failed to delete catalog item variable: {_format_http_error(e)}",
        )