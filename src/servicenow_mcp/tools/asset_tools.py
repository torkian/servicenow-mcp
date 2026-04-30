"""
Asset management tools for the ServiceNow MCP server.

Provides tools for managing hardware and software assets via the alm_asset table.
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

ASSET_TABLE = "alm_asset"
HARDWARE_TABLE = "alm_hardware"

ASSET_FIELDS = [
    "sys_id",
    "asset_tag",
    "display_name",
    "serial_number",
    "model",
    "model_category",
    "assigned_to",
    "assigned",
    "install_status",
    "substatus",
    "cost",
    "cost_currency",
    "purchase_date",
    "warranty_expiration",
    "lease_id",
    "vendor",
    "acquisition_method",
    "owned_by",
    "managed_by",
    "location",
    "company",
    "department",
    "sys_created_on",
    "sys_updated_on",
]

HARDWARE_EXTRA_FIELDS = [
    "cpu_count",
    "cpu_core_count",
    "cpu_manufacturer",
    "cpu_name",
    "cpu_speed",
    "disk_space",
    "ram",
    "os",
    "os_version",
    "os_service_pack",
    "os_domain",
    "mac_address",
    "ip_address",
]

# install_status values for the alm_asset table
INSTALL_STATUS_VALUES = (
    "1=In use, 2=On order, 3=In maintenance, 4=In stock, 5=Retired, "
    "6=Consumed, 7=In transit, 8=Missing, 9=Stolen"
)


class ListAssetsParams(BaseModel):
    """Parameters for listing assets."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    asset_tag: Optional[str] = Field(None, description="Filter by asset tag (exact match)")
    display_name: Optional[str] = Field(None, description="Filter by display name (substring match)")
    install_status: Optional[str] = Field(
        None, description=f"Filter by install status: {INSTALL_STATUS_VALUES}"
    )
    assigned_to: Optional[str] = Field(
        None, description="Filter by assigned user sys_id or user name (substring match)"
    )
    model_category: Optional[str] = Field(
        None, description="Filter by model category sys_id or name (substring match)"
    )
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetAssetParams(BaseModel):
    """Parameters for retrieving a single asset."""

    sys_id: Optional[str] = Field(None, description="sys_id of the asset to retrieve")
    asset_tag: Optional[str] = Field(None, description="Asset tag of the asset to retrieve")


class UpdateAssetParams(BaseModel):
    """Parameters for updating an existing asset."""

    sys_id: str = Field(..., description="sys_id of the asset to update")
    display_name: Optional[str] = Field(None, description="Updated display name")
    asset_tag: Optional[str] = Field(None, description="Updated asset tag")
    serial_number: Optional[str] = Field(None, description="Updated serial number")
    install_status: Optional[str] = Field(
        None, description=f"Updated install status: {INSTALL_STATUS_VALUES}"
    )
    substatus: Optional[str] = Field(None, description="Updated substatus")
    cost: Optional[str] = Field(None, description="Updated cost value")
    cost_currency: Optional[str] = Field(None, description="Updated currency code (e.g. USD)")
    purchase_date: Optional[str] = Field(None, description="Updated purchase date (YYYY-MM-DD)")
    warranty_expiration: Optional[str] = Field(
        None, description="Updated warranty expiration date (YYYY-MM-DD)"
    )
    lease_id: Optional[str] = Field(None, description="Updated lease identifier")
    vendor: Optional[str] = Field(None, description="Updated vendor sys_id")
    acquisition_method: Optional[str] = Field(
        None, description="Updated acquisition method (purchase, lease, rental)"
    )
    assigned_to: Optional[str] = Field(None, description="Updated assigned user sys_id")
    owned_by: Optional[str] = Field(None, description="Updated owned_by user sys_id")
    managed_by: Optional[str] = Field(None, description="Updated managed_by user sys_id")
    location: Optional[str] = Field(None, description="Updated location sys_id")
    company: Optional[str] = Field(None, description="Updated company sys_id")
    department: Optional[str] = Field(None, description="Updated department sys_id")


class CreateAssetParams(BaseModel):
    """Parameters for creating a new asset record."""

    display_name: str = Field(..., description="Display name for the asset")
    asset_class: Optional[str] = Field(
        None,
        description=(
            "Asset table to create the record in. Use 'alm_hardware' for hardware assets "
            "with CPU/RAM/OS fields. Defaults to alm_asset."
        ),
    )
    asset_tag: Optional[str] = Field(None, description="Unique asset tag identifier")
    serial_number: Optional[str] = Field(None, description="Serial number of the asset")
    model: Optional[str] = Field(None, description="sys_id of the product model record")
    model_category: Optional[str] = Field(None, description="sys_id of the model category record")
    install_status: Optional[str] = Field(
        None, description=f"Install status: {INSTALL_STATUS_VALUES}"
    )
    substatus: Optional[str] = Field(None, description="Substatus value")
    cost: Optional[str] = Field(None, description="Cost value (numeric string)")
    cost_currency: Optional[str] = Field(None, description="Currency code (e.g. USD)")
    purchase_date: Optional[str] = Field(None, description="Purchase date (YYYY-MM-DD)")
    warranty_expiration: Optional[str] = Field(
        None, description="Warranty expiration date (YYYY-MM-DD)"
    )
    lease_id: Optional[str] = Field(None, description="Lease identifier")
    vendor: Optional[str] = Field(None, description="sys_id of the vendor record")
    acquisition_method: Optional[str] = Field(
        None, description="Acquisition method (purchase, lease, rental)"
    )
    assigned_to: Optional[str] = Field(None, description="sys_id of the user to assign to")
    owned_by: Optional[str] = Field(None, description="sys_id of the owning user")
    managed_by: Optional[str] = Field(None, description="sys_id of the managing user")
    location: Optional[str] = Field(None, description="sys_id of the location record")
    company: Optional[str] = Field(None, description="sys_id of the company record")
    department: Optional[str] = Field(None, description="sys_id of the department record")
    # alm_hardware subclass fields
    cpu_count: Optional[int] = Field(None, description="Number of CPUs (alm_hardware only)")
    cpu_core_count: Optional[int] = Field(
        None, description="Number of CPU cores (alm_hardware only)"
    )
    cpu_manufacturer: Optional[str] = Field(
        None, description="CPU manufacturer name (alm_hardware only)"
    )
    cpu_name: Optional[str] = Field(None, description="CPU model name (alm_hardware only)")
    cpu_speed: Optional[int] = Field(None, description="CPU speed in MHz (alm_hardware only)")
    disk_space: Optional[int] = Field(None, description="Total disk space in GB (alm_hardware only)")
    ram: Optional[int] = Field(None, description="RAM in MB (alm_hardware only)")
    os: Optional[str] = Field(None, description="Operating system name (alm_hardware only)")
    os_version: Optional[str] = Field(None, description="OS version string (alm_hardware only)")
    os_service_pack: Optional[str] = Field(
        None, description="OS service pack (alm_hardware only)"
    )
    os_domain: Optional[str] = Field(None, description="OS domain (alm_hardware only)")
    mac_address: Optional[str] = Field(None, description="MAC address (alm_hardware only)")
    ip_address: Optional[str] = Field(None, description="IP address (alm_hardware only)")


def _format_asset(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw alm_asset or alm_hardware record."""

    def _ref(value: Any) -> Any:
        if isinstance(value, dict):
            return value.get("display_value") or value.get("value")
        return value

    result = {
        "sys_id": record.get("sys_id"),
        "asset_tag": record.get("asset_tag"),
        "display_name": record.get("display_name"),
        "serial_number": record.get("serial_number"),
        "model": _ref(record.get("model")),
        "model_category": _ref(record.get("model_category")),
        "assigned_to": _ref(record.get("assigned_to")),
        "assigned": record.get("assigned"),
        "install_status": record.get("install_status"),
        "substatus": record.get("substatus"),
        "cost": record.get("cost"),
        "cost_currency": record.get("cost_currency"),
        "purchase_date": record.get("purchase_date"),
        "warranty_expiration": record.get("warranty_expiration"),
        "lease_id": record.get("lease_id"),
        "vendor": _ref(record.get("vendor")),
        "acquisition_method": record.get("acquisition_method"),
        "owned_by": _ref(record.get("owned_by")),
        "managed_by": _ref(record.get("managed_by")),
        "location": _ref(record.get("location")),
        "company": _ref(record.get("company")),
        "department": _ref(record.get("department")),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }
    # Include hardware-specific fields when present in the record
    for field in HARDWARE_EXTRA_FIELDS:
        if field in record:
            result[field] = record[field]
    return result


def _build_update_body(validated: UpdateAssetParams) -> Dict:
    """Build a PATCH body from non-None update fields."""
    fields: List[str] = [
        "display_name", "asset_tag", "serial_number", "install_status",
        "substatus", "cost", "cost_currency", "purchase_date", "warranty_expiration",
        "lease_id", "vendor", "acquisition_method", "assigned_to",
        "owned_by", "managed_by", "location", "company", "department",
    ]
    return {f: getattr(validated, f) for f in fields if getattr(validated, f) is not None}


def _build_create_body(validated: "CreateAssetParams") -> Dict:
    """Build a POST body for asset creation, excluding asset_class routing field."""
    skip = {"asset_class"}
    body = {}
    for field in CreateAssetParams.model_fields:
        if field in skip:
            continue
        value = getattr(validated, field)
        if value is not None:
            body[field] = value
    return body


class DeleteAssetParams(BaseModel):
    """Parameters for deleting an asset record."""

    sys_id: str = Field(..., description="sys_id of the asset to delete")


def delete_asset(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Permanently delete an asset record from the alm_asset table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching DeleteAssetParams.

    Returns:
        Dictionary with ``success`` and ``message`` keys.
    """
    result = _unwrap_and_validate_params(params, DeleteAssetParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    url = f"{instance_url}/api/now/table/{ASSET_TABLE}/{validated.sys_id}"
    try:
        response = _make_request("DELETE", url, headers=headers)
        if response.status_code == 404:
            return {"success": False, "message": f"Asset not found: {validated.sys_id}"}
        if response.status_code == 204:
            return {
                "success": True,
                "message": f"Asset {validated.sys_id} deleted successfully",
            }
        response.raise_for_status()
        return {"success": True, "message": f"Asset {validated.sys_id} deleted successfully"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting asset: {e}")
        return {"success": False, "message": f"Error deleting asset: {_format_http_error(e)}"}


def create_asset(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new asset record in the alm_asset table or a subclass such as alm_hardware.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching CreateAssetParams.

    Returns:
        Dictionary with ``success``, ``sys_id``, and ``asset`` keys.
    """
    result = _unwrap_and_validate_params(params, CreateAssetParams, required_fields=["display_name"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    table = validated.asset_class or ASSET_TABLE
    body = _build_create_body(validated)

    url = f"{instance_url}/api/now/table/{table}"
    try:
        response = _make_request("POST", url, headers=headers, json=body)
        response.raise_for_status()
        record = response.json().get("result", {})
        return {
            "success": True,
            "sys_id": record.get("sys_id"),
            "asset": _format_asset(record),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating asset: {e}")
        return {"success": False, "message": f"Error creating asset: {_format_http_error(e)}"}


def list_assets(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List hardware/software assets from the alm_asset table with optional filters.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListAssetsParams.

    Returns:
        Dictionary with ``success``, ``assets`` (list), ``count``, and pagination keys.
    """
    result = _unwrap_and_validate_params(params, ListAssetsParams)
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
    if validated.asset_tag:
        query_parts.append(f"asset_tag={validated.asset_tag}")
    if validated.display_name:
        query_parts.append(f"display_nameLIKE{validated.display_name}")
    if validated.install_status:
        query_parts.append(f"install_status={validated.install_status}")
    if validated.assigned_to:
        query_parts.append(f"assigned_to.nameLIKE{validated.assigned_to}")
    if validated.model_category:
        query_parts.append(f"model_category.nameLIKE{validated.model_category}")
    if validated.query:
        query_parts.append(validated.query)

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        fields=",".join(ASSET_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{ASSET_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        assets = [_format_asset(r) for r in response.json().get("result", [])]
        return _paginated_list_response(assets, validated.limit, validated.offset, "assets")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing assets: {e}")
        return {"success": False, "message": f"Error listing assets: {_format_http_error(e)}"}


def get_asset(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single asset by sys_id or asset_tag.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetAssetParams.

    Returns:
        Dictionary with ``success`` and ``asset`` keys.
    """
    result = _unwrap_and_validate_params(params, GetAssetParams)
    if not result["success"]:
        return result
    validated = result["params"]

    if not validated.sys_id and not validated.asset_tag:
        return {"success": False, "message": "Either sys_id or asset_tag is required"}

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    base_query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(ASSET_FIELDS),
    }

    try:
        if validated.sys_id:
            url = f"{instance_url}/api/now/table/{ASSET_TABLE}/{validated.sys_id}"
            response = _make_request("GET", url, headers=headers, params=base_query_params)
            if response.status_code == 404:
                return {"success": False, "message": f"Asset not found: {validated.sys_id}"}
            response.raise_for_status()
            record = response.json().get("result", {})
            if not record:
                return {"success": False, "message": f"Asset not found: {validated.sys_id}"}
        else:
            url = f"{instance_url}/api/now/table/{ASSET_TABLE}"
            qp = dict(base_query_params)
            qp["sysparm_query"] = f"asset_tag={validated.asset_tag}"
            qp["sysparm_limit"] = "1"
            response = _make_request("GET", url, headers=headers, params=qp)
            response.raise_for_status()
            results = response.json().get("result", [])
            if not results:
                return {"success": False, "message": f"Asset not found: {validated.asset_tag}"}
            record = results[0]

        return {"success": True, "asset": _format_asset(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving asset: {e}")
        return {"success": False, "message": f"Error retrieving asset: {_format_http_error(e)}"}


def update_asset(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing asset record in the alm_asset table.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching UpdateAssetParams.

    Returns:
        Dictionary with ``success`` and ``asset`` keys.
    """
    result = _unwrap_and_validate_params(params, UpdateAssetParams, required_fields=["sys_id"])
    if not result["success"]:
        return result
    validated = result["params"]

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    body = _build_update_body(validated)
    if not body:
        return {"success": False, "message": "No fields provided to update"}

    url = f"{instance_url}/api/now/table/{ASSET_TABLE}/{validated.sys_id}"
    try:
        response = _make_request("PATCH", url, headers=headers, json=body)
        if response.status_code == 404:
            return {"success": False, "message": f"Asset not found: {validated.sys_id}"}
        response.raise_for_status()
        record = response.json().get("result", {})
        return {"success": True, "asset": _format_asset(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating asset: {e}")
        return {"success": False, "message": f"Error updating asset: {_format_http_error(e)}"}
