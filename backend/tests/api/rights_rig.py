"""A real small-city AppState behind the real app, with chosen feature flags, for the N5 and N6 route tests."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from pydantic import BaseModel

from chhatri.api.app import create_app
from chhatri.api.schemas import (
    ConsentActivityItem,
    ConsentItem,
    ConsentWithdrawal,
    Grievance,
    PrecheckConfirmation,
    PrecheckView,
    SlipForgetResult,
)
from chhatri.replay.state import AppState, Runtime
from chhatri.replay.static import StaticContext
from tests.replay import small_world
from tests.replay.helpers import OFFICER_TOKEN, make_static, offline_settings

BASE = "http://testserver"
OFFICER = {"Authorization": f"Bearer {OFFICER_TOKEN}"}
# Every 2xx body of a rights route is checked against its strict mirror schema (implementation guide 1.5).
# (method, path pattern, schema, the body is a list)
SCHEMAS: Final[tuple[tuple[str, re.Pattern[str], type[BaseModel], bool], ...]] = (
    ("GET", re.compile(r"^/api/merchants/[^/]+/consents$"), ConsentItem, True),
    ("GET", re.compile(r"^/api/merchants/[^/]+/consents/activity$"), ConsentActivityItem, True),
    ("POST", re.compile(r"^/api/merchants/[^/]+/consents/[^/]+/withdraw$"), ConsentWithdrawal, False),
    ("POST", re.compile(r"^/api/merchants/[^/]+/slips/[^/]+/forget$"), SlipForgetResult, False),
    ("GET", re.compile(r"^/api/merchants/[^/]+/grievances$"), Grievance, True),
    ("POST", re.compile(r"^/api/merchants/[^/]+/grievances$"), Grievance, False),
    ("POST", re.compile(r"^/api/merchants/[^/]+/slip-precheck$"), PrecheckView, False),
    ("POST", re.compile(r"^/api/merchants/[^/]+/slip-precheck/[^/]+/confirm$"), PrecheckConfirmation, False),
)


def validate_body(method: str, path: str, status: int, body: object) -> None:
    """Validate a 2xx `{ok, data}` body of a rights route against its schema; other routes pass through."""
    if not 200 <= status < 300:
        return
    for want_method, pattern, schema, many in SCHEMAS:
        if method == want_method and pattern.match(path):
            assert isinstance(body, dict) and body.get("ok") is True, body
            data = body["data"]
            for item in data if many else [data]:
                schema.model_validate(item)
            return


async def check_schema(response: Response) -> None:
    if response.headers.get("content-type", "").startswith("application/json"):
        await response.aread()
        validate_body(
            response.request.method, response.request.url.path, response.status_code, response.json()
        )


def build_static(var_dir: Path) -> StaticContext:
    return make_static(
        offline_settings(var_dir), small_world.small_city(), small_world.small_model(), var_dir / "artifacts"
    )


@dataclass(frozen=True, slots=True)
class Rig:
    state: AppState
    app: FastAPI
    http: AsyncClient

    @property
    def rt(self) -> Runtime:
        return self.state.runtime


async def open_rig(
    static: StaticContext, *, features: str, scenario: str, seek: str | None
) -> AsyncIterator[Rig]:
    settings = static.settings.model_copy(update={"chhatri_features": features})
    state = AppState(
        replace(static, settings=settings)
    )  # the flags must reach the load too (N6 seeds at load)
    rt = await state.load(scenario)
    if seek:
        await rt.engine.seek(seek)
    app = create_app(settings, state=state)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=BASE, event_hooks={"response": [check_schema]}
    ) as http:
        yield Rig(state, app, http)
