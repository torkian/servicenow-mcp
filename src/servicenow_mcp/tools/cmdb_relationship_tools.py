"""
CMDB relationship tools for the ServiceNow MCP server.

Provides tools for managing relationships between Configuration Items (CIs)
via the cmdb_rel_ci junction table and querying relationship types from
cmdb_rel_type.
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

CMDB_REL_CI_TABLE = "cmdb_rel_ci"
CMDB_REL_TYPE_TABLE = "cmdb_rel_type"

_REL_CI_FIELDS = [
    "sys_id",
    "parent",
    "child",
    "type",
    "sys_created_on",
    "sys_updated_on",
]

_REL_TYPE_FIELDS = [
    "sys_id",
    "name",
    "parent_descriptor",
    "child_descriptor",
]


# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------


class ListCIRelationshipsParams(BaseModel):
    """Parameters for listing CI relationships."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    parent_ci: Optional[str] = Field(
        None, description="sys_id of the parent CI to filter relationships by"
    )
    child_ci: Optional[str] = Field(
        None, description="sys_id of the child CI to filter relationships by"
    )
    relationship_type: Optional[str] = Field(
        None,
        description=(
            "sys_id of the cmdb_rel_type record to filter by (e.g. only 'Depends on' links)"
        ),
    )
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetCIRelationshipParams(BaseModel):
    """Parameters for retrieving a single CI relationship."""

    sys_id: str = Field(..., description="sys_id of the cmdb_rel_ci record to retrieve")


class CreateCIRelationshipParams(BaseModel):
    """Parameters for creating a new CI relationship."""

    parent_ci: str = Field(..., description="sys_id of the parent configuration item")
    child_ci: str = Field(..., description="sys_id of the child configuration item")
    relationship_type: str = Field(
        ...,
        description="sys_id of the cmdb_rel_type record that defines the relationship kind",
    )


class DeleteCIRelationshipParams(BaseModel):
    """Parameters for deleting a CI relationship."""

    sys_id: str = Field(..., description="sys_id of the cmdb_rel_ci record to delete")


class ListCIRelationshipTypesParams(BaseModel):
    """Parameters for listing CI relationship types."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    name: Optional[str] = Field(
        None, description="Filter by relationship type name (substring match)"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_relationship(record: Dict) -> Dict:
    """Normalise a raw cmdb_rel_ci record into a clean dict."""

    def _ref(val) -> str:
        if isinstance(val, dict):
            return val.get("value") or val.get("display_value") or str(val)
        return val or ""

    return {
        "sys_id": record.get("sys_id"),
        "parent": _ref(record.get("parent")),
        "child": _ref(record.get("child")),
        "type": _ref(record.get("type")),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def _format_rel_type(record: Dict) -> Dict:
    """Normalise a raw cmdb_rel_type record into a clean dict."""
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "parent_descriptor": record.get("parent_descriptor"),
        "child_descriptor": record.get("child_descriptor"),
    }


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def list_ci_relationships(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List CI relationships from the cmdb_rel_ci table.

    Returns:
        Dictionary with ``success``, ``relationships`` (list), ``count``,
        and pagination keys.
    """
    result = _unwrap_and_validate_params(params, ListCIRelationshipsParams)
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
    if validated.parent_ci:
        query_parts.append(f"parent={validated.parent_ci}")
    if validated.child_ci:
        query_parts.append(f"child={validated.child_ci}")
    if validated.relationship_type:
        query_parts.append(f"type={validated.relationship_type}")
    if validated.query:
        query_parts.append(validated.query)

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        fields=",".join(_REL_CI_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{CMDB_REL_CI_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        rels = [_format_relationship(r) for r in response.json().get("result", [])]
        return _paginated_list_response(rels, validated.limit, validated.offset, "relationships")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing CI relationships: {e}")
        return {
            "success": False,
            "message": f"Error listing CI relationships: {_format_http_error(e)}",
        }


def get_ci_relationship(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single CI relationship by its sys_id.

    Returns:
        Dictionary with ``success`` and ``relationship`` keys.
    """
    result = _unwrap_and_validate_params(params, GetCIRelationshipParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}/api/now/table/{CMDB_REL_CI_TABLE}/{validated.sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(_REL_CI_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {
                "success": False,
                "message": f"CI relationship not found: {validated.sys_id}",
            }
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {
                "success": False,
                "message": f"CI relationship not found: {validated.sys_id}",
            }
        return {"success": True, "relationship": _format_relationship(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving CI relationship: {e}")
        return {
            "success": False,
            "message": f"Error retrieving CI relationship: {_format_http_error(e)}",
        }


def create_ci_relationship(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new relationship between two CIs.

    Returns:
        Dictionary with ``success``, ``sys_id``, and ``relationship`` keys.
    """
    result = _unwrap_and_validate_params(
        params,
        CreateCIRelationshipParams,
        required_fields=["parent_ci", "child_ci", "relationship_type"],
    )
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    body = {
        "parent": validated.parent_ci,
        "child": validated.child_ci,
        "type": validated.relationship_type,
    }

    url = f"{instance_url}/api/now/table/{CMDB_REL_CI_TABLE}"
    try:
        response = _make_request("POST", url, headers=headers, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "sys_id": record.get("sys_id"),
            "relationship": _format_relationship(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating CI relationship: {e}")
        return {
            "success": False,
            "message": f"Error creating CI relationship: {_format_http_error(e)}",
        }


def delete_ci_relationship(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete a CI relationship record.

    Returns:
        Dictionary with ``success`` and ``message`` keys.
    """
    result = _unwrap_and_validate_params(
        params, DeleteCIRelationshipParams, required_fields=["sys_id"]
    )
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}/api/now/table/{CMDB_REL_CI_TABLE}/{validated.sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {
                "success": False,
                "message": f"CI relationship not found: {validated.sys_id}",
            }
        if response.status_code == 204:
            return {
                "success": True,
                "message": f"CI relationship {validated.sys_id} deleted successfully",
            }
        response.raise_for_status()
        return {
            "success": True,
            "message": f"CI relationship {validated.sys_id} deleted successfully",
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting CI relationship: {e}")
        return {
            "success": False,
            "message": f"Error deleting CI relationship: {_format_http_error(e)}",
        }


def list_ci_relationship_types(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List available CI relationship types from the cmdb_rel_type table.

    Returns:
        Dictionary with ``success``, ``relationship_types`` (list), ``count``,
        and pagination keys.
    """
    result = _unwrap_and_validate_params(params, ListCIRelationshipTypesParams)
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

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        fields=",".join(_REL_TYPE_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{CMDB_REL_TYPE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        types = [_format_rel_type(r) for r in response.json().get("result", [])]
        return _paginated_list_response(
            types, validated.limit, validated.offset, "relationship_types"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing CI relationship types: {e}")
        return {
            "success": False,
            "message": f"Error listing CI relationship types: {_format_http_error(e)}",
        }
