"""
Shared helper utilities for ServiceNow MCP tool modules.

These functions were previously duplicated across 8 tool files. Import them
from here instead of redefining them locally.
"""

import json
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_RETRYABLE_EXCEPTIONS = (requests.exceptions.ConnectionError, requests.exceptions.Timeout)

_REDACTED = "<redacted>"
_SENSITIVE_HEADERS = frozenset(
    {"authorization", "x-servicenow-api-key", "cookie", "set-cookie", "proxy-authorization"}
)
_DEBUG_BODY_LIMIT = 500


def _redact_headers(headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Return a copy of *headers* with sensitive values replaced by ``<redacted>``."""
    if not headers:
        return {}
    return {
        k: (_REDACTED if k.lower() in _SENSITIVE_HEADERS else v)
        for k, v in headers.items()
    }


def _truncate_body(body: Any) -> str:
    """Serialise *body* to a string and truncate at :data:`_DEBUG_BODY_LIMIT` chars."""
    if body is None:
        return ""
    if isinstance(body, (dict, list)):
        text = json.dumps(body)
    else:
        text = str(body)
    if len(text) > _DEBUG_BODY_LIMIT:
        return text[:_DEBUG_BODY_LIMIT] + " [truncated]"
    return text


class RateLimitTracker:
    """Tracks ServiceNow API rate limit state parsed from response headers.

    Parses standard ``X-RateLimit-*`` and ``RateLimit-*`` headers from each
    response, logs warnings when the quota is nearly exhausted, and sleeps
    proactively before the next request when the quota is critically low.
    """

    _REMAINING_HEADERS = ("X-RateLimit-Remaining", "RateLimit-Remaining")
    _LIMIT_HEADERS = ("X-RateLimit-Limit", "RateLimit-Limit")
    _RESET_HEADERS = ("X-RateLimit-Reset", "RateLimit-Reset")

    def __init__(self, warning_threshold: float = 0.1, throttle_threshold: float = 0.05) -> None:
        """
        Args:
            warning_threshold: Warn when remaining/limit drops below this ratio (default 10%).
            throttle_threshold: Sleep before next request below this ratio (default 5%).
        """
        self.remaining: Optional[int] = None
        self.limit: Optional[int] = None
        self.reset_at: Optional[float] = None
        self._warning_threshold = warning_threshold
        self._throttle_threshold = throttle_threshold

    def update(self, response: requests.Response) -> None:
        """Parse rate limit headers from a response and update internal state."""
        for h in self._REMAINING_HEADERS:
            val = response.headers.get(h)
            if val is not None:
                try:
                    self.remaining = int(val)
                except (ValueError, TypeError):
                    pass
                break

        for h in self._LIMIT_HEADERS:
            val = response.headers.get(h)
            if val is not None:
                try:
                    self.limit = int(val)
                except (ValueError, TypeError):
                    pass
                break

        for h in self._RESET_HEADERS:
            val = response.headers.get(h)
            if val is not None:
                try:
                    self.reset_at = float(val)
                except (ValueError, TypeError):
                    pass
                break

        self._maybe_warn()

    def _maybe_warn(self) -> None:
        if self.remaining is None or self.limit is None or self.limit == 0:
            return
        ratio = self.remaining / self.limit
        if ratio <= self._warning_threshold:
            reset_msg = f"; resets at {self.reset_at:.0f}" if self.reset_at else ""
            logger.warning(
                "Rate limit warning: %d/%d requests remaining (%.0f%%)%s",
                self.remaining,
                self.limit,
                ratio * 100,
                reset_msg,
            )

    def check_and_throttle(self) -> None:
        """Sleep proactively before a request if quota is critically low."""
        if self.remaining is None or self.limit is None or self.limit == 0:
            return
        ratio = self.remaining / self.limit
        if ratio > self._throttle_threshold:
            return

        now = time.time()
        if self.reset_at and self.reset_at > now:
            sleep_for = min(self.reset_at - now, 60.0)
        else:
            sleep_for = 1.0

        logger.warning(
            "Rate limit critical: %d/%d remaining (%.0f%%); pausing %.1fs before next request",
            self.remaining,
            self.limit,
            ratio * 100,
            sleep_for,
        )
        time.sleep(sleep_for)

    @property
    def utilization(self) -> Optional[float]:
        """Fraction of rate limit consumed (0.0 = none used, 1.0 = fully exhausted)."""
        if self.remaining is None or self.limit is None or self.limit == 0:
            return None
        return 1.0 - (self.remaining / self.limit)

    def reset(self) -> None:
        """Clear tracked state."""
        self.remaining = None
        self.limit = None
        self.reset_at = None


_rate_limit_tracker = RateLimitTracker()


def _make_request(
    method: str,
    url: str,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    rate_limit_tracker: Optional[RateLimitTracker] = None,
    **kwargs,
) -> requests.Response:
    """Call the named HTTP method with exponential-backoff retry.

    Retries on transient network errors (ConnectionError, Timeout) and on
    retryable HTTP status codes (429, 500, 502, 503, 504).  Client errors
    (4xx except 429) are returned immediately — retrying won't help.

    For 429 responses, honours the ``Retry-After`` header when present.
    Delay formula without Retry-After: backoff_factor × 2^attempt (1 s, 2 s, 4 s by default).

    Rate limit headers (``X-RateLimit-Remaining`` etc.) are parsed after every
    response and forwarded to *rate_limit_tracker*.  When remaining quota is
    critically low the tracker sleeps before the next attempt.  Pass a
    dedicated :class:`RateLimitTracker` instance to isolate state; pass
    ``rate_limit_tracker=None`` (default) to use the module-level shared tracker.

    Args:
        method: HTTP method name (case-insensitive): "GET", "POST", etc.
        url: Request URL.
        max_retries: Maximum number of retry attempts (0 = no retries).
        backoff_factor: Multiplier for exponential delay (seconds).
        rate_limit_tracker: Tracker to update with rate limit headers.  Defaults
            to the module-level :data:`_rate_limit_tracker` singleton.
        **kwargs: Passed verbatim to the underlying requests method.

    Returns:
        The :class:`requests.Response` object from the final attempt.
        Callers are responsible for calling ``response.raise_for_status()``.
    """
    tracker: RateLimitTracker = rate_limit_tracker if rate_limit_tracker is not None else _rate_limit_tracker
    fn: Callable = getattr(requests, method.lower())
    response: Optional[requests.Response] = None
    _debug = logger.isEnabledFor(logging.DEBUG)

    for attempt in range(max_retries + 1):
        tracker.check_and_throttle()
        if _debug:
            logger.debug(
                ">> %s %s | params=%s headers=%s body=%s",
                method.upper(),
                url,
                _truncate_body(kwargs.get("params")),
                _redact_headers(kwargs.get("headers")),
                _truncate_body(kwargs.get("json") or kwargs.get("data")),
            )
        try:
            _t0 = time.monotonic()
            response = fn(url, **kwargs)
            _elapsed = time.monotonic() - _t0
            tracker.update(response)
            if _debug:
                try:
                    resp_body = _truncate_body(response.json())
                except Exception:
                    resp_body = _truncate_body(response.text)
                logger.debug(
                    "<< %s in %.3fs | body=%s",
                    response.status_code,
                    _elapsed,
                    resp_body,
                )
            if response.status_code not in _RETRYABLE_STATUS_CODES or attempt == max_retries:
                return response
            if response.status_code == 429:
                delay = float(response.headers.get("Retry-After") or backoff_factor * (2 ** attempt))
            else:
                delay = backoff_factor * (2 ** attempt)
            logger.warning(
                "HTTP %s from %s; retrying in %.1fs (attempt %d/%d)",
                response.status_code, url, delay, attempt + 1, max_retries,
            )
            time.sleep(delay)
        except _RETRYABLE_EXCEPTIONS as exc:
            if attempt == max_retries:
                raise
            delay = backoff_factor * (2 ** attempt)
            logger.warning(
                "Request error (%s); retrying in %.1fs (attempt %d/%d)",
                exc, delay, attempt + 1, max_retries,
            )
            time.sleep(delay)

    return response  # type: ignore[return-value]

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


def _build_sysparm_params(
    limit: int,
    offset: int,
    query: Optional[str] = None,
    display_value: str = "true",
    exclude_reference_link: bool = False,
    order_by: Optional[str] = None,
    fields: Optional[str] = None,
) -> Dict[str, Any]:
    """Build sysparm_* query parameters for ServiceNow Table API list requests.

    Args:
        limit: Maximum number of records to return.
        offset: Zero-based starting position for pagination.
        query: ServiceNow encoded query string (filter parts already joined).
        display_value: Value for sysparm_display_value (default ``"true"``).
        exclude_reference_link: When True, adds sysparm_exclude_reference_link.
        order_by: Field ordering expression for sysparm_orderby.
        fields: Comma-separated field list for sysparm_fields.

    Returns:
        Dictionary ready to pass as the ``params`` argument of ``requests.get``.
    """
    p: Dict[str, Any] = {
        "sysparm_limit": limit,
        "sysparm_offset": offset,
        "sysparm_display_value": display_value,
    }
    if exclude_reference_link:
        p["sysparm_exclude_reference_link"] = "true"
    if query:
        p["sysparm_query"] = query
    if order_by:
        p["sysparm_orderby"] = order_by
    if fields:
        p["sysparm_fields"] = fields
    return p


def _join_query_parts(parts: List[str]) -> str:
    """Join ServiceNow query filter parts with the ``^`` operator.

    Skips empty/None entries so callers can append conditions unconditionally.

    Args:
        parts: Individual encoded-query conditions.

    Returns:
        Combined query string, or empty string when all parts are empty.
    """
    return "^".join(p for p in parts if p)


def _paginated_list_response(
    items: List[Any],
    limit: int,
    offset: int,
    result_key: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a standardised success response for list/query operations.

    Includes ``has_more`` and ``next_offset`` so callers can page through
    results without needing to know the total record count upfront.

    Args:
        items: The records returned for this page.
        limit: The page size that was requested.
        offset: Zero-based starting position of this page.
        result_key: Dict key under which items are returned.
        extra: Optional additional fields merged into the response.

    Returns:
        Dict with success, count, limit, offset, has_more, next_offset, and *result_key*.
    """
    count = len(items)
    has_more = count == limit
    resp: Dict[str, Any] = {
        "success": True,
        "count": count,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "next_offset": offset + limit if has_more else None,
        result_key: items,
    }
    if extra:
        resp.update(extra)
    return resp


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
