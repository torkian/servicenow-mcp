"""
Data source tools for the ServiceNow MCP server.

Provides tools for managing sys_data_source records (import set data sources)
and for triggering data source loads.
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

DATA_SOURCE_TABLE = "sys_data_source"

DATA_SOURCE_FIELDS = [
    "sys_id",
    "name",
    "import_set_table_name",
    "format",
    "file_retrieval_method",
    "source",
    "header_row",
    "comma_separated",
    "csv_separator",
    "active",
    "last_import_set",
    "last_run",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
    "sys_updated_by",
]


def _format_data_source(record: Dict) -> Dict:
    """Normalise a raw sys_data_source record."""
    active = record.get("active")
    if isinstance(active, str):
        active = active.lower() == "true"
    header_row = record.get("header_row")
    if isinstance(header_row, str):
        header_row = header_row.lower() == "true"
    comma_separated = record.get("comma_separated")
    if isinstance(comma_separated, str):
        comma_separated = comma_separated.lower() == "true"
    last_import = record.get("last_import_set")
    if isinstance(last_import, dict):
        last_import = last_import.get("display_value") or last_import.get("value")
    return {
        "sys_id": record.get("sys_id"),
        "name": record.get("name"),
        "import_set_table_name": record.get("import_set_table_name"),
        "format": record.get("format"),
        "file_retrieval_method": record.get("file_retrieval_method"),
        "source": record.get("source"),
        "header_row": header_row,
        "comma_separated": comma_separated,
        "csv_separator": record.get("csv_separator"),
        "active": active,
        "last_import_set": last_import,
        "last_run": record.get("last_run"),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
        "created_by": record.get("sys_created_by"),
        "updated_by": record.get("sys_updated_by"),
    }


def _resolve_data_source_sys_id(
    source_id: str,
    instance_url: str,
    headers: Dict,
) -> Optional[str]:
    """Return the sys_id for a data source given a sys_id or exact name."""
    if len(source_id) == 32 and all(c in "0123456789abcdef" for c in source_id.lower()):
        return source_id
    url = f"{instance_url}/api/now/table/{DATA_SOURCE_TABLE}"
    params: Dict[str, Any] = {
        "sysparm_query": f"name={source_id}",
        "sysparm_limit": "1",
        "sysparm_fields": "sys_id",
        "sysparm_exclude_reference_link": "true",
    }
    try:
        resp = _make_request("GET", url, headers=headers, params=params)
        resp.raise_for_status()
        results = resp.json().get("result", [])
        return results[0]["sys_id"] if results else None
    except requests.exceptions.RequestException:
        return None


class ListDataSourcesParams(BaseModel):
    """Parameters for listing sys_data_source records."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    name: Optional[str] = Field(None, description="Filter by name pattern (LIKE match)")
    format: Optional[str] = Field(None, description="Filter by format (e.g. csv, xml, json, jdbc)")
    file_retrieval_method: Optional[str] = Field(
        None, description="Filter by retrieval method (e.g. http, ftp, attachment)"
    )
    active: Optional[bool] = Field(None, description="Filter by active state")


class GetDataSourceParams(BaseModel):
    """Parameters for retrieving a single data source."""

    source_id: str = Field(
        ...,
        description="sys_id (32-char hex) or exact name of the data source",
    )


class CreateDataSourceParams(BaseModel):
    """Parameters for creating a new sys_data_source."""

    name: str = Field(..., description="Human-readable name for the data source")
    import_set_table_name: str = Field(
        ...,
        description="Name of the import set staging table to load data into (e.g. 'u_import_users')",
    )
    format: Optional[str] = Field(
        "csv",
        description="Data format: csv, xml, json, jdbc, excel (default: csv)",
    )
    file_retrieval_method: Optional[str] = Field(
        None,
        description="How to retrieve the file: http, ftp, attachment, scheduled",
    )
    source: Optional[str] = Field(None, description="URL or other source path for the file")
    header_row: Optional[bool] = Field(True, description="Whether the first row is a header row (default true)")
    comma_separated: Optional[bool] = Field(
        True, description="Whether fields are comma-separated for CSV (default true)"
    )
    csv_separator: Optional[str] = Field(None, description="Custom field separator character (overrides comma_separated)")
    active: Optional[bool] = Field(True, description="Whether the data source is active (default true)")


class UpdateDataSourceParams(BaseModel):
    """Parameters for updating an existing sys_data_source."""

    source_id: str = Field(..., description="sys_id (32-char hex) or exact name of the data source to update")
    name: Optional[str] = Field(None, description="New name for the data source")
    import_set_table_name: Optional[str] = Field(None, description="New staging table name")
    format: Optional[str] = Field(None, description="New data format")
    file_retrieval_method: Optional[str] = Field(None, description="New retrieval method")
    source: Optional[str] = Field(None, description="New source URL or path")
    header_row: Optional[bool] = Field(None, description="Toggle header row flag")
    comma_separated: Optional[bool] = Field(None, description="Toggle comma-separated flag")
    csv_separator: Optional[str] = Field(None, description="New field separator character")
    active: Optional[bool] = Field(None, description="Enable or disable the data source")


class DeleteDataSourceParams(BaseModel):
    """Parameters for deleting a sys_data_source."""

    source_id: str = Field(..., description="sys_id (32-char hex) or exact name of the data source to delete")


class LoadDataSourceParams(BaseModel):
    """Parameters for triggering a data source load."""

    source_id: str = Field(
        ...,
        description="sys_id (32-char hex) or exact name of the data source to load",
    )


def list_data_sources(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List data source definitions from the sys_data_source table.

    Supports filtering by name, format, retrieval method, and active state.
    Results are ordered by name ascending.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListDataSourcesParams.

    Returns:
        Dictionary with ``success``, ``data_sources`` (list), ``count``,
        and optional ``has_more``/``next_offset`` keys.
    """
    result = _unwrap_and_validate_params(params, ListDataSourcesParams)
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    query_parts = []
    if validated.name:
        query_parts.append(f"nameLIKE{validated.name}")
    if validated.format:
        query_parts.append(f"format={validated.format}")
    if validated.file_retrieval_method:
        query_parts.append(f"file_retrieval_method={validated.file_retrieval_method}")
    if validated.active is not None:
        query_parts.append(f"active={'true' if validated.active else 'false'}")

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        order_by="name",
        fields=",".join(DATA_SOURCE_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{DATA_SOURCE_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        sources = [_format_data_source(r) for r in response.json().get("result", [])]
        return _paginated_list_response(sources, validated.limit, validated.offset, "data_sources")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing data sources: {e}")
        return {"success": False, "message": f"Error listing data sources: {_format_http_error(e)}"}


def get_data_source(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single sys_data_source record by sys_id or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetDataSourceParams.

    Returns:
        Dictionary with ``success`` and ``data_source`` keys.
    """
    result = _unwrap_and_validate_params(params, GetDataSourceParams, required_fields=["source_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_data_source_sys_id(validated.source_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Data source not found: {validated.source_id}"}

    url = f"{instance_url}/api/now/table/{DATA_SOURCE_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(DATA_SOURCE_FIELDS),
    }
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        if response.status_code == 404:
            return {"success": False, "message": f"Data source not found: {validated.source_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        if not record:
            return {"success": False, "message": f"Data source not found: {validated.source_id}"}
        return {"success": True, "data_source": _format_data_source(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving data source: {e}")
        return {"success": False, "message": f"Error retrieving data source: {_format_http_error(e)}"}


def create_data_source(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new data source in the sys_data_source table.

    A data source defines the origin and format of data to load into an import
    set staging table for subsequent transformation via transform maps.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateDataSourceParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``data_source`` keys.
    """
    result = _unwrap_and_validate_params(
        params, CreateDataSourceParams, required_fields=["name", "import_set_table_name"]
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

    body: Dict[str, Any] = {
        "name": validated.name,
        "import_set_table_name": validated.import_set_table_name,
        "active": "true" if validated.active else "false",
    }
    if validated.format is not None:
        body["format"] = validated.format
    if validated.file_retrieval_method is not None:
        body["file_retrieval_method"] = validated.file_retrieval_method
    if validated.source is not None:
        body["source"] = validated.source
    if validated.header_row is not None:
        body["header_row"] = "true" if validated.header_row else "false"
    if validated.comma_separated is not None:
        body["comma_separated"] = "true" if validated.comma_separated else "false"
    if validated.csv_separator is not None:
        body["csv_separator"] = validated.csv_separator

    url = f"{instance_url}/api/now/table/{DATA_SOURCE_TABLE}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(DATA_SOURCE_FIELDS),
    }
    try:
        response = _make_request("POST", url, headers=headers, params=query_params, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Data source '{validated.name}' created successfully",
            "data_source": _format_data_source(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating data source: {e}")
        return {"success": False, "message": f"Error creating data source: {_format_http_error(e)}"}


def update_data_source(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing data source (PATCH).

    Only the fields supplied are changed; omitted optional fields are left as-is.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdateDataSourceParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``data_source`` keys.
    """
    result = _unwrap_and_validate_params(params, UpdateDataSourceParams, required_fields=["source_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_data_source_sys_id(validated.source_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Data source not found: {validated.source_id}"}

    body: Dict[str, Any] = {}
    if validated.name is not None:
        body["name"] = validated.name
    if validated.import_set_table_name is not None:
        body["import_set_table_name"] = validated.import_set_table_name
    if validated.format is not None:
        body["format"] = validated.format
    if validated.file_retrieval_method is not None:
        body["file_retrieval_method"] = validated.file_retrieval_method
    if validated.source is not None:
        body["source"] = validated.source
    if validated.header_row is not None:
        body["header_row"] = "true" if validated.header_row else "false"
    if validated.comma_separated is not None:
        body["comma_separated"] = "true" if validated.comma_separated else "false"
    if validated.csv_separator is not None:
        body["csv_separator"] = validated.csv_separator
    if validated.active is not None:
        body["active"] = "true" if validated.active else "false"

    if not body:
        return {"success": False, "message": "No fields provided to update"}

    url = f"{instance_url}/api/now/table/{DATA_SOURCE_TABLE}/{sys_id}"
    query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(DATA_SOURCE_FIELDS),
    }
    try:
        response = _make_request("PATCH", url, headers=headers, params=query_params, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"Data source not found: {validated.source_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "message": f"Data source '{validated.source_id}' updated successfully",
            "data_source": _format_data_source(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating data source: {e}")
        return {"success": False, "message": f"Error updating data source: {_format_http_error(e)}"}


def delete_data_source(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Delete a data source by sys_id or exact name.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeleteDataSourceParams.

    Returns:
        Dictionary with ``success`` and ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, DeleteDataSourceParams, required_fields=["source_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_data_source_sys_id(validated.source_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Data source not found: {validated.source_id}"}

    url = f"{instance_url}/api/now/table/{DATA_SOURCE_TABLE}/{sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {"success": False, "message": f"Data source not found: {validated.source_id}"}
        if response.status_code in (200, 204):
            return {"success": True, "message": f"Data source '{validated.source_id}' deleted successfully"}
        response.raise_for_status()
        return {"success": True, "message": f"Data source '{validated.source_id}' deleted successfully"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting data source: {e}")
        return {"success": False, "message": f"Error deleting data source: {_format_http_error(e)}"}


def load_data_source(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Trigger a data source load to populate its import set staging table.

    POSTs to the Import Set Run API to execute the data source and load new
    records into the staging table for subsequent transform processing.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching LoadDataSourceParams.

    Returns:
        Dictionary with ``success``, ``message``, and ``import_set`` keys.
    """
    result = _unwrap_and_validate_params(params, LoadDataSourceParams, required_fields=["source_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    sys_id = _resolve_data_source_sys_id(validated.source_id, instance_url, headers)
    if not sys_id:
        return {"success": False, "message": f"Data source not found: {validated.source_id}"}

    url = f"{instance_url}/api/now/table/sys_import_set_run"
    body = {"data_source": sys_id}
    try:
        response = _make_request("POST", url, headers=headers, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        import_set_id = record.get("import_set")
        if isinstance(import_set_id, dict):
            import_set_id = import_set_id.get("display_value") or import_set_id.get("value")
        return {
            "success": True,
            "message": f"Data source '{validated.source_id}' load triggered successfully",
            "import_set": {
                "sys_id": record.get("sys_id"),
                "import_set": import_set_id,
                "state": record.get("state"),
                "data_source": record.get("data_source"),
            },
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error loading data source: {e}")
        return {"success": False, "message": f"Error loading data source: {_format_http_error(e)}"}
