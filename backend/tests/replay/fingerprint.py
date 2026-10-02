"""Everything a read-only call must leave alone: audit log, id counters, store, feed and event bus.

`fingerprint(rt)` captures it all as plain comparable values. The ops summary (H8) and the what-if call (H24)
promise to write nothing, and their tests compare the fingerprint before and after many calls.
"""

from __future__ import annotations

from typing import Any

from chhatri.replay.state import Runtime

DEMO_MERCHANTS = ("S-0142", "S-0907")  # Anil and Ramesh: the two shops the conversations run for


def fingerprint(rt: Runtime) -> dict[str, Any]:
    """A snapshot of the state a read-only route must not change."""
    store = rt.store
    return {
        "audit": (len(rt.audit), rt.audit.verify()["head_hash"]),
        "ids": (dict(rt.ids._counters), rt.ids._next_case),  # noqa: SLF001 - the counters are the point
        "store": {
            "claims": store.claims(),
            "decisions": store.decisions(),
            "payouts": store.payouts(),
            "pauses": store.pauses(),
            "holiday_requests": store.holiday_requests(),
            "cases": store.cases(),
            "triggers": store.triggers(),
            "premiums": store.premiums(),
            "covers": dict(store.covers()),
            "messages": {mid: store.messages(mid) for mid in DEMO_MERCHANTS},
        },
        "feed": rt.feed.items(),
        "bus": [event.id for event in rt.bus.history()],
        "board": (dict(rt.board.states), rt.board.triggered, rt.board.evaluated_at),
        "clock": rt.clock.now(),
    }
