"""HTTP routers, one per area of the SPEC §19 route table; ``ROUTERS`` is mounted by ``create_app``."""

from __future__ import annotations

from fastapi import APIRouter

from chhatri.api.routers import (
    ask,
    cases,
    channel,
    consents,
    evals,
    fallback,
    grievances,
    internal,
    live,
    media,
    merchants,
    meta,
    ops,
    phone,
    precheck,
    premium,
    records,
    replay,
    stream,
    voice,
    webhooks,
    whatif,
)

ROUTERS: tuple[APIRouter, ...] = (
    meta.router,
    live.router,
    replay.router,
    stream.router,
    merchants.router,
    phone.router,
    precheck.router,
    cases.router,
    records.router,
    premium.router,
    webhooks.router,
    internal.router,
    media.router,
    ops.router,
    whatif.router,
    evals.router,
    ask.router,
    voice.router,
    fallback.router,
    grievances.router,
    consents.router,
    channel.router,
)

__all__ = ["ROUTERS"]
