"""In-process memory graph and precedent ranking (SPEC §14.6, §16).

`SimulatedMemoryGraph` is a networkx `MultiDiGraph`:
- nodes: `shop:{merchant}`, `zone:{zone}`, and one node per remembered fact typed by its kind —
  `event` (area trigger), `payout`, `dispute`, `case`, `decision`;
- edges: `shop -IN_ZONE-> zone`, `event -IN_ZONE-> zone`, `payout -PAID_FOR-> shop`,
  `payout -PAID_FOR-> event` (attrs `trigger_id`), `shop -DISPUTED-> dispute`,
  `dispute -DISPUTED-> decision` (attrs `decision_id`), `decision|case -DECIDED_BY-> shop`,
  `case -DECIDED_BY-> decision` (attrs `decision_id`), and `SIMILAR_TO` from a fact to the earlier
  facts of the same kind for the same shop.

`precedents()` ranks facts of the requested kind (or any) — same merchant 1.0, same zone 0.7, other
0.4; ties by most recent, then subject id (deterministic); the subject itself is excluded
(`exclude_subject_id`, e.g. the case the officer is looking at).
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import networkx as nx

from chhatri.clock import require_aware
from chhatri.integrations.base import MemoryFact, Precedent

SAME_MERCHANT_SCORE = 1.0  # SPEC §16
SAME_ZONE_SCORE = 0.7
OTHER_SCORE = 0.4
DEFAULT_LIMIT = 5
IN_ZONE, PAID_FOR, DISPUTED, DECIDED_BY, SIMILAR_TO = (
    "IN_ZONE",
    "PAID_FOR",
    "DISPUTED",
    "DECIDED_BY",
    "SIMILAR_TO",
)
NODE_TYPE_BY_KIND: Mapping[str, str] = MappingProxyType(
    {"trigger": "event", "payout": "payout", "dispute": "dispute", "case": "case", "decision": "decision"}
)


@dataclass(frozen=True, slots=True)
class StoredFact:
    node: str
    fact: MemoryFact


def fact_node(fact: MemoryFact) -> str:
    return f"{NODE_TYPE_BY_KIND.get(fact.kind, fact.kind)}:{fact.subject_id}"


def score_fact(fact: MemoryFact, merchant_id: str | None, zone_id: str | None) -> float:
    """SPEC §16 precedent score."""
    if merchant_id is not None and fact.merchant_id == merchant_id:
        return SAME_MERCHANT_SCORE
    if zone_id is not None and fact.zone_id == zone_id:
        return SAME_ZONE_SCORE
    return OTHER_SCORE


def rank_precedents(
    facts: list[MemoryFact],
    *,
    merchant_id: str | None,
    zone_id: str | None,
    kind: str | None,
    limit: int,
    exclude_subject_id: str | None,
) -> list[Precedent]:
    """Score, filter and order facts; shared by the in-process graph and the Cognee adapter."""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    scored = [
        (score_fact(fact, merchant_id, zone_id), fact)
        for fact in facts
        if (kind is None or fact.kind == kind) and fact.subject_id != exclude_subject_id
    ]
    scored.sort(key=lambda item: (-item[0], -item[1].at.timestamp(), item[1].subject_id))
    return [
        Precedent(subject_id=fact.subject_id, kind=fact.kind, at=fact.at, text=fact.text, score=score)
        for score, fact in scored[:limit]
    ]


class SimulatedMemoryGraph:
    """MemoryGraph backed by a networkx MultiDiGraph (thread-safe)."""

    def __init__(self) -> None:
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self._facts: dict[str, StoredFact] = {}
        self._by_shop_kind: dict[tuple[str, str], list[str]] = {}
        self._lock = threading.Lock()

    def facts(self) -> list[MemoryFact]:
        with self._lock:
            return [stored.fact for stored in self._facts.values()]

    async def remember(self, fact: MemoryFact) -> None:
        require_aware(fact.at)
        if not fact.subject_id or not fact.kind:
            raise ValueError("a memory fact needs a kind and a subject id")
        node = fact_node(fact)
        with self._lock:
            siblings = (
                self._by_shop_kind.setdefault((fact.merchant_id, fact.kind), []) if fact.merchant_id else []
            )
            earlier = [other for other in siblings if other != node]
            if node not in siblings and fact.merchant_id:
                siblings.append(node)
            self._facts[node] = StoredFact(node, fact)
            self.graph.add_node(
                node, type=NODE_TYPE_BY_KIND.get(fact.kind, fact.kind), at=fact.at, text=fact.text
            )
            self._link(node, fact)
            for other in earlier:
                self.graph.add_edge(node, other, key=SIMILAR_TO, relation=SIMILAR_TO)

    def _link(self, node: str, fact: MemoryFact) -> None:
        shop = f"shop:{fact.merchant_id}" if fact.merchant_id else None
        zone = f"zone:{fact.zone_id}" if fact.zone_id else None
        edges: list[tuple[str, str, str]] = []
        if shop and zone:
            edges.append((shop, zone, IN_ZONE))
        if fact.kind == "trigger" and zone:
            edges.append((node, zone, IN_ZONE))
        edges.extend(_kind_edges(node, fact, shop))
        for source, target, relation in edges:
            self._add_typed(source)
            self._add_typed(target)
            self.graph.add_edge(source, target, key=relation, relation=relation)

    def _add_typed(self, node: str) -> None:
        if node not in self.graph:
            self.graph.add_node(node, type=node.split(":", 1)[0])

    async def precedents(
        self,
        *,
        merchant_id: str | None = None,
        zone_id: str | None = None,
        kind: str | None = None,
        limit: int = DEFAULT_LIMIT,
        exclude_subject_id: str | None = None,
    ) -> list[Precedent]:
        return rank_precedents(
            self.facts(),
            merchant_id=merchant_id,
            zone_id=zone_id,
            kind=kind,
            limit=limit,
            exclude_subject_id=exclude_subject_id,
        )


def _attr(fact: MemoryFact, name: str) -> str | None:
    value = fact.attrs.get(name)
    return value if isinstance(value, str) and value else None


def _kind_edges(node: str, fact: MemoryFact, shop: str | None) -> list[tuple[str, str, str]]:
    trigger_id, decision_id = _attr(fact, "trigger_id"), _attr(fact, "decision_id")
    edges: list[tuple[str, str, str]] = []
    if fact.kind == "payout":
        edges += [(node, shop, PAID_FOR)] if shop else []
        edges += [(node, f"event:{trigger_id}", PAID_FOR)] if trigger_id else []
    elif fact.kind == "dispute":
        edges += [(shop, node, DISPUTED)] if shop else []
        edges += [(node, f"decision:{decision_id}", DISPUTED)] if decision_id else []
    elif fact.kind in ("decision", "case"):
        edges += [(node, shop, DECIDED_BY)] if shop else []
        edges += (
            [(node, f"decision:{decision_id}", DECIDED_BY)] if decision_id and fact.kind == "case" else []
        )
    return edges


def __getattr__(name: str) -> object:
    """Keep `chhatri.integrations.memory.CogneeMemoryGraph` importable (it lives in memory_cognee)."""
    if name == "CogneeMemoryGraph":
        from chhatri.integrations.memory_cognee import CogneeMemoryGraph

        return CogneeMemoryGraph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
