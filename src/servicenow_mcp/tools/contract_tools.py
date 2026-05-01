"""
Asset contract tools for the ServiceNow MCP server.

Provides tools for querying software/hardware maintenance contracts via the
alm_contract table (Contract Management application).
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

CONTRACT_TABLE = "alm_contract"

CONTRACT_FIELDS = [
    "sys_id",
    "number",
    "short_description",
    "vendor",
    "state",
    "contract_type",
    "category",
    "start_date",
    "end_date",
    "value",
    "currency",
    "assigned_to",
    "department",
    "company",
    "location",
    "sys_created_on",
    "sys_updated_on",
]

CONTRACT_STATE_VALUES = (
    "draft, pending_review, active, expired, cancelled"
)


class ListAssetContractsParams(BaseModel):
    """Parameters for listing asset contracts."""

    limit: Optional[int] = Field(20, description="Maximum number of records to return (default 20)")
    offset: Optional[int] = Field(0, description="Pagination offset")
    vendor: Optional[str] = Field(None, description="Filter by vendor name (substring match)")
    state: Optional[str] = Field(
        None,
        description=f"Filter by contract state: {CONTRACT_STATE_VALUES}",
    )
    contract_type: Optional[str] = Field(
        None, description="Filter by contract type (substring match)"
    )
    short_description: Optional[str] = Field(
        None, description="Filter by short description (substring match)"
    )
    start_date_from: Optional[str] = Field(
        None, description="Filter contracts with start_date >= this date (YYYY-MM-DD)"
    )
    end_date_before: Optional[str] = Field(
        None, description="Filter contracts with end_date <= this date (YYYY-MM-DD)"
    )
    query: Optional[str] = Field(None, description="Raw ServiceNow encoded query string")


class GetAssetContractParams(BaseModel):
    """Parameters for retrieving a single asset contract."""

    sys_id: Optional[str] = Field(None, description="sys_id of the contract to retrieve")
    number: Optional[str] = Field(None, description="Contract number (e.g. CON0001234)")


def _format_contract(record: Dict) -> Dict:
    """Extract and normalise relevant fields from a raw alm_contract record."""

    def _ref(value: Any) -> Any:
        if isinstance(value, dict):
            return value.get("display_value") or value.get("value")
        return value

    return {
        "sys_id": record.get("sys_id"),
        "number": record.get("number"),
        "short_description": record.get("short_description"),
        "vendor": _ref(record.get("vendor")),
        "state": record.get("state"),
        "contract_type": _ref(record.get("contract_type")),
        "category": _ref(record.get("category")),
        "start_date": record.get("start_date"),
        "end_date": record.get("end_date"),
        "value": record.get("value"),
        "currency": record.get("currency"),
        "assigned_to": _ref(record.get("assigned_to")),
        "department": _ref(record.get("department")),
        "company": _ref(record.get("company")),
        "location": _ref(record.get("location")),
        "created_on": record.get("sys_created_on"),
        "updated_on": record.get("sys_updated_on"),
    }


def list_asset_contracts(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """List asset contracts from the alm_contract table with optional filters.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching ListAssetContractsParams.

    Returns:
        Dictionary with ``success``, ``contracts`` (list), ``count``, and pagination keys.
    """
    result = _unwrap_and_validate_params(params, ListAssetContractsParams)
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
    if validated.vendor:
        query_parts.append(f"vendor.nameLIKE{validated.vendor}")
    if validated.state:
        query_parts.append(f"state={validated.state}")
    if validated.contract_type:
        query_parts.append(f"contract_type.nameLIKE{validated.contract_type}")
    if validated.short_description:
        query_parts.append(f"short_descriptionLIKE{validated.short_description}")
    if validated.start_date_from:
        query_parts.append(f"start_date>={validated.start_date_from}")
    if validated.end_date_before:
        query_parts.append(f"end_date<={validated.end_date_before}")
    if validated.query:
        query_parts.append(validated.query)

    query_params = _build_sysparm_params(
        validated.limit,
        validated.offset,
        query=_join_query_parts(query_parts),
        exclude_reference_link=True,
        fields=",".join(CONTRACT_FIELDS),
    )

    url = f"{instance_url}/api/now/table/{CONTRACT_TABLE}"
    try:
        response = _make_request("GET", url, headers=headers, params=query_params)
        response.raise_for_status()
        contracts = [_format_contract(r) for r in response.json().get("result", [])]
        return _paginated_list_response(contracts, validated.limit, validated.offset, "contracts")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing asset contracts: {e}")
        return {
            "success": False,
            "message": f"Error listing asset contracts: {_format_http_error(e)}",
        }


def get_asset_contract(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve a single asset contract by sys_id or contract number.

    Args:
        auth_manager: Authentication manager.
        server_config: Server configuration.
        params: Parameters matching GetAssetContractParams.

    Returns:
        Dictionary with ``success`` and ``contract`` keys.
    """
    result = _unwrap_and_validate_params(params, GetAssetContractParams)
    if not result["success"]:
        return result
    validated = result["params"]

    if not validated.sys_id and not validated.number:
        return {"success": False, "message": "Either sys_id or number is required"}

    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {"success": False, "message": "Cannot find instance_url"}
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {"success": False, "message": "Cannot find get_headers method"}

    base_query_params: Dict[str, Any] = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": ",".join(CONTRACT_FIELDS),
    }

    try:
        if validated.sys_id:
            url = f"{instance_url}/api/now/table/{CONTRACT_TABLE}/{validated.sys_id}"
            response = _make_request("GET", url, headers=headers, params=base_query_params)
            if response.status_code == 404:
                return {"success": False, "message": f"Contract not found: {validated.sys_id}"}
            response.raise_for_status()
            record = response.json().get("result", {})
            if not record:
                return {"success": False, "message": f"Contract not found: {validated.sys_id}"}
        else:
            url = f"{instance_url}/api/now/table/{CONTRACT_TABLE}"
            qp = dict(base_query_params)
            qp["sysparm_query"] = f"number={validated.number}"
            qp["sysparm_limit"] = "1"
            response = _make_request("GET", url, headers=headers, params=qp)
            response.raise_for_status()
            results = response.json().get("result", [])
            if not results:
                return {"success": False, "message": f"Contract not found: {validated.number}"}
            record = results[0]

        return {"success": True, "contract": _format_contract(record)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving asset contract: {e}")
        return {
            "success": False,
            "message": f"Error retrieving asset contract: {_format_http_error(e)}",
        }
