"""Shared transport for the Enterprise Intelligence clients.

Every operation is described once as a :class:`RequestSpec`. A sender turns
the spec into one call on the SDK HTTP client. The sync sender returns the
response; the async sender returns an awaitable. Because both service
classes build their grouped clients from the same operation classes, the
sync and async surfaces cannot drift apart.

Every mutation route requires an ``idempotency-key`` header (8-255 chars
after trimming). When a caller passes none (and has not set the header in
``request_config.headers``) a UUID4 key is generated per call.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import quote

from ...exceptions import AuraOneError
from ...types import RequestConfig

IDEMPOTENCY_HEADER = "idempotency-key"
_IDEMPOTENCY_MIN = 8
_IDEMPOTENCY_MAX = 255

# Operation paths are written out in full at each call site: the SDK
# route-contract check resolves every literal path to a platform route file.

JsonValue = Any


class EnterpriseIntelligenceUnavailableError(AuraOneError):
    """An Enterprise Intelligence route answered 503.

    The runtime, or one part of it (incidents, replay, improvement,
    regression, ingestion), is not configured in this deployment. Detection
    keys on the status: one route answers 503 with code ``ACCESS_DENIED``,
    so read ``code`` for detail only. The HTTP client retries 5xx responses
    before this error is raised.
    """

    def __init__(
        self,
        message: str = "Enterprise Intelligence is not available in this deployment.",
        code: Optional[str] = "ENTERPRISE_COMPOSITION_UNAVAILABLE",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, details, 503)


def is_enterprise_intelligence_unavailable(error: BaseException) -> bool:
    """True for any 503 raised by an Enterprise Intelligence call."""
    return isinstance(error, EnterpriseIntelligenceUnavailableError) or (
        isinstance(error, AuraOneError) and error.status_code == 503
    )


def _to_enterprise_error(error: AuraOneError) -> AuraOneError:
    if isinstance(error, EnterpriseIntelligenceUnavailableError):
        return error
    if error.status_code == 503:
        return EnterpriseIntelligenceUnavailableError(
            error.message,
            error.code or "ENTERPRISE_COMPOSITION_UNAVAILABLE",
            error.details or None,
        )
    return error


def is_truncated(meta: Optional[Dict[str, Any]]) -> bool:
    """True when a collection read returned fewer records than match.

    Collection reads return at most ``meta["limit"]`` (100) records and have
    no cursor; narrow the read with ``q`` / ``status`` instead.
    """
    if not meta:
        return False
    return int(meta.get("loaded", 0)) < int(meta.get("total", 0))


def _with_idempotency(
    request_config: Optional[RequestConfig],
    idempotency_key: Optional[str],
) -> RequestConfig:
    """Return a copy of ``request_config`` carrying an ``idempotency-key`` header.

    Precedence: explicit ``idempotency_key`` argument, then a key the caller
    already set in ``request_config.headers`` (any casing), then a generated
    UUID4. Other caller headers are preserved; the caller's config object is
    never mutated.
    """
    base = request_config or RequestConfig()
    headers: Dict[str, str] = dict(base.headers or {})
    existing = next(
        (name for name in headers if name.lower() == IDEMPOTENCY_HEADER), None
    )

    if idempotency_key is not None:
        key = idempotency_key
        if existing is not None:
            del headers[existing]
    elif existing is not None:
        key = headers.pop(existing)
    else:
        key = str(uuid.uuid4())

    trimmed_length = len(key.strip())
    if trimmed_length < _IDEMPOTENCY_MIN or trimmed_length > _IDEMPOTENCY_MAX:
        raise ValueError(
            f"idempotency key must be {_IDEMPOTENCY_MIN}-{_IDEMPOTENCY_MAX} "
            f"characters after trimming (got {trimmed_length})"
        )

    headers[IDEMPOTENCY_HEADER] = key
    return dataclasses.replace(base, headers=headers)


def _iso(value: Union[str, datetime]) -> str:
    return value.isoformat() if isinstance(value, datetime) else value


def _compact(values: Dict[str, Any]) -> Dict[str, Any]:
    """Drop ``None`` values (optional fields the caller did not set)."""
    return {key: value for key, value in values.items() if value is not None}


def queue_params(
    q: Optional[str] = None,
    status: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """``q`` / ``f.status`` query keys for the queue-backed collection reads."""
    merged: Dict[str, Any] = dict(params or {})
    if q:
        merged["q"] = q
    if status:
        merged["f.status"] = status
    return merged or None


@dataclasses.dataclass(frozen=True)
class RequestSpec:
    """One HTTP call: method, path template and payload."""

    method: str
    path: str
    path_params: Dict[str, str] = dataclasses.field(default_factory=dict)
    params: Optional[Dict[str, Any]] = None
    json: Optional[Any] = None
    form: Optional[Dict[str, str]] = None
    files: Optional[List[Tuple[str, Tuple[str, bytes, str]]]] = None
    idempotency_key: Optional[str] = None
    request_config: Optional[RequestConfig] = None

    @property
    def idempotent(self) -> bool:
        return self.method != "GET"

    def url(self) -> str:
        encoded = {k: quote(str(v), safe="") for k, v in self.path_params.items()}
        return self.path.format(**encoded)

    def config(self) -> Optional[RequestConfig]:
        if self.idempotent:
            return _with_idempotency(self.request_config, self.idempotency_key)
        return self.request_config


def _call(http: Any, spec: RequestSpec) -> Any:
    """Issue the spec on ``http`` (returns a value or an awaitable)."""
    url = spec.url()
    config = spec.config()
    if spec.method == "GET":
        return http.get(url, params=spec.params, config=config)
    if spec.method == "POST":
        if spec.files is not None:
            return http.post(url, data=spec.form, config=config, files=spec.files)
        return http.post(url, data=spec.json, config=config)
    if spec.method == "PATCH":
        return http.patch(url, data=spec.json, config=config)
    if spec.method == "DELETE":
        if spec.json is not None:
            return http.delete(url, config=config, data=spec.json)
        return http.delete(url, config=config)
    raise ValueError(f"unsupported method {spec.method}")


class SyncSender:
    """Sends specs on a synchronous HTTP client."""

    def __init__(self, http: Any):
        self.http = http

    def __call__(self, spec: RequestSpec) -> Any:
        try:
            return _call(self.http, spec)
        except AuraOneError as error:
            mapped = _to_enterprise_error(error)
            if mapped is error:
                raise
            raise mapped from error


class AsyncSender:
    """Sends specs on an asynchronous HTTP client."""

    def __init__(self, http: Any):
        self.http = http

    async def __call__(self, spec: RequestSpec) -> Any:
        try:
            return await _call(self.http, spec)
        except AuraOneError as error:
            mapped = _to_enterprise_error(error)
            if mapped is error:
                raise
            raise mapped from error


Sender = Callable[[RequestSpec], Any]


class _Ops:
    """Base for grouped operation clients."""

    def __init__(self, send: Sender):
        self._send = send
