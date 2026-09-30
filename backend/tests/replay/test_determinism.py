"""Determinism and the clock on real runtimes (SPEC §0.2, §3, §17.1; binding decisions B1-B4)."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from chhatri.replay.state import AppState, Runtime
from chhatri.replay.static import StaticContext
from tests.replay.helpers import ANIL, GateSleep, StepClock, loaded, monsoon_at, slip_bytes


def fingerprint(rt: Runtime) -> dict:
    """Every id, amount and time the run produced, plus the audit chain head."""
    return {
        "decisions": [(d.id, d.claim_id, d.outcome, d.amount_paise, d.decided_at) for d in _decisions(rt)],
        "payouts": [
            (p.id, p.decision_id, p.amount_paise, p.created_at, p.credited_at) for p in rt.store.payouts()
        ],
        "pauses": [(p.id, p.merchant_id, p.instalment_date, p.created_at) for p in rt.store.pauses()],
        "cases": [(c.id, c.kind, c.status, c.decision_id) for c in rt.store.cases()],
        "messages": [(m.id, m.created_at, m.text_en, m.text_hi) for m in rt.store.messages(ANIL)],
        "audit": (len(rt.audit), rt.audit.head_hash()),
        "feed": [(i.id, i.at, i.text_en) for i in rt.feed.items()],
    }


def _decisions(rt: Runtime) -> list:
    return [d for m in rt.static.city.merchants for d in rt.store.decisions_for(m.id)]


async def test_two_independent_monsoon_replays_to_the_end_are_identical(static: StaticContext) -> None:
    first = await loaded(static, "monsoon", seek="20:00")
    second = await loaded(static, "monsoon", seek="20:00")
    assert first.clock.now() == second.clock.now() == monsoon_at(20)
    assert fingerprint(first) == fingerprint(second)
    assert first.audit.verify() == second.audit.verify() and first.audit.verify()["valid"] is True
    assert len(first.store.triggers()) == 3  # a zone triggers at most once a day (SPEC §8.2 (d))


async def test_two_independent_human_review_runs_are_identical(static: StaticContext) -> None:
    async def run() -> Runtime:
        rt = await loaded(static, "illness_mismatch", seek="11:21")
        await rt.conversation.handle_text(ANIL, "मैं अस्पताल में हूँ, बुखार है।")
        await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
        await rt.orchestrator.officer_decide("C-2291", approve=True, officer_id="officer", note="same person")
        await rt.engine.seek("13:00")
        return rt

    first, second = await run(), await run()
    assert fingerprint(first) == fingerprint(second)
    assert [c[:3] for c in fingerprint(first)["cases"]] == [
        ("C-2291", first.store.case("C-2291").kind, first.store.case("C-2291").status)
    ]


async def test_seeking_back_reloads_and_seeking_forward_again_reproduces_the_run(
    static: StaticContext, monsoon_1705: Runtime
) -> None:
    state = AppState(static)
    old = await state.load("monsoon")
    await old.engine.seek("17:05")
    await old.engine.seek("12:00")
    fresh = state.runtime
    assert fresh is not old and fresh.clock.now() == monsoon_at(12)
    assert fresh.store.triggers() == () and fresh.store.payouts() == ()
    assert old.clock.now() == monsoon_at(17, 5)  # the replaced runtime is left as it was
    await fresh.engine.seek("17:05")
    assert fingerprint(fresh) == fingerprint(monsoon_1705)


async def test_playing_a_real_runtime_paces_minutes_hours_and_hexes(static: StaticContext) -> None:
    sleep = GateSleep(wakes=8)
    state = AppState(static, sleep=sleep, monotonic=StepClock(0.25))
    rt = await state.load("monsoon")
    await rt.engine.play(60)  # 15 sim minutes per 250 ms wake
    assert rt.engine.running is True
    await asyncio.wait_for(sleep.blocked.wait(), timeout=30)
    await rt.engine.pause()
    assert rt.clock.now() == monsoon_at(10) and rt.engine.running is False
    hexes = [e.at for e in rt.bus.history() if e.type == "hexes"]
    assert hexes == [monsoon_at(8) + timedelta(minutes=15 * k) for k in range(1, 9)]
    zone_hours = sorted({e.at for e in rt.bus.history() if e.type == "zone"})
    assert zone_hours == [monsoon_at(9), monsoon_at(10)]
    ticks = [e for e in rt.bus.history() if e.type == "tick"]
    assert ticks[-1].data["clock"]["running"] is False and ticks[-1].data["clock"]["speed"] == 60.0
    assert rt.board.evaluated_at == monsoon_at(10)
