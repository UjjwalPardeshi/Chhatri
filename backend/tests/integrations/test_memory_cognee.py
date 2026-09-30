"""Cognee adapter with a fake cognee module; lazy-import fallback (SPEC §14.6, §0.1)."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from chhatri.clock import ist
from chhatri.integrations.base import IntegrationError, MemoryFact
from chhatri.integrations.memory_cognee import (
    CogneeMemoryGraph,
    cognee_unavailable_reason,
    load_cognee,
    render_fact,
    subject_ids,
)

T0 = ist(2025, 8, 19, 17, 0)


class FakeCognee:
    SearchType = SimpleNamespace(CHUNKS="CHUNKS")

    def __init__(self, *, fail_add: bool = False, fail_search: bool = False) -> None:
        self.added: list[tuple[str, str]] = []
        self.cognified: list[list[str]] = []
        self.searches: list[dict[str, Any]] = []
        self.fail_add, self.fail_search = fail_add, fail_search

    async def add(self, text: str, *, dataset_name: str) -> None:
        if self.fail_add:
            raise RuntimeError("llm down")
        self.added.append((text, dataset_name))

    async def cognify(self, *, datasets: list[str]) -> None:
        self.cognified.append(datasets)

    async def search(self, **kwargs: Any) -> list[dict[str, str]]:
        self.searches.append(kwargs)
        if self.fail_search:
            raise RuntimeError("graph db down")
        return [{"text": text} for text, _ in self.added]


def fact(subject: str, merchant: str, minutes: int) -> MemoryFact:
    return MemoryFact("case", subject, merchant, "Z7", T0 + timedelta(minutes=minutes), "officer approved")


async def test_remember_adds_and_cognifies_lazily() -> None:
    cognee = FakeCognee()
    graph = CogneeMemoryGraph(cognee)
    await graph.remember(fact("C-1", "S-0142", 0))
    await graph.remember(fact("C-2", "S-0001", 5))
    assert [d for _, d in cognee.added] == ["chhatri", "chhatri"] and cognee.cognified == []
    result = await graph.precedents(merchant_id="S-0142", zone_id="Z7", kind="case")
    assert [(p.subject_id, p.score) for p in result] == [("C-1", 1.0), ("C-2", 0.7)]
    assert cognee.cognified == [["chhatri"]]
    assert cognee.searches[0] == {
        "query_text": "past case shop S-0142 zone Z7",
        "query_type": "CHUNKS",
        "datasets": ["chhatri"],
    }
    await graph.precedents()
    assert cognee.cognified == [["chhatri"]]
    assert cognee.searches[1]["query_text"] == "past claims"


async def test_failures() -> None:
    failing_add = CogneeMemoryGraph(FakeCognee(fail_add=True))
    await failing_add.remember(fact("C-1", "S-0142", 0))  # logged; kept locally
    failing_search = CogneeMemoryGraph(FakeCognee(fail_search=True))
    with pytest.raises(IntegrationError, match="search failed"):
        await failing_search.precedents()


def test_render_and_tags() -> None:
    text = render_fact(fact("C-7", "S-0142", 0))
    assert text.startswith("[subject:C-7]") and "shop S-0142" in text and "zone Z7" in text
    assert subject_ids([{"text": text}, "[subject:P-000001] x"]) == {"C-7", "P-000001"}
    assert render_fact(MemoryFact("trigger", "E-Z7", None, None, T0, "t")).count("·") == 2


def test_availability_reasons(monkeypatch: pytest.MonkeyPatch) -> None:
    module = SimpleNamespace()
    assert cognee_unavailable_reason(False, module, {}) == "COGNEE_ENABLED is not true"  # type: ignore[arg-type]
    assert cognee_unavailable_reason(True, None, {"LLM_API_KEY": "x"}) == "cognee is not installed"
    assert "LLM_API_KEY" in (cognee_unavailable_reason(True, module, {}) or "")  # type: ignore[arg-type]
    assert cognee_unavailable_reason(True, module, {"LLM_API_KEY": "k"}) is None  # type: ignore[arg-type]
    monkeypatch.setitem(__import__("sys").modules, "cognee", None)
    assert load_cognee() is None
