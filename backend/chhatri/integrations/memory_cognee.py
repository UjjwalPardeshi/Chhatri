"""Cognee-backed memory behind the MemoryGraph interface (SPEC §14.6, §0.1; optional extra `memory`).

Live only when `COGNEE_ENABLED=true`, the `cognee` package imports, and an LLM is configured for it
(`LLM_API_KEY`, cognee's own setting). Facts are written with `cognee.add` (tagged
`[subject:<id>]`), `cognee.cognify` runs lazily before the next search (not once per fact — a monsoon
replay writes hundreds of facts), and `cognee.search` retrieves candidate facts that are then ranked by
the SPEC §16 rules. Every fact is also kept in the in-process graph, so the ranking data never depends
on what Cognee returns verbatim. A failed `add` is logged and the fact stays in the local graph; a
failed search raises IntegrationError.
"""

from __future__ import annotations

import importlib
import logging
import re
from collections.abc import Mapping
from types import ModuleType
from typing import Any

from chhatri.integrations.base import IntegrationError, MemoryFact, Precedent
from chhatri.integrations.memory import DEFAULT_LIMIT, SimulatedMemoryGraph, rank_precedents

logger = logging.getLogger(__name__)

INTEGRATION = "memory"
COGNEE_DATASET = "chhatri"
LLM_KEY_ENV = "LLM_API_KEY"
_SUBJECT_TAG = re.compile(r"\[subject:([A-Za-z0-9_:\-]+)\]")


def load_cognee() -> ModuleType | None:
    """Import cognee lazily; None when the optional extra is not installed."""
    try:
        return importlib.import_module("cognee")
    except ImportError:
        logger.info("cognee is not installed; memory stays in-process")
        return None


def cognee_unavailable_reason(enabled: bool, module: ModuleType | None, env: Mapping[str, str]) -> str | None:
    """None when Cognee can run live, otherwise the reason shown in the integration badge."""
    if not enabled:
        return "COGNEE_ENABLED is not true"
    if module is None:
        return "cognee is not installed"
    if not env.get(LLM_KEY_ENV, "").strip():
        return f"no LLM configured for cognee ({LLM_KEY_ENV})"
    return None


def render_fact(fact: MemoryFact) -> str:
    parts = [f"[subject:{fact.subject_id}]", f"{fact.kind} at {fact.at.isoformat()}"]
    if fact.merchant_id:
        parts.append(f"shop {fact.merchant_id}")
    if fact.zone_id:
        parts.append(f"zone {fact.zone_id}")
    parts.append(fact.text)
    return " · ".join(parts)


def subject_ids(results: Any) -> set[str]:
    """Subject tags mentioned anywhere in Cognee search results."""
    return set(_SUBJECT_TAG.findall(str(results)))


class CogneeMemoryGraph:
    """MemoryGraph using Cognee for retrieval and the SPEC §16 rules for ranking."""

    def __init__(self, cognee: Any, *, dataset: str = COGNEE_DATASET) -> None:
        self._cognee = cognee
        self._dataset = dataset
        self._local = SimulatedMemoryGraph()
        self._pending_cognify = False

    async def remember(self, fact: MemoryFact) -> None:
        await self._local.remember(fact)
        try:
            await self._cognee.add(render_fact(fact), dataset_name=self._dataset)
        except Exception as exc:
            logger.error(
                "cognee add failed for %s (%s); kept in-process only", fact.subject_id, type(exc).__name__
            )
            return
        self._pending_cognify = True

    async def precedents(
        self,
        *,
        merchant_id: str | None = None,
        zone_id: str | None = None,
        kind: str | None = None,
        limit: int = DEFAULT_LIMIT,
        exclude_subject_id: str | None = None,
    ) -> list[Precedent]:
        candidates = await self._search(merchant_id, zone_id, kind)
        facts = [fact for fact in self._local.facts() if fact.subject_id in candidates]
        return rank_precedents(
            facts,
            merchant_id=merchant_id,
            zone_id=zone_id,
            kind=kind,
            limit=limit,
            exclude_subject_id=exclude_subject_id,
        )

    async def _search(self, merchant_id: str | None, zone_id: str | None, kind: str | None) -> set[str]:
        query = " ".join(
            part
            for part in (
                f"past {kind or 'claims'}",
                f"shop {merchant_id}" if merchant_id else "",
                f"zone {zone_id}" if zone_id else "",
            )
            if part
        )
        try:
            if self._pending_cognify:
                await self._cognee.cognify(datasets=[self._dataset])
                self._pending_cognify = False
            results = await self._cognee.search(
                query_text=query, query_type=self._cognee.SearchType.CHUNKS, datasets=[self._dataset]
            )
        except Exception as exc:
            logger.error("cognee search failed (%s)", type(exc).__name__)
            raise IntegrationError(INTEGRATION, "cognee search failed") from exc
        return subject_ids(results)
