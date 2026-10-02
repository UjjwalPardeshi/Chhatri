"""Plain result types of the Ask service (data-model 5.2). The router turns them into the response schema."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from chhatri.ai.labels import AiLabel
from chhatri.ask.facts import Fact

__all__ = ["AskAnswer", "ClauseRef", "MAX_QUESTION_CHARS", "NextAction"]

MAX_QUESTION_CHARS: Final = 500
Lang = Literal["hi", "en"]


@dataclass(frozen=True, slots=True)
class ClauseRef:
    id: str
    title: str


@dataclass(frozen=True, slots=True)
class NextAction:
    kind: str
    label_hi: str
    label_en: str


@dataclass(frozen=True, slots=True)
class AskAnswer:
    """One answered question. `answer` is in `lang`; `answer_hi` and `answer_en` are both always kept."""

    ask_id: str
    intent: str
    lang: Lang
    answer_hi: str
    answer_en: str
    clauses: tuple[ClauseRef, ...]
    facts: tuple[Fact, ...]
    next_action: NextAction
    handoff: bool
    case_id: str | None
    scam_warning: bool
    label: AiLabel

    @property
    def answer(self) -> str:
        return self.answer_hi if self.lang == "hi" else self.answer_en
