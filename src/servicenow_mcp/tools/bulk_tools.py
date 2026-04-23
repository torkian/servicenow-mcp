"""
Bulk operations tools for the ServiceNow MCP server.

Wraps the ServiceNow Batch API (POST /api/now/v1/batch) so multiple
Table API calls can be executed in a single HTTP round-trip.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from pydantic import BaseModel, Field, field_validator

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.helpers import _format_http_error, _make_request

logger = logging.getLogger(__name__)

_ALLOWED_METHODS = frozenset({"DELETE", "GET", "PATCH", "POST", "PUT"})


class BulkOperationRequest(BaseModel):
    """A single API call within a bulk batch request."""

    id: str = Field(..., description="Unique identifier for this request within the batch")
    method: str = Field(..., description="HTTP method: GET, POST, PUT, PATCH, or DELETE")
    url: str = Field(
        ...,
        description=(
            "Relative API path starting with /api/ "
            "(e.g. /api/now/v2/table/incident). "
            "Full URLs are accepted; the scheme and host are stripped automatically."
        ),
    )
    body: Optional[Dict[str, Any]] = Field(
        None,
        description="Request body for POST/PUT/PATCH operations; omit or set null for GET/DELETE",
    )

    @field_validator("method", mode="before")
    @classmethod
    def normalize_method(cls, v: str) -> str:
        upper = v.upper()
        if upper not in _ALLOWED_METHODS:
            raise ValueError(
                f"Invalid HTTP method '{v}'. Allowed: {sorted(_ALLOWED_METHODS)}"
            )
        return upper

    @field_validator("url", mode="before")
    @classmethod
    def ensure_relative_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme:
            path = parsed.path
            if parsed.query:
                path = f"{path}?{parsed.query}"
            return path
        return v


class BulkOperationsParams(BaseModel):
    """Parameters for executing a batch of ServiceNow API calls."""

    requests: List[BulkOperationRequest] = Field(
        ...,
        description="API calls to execute as one batch (1–100 requests).",
    )


def execute_bulk_operations(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: BulkOperationsParams,
) -> Dict[str, Any]:
    """Execute up to 100 ServiceNow API calls in a single batch HTTP request.

    Uses POST /api/now/v1/batch. Responses are returned in the same order as
    the input requests. Each result includes the original request id, HTTP
    status code, a boolean ok flag, and the parsed response body.
    """
    if not params.requests:
        return {"success": False, "message": "No requests provided"}

    if len(params.requests) > 100:
        return {
            "success": False,
            "message": f"Too many requests: {len(params.requests)} (maximum 100)",
        }

    # Build the batch payload; sub-request bodies must be JSON strings
    batch_payload: Dict[str, Any] = {
        "requests": [
            {
                "id": req.id,
                "method": req.method,
                "url": req.url,
                "headers": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Accept", "value": "application/json"},
                ],
                "body": json.dumps(req.body) if req.body is not None else "",
            }
            for req in params.requests
        ]
    }

    batch_url = f"{config.api_url}/v1/batch"

    try:
        response = _make_request("POST", 
            batch_url,
            json=batch_payload,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Batch request failed: %s", e)
        return {
            "success": False,
            "message": f"Batch request failed: {_format_http_error(e)}",
        }

    data = response.json()
    serviced = data.get("servicedRequests", [])

    results = []
    all_ok = True
    for item in serviced:
        status_code = item.get("statusCode", 0)
        ok = 200 <= status_code < 300

        raw_body = item.get("body", "")
        try:
            parsed_body = json.loads(raw_body) if raw_body else None
        except (json.JSONDecodeError, TypeError):
            parsed_body = raw_body

        if not ok:
            all_ok = False

        results.append(
            {
                "id": item.get("id"),
                "status_code": status_code,
                "status_text": item.get("statusText", ""),
                "ok": ok,
                "body": parsed_body,
            }
        )

    total = len(results)
    succeeded = sum(1 for r in results if r["ok"])

    return {
        "success": all_ok,
        "message": f"Batch completed: {succeeded}/{total} requests succeeded",
        "total": total,
        "succeeded": succeeded,
        "failed": total - succeeded,
        "results": results,
    }
