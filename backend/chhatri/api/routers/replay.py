"""Replay clock control (SPEC §19, §17.1, §24.6).

Every route answers with the ``ClockState`` of the runtime that is loaded *after* the action: a
backward seek and a reset reload the scenario, which replaces the runtime (SPEC §3). Control calls
are serialised with one lock so a double click cannot interleave two loads, and the runtime is
looked up inside the lock (409 ``no_scenario`` when nothing is loaded).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from chhatri.api.deps import StateDep, control_lock, get_runtime
from chhatri.api.envelope import ok
from chhatri.api.errors import ApiError
from chhatri.api.requests import LoadRequest, PlayRequest, SeekRequest, StepRequest
from chhatri.replay import views

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/replay", tags=["replay"])

LockDep = Annotated[asyncio.Lock, Depends(control_lock)]


@router.post("/load")
async def load(body: LoadRequest, state: StateDep, lock: LockDep) -> dict[str, Any]:
    """Load a scenario; resets ids, store, audit log and clock (SPEC §3, §17)."""
    async with lock:
        try:
            runtime = await state.load(body.scenario)
        except ValueError as exc:
            raise ApiError(422, "invalid request", fields={"scenario": "unknown scenario"}) from exc
        except (RuntimeError, OSError) as exc:
            raise _not_loadable(body.scenario, exc) from exc
        logger.info("scenario %s loaded", body.scenario)
        return ok(views.clock_view(runtime))


@router.post("/play")
async def play(state: StateDep, lock: LockDep, body: PlayRequest | None = None) -> dict[str, Any]:
    """Start the clock at ``speed`` sim minutes per real second (1..120; default: current speed)."""
    async with lock:
        await get_runtime(state).engine.play(body.speed if body else None)
        return ok(views.clock_view(get_runtime(state)))


@router.post("/pause")
async def pause(state: StateDep, lock: LockDep) -> dict[str, Any]:
    """Pause the clock."""
    async with lock:
        await get_runtime(state).engine.pause()
        return ok(views.clock_view(get_runtime(state)))


@router.post("/step")
async def step(body: StepRequest, state: StateDep, lock: LockDep) -> dict[str, Any]:
    """Advance ``minutes`` of simulated time, awaiting every effect (SPEC §24.6)."""
    async with lock:
        try:
            await get_runtime(state).engine.step(body.minutes)
        except ValueError as exc:
            raise ApiError(
                422, "invalid request", fields={"minutes": "beyond the end of the scenario"}
            ) from exc
        return ok(views.clock_view(get_runtime(state)))


@router.post("/seek")
async def seek(body: SeekRequest, state: StateDep, lock: LockDep) -> dict[str, Any]:
    """Jump to ``HH:MM``: forward steps, backward reloads then steps (SPEC §17.1)."""
    async with lock:
        try:
            await get_runtime(state).engine.seek(body.to)
        except ValueError as exc:
            raise ApiError(
                422, "invalid request", fields={"to": "outside the scenario's time window"}
            ) from exc
        return ok(views.clock_view(get_runtime(state)))


@router.post("/reset")
async def reset(state: StateDep, lock: LockDep) -> dict[str, Any]:
    """Reload the current scenario at its start, paused."""
    async with lock:
        name = get_runtime(state).scenario.name
        try:
            fresh = await state.load(name)
        except (RuntimeError, OSError) as exc:
            raise _not_loadable(name, exc) from exc
        return ok(views.clock_view(fresh))


def _not_loadable(name: str, exc: Exception) -> ApiError:
    """A scenario that cannot be built (e.g. model artefacts missing) is a 503, not a crash."""
    logger.error("scenario %s could not be loaded: %s", name, exc, exc_info=exc)
    return ApiError(503, f"scenario {name} could not be loaded; see /api/preflight")
