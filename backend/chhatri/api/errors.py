"""Error handling: every failure leaves the API as the §19 error envelope (SPEC §19, §21).

- ``ApiError`` is raised by routers and dependencies for expected failures.
- Starlette ``HTTPException`` (unknown path 404, wrong method 405) and FastAPI
  ``RequestValidationError`` (422 with a ``fields`` map) are translated by handlers.
- ``UnhandledErrorMiddleware`` turns any other exception into a 500 envelope that never contains a
  stack trace, exception text or secret (SPEC §21); the details are logged server side.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any, Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from chhatri.api.envelope import error

logger = logging.getLogger(__name__)

__all__ = [
    "CODE_BY_STATUS",
    "ApiError",
    "UnhandledErrorMiddleware",
    "install_error_handlers",
]

CODE_BY_STATUS: Final[Mapping[int, str]] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    500: "internal",
    502: "upstream_error",
    503: "unavailable",
}
MESSAGE_BY_STATUS: Final[Mapping[int, str]] = {
    404: "not found",
    405: "method not allowed",
    500: "internal error",
}
VALIDATION_MESSAGE: Final = "invalid request"
INTERNAL_STATUS: Final = 500
VALIDATION_STATUS: Final = 422
_LOCATION_ROOTS: Final = frozenset({"body", "query", "path", "header", "cookie"})


class ApiError(Exception):
    """An expected API failure rendered as the §19 error envelope."""

    def __init__(
        self,
        status: int,
        message: str,
        *,
        code: str | None = None,
        fields: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if status not in CODE_BY_STATUS:
            raise ValueError(f"unsupported API error status {status}")
        super().__init__(message)
        self.status = status
        self.code = code or CODE_BY_STATUS[status]
        self.message = message
        self.fields = dict(fields) if fields else None
        self.headers = dict(headers) if headers else None


def error_response(
    status: int,
    code: str,
    message: str,
    *,
    fields: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Render an error envelope response."""
    return JSONResponse(status_code=status, content=error(code, message, fields), headers=headers)


def _field_name(loc: tuple[Any, ...]) -> str:
    parts = [str(part) for part in loc]
    if parts and parts[0] in _LOCATION_ROOTS and len(parts) > 1:
        parts = parts[1:]
    return ".".join(parts) or "body"


def validation_fields(errors: list[dict[str, Any]]) -> dict[str, str]:
    """Map pydantic/FastAPI error entries to ``{field: reason}`` (SPEC §19). Inputs are never echoed."""
    fields: dict[str, str] = {}
    for item in errors:
        if item.get("type") == "json_invalid":
            fields["body"] = "invalid JSON"
            continue
        name = _field_name(tuple(item.get("loc", ())))
        fields.setdefault(name, str(item.get("msg", "invalid value")))
    return fields


async def _api_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiError):
        raise TypeError("handler registered for ApiError only")
    return error_response(exc.status, exc.code, exc.message, fields=exc.fields, headers=exc.headers)


async def _http_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise TypeError("handler registered for HTTPException only")
    status = exc.status_code if exc.status_code in CODE_BY_STATUS else INTERNAL_STATUS
    message = MESSAGE_BY_STATUS.get(status) or (str(exc.detail) if exc.detail else CODE_BY_STATUS[status])
    return error_response(status, CODE_BY_STATUS[status], message, headers=exc.headers)


async def _validation_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise TypeError("handler registered for RequestValidationError only")
    fields = validation_fields(list(exc.errors()))
    return error_response(
        VALIDATION_STATUS, CODE_BY_STATUS[VALIDATION_STATUS], VALIDATION_MESSAGE, fields=fields
    )


def install_error_handlers(app: FastAPI) -> None:
    """Register the envelope handlers on ``app`` (SPEC §19)."""
    app.add_exception_handler(ApiError, _api_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)


_INTERNAL_BODY: Final = json.dumps(
    error(CODE_BY_STATUS[INTERNAL_STATUS], MESSAGE_BY_STATUS[INTERNAL_STATUS])
).encode()


class UnhandledErrorMiddleware:
    """Pure ASGI middleware: unexpected exceptions become a 500 envelope (SPEC §19, §21).

    Implemented as raw ASGI (not ``BaseHTTPMiddleware``) so SSE streams are not buffered. If the
    response has already started the exception is logged and re-raised for the server to close the
    connection, because a second response cannot be sent.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            logger.error(
                "unhandled %s on %s %s",
                type(exc).__name__,
                scope.get("method"),
                scope.get("path"),
                exc_info=exc,
            )
            if started:
                raise
            await _send_internal_error(send)


async def _send_internal_error(send: Send) -> None:
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(_INTERNAL_BODY)).encode())]
    await send({"type": "http.response.start", "status": INTERNAL_STATUS, "headers": headers})
    await send({"type": "http.response.body", "body": _INTERNAL_BODY})
