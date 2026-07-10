"""
CMDB relationship tools for the ServiceNow MCP server.

Provides tools for managing relationships between Configuration Items (CIs)
via the cmdb_rel_ci junction table and querying relationship types from
cmdb_rel_type.
"""

import logging
from typing import Any, Dict, List, Literal, Optional, Set

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


class ListCIDependenciesParams(BaseModel):
    """Parameters for listing CI dependencies as a directional graph."""

    ci_sys_id: str = Field(..., description="sys_id of the CI whose dependencies to fetch")
    direction: Literal["upstream", "downstream", "both"] = Field(
        "both",
        description=(
            "'upstream': CIs that this CI depends on (parent=ci_sys_id); "
            "'downstream': CIs that depend on this CI (child=ci_sys_id); "
            "'both': include both directions (default)"
        ),
    )
    depth: int = Field(
        1,
        ge=1,
        le=3,
        description="Traversal depth (1=immediate neighbours, max 3). Default 1.",
    )
    relationship_type: Optional[str] = Field(
        None, description="sys_id of cmdb_rel_type to restrict which relationship kinds to follow"
    )
    limit: Optional[int] = Field(
        50,
        description="Max edges to return per direction per depth level (default 50)",
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


# ---------------------------------------------------------------------------
# CI dependency graph
# ---------------------------------------------------------------------------


def _fetch_rel_ci_edges(
    url_base: str,
    headers: Dict,
    ci_sys_ids: Set[str],
    direction: str,
    relationship_type: Optional[str],
    limit: int,
) -> List[Dict]:
    """Fetch cmdb_rel_ci edges for a set of CI sys_ids in one or two queries."""
    all_edges: List[Dict] = []
    id_list = ",".join(ci_sys_ids)
    directions = []
    if direction in ("upstream", "both"):
        directions.append("upstream")
    if direction in ("downstream", "both"):
        directions.append("downstream")

    for d in directions:
        if d == "upstream":
            query = f"parentIN{id_list}"
        else:
            query = f"childIN{id_list}"
        if relationship_type:
            query += f"^type={relationship_type}"

        query_params: Dict[str, Any] = {
            "sysparm_query": query,
            "sysparm_limit": str(limit),
            "sysparm_display_value": "all",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": ",".join(_REL_CI_FIELDS),
        }
        try:
            response = _make_request(
                "GET", f"{url_base}/api/now/table/{CMDB_REL_CI_TABLE}",
                headers=headers, params=query_params
            )
            response.raise_for_status()
            for rec in response.json().get("result", []):
                rec["_direction"] = d
                all_edges.append(rec)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching {d} edges for {ci_sys_ids}: {e}")

    return all_edges


def _extract_node(rec: Dict, ci_sys_id: str, d: str) -> Optional[Dict]:
    """Extract the neighbour CI node from an edge record."""

    def _ref_val(field):
        v = rec.get(field, {})
        if isinstance(v, dict):
            return v.get("value", ""), v.get("display_value", "")
        return v or "", ""

    parent_id, parent_name = _ref_val("parent")
    child_id, child_name = _ref_val("child")

    if d == "upstream":
        neighbour_id, neighbour_name = child_id, child_name
    else:
        neighbour_id, neighbour_name = parent_id, parent_name

    if not neighbour_id or neighbour_id == ci_sys_id:
        return None

    return {"sys_id": neighbour_id, "name": neighbour_name, "direction": d}


def _build_edge(rec: Dict, d: str) -> Dict:
    """Build a clean edge dict from a raw cmdb_rel_ci record."""

    def _ref_val(field):
        v = rec.get(field, {})
        if isinstance(v, dict):
            return v.get("value", ""), v.get("display_value", "")
        return v or "", ""

    parent_id, parent_name = _ref_val("parent")
    child_id, child_name = _ref_val("child")
    type_id, type_name = _ref_val("type")

    return {
        "sys_id": rec.get("sys_id"),
        "parent_sys_id": parent_id,
        "parent_name": parent_name,
        "child_sys_id": child_id,
        "child_name": child_name,
        "type_sys_id": type_id,
        "type_name": type_name,
        "direction": d,
    }


def list_ci_dependencies(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Return the dependency graph for a CI up to the requested traversal depth.

    Each level of depth follows the edges returned by the previous level,
    performing BFS across ``cmdb_rel_ci``.  The response contains deduplicated
    ``nodes`` (neighbour CIs) and ``edges`` (relationship records) in a
    format suitable for graph rendering.

    Returns:
        Dictionary with ``success``, ``ci_sys_id``, ``direction``, ``depth``,
        ``nodes``, ``edges``, and ``count`` (total edge count).
    """
    result = _unwrap_and_validate_params(
        params, ListCIDependenciesParams, required_fields=["ci_sys_id"]
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

    limit = validated.limit or 50

    seen_edge_ids: Set[str] = set()
    seen_node_ids: Set[str] = {validated.ci_sys_id}
    all_edges: List[Dict] = []
    all_nodes: List[Dict] = []

    frontier: Set[str] = {validated.ci_sys_id}

    for _level in range(validated.depth):
        if not frontier:
            break
        raw_edges = _fetch_rel_ci_edges(
            instance_url,
            headers,
            frontier,
            validated.direction,
            validated.relationship_type,
            limit,
        )
        new_frontier: Set[str] = set()
        for rec in raw_edges:
            edge_id = rec.get("sys_id", "")
            if edge_id in seen_edge_ids:
                continue
            seen_edge_ids.add(edge_id)
            d = rec.get("_direction", "upstream")
            all_edges.append(_build_edge(rec, d))
            node = _extract_node(rec, validated.ci_sys_id, d)
            if node and node["sys_id"] not in seen_node_ids:
                seen_node_ids.add(node["sys_id"])
                all_nodes.append(node)
                new_frontier.add(node["sys_id"])
        frontier = new_frontier

    return {
        "success": True,
        "ci_sys_id": validated.ci_sys_id,
        "direction": validated.direction,
        "depth": validated.depth,
        "nodes": all_nodes,
        "edges": all_edges,
        "count": len(all_edges),
    }
