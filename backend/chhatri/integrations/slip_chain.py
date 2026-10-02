"""The slip reader chain: Gemini vision, then Sarvam Vision, then REFERRED (ADR 0003, fs-02 sections 7.2 and 7.3.8).

Both readers implement the BUILT `SlipReader` protocol. A link is in the chain only when fully configured. The
simulated reader (the answer key embedded in the sample slips) answers only when no live link was actually called:
nothing configured, a Gemini key without a model id, the free-tier gate closed (ADR 0009) or every link forced off (X6).
It is never used after a live link failed, so a simulated read is never shown as the fallback of a live one. When
the live links fail the result has no value and provider `none`: the caller sends the merchant to the team.

Live providers receive the cleaned copy of the photo (no EXIF, XMP or PNG text chunk). The simulated reader receives
the original so that the sample slips keep working: its input never leaves the machine. The cleaning is card 4.2's
job; here `image` is what a provider may see and `original` what only the simulator may.

`read_slip` keeps the BUILT signature for compatibility. `read_with_label` returns the read with its H26 label, as the
pre-check service (card 4.2) needs. Nothing calls either yet.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Collection, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Final

from chhatri.ai.chain import ChainResult, Clock, Fallback, Gate, Link, Rejection, run_chain
from chhatri.ai.labels import AiProvider, FallbackReason
from chhatri.config import Settings
from chhatri.domain.models import SlipExtraction
from chhatri.integrations.base import IntegrationError, SlipReader
from chhatri.integrations.free_tier import free_tier_allowed
from chhatri.integrations.retry import DEFAULT_TIMEOUT_S, DOC_AI_TIMEOUT_S

INTEGRATION = "slip_chain"
GEMINI_VISION: Final = "gemini_vision"  # the status names: the keys of the data gate and of the X6 switch
SARVAM_VISION: Final = "sarvam_vision"
NO_READ: Final[Fallback[SlipExtraction]] = Fallback(AiProvider.NONE)
# The BUILT bounds, for the compatibility call: 10 s by default and 60 s for Sarvam doc-ai.
DEFAULT_LINK_TIMEOUTS: Final[Mapping[AiProvider, float]] = {
    AiProvider.GEMINI: DEFAULT_TIMEOUT_S,
    AiProvider.SARVAM: DOC_AI_TIMEOUT_S,
}


def _no_forced() -> Collection[str]:
    return frozenset()


@dataclass(frozen=True, slots=True)
class ReaderLink:
    """One slip reader as configured. `adapter` is None when left out; `missing` then says why."""

    provider: AiProvider
    component: str
    model: str | None
    adapter: SlipReader | None
    missing: FallbackReason | None = None


@dataclass(frozen=True, slots=True)
class SlipChain:
    links: tuple[ReaderLink, ...]
    simulated: SlipReader
    gate: Gate
    forced_source: Callable[[], Collection[str]] = _no_forced  # the X6 switch, read on every call

    async def read_with_label(
        self,
        image: bytes,
        mime_type: str,
        *,
        timeout_s: float,
        original: bytes | None = None,
        original_mime_type: str | None = None,
        accept: Callable[[SlipExtraction], Rejection | None] | None = None,
        forced: Collection[str] = frozenset(),
        link_timeouts: Mapping[AiProvider, float] | None = None,
        total_timeout_s: float | None = None,
        clock: Clock = time.monotonic,
    ) -> ChainResult[SlipExtraction]:
        """Read `image` with the live links in order. `value` is the first accepted read; with no live link called it
        is the simulated reader's read of `original` (default `image`); after live failures it is None (provider
        `none`). `accept` is the caller's validator: a refused read is a failed link, and a `stop` rejection
        (an injected slip) ends the chain because the same image would hit every later provider."""
        links = [
            Link(
                link.provider,
                link.component,
                link.model,
                _bind(link.adapter, image, mime_type),
                link.missing,
            )
            for link in self.links
        ]
        offline = Fallback(
            AiProvider.SIMULATED,
            partial(self.simulated.read_slip, original or image, original_mime_type or mime_type),
        )
        return await run_chain(
            links,
            gate=self.gate,
            timeout_s=timeout_s,
            fallback=NO_READ,
            offline_fallback=offline,
            accept=accept,
            forced=frozenset(forced) | frozenset(self.forced_source()),
            link_timeouts=link_timeouts,
            total_timeout_s=total_timeout_s,
            clock=clock,
        )

    async def read_slip(self, image: bytes, mime_type: str) -> SlipExtraction:
        """The BUILT `SlipReader` call: the read, or an `IntegrationError` when no reader could read the slip."""
        result = await self.read_with_label(
            image, mime_type, timeout_s=DEFAULT_TIMEOUT_S, link_timeouts=DEFAULT_LINK_TIMEOUTS
        )
        if result.value is None:
            raise IntegrationError(INTEGRATION, "no reader could read the slip")
        return result.value


def _bind(
    adapter: SlipReader | None, image: bytes, mime_type: str
) -> Callable[[], Awaitable[SlipExtraction]] | None:
    return None if adapter is None else partial(adapter.read_slip, image, mime_type)


def build_slip_chain(
    settings: Settings,
    *,
    gemini: SlipReader | None,
    sarvam: SlipReader | None,
    simulated: SlipReader,
    forced_source: Callable[[], Collection[str]] = _no_forced,
) -> SlipChain:
    """The chain for `settings`: `gemini` and `sarvam` are the live readers (None when not configured)."""
    gemini_missing = FallbackReason.MODEL_NOT_SET if settings.gemini_key_set else FallbackReason.NO_KEY
    return SlipChain(
        links=(
            ReaderLink(
                AiProvider.GEMINI,
                GEMINI_VISION,
                (settings.gemini_vision_model_id or None) if gemini is not None else None,
                gemini,
                None if gemini is not None else gemini_missing,
            ),
            ReaderLink(
                AiProvider.SARVAM,
                SARVAM_VISION,
                None,  # Sarvam doc-ai has no model id to echo
                sarvam,
                None if sarvam is not None else FallbackReason.NO_KEY,
            ),
        ),
        simulated=simulated,
        gate=partial(free_tier_allowed, settings=settings),
        forced_source=forced_source,
    )
