"""Response envelopes (SPEC §19).

Every JSON response is either ``{"ok": true, "data": …}`` (lists add
``"meta": {"total", "limit", "offset"}``) or ``{"ok": false, "error": {"code", "message", "fields"?}}``.
Routers build bodies only through these helpers so the shape cannot drift.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["error", "ok", "ok_list"]


def ok(data: Any) -> dict[str, Any]:
    """Success envelope for a single object (SPEC §19)."""
    return {"ok": True, "data": data}


def ok_list(items: Sequence[Any], *, total: int, limit: int, offset: int) -> dict[str, Any]:
    """Success envelope for a list with paging metadata (SPEC §19).

    ``total`` is the size of the full (filtered) collection, ``limit`` the page size asked for and
    ``offset`` the position of the first item in ``items``.
    """
    if total < 0 or limit < 0 or offset < 0:
        raise ValueError("list metadata must be non-negative")
    return {"ok": True, "data": list(items), "meta": {"total": total, "limit": limit, "offset": offset}}


def error(code: str, message: str, fields: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Error envelope (SPEC §19). ``fields`` maps input names to reasons (validation only)."""
    body: dict[str, Any] = {"code": code, "message": message}
    if fields:
        body["fields"] = dict(fields)
    return {"ok": False, "error": body}
