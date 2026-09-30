"""Assertions that validate HTTP responses against the §19 envelope and §19.2 schemas."""

from __future__ import annotations

from typing import Any

from httpx import Response
from pydantic import BaseModel

from chhatri.api.schemas import Envelope, ErrorEnvelope, ListEnvelope


def data_of(response: Response, model: type[BaseModel], *, status: int = 200) -> Any:
    """Validate ``{ok: true, data: model}`` and return the parsed data."""
    assert response.status_code == status, response.text
    return Envelope[model].model_validate_json(response.content).data  # type: ignore[valid-type]


def list_of(response: Response, model: type[BaseModel]) -> tuple[list[Any], Any]:
    """Validate ``{ok: true, data: model[], meta}`` and return (items, meta)."""
    assert response.status_code == 200, response.text
    parsed = ListEnvelope[model].model_validate_json(response.content)  # type: ignore[valid-type]
    return parsed.data, parsed.meta


def error_of(response: Response, status: int, code: str) -> Any:
    """Validate the error envelope with the expected status and code; return the error body."""
    assert response.status_code == status, response.text
    parsed = ErrorEnvelope.model_validate_json(response.content)
    assert parsed.error.code == code, parsed.error
    return parsed.error
