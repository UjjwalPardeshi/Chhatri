"""Errors of the consent centre: a refusal that carries its API error code (HTTP 409)."""

from __future__ import annotations

__all__ = ["ConsentConflict"]


class ConsentConflict(ValueError):
    """The request is refused because of the state of the records: ``code`` is the API error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
