"""networkx memory graph and SPEC §16 precedent ranking."""

from __future__ import annotations

from datetime import timedelta

import pytest

from chhatri.clock import ist
from chhatri.integrations.base import MemoryFact
from chhatri.integrations.memory import (
    DECIDED_BY,
    DISPUTED,
    IN_ZONE,
    PAID_FOR,
    SIMILAR_TO,
    SimulatedMemoryGraph,
    rank_precedents,
)

T0 = ist(2025, 8, 19, 17, 0)


def fact(
    kind: str, subject: str, merchant: str | None, zone: str | None, minutes: int = 0, **attrs: str
) -> MemoryFact:
    return MemoryFact(
        kind=kind,
        subject_id=subject,
        merchant_id=merchant,
        zone_id=zone,
        at=T0 + timedelta(minutes=minutes),
        text=f"{kind} {subject}",
        attrs=attrs,
    )


async def test_graph_nodes_and_edges() -> None:
    graph = SimulatedMemoryGraph()
    await graph.remember(fact("trigger", "E-Z7-20250819", None, "Z7"))
    await graph.remember(fact("decision", "D-000001", "S-0142", "Z7"))
    await graph.remember(fact("payout", "P-000001", "S-0142", "Z7", 4, trigger_id="E-Z7-20250819"))
    await graph.remember(fact("dispute", "C-2291", "S-0142", "Z7", 12, decision_id="D-000001"))
    await graph.remember(fact("case", "C-2292", "S-0142", "Z7", 13, decision_id="D-000001"))
    await graph.remember(fact("payout", "P-000002", "S-0142", "Z7", 20))
    g = graph.graph
    edges = {(u, v, k) for u, v, k in g.edges(keys=True)}
    assert ("shop:S-0142", "zone:Z7", IN_ZONE) in edges
    assert ("event:E-Z7-20250819", "zone:Z7", IN_ZONE) in edges
    assert ("payout:P-000001", "shop:S-0142", PAID_FOR) in edges
    assert ("payout:P-000001", "event:E-Z7-20250819", PAID_FOR) in edges
    assert ("shop:S-0142", "dispute:C-2291", DISPUTED) in edges
    assert ("dispute:C-2291", "decision:D-000001", DISPUTED) in edges
    assert ("decision:D-000001", "shop:S-0142", DECIDED_BY) in edges
    assert ("case:C-2292", "decision:D-000001", DECIDED_BY) in edges
    assert ("payout:P-000002", "payout:P-000001", SIMILAR_TO) in edges
    assert {g.nodes[n]["type"] for n in g.nodes} == {
        "shop",
        "zone",
        "event",
        "payout",
        "dispute",
        "case",
        "decision",
    }


async def test_precedent_scores_ties_and_exclusion() -> None:
    graph = SimulatedMemoryGraph()
    await graph.remember(fact("case", "C-1", "S-0142", "Z7", 0))
    await graph.remember(fact("case", "C-2", "S-0001", "Z7", 5))
    await graph.remember(fact("case", "C-3", "S-0002", "Z3", 10))
    await graph.remember(fact("case", "C-4", "S-0142", "Z7", 20))
    await graph.remember(fact("case", "C-5", "S-0003", "Z7", 5))
    await graph.remember(fact("payout", "P-1", "S-0142", "Z7", 30))
    result = await graph.precedents(merchant_id="S-0142", zone_id="Z7", kind="case", exclude_subject_id="C-4")
    assert [(p.subject_id, p.score) for p in result] == [
        ("C-1", 1.0),
        ("C-2", 0.7),
        ("C-5", 0.7),
        ("C-3", 0.4),
    ]
    limited = await graph.precedents(zone_id="Z3", limit=2)
    assert [p.subject_id for p in limited] == ["C-3", "P-1"]
    assert [p.score for p in limited] == [0.7, 0.4]


async def test_remember_is_idempotent_per_subject_and_validates() -> None:
    graph = SimulatedMemoryGraph()
    await graph.remember(fact("payout", "P-1", "S-0142", "Z7"))
    await graph.remember(fact("payout", "P-1", "S-0142", "Z7"))
    assert len(graph.facts()) == 1
    assert not any(k == SIMILAR_TO for *_, k in graph.graph.edges(keys=True))
    with pytest.raises(ValueError):
        await graph.remember(fact("payout", "", "S-0142", "Z7"))
    with pytest.raises(ValueError):
        await graph.remember(MemoryFact("payout", "P-9", None, None, T0.replace(tzinfo=None), "naive"))


def test_rank_precedents_rejects_negative_limit() -> None:
    with pytest.raises(ValueError):
        rank_precedents([], merchant_id=None, zone_id=None, kind=None, limit=-1, exclude_subject_id=None)


def test_cognee_class_still_importable_from_memory() -> None:
    from chhatri.integrations import memory, memory_cognee

    assert memory.CogneeMemoryGraph is memory_cognee.CogneeMemoryGraph
    with pytest.raises(AttributeError):
        memory.DoesNotExist  # noqa: B018
