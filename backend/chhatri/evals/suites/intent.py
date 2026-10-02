"""S1 intent routing, part A (plan section 4.1): the keyword rules on text their authors did not write."""

from __future__ import annotations

from typing import Final

from chhatri.conversation.explain_first import explain_first
from chhatri.conversation.intents import Intent, classify
from chhatri.evals.fixtures import load_rows, select_split
from chhatri.evals.metrics import MetricSpec, measured_metric
from chhatri.evals.suites import SuiteResult

GROUNDED: Final = "GROUNDED"
WRITE_ROUTES: Final = frozenset({Intent.DISPUTE_AMOUNT.value, Intent.BUY_COVER.value})
PROVIDER: Final = {"component": "intent_rules", "mode": "RULES", "provider": "rules", "model": None}
ACCURACY = MetricSpec("intent.route_accuracy", "Messages routed as labelled")
WRITE_MISROUTE = MetricSpec(
    "intent.write_misroute",
    "Messages that reached a write handler without a write risk",
    "at_most",
    0,
    "proposed",
)
SEEDED = MetricSpec(
    "intent.explain_first_seeded",
    "Seeded coverage questions that reach the grounded path",
    "all",
    6,
    "fs-05 section 2.2",
)
RECALL = MetricSpec("intent.explain_first_recall", "Grounded questions that reach the grounded path")


def route_of(text: str) -> str:
    """The route the built code takes with N2 on: a rule intent, or the model path (GROUNDED) for UNKNOWN text and for
    a question about a rule (explain-first routing, N2.7)."""
    intent = classify(text)
    return GROUNDED if intent is Intent.UNKNOWN or explain_first(text, intent) else intent.value


def run(split: str = "all") -> SuiteResult:
    rows = select_split(load_rows("intents.jsonl"), split)
    items = tuple(
        {
            "id": r["id"],
            "expected": r["expected_route"],
            "route": (route := route_of(r["text"])),
            "ok": route == r["expected_route"],
        }
        for r in rows
    )
    by_id = {r["id"]: r for r in rows}
    unsafe = [i for i in items if not by_id[i["id"]]["write_risk"]]
    seeded = [i for i in items if by_id[i["id"]]["source"] == "misroute"]
    grounded = [i for i in items if i["expected"] == GROUNDED]
    metrics = (
        measured_metric(ACCURACY, sum(i["ok"] for i in items), len(items), split=split),
        measured_metric(
            WRITE_MISROUTE, sum(i["route"] in WRITE_ROUTES for i in unsafe), len(unsafe), split=split
        ),
        measured_metric(SEEDED, sum(i["route"] == GROUNDED for i in seeded), len(seeded), split=split),
        measured_metric(RECALL, sum(i["route"] == GROUNDED for i in grounded), len(grounded), split=split),
    )
    return SuiteResult("intent", "MEASURED", None, metrics, items, (PROVIDER,))
