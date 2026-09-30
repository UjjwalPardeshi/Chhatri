"""Fake `sarvamai.SarvamAI` client: records every SDK call and replays scripted results."""

from __future__ import annotations

from collections.abc import Iterable
from types import SimpleNamespace
from typing import Any

from sarvamai.core.api_error import ApiError


def api_error(status: int) -> ApiError:
    return ApiError(status_code=status, body={"error": {"message": "provider detail with sk_live_secret"}})


class ScriptedCall:
    """Callable that records (args, kwargs) and returns/raises the next scripted outcome."""

    def __init__(self, outcomes: Iterable[Any]) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        outcome = self._outcomes.pop(0) if len(self._outcomes) > 1 else self._outcomes[0]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def fake_client(**groups: dict[str, ScriptedCall]) -> SimpleNamespace:
    """`fake_client(speech_to_text={"transcribe": ScriptedCall([...])})`."""
    return SimpleNamespace(**{name: SimpleNamespace(**methods) for name, methods in groups.items()})
