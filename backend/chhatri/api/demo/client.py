"""HTTP access for the demo rehearsal: the SPEC §19 routes only, envelopes unwrapped.

`DemoApi` wraps an ``httpx.AsyncClient`` pointed at a running backend or at the ASGI app in
process. Every call checks the §19 envelope: a non-2xx answer or ``{"ok": false}`` raises
`DemoHttpError` naming the route, status and error code, so a failed rehearsal says where it broke.
The officer token comes from the constructor or, in demo mode, from ``GET /api/session`` (SPEC §19).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Final

import httpx

__all__ = ["DemoApi", "DemoHttpError"]

logger = logging.getLogger(__name__)

SUCCESS_MIN: Final = 200
SUCCESS_MAX: Final = 299
PAGE_SIZE: Final = 500  # every §19 list route accepts limit ≤ 500
MAX_BODY_CHARS: Final = 300


class DemoHttpError(RuntimeError):
    """A §19 route answered with an error (or not with the envelope)."""

    def __init__(self, method: str, path: str, status: int, detail: str) -> None:
        super().__init__(f"{method} {path} answered {status}: {detail}")
        self.method = method
        self.path = path
        self.status = status
        self.detail = detail


def _unwrap(method: str, path: str, response: httpx.Response) -> dict[str, Any]:
    """The parsed ``{ok: true, …}`` body, or DemoHttpError."""
    try:
        body = response.json()
    except ValueError as exc:
        raise DemoHttpError(method, path, response.status_code, response.text[:MAX_BODY_CHARS]) from exc
    ok_status = SUCCESS_MIN <= response.status_code <= SUCCESS_MAX
    if not ok_status or not isinstance(body, dict) or body.get("ok") is not True:
        error = body.get("error", {}) if isinstance(body, dict) else {}
        detail = f"{error.get('code', 'no_envelope')}: {error.get('message', response.text[:MAX_BODY_CHARS])}"
        raise DemoHttpError(method, path, response.status_code, detail)
    return body


class DemoApi:
    """The rehearsal's view of the backend (SPEC §19)."""

    def __init__(self, client: httpx.AsyncClient, *, officer_token: str | None = None) -> None:
        self._client = client
        self._officer_token = officer_token

    async def get(self, path: str, **params: Any) -> Any:
        """``data`` of a GET."""
        response = await self._client.get(path, params=params or None)
        return _unwrap("GET", path, response)["data"]

    async def get_all(self, path: str, **params: Any) -> list[Any]:
        """Every item of a paged list route (``limit``/``offset`` paging)."""
        items: list[Any] = []
        while True:
            response = await self._client.get(path, params={**params, "limit": PAGE_SIZE, "offset": len(items)})
            body = _unwrap("GET", path, response)
            items.extend(body["data"])
            if not body["data"] or len(items) >= body["meta"]["total"]:
                return items

    async def audit(self) -> list[dict[str, Any]]:
        """The whole audit log (``/api/audit`` pages with ``after``, SPEC §19)."""
        entries: list[dict[str, Any]] = []
        while True:
            after = entries[-1]["seq"] if entries else 0
            response = await self._client.get("/api/audit", params={"after": after, "limit": PAGE_SIZE})
            page = _unwrap("GET", "/api/audit", response)["data"]
            if not page:
                return entries
            entries.extend(page)

    async def post(self, path: str, body: Mapping[str, Any] | None = None, *, officer: bool = False) -> Any:
        """``data`` of a JSON POST; `officer` adds the bearer token (SPEC §21)."""
        headers = {"Authorization": f"Bearer {await self.officer_token()}"} if officer else None
        response = await self._client.post(path, json=dict(body or {}), headers=headers)
        return _unwrap("POST", path, response)["data"]

    async def post_form(self, path: str, form: Mapping[str, str]) -> Any:
        """``data`` of a form POST (the Paytm callback, SPEC §14.3)."""
        response = await self._client.post(path, data=dict(form))
        return _unwrap("POST", path, response)["data"]

    async def officer_token(self) -> str:
        """The configured token, else the demo-mode session token (SPEC §19 /api/session)."""
        if self._officer_token is None:
            session = await self.get("/api/session")
            self._officer_token = str(session["officer_token"])
            logger.info("demo check: officer token read from /api/session")
        return self._officer_token
