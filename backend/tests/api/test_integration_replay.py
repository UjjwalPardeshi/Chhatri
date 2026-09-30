"""Replay clock control through HTTP on the REAL AppState (SPEC §17.1, §19, §24.6).

Play runs the background clock in real time, so these tests use short real waits at high speed;
seek backwards reloads the scenario (fresh ids, store and audit, SPEC §3) and replays forward
deterministically, which the audit head hash proves over HTTP.
"""

from __future__ import annotations

import asyncio
from typing import Final

from httpx import AsyncClient

from chhatri.api.schemas import AuditEntry, AuditVerify, Case, ClockState, MerchantDetail, StateSnapshot
from tests.api.helpers import data_of, error_of, list_of

PLAY_SPEED: Final = 120.0
PLAY_WAIT_S: Final = 0.6  # > 2 wake-ups of 250 ms at 120 sim min/s: well over an hour of replay
ANIL: Final = "S-0142"


async def post_clock(http: AsyncClient, path: str, body: dict | None = None) -> ClockState:
    return data_of(await http.post(f"/api/replay/{path}", json=body), ClockState)


async def wait_paused(http: AsyncClient, polls: int = 50) -> ClockState:
    """Poll /api/state until the clock has paused itself (at most `polls` × 0.1 s)."""
    for _ in range(polls):
        clock = data_of(await http.get("/api/state"), StateSnapshot).clock
        if not clock.running:
            return clock
        await asyncio.sleep(0.1)
    raise AssertionError("the replay clock never paused")


async def test_play_pause_and_the_api_stays_responsive(real_client: AsyncClient) -> None:
    await post_clock(real_client, "load", {"scenario": "monsoon"})
    started = await post_clock(real_client, "play", {"speed": PLAY_SPEED})
    assert (started.running, started.speed) == (True, PLAY_SPEED)
    await asyncio.sleep(PLAY_WAIT_S)
    during = data_of(await real_client.get("/api/state"), StateSnapshot)
    assert during.clock.running is True and during.clock.now > started.now
    paused = await post_clock(real_client, "pause")
    assert paused.running is False
    await asyncio.sleep(PLAY_WAIT_S)
    still = data_of(await real_client.get("/api/state"), StateSnapshot)
    assert still.clock.now == paused.now


async def test_play_to_the_end_pauses_itself(real_client: AsyncClient) -> None:
    await post_clock(real_client, "load", {"scenario": "buy_cover"})  # 18:00 → 19:00
    await post_clock(real_client, "play", {"speed": PLAY_SPEED})
    clock = await wait_paused(real_client)
    assert (clock.running, clock.now) == (False, clock.end)
    ignored = await post_clock(real_client, "play")
    assert ignored.running is False


async def test_seek_back_reloads_and_replays_to_the_same_audit_chain(real_client: AsyncClient) -> None:
    await post_clock(real_client, "load", {"scenario": "monsoon"})
    await post_clock(real_client, "seek", {"to": "17:06"})
    first = data_of(await real_client.get("/api/audit/verify"), AuditVerify)
    await real_client.post(f"/api/merchants/{ANIL}/messages", json={"text": "मेरा नुकसान ज़्यादा हुआ।"})
    assert [c.id for c in list_of(await real_client.get("/api/cases"), Case)[0]] == ["C-2291"]
    back = await post_clock(real_client, "seek", {"to": "09:00"})
    assert back.now == "2025-08-19T09:00:00+05:30"
    assert list_of(await real_client.get("/api/cases"), Case)[0] == []
    entries, _ = list_of(await real_client.get("/api/audit?after=0&limit=5"), AuditEntry)
    assert entries[0].seq == 1 and entries[0].action == "scenario.loaded"
    await post_clock(real_client, "seek", {"to": "17:06"})
    again = data_of(await real_client.get("/api/audit/verify"), AuditVerify)
    assert (again.valid, again.entries, again.head_hash) == (True, first.entries, first.head_hash)


async def test_reset_and_step(real_client: AsyncClient) -> None:
    await post_clock(real_client, "load", {"scenario": "illness"})
    stepped = await post_clock(real_client, "step", {"minutes": 50})
    assert stepped.now == "2025-08-21T11:20:00+05:30"
    reset = await post_clock(real_client, "reset")
    assert (reset.now, reset.running) == (reset.start, False)


async def test_invalid_clock_requests_are_422(real_client: AsyncClient) -> None:
    await post_clock(real_client, "load", {"scenario": "buy_cover"})
    for path, body, field in (
        ("seek", {"to": "07:00"}, "to"),
        ("seek", {"to": "7pm"}, "to"),
        ("step", {"minutes": 61}, "minutes"),
        ("step", {"minutes": 0}, "minutes"),
        ("play", {"speed": 0}, "speed"),
        ("play", {"speed": 121}, "speed"),
    ):
        error = error_of(await real_client.post(f"/api/replay/{path}", json=body), 422, "validation_error")
        assert field in error.fields, (path, body)


async def test_a_claim_decided_at_the_end_is_still_paid_on_time(real_client: AsyncClient) -> None:
    """illness ends at 13:00 (SPEC §17.2); a slip sent then is paid at 13:04 and paused at 13:05 (B1)."""
    await post_clock(real_client, "load", {"scenario": "illness"})
    end = await post_clock(real_client, "seek", {"to": "13:00"})
    assert end.now == end.end
    await real_client.post(f"/api/merchants/{ANIL}/voice-demo", json={"key": "ill"})
    await real_client.post(f"/api/merchants/{ANIL}/photo", json={})
    settled = await post_clock(real_client, "play", {"speed": PLAY_SPEED})
    assert settled.running is True
    clock = await wait_paused(real_client)
    assert (clock.running, clock.now) == (False, "2025-08-21T13:05:00+05:30")
    detail = data_of(await real_client.get(f"/api/merchants/{ANIL}"), MerchantDetail)
    assert [(p.status, p.credited_at) for p in detail.payouts] == [("CREDITED", "2025-08-21T13:04:00+05:30")]
    error = error_of(await real_client.post("/api/replay/step", json={"minutes": 1}), 422, "validation_error")
    assert "minutes" in error.fields
