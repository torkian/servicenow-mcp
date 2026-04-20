"""
Shared helper utilities for ServiceNow MCP tool modules.

These functions were previously duplicated across 8 tool files. Import them
from here instead of redefining them locally.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Type, TypeVar

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _format_http_error(e: Exception) -> str:
    """Extract a readable message from a requests exception.

    For HTTPError (raised by raise_for_status()), tries to parse the ServiceNow
    JSON error body which typically contains ``error.message`` and
    ``error.detail``. Falls back to ``str(e)`` for network errors or responses
    that cannot be parsed as JSON.
    """
    if isinstance(e, requests.HTTPError) and e.response is not None:
        status = e.response.status_code
        try:
            body = e.response.json()
            err = body.get("error", {})
            if isinstance(err, dict):
                msg = err.get("message", "")
                detail = err.get("detail", "")
                if msg and detail:
                    return f"HTTP {status}: {msg} — {detail}"
                if msg:
                    return f"HTTP {status}: {msg}"
        except Exception:
            pass
        raw = e.response.text
        return f"HTTP {status}: {raw[:300]}" if raw else f"HTTP {status}"
    return str(e)


def _unwrap_and_validate_params(
    params: Any,
    model_class: Type[T],
    required_fields: List[str] = None,
) -> Dict[str, Any]:
    """Unwrap and validate tool parameters against a Pydantic model.

    Handles three input shapes:
    - Already a Pydantic model instance (passed through or re-validated).
    - A dict whose sole key is ``"params"`` wrapping the real dict.
    - A plain dict.

    Args:
        params: Raw parameters from the MCP call.
        model_class: Pydantic model to validate against.
        required_fields: Optional list of field names that must be present.

    Returns:
        ``{"success": True, "params": <model_instance>}`` on success, or
        ``{"success": False, "message": <str>}`` on failure.
    """
    # If already a Pydantic model, re-use or convert
    if isinstance(params, BaseModel):
        if isinstance(params, model_class):
            model_instance = params
        else:
            try:
                model_instance = model_class(**params.dict())
            except Exception as e:
                return {"success": False, "message": f"Error converting parameters: {e}"}
        if required_fields:
            missing = [f for f in required_fields if getattr(model_instance, f, None) is None]
            if missing:
                return {"success": False, "message": f"Missing required fields: {', '.join(missing)}"}
        return {"success": True, "params": model_instance}

    # Unwrap {"params": {...}} envelope
    if isinstance(params, dict) and list(params.keys()) == ["params"] and isinstance(params["params"], dict):
        logger.warning("Detected params wrapped in a 'params' key. Unwrapping...")
        params = params["params"]

    # Coerce non-dict to dict
    if not isinstance(params, dict):
        try:
            logger.warning("Params is not a dictionary. Attempting to convert...")
            params = params.dict() if hasattr(params, "dict") else dict(params)
        except Exception as e:
            logger.error(f"Failed to convert params to dictionary: {e}")
            return {
                "success": False,
                "message": f"Invalid parameters format. Expected a dictionary, got {type(params).__name__}",
            }

    # Validate required fields before model construction
    if required_fields:
        for field in required_fields:
            if field not in params:
                return {"success": False, "message": f"Missing required parameter '{field}'"}

    try:
        validated = model_class(**params)
        return {"success": True, "params": validated}
    except Exception as e:
        logger.error(f"Error validating parameters: {e}")
        return {"success": False, "message": f"Error validating parameters: {e}"}


_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DURATION_RE = re.compile(r"^\d{2,}:\d{2}:\d{2}$")


def validate_servicenow_datetime(v: Optional[str]) -> Optional[str]:
    """Validate a ServiceNow datetime string (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD).

    Raises ValueError if the value is present but does not match either format.
    Returns the value unchanged when valid or None.
    """
    if v is None:
        return v
    if _DATETIME_RE.match(v) or _DATE_RE.match(v):
        return v
    raise ValueError(
        f"Invalid date/datetime '{v}'. Expected format: YYYY-MM-DD HH:MM:SS or YYYY-MM-DD"
    )


def validate_servicenow_date(v: Optional[str]) -> Optional[str]:
    """Validate a ServiceNow date string (YYYY-MM-DD only).

    Raises ValueError if the value is present but does not match YYYY-MM-DD.
    Returns the value unchanged when valid or None.
    """
    if v is None:
        return v
    if _DATE_RE.match(v):
        return v
    raise ValueError(f"Invalid date '{v}'. Expected format: YYYY-MM-DD")


def validate_duration_hhmmss(v: Optional[str]) -> Optional[str]:
    """Validate a duration string in HH:MM:SS format.

    Raises ValueError if the value is present but does not match HH:MM:SS.
    Returns the value unchanged when valid or None.
    """
    if v is None:
        return v
    if _DURATION_RE.match(v):
        return v
    raise ValueError(f"Invalid duration '{v}'. Expected format: HH:MM:SS (e.g. '02:30:00')")


def _get_instance_url(auth_manager: Any, server_config: Any) -> Optional[str]:
    """Return the ServiceNow instance URL from config or auth manager.

    Checks ``server_config.instance_url`` first, then ``auth_manager.instance_url``.

    Args:
        auth_manager: Authentication manager object.
        server_config: Server configuration object.

    Returns:
        Instance URL string, or ``None`` if not found.
    """
    if hasattr(server_config, "instance_url"):
        return server_config.instance_url
    if hasattr(auth_manager, "instance_url"):
        return auth_manager.instance_url
    logger.error("Cannot find instance_url in either server_config or auth_manager")
    return None


def _get_headers(auth_manager: Any, server_config: Any) -> Optional[Dict[str, str]]:
    """Return HTTP headers for ServiceNow API requests.

    Tries ``auth_manager.get_headers()`` first, then ``server_config.get_headers()``.

    Args:
        auth_manager: Authentication manager object.
        server_config: Server configuration object.

    Returns:
        Headers dict, or ``None`` if not found.
    """
    if hasattr(auth_manager, "get_headers"):
        return auth_manager.get_headers()
    if hasattr(server_config, "get_headers"):
        return server_config.get_headers()
    logger.error("Cannot find get_headers method in either auth_manager or server_config")
    return None
