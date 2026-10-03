"""The Ask chat chain: Gemini chat, then Sarvam chat, then the caller's template (ADR 0003, fs-05 sections 4 and 10).

Both providers implement the BUILT `ChatModel` protocol. A link is in the chain only when fully configured: Sarvam
needs `SARVAM_API_KEY`, Gemini needs `GOOGLE_API_KEY` and a model id in `GEMINI_MODEL`; a Gemini key without a model
id leaves Gemini out and the label says MODEL_NOT_SET when nothing else is left. Every free-tier link is asked of the
data gate first (ADR 0009). The result is the reply plus the H26 label (`mode`, `provider`, `model`, `fallback_reason`,
`attempts`); a model failure is never an exception, the caller gets a label and builds its template. No provider
output sets money (ADR 0001): the caller's `accept` check (schema extras, clause ids, the guard) runs on every reply,
and a refused reply is a failed link.

Nothing calls this yet: the Ask service (card 4.3) and the voice routes (card 4.4) do. Per-link budgets are the
caller's, set in the Wave 2 rehearsal (`timeout_s`, `link_timeouts`, `total_timeout_s`).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any, Final

from chhatri.ai.chain import ChainResult, Clock, Fallback, Gate, Link, Rejection, run_chain
from chhatri.ai.labels import AiProvider, FallbackReason
from chhatri.config import Settings
from chhatri.integrations.base import ChatModel
from chhatri.integrations.free_tier import free_tier_allowed
from chhatri.integrations.sarvam_chat import check_schema

GEMINI_CHAT: Final = "gemini_chat"  # the status names: the keys of the data gate and of the X6 switch
SARVAM_CHAT: Final = "sarvam_chat"
TEMPLATE_FALLBACK: Final[Fallback[dict[str, Any]]] = Fallback(AiProvider.TEMPLATE)


def _no_forced() -> Collection[str]:
    return frozenset()


@dataclass(frozen=True, slots=True)
class ChatLink:
    """One chat provider as configured: who, under which component name, with which model, and its adapter.

    `adapter` is None when the link is left out; `missing` then says why (NO_KEY or MODEL_NOT_SET).
    """

    provider: AiProvider
    component: str
    model: str | None
    adapter: ChatModel | None
    missing: FallbackReason | None = None


@dataclass(frozen=True, slots=True)
class ChatChain:
    links: tuple[ChatLink, ...]
    gate: Gate
    forced_source: Callable[[], Collection[str]] = _no_forced  # the X6 switch, read on every call

    async def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        schema_name: str,
        timeout_s: float,
        fallback: Fallback[dict[str, Any]] = TEMPLATE_FALLBACK,
        accept: Callable[[dict[str, Any]], Rejection | None] | None = None,
        forced: Collection[str] = frozenset(),
        link_timeouts: Mapping[AiProvider, float] | None = None,
        total_timeout_s: float | None = None,
        clock: Clock = time.monotonic,
    ) -> ChainResult[dict[str, Any]]:
        """Ask the links in order. `value` is the first accepted reply, else what `fallback` makes (None for a plain
        template: the caller builds it from `label`). `timeout_s` is each link's budget, `forced` the components the
        presenter switched off (X6), `accept` the caller's check of a reply (schema extras, guard)."""
        if not schema_name.strip():
            raise ValueError("schema_name is required")
        check_schema(schema)
        links = [
            Link(
                link.provider,
                link.component,
                link.model,
                _bind(link.adapter, system, user, schema, schema_name),
                link.missing,
            )
            for link in self.links
        ]
        return await run_chain(
            links,
            gate=self.gate,
            timeout_s=timeout_s,
            fallback=fallback,
            accept=accept,
            forced=frozenset(forced) | frozenset(self.forced_source()),
            link_timeouts=link_timeouts,
            total_timeout_s=total_timeout_s,
            clock=clock,
        )


def _bind(
    adapter: ChatModel | None, system: str, user: str, schema: dict[str, Any], schema_name: str
) -> Callable[[], Awaitable[dict[str, Any]]] | None:
    return (
        None
        if adapter is None
        else partial(adapter.complete_json, system, user, schema, schema_name=schema_name)
    )


def build_chat_chain(
    settings: Settings,
    *,
    gemini: ChatModel | None,
    sarvam: ChatModel | None,
    forced_source: Callable[[], Collection[str]] = _no_forced,
    gemini_backups: Sequence[ChatModel] = (),
) -> ChatChain:
    """The chain for `settings`: `gemini` and `sarvam` are the live adapters, None when not configured, and
    `gemini_backups` the GEMINI_BACKUP_MODELS adapters, asked after the main model (same component, so the X6
    switch turns them off together)."""
    gemini_missing = FallbackReason.MODEL_NOT_SET if settings.gemini_key_set else FallbackReason.NO_KEY
    backups = tuple(
        ChatLink(AiProvider.GEMINI, GEMINI_CHAT, getattr(b, "model", None), b) for b in gemini_backups
    )
    return ChatChain(
        links=(
            ChatLink(
                AiProvider.GEMINI,
                GEMINI_CHAT,
                (settings.gemini_chat_model_id or None) if gemini is not None else None,
                gemini,
                None if gemini is not None else gemini_missing,
            ),
            *backups,
            ChatLink(
                AiProvider.SARVAM,
                SARVAM_CHAT,
                settings.sarvam_chat_model if sarvam is not None else None,
                sarvam,
                None if sarvam is not None else FallbackReason.NO_KEY,
            ),
        ),
        gate=partial(free_tier_allowed, settings=settings),
        forced_source=forced_source,
    )
