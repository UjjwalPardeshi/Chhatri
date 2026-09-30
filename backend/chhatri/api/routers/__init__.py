"""HTTP routers, one per area of the SPEC §19 route table; ``ROUTERS`` is mounted by ``create_app``."""

from __future__ import annotations

from fastapi import APIRouter

from chhatri.api.routers import (
    cases,
    internal,
    live,
    media,
    merchants,
    meta,
    phone,
    premium,
    records,
    replay,
    stream,
    webhooks,
)

ROUTERS: tuple[APIRouter, ...] = (
    meta.router,
    live.router,
    replay.router,
    stream.router,
    merchants.router,
    phone.router,
    cases.router,
    records.router,
    premium.router,
    webhooks.router,
    internal.router,
    media.router,
)

__all__ = ["ROUTERS"]
