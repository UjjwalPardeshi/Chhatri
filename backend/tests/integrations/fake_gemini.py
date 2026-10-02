"""A fake Gemini REST endpoint: an `httpx.MockTransport` that records every request and replays scripted answers."""

from __future__ import annotations

import json
from typing import Any

import httpx

KEY = "AIza-test-key-SECRET"
MODEL = "test-model"
GENERATE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


class GeminiDouble:
    """Scripted outcomes (a response, or an exception to raise) served in order; the last one repeats."""

    def __init__(self, *outcomes: httpx.Response | Exception) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)

    def body(self, index: int = 0) -> dict[str, Any]:
        parsed = json.loads(self.requests[index].content)
        assert isinstance(parsed, dict)
        return parsed


def gemini_reply(
    text: str, *, finish: str | None = "STOP", parts: list[dict[str, Any]] | None = None
) -> httpx.Response:
    """A 200 `generateContent` answer whose candidate holds `text` (or the given parts)."""
    candidate: dict[str, Any] = {"content": {"role": "model", "parts": parts or [{"text": text}]}, "index": 0}
    if finish is not None:
        candidate["finishReason"] = finish
    usage = {"promptTokenCount": 12, "candidatesTokenCount": 7, "totalTokenCount": 19}
    return httpx.Response(200, json={"candidates": [candidate], "usageMetadata": usage})


def gemini_json(value: Any) -> httpx.Response:
    return gemini_reply(json.dumps(value))


def gemini_error(status: int, name: str = "INVALID_ARGUMENT") -> httpx.Response:
    """Google's error body. The message carries the key on purpose: no adapter may ever repeat it."""
    body = {"error": {"code": status, "message": f"provider detail {KEY}", "status": name}}
    return httpx.Response(status, json=body)


def slip(**overrides: Any) -> dict[str, Any]:
    """The JSON a slip reader replies with: the five fields and one confidence per scored field."""
    base: dict[str, Any] = {
        "patient_name": "ANIL RAMESH JADHAV",
        "admission_date": "2025-08-21",
        "discharge_date": None,
        "hospital_name": "Sion Hospital",
        "document_type": "admission_slip",
        "field_confidence": {"patient_name": 0.93, "admission_date": 0.88},
    }
    return base | overrides
