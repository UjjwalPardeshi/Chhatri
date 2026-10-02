"""Request and response shapes of Ask Chhatri (N2) and voice (N4): data-model sections 5.2 and 5.11.

Responses are frozen and strict, like every schema in this package; the routes build them from the service's plain
results, so a drift between the code and the contract fails a test instead of reaching the client.
"""

from __future__ import annotations

from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from chhatri.ai.labels import AiLabel
from chhatri.api.schemas.base import Schema
from chhatri.api.schemas.receipt import SourceView
from chhatri.ask.facts import Fact
from chhatri.ask.mentions import Mention
from chhatri.ask.types import MAX_QUESTION_CHARS, AskAnswer
from chhatri.ask.voice import MAX_TRANSCRIPT_CHARS, SttResult, TtsResult
from chhatri.replay.view_records import iso_or_none

__all__ = [
    "AskRequest",
    "AskResponse",
    "SttBrowserRequest",
    "SttResponse",
    "TtsRequest",
    "TtsResponse",
    "ask_response",
    "stt_response",
    "tts_response",
]

MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"
ASK_ID_PATTERN: Final = r"^AQ-\d{6,}$"
STT_ID_PATTERN: Final = r"^ST-\d{6,}$"
MENTION_ID_PATTERN: Final = r"^m\d{1,3}$"
LANGUAGE_CODE_PATTERN: Final = r"^(unknown|[a-z]{2,3}-[A-Z]{2})$"
MAX_CONFIRMED: Final = 50


class _Body(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class AskRequest(_Body):
    """POST /api/merchants/{id}/ask. `question` is 1 to 500 characters after trimming and is untrusted text (H16)."""

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    lang: Literal["hi", "en"] | None = None
    stt_id: str | None = Field(default=None, pattern=STT_ID_PATTERN)
    confirmed_mentions: list[Annotated[str, StringConstraints(pattern=MENTION_ID_PATTERN)]] | None = Field(
        default=None, max_length=MAX_CONFIRMED
    )


class SttBrowserRequest(_Body):
    """POST /api/voice/stt as JSON: the browser recognised the speech and the server never sees audio."""

    merchant_id: str = Field(pattern=MERCHANT_ID_PATTERN)
    transcript: str = Field(min_length=1, max_length=MAX_TRANSCRIPT_CHARS)
    source: Literal["browser"]
    language_code: str | None = Field(default=None, pattern=LANGUAGE_CODE_PATTERN)


class TtsRequest(_Body):
    """POST /api/voice/tts: only the answer of an earlier ask can be voiced."""

    merchant_id: str = Field(pattern=MERCHANT_ID_PATTERN)
    ask_id: str = Field(pattern=ASK_ID_PATTERN)
    lang: Literal["hi", "en"]


class AttemptView(Schema):
    provider: str
    outcome: str
    ms: int = Field(ge=0)


class LabelFields(Schema):
    """The H26 label (data-model 5.0) every AI-backed response carries."""

    mode: Literal["LIVE", "FALLBACK", "SIMULATED"]
    provider: Literal["rules", "gemini", "sarvam", "template", "simulated", "mock", "browser", "none"]
    model: str | None
    fallback_reason: str | None


class ClauseView(Schema):
    id: str = Field(pattern=r"^C\d{1,2}(\.\d)?$")
    title: str


class FactView(Schema):
    key: str
    label_hi: str
    label_en: str
    value: str
    sources: list[SourceView] = Field(min_length=1)


class NextActionView(Schema):
    kind: Literal[
        "SEE_CLAIM",
        "SEE_COVER",
        "GET_COVER",
        "SEND_SLIP",
        "TRACK_CASE",
        "OPEN_CONSENTS",
        "TALK_TO_TEAM",
        "ASK_AGAIN",
    ]
    label_hi: str
    label_en: str


class AskResponse(LabelFields):
    ask_id: str = Field(pattern=ASK_ID_PATTERN)
    intent: Literal[
        "WHY_AMOUNT",
        "DISPUTE_AMOUNT",
        "REPORT_ILLNESS",
        "BUY_COVER",
        "COVER_STATUS",
        "GREETING",
        "AFFIRM",
        "DENY",
        "UNKNOWN",
    ]
    intent_source: Literal["rules"]
    lang: Literal["hi", "en"]
    answer: str
    answer_en: str
    clauses: list[ClauseView]
    facts_used: list[FactView]
    next_action: NextActionView
    handoff: bool
    case_id: str | None
    scam_warning: bool
    attempts: list[AttemptView]


class MentionView(Schema):
    id: str = Field(pattern=MENTION_ID_PATTERN)
    kind: Literal["amount", "date"]
    heard: str
    value: str | None
    value_paise: int | None
    value_date: str | None
    chip_hi: str
    chip_en: str


class SttResponse(LabelFields):
    stt_id: str = Field(pattern=STT_ID_PATTERN)
    transcript: str
    language_code: str | None
    language_probability: float | None
    duration_s: float | None
    mentions: list[MentionView]
    attempts: list[AttemptView]


class TtsResponse(LabelFields):
    audio_url: str | None
    mime_type: str | None


def _label(label: AiLabel) -> dict[str, Any]:
    wire = label.to_wire()
    return {key: wire[key] for key in ("mode", "provider", "model", "fallback_reason")}


def _attempts(label: AiLabel) -> list[dict[str, Any]]:
    return [attempt.to_wire() for attempt in label.attempts]


def _fact(fact: Fact) -> dict[str, Any]:
    return {
        "key": fact.key,
        "label_hi": fact.label_hi,
        "label_en": fact.label_en,
        "value": fact.value,
        "sources": [
            {
                "kind": s.kind.value,
                "label": s.label,
                "ref": s.ref,
                "as_of": iso_or_none(s.as_of),
                "origin": s.origin.value,
                "clause": s.clause,
            }
            for s in fact.sources
        ],
    }


def ask_response(answer: AskAnswer) -> dict[str, Any]:
    """The response data of POST /ask, validated against `AskResponse`."""
    data = AskResponse(
        ask_id=answer.ask_id,
        intent=answer.intent,  # type: ignore[arg-type]
        intent_source="rules",
        lang=answer.lang,
        answer=answer.answer,
        answer_en=answer.answer_en,
        clauses=[{"id": c.id, "title": c.title} for c in answer.clauses],  # type: ignore[misc]
        facts_used=[_fact(f) for f in answer.facts],  # type: ignore[misc]
        next_action={  # type: ignore[arg-type]
            "kind": answer.next_action.kind,
            "label_hi": answer.next_action.label_hi,
            "label_en": answer.next_action.label_en,
        },
        handoff=answer.handoff,
        case_id=answer.case_id,
        scam_warning=answer.scam_warning,
        attempts=_attempts(answer.label),  # type: ignore[arg-type]
        **_label(answer.label),
    )
    return data.model_dump(mode="json")


def _mention(mention: Mention) -> dict[str, Any]:
    return mention.to_wire()


def stt_response(result: SttResult) -> dict[str, Any]:
    data = SttResponse(
        stt_id=result.stt_id,
        transcript=result.transcript,
        language_code=result.language_code,
        language_probability=None,
        duration_s=result.duration_s,
        mentions=[_mention(m) for m in result.mentions],  # type: ignore[misc]
        attempts=_attempts(result.label),  # type: ignore[arg-type]
        **_label(result.label),
    )
    return data.model_dump(mode="json")


def tts_response(result: TtsResult) -> dict[str, Any]:
    data = TtsResponse(audio_url=result.audio_url, mime_type=result.mime_type, **_label(result.label))
    return data.model_dump(mode="json")
