"""
Attachment management tools for the ServiceNow MCP server.

Provides tools for listing, retrieving, and deleting file attachments via
the /api/now/attachment endpoint.
"""

import logging
from typing import Any, Dict, Optional

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

ATTACHMENT_API = "/api/now/attachment"

ATTACHMENT_FIELDS = [
    "sys_id",
    "file_name",
    "content_type",
    "size_bytes",
    "size_compressed",
    "table_name",
    "table_sys_id",
    "sys_created_on",
    "sys_created_by",
    "sys_updated_on",
    "download_link",
]


class ListAttachmentsParams(BaseModel):
    """Parameters for listing attachments for a record."""

    table_name: str = Field(..., description="ServiceNow table name (e.g. 'incident', 'change_request')")
    table_sys_id: str = Field(..., description="sys_id of the record whose attachments to list")
    file_name: Optional[str] = Field(None, description="Filter by file name (substring match)")
    content_type: Optional[str] = Field(None, description="Filter by MIME type (e.g. 'application/pdf')")
    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")


class GetAttachmentParams(BaseModel):
    """Parameters for retrieving a single attachment's metadata."""

    sys_id: str = Field(..., description="sys_id of the attachment record")


class DeleteAttachmentParams(BaseModel):
    """Parameters for deleting an attachment."""

    sys_id: str = Field(..., description="sys_id of the attachment to delete")


def _format_attachment(record: Dict) -> Dict:
    """Extract relevant fields from a raw attachment API record."""
    return {
        "sys_id": record.get("sys_id"),
        "file_name": record.get("file_name"),
        "content_type": record.get("content_type"),
        "size_bytes": record.get("size_bytes"),
        "size_compressed": record.get("size_compressed"),
        "table_name": record.get("table_name"),
        "table_sys_id": record.get("table_sys_id"),
        "created_on": record.get("sys_created_on"),
        "created_by": record.get("sys_created_by"),
        "updated_on": record.get("sys_updated_on"),
        "download_link": record.get("download_link"),
    }


def list_attachments(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List file attachments for a specific ServiceNow record.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListAttachmentsParams.

    Returns:
        Dictionary with ``success``, ``attachments`` (list), ``count``, and
        pagination keys.
    """
    result = _unwrap_and_validate_params(
        params, ListAttachmentsParams, required_fields=["table_name", "table_sys_id"]
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

    query_parts = [
        f"table_name={validated.table_name}",
        f"table_sys_id={validated.table_sys_id}",
    ]
    if validated.file_name:
        query_parts.append(f"file_nameLIKE{validated.file_name}")
    if validated.content_type:
        query_parts.append(f"content_type={validated.content_type}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        fields=",".join(ATTACHMENT_FIELDS),
    )

    url = f"{instance_url}{ATTACHMENT_API}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        attachments = [_format_attachment(r) for r in response.json().get("result", [])]
        return _paginated_list_response(attachments, validated.limit, validated.offset, "attachments")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing attachments: {e}")
        return {"success": False, "message": f"Error listing attachments: {_format_http_error(e)}"}


def get_attachment(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve metadata for a single attachment by sys_id.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetAttachmentParams.

    Returns:
        Dictionary with ``success`` and ``attachment`` keys.
    """
    result = _unwrap_and_validate_params(params, GetAttachmentParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}{ATTACHMENT_API}/{validated.sys_id}"
    try:
        response = _make_request("GET", url, headers=headers)
        if response.status_code == 404:
            return {"success": False, "message": f"Attachment not found: {validated.sys_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Attachment not found: {validated.sys_id}"}
        return {"success": True, "attachment": _format_attachment(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving attachment: {e}")
        return {"success": False, "message": f"Error retrieving attachment: {_format_http_error(e)}"}


def delete_attachment(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Permanently delete a file attachment from ServiceNow.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeleteAttachmentParams.

    Returns:
        Dictionary with ``success`` and ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, DeleteAttachmentParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}{ATTACHMENT_API}/{validated.sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {"success": False, "message": f"Attachment not found: {validated.sys_id}"}
        if response.status_code == 204:
            return {"success": True, "message": f"Attachment {validated.sys_id} deleted successfully"}
        response.raise_for_status()
        return {"success": True, "message": f"Attachment {validated.sys_id} deleted successfully"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting attachment: {e}")
        return {"success": False, "message": f"Error deleting attachment: {_format_http_error(e)}"}
