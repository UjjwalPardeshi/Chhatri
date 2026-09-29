"""API response envelopes (SPEC §19).

All responses follow the envelope format: either {"ok": true, "data": ...} or
{"ok": false, "error": {"code": ..., "message": ...}}.
Paginated responses include "meta": {"total", "limit", "offset"}.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Error details with optional field-level validation errors."""

    code: str
    message: str
    fields: dict[str, str] | None = None


class SuccessEnvelope(BaseModel, Generic[T]):
    """Success response with optional pagination metadata."""

    ok: bool = True
    data: T
    meta: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    """Error response."""

    ok: bool = False
    error: ErrorDetail


def ok(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a success envelope."""
    result: dict[str, Any] = {"ok": True, "data": data}
    if meta is not None:
        result["meta"] = meta
    return result


def error(
    code: str, message: str, fields: dict[str, str] | None = None
) -> dict[str, Any]:
    """Create an error envelope."""
    return {
        "ok": False,
        "error": {"code": code, "message": message, **({"fields": fields} if fields else {})},
    }
