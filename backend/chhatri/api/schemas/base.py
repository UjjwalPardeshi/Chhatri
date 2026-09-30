"""Shared schema machinery for the §19.2 mirror (SPEC §19, §19.2, §4.2).

- ``Schema``: frozen, ``extra="forbid"``, strict (no string→number coercion).
- ``Optional``-in-TypeScript fields (``name?: T``) use ``absent(T)``: the key may be missing, but an
  explicit ``null`` is rejected, exactly like the TypeScript declaration.
- Timestamps must be ISO-8601 with the IST offset (+05:30); dates must be ``YYYY-MM-DD``.
- Every ``<x>_paise`` field that has a ``<x>_label`` sibling must satisfy
  ``label == format_inr(paise)`` (SPEC §19.2: labels come from ``format_inr``).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Any, Final, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from chhatri.money import format_inr

__all__ = [
    "AwareTimestamp",
    "IsoDate",
    "IstTimestamp",
    "ListMeta",
    "Envelope",
    "ErrorBody",
    "ErrorEnvelope",
    "ListEnvelope",
    "Schema",
    "absent",
]

IST_OFFSET: Final = timedelta(hours=5, minutes=30)
PAISE_SUFFIX: Final = "_paise"
LABEL_SUFFIX: Final = "_label"


def _check_ist(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() != IST_OFFSET:
        raise ValueError("timestamp must carry the IST offset +05:30")
    return value


def _check_aware(value: str) -> str:
    if datetime.fromisoformat(value).utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value


def _check_date(value: str) -> str:
    date.fromisoformat(value)
    if len(value) != len("YYYY-MM-DD"):
        raise ValueError("date must be YYYY-MM-DD")
    return value


def _reject_null(value: Any) -> Any:
    if value is None:
        raise ValueError("optional field may be omitted but not null")
    return value


IstTimestamp = Annotated[str, AfterValidator(_check_ist)]
AwareTimestamp = Annotated[str, AfterValidator(_check_aware)]
IsoDate = Annotated[str, AfterValidator(_check_date)]


def absent(tp: Any) -> Any:
    """Type for a TypeScript ``field?: T``: omit it or give a T; ``null`` is invalid."""
    return Annotated[tp | None, BeforeValidator(_reject_null)]


class Schema(BaseModel):
    """Base of every §19.2 mirror type."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @model_validator(mode="after")
    def _labels_match_paise(self) -> Schema:
        for name in type(self).model_fields:
            if not name.endswith(PAISE_SUFFIX):
                continue
            label_name = name[: -len(PAISE_SUFFIX)] + LABEL_SUFFIX
            if label_name not in type(self).model_fields:
                continue
            paise, label = getattr(self, name), getattr(self, label_name)
            if paise is not None and label != format_inr(paise):
                raise ValueError(f"{label_name} must equal format_inr({name})")
        return self


class ListMeta(Schema):
    total: int = Field(ge=0)
    limit: int = Field(ge=0)
    offset: int = Field(ge=0)


class Envelope[T](Schema):
    """``{ok: true, data}`` (SPEC §19)."""

    ok: Literal[True]
    data: T


class ListEnvelope[T](Schema):
    """``{ok: true, data: T[], meta}`` (SPEC §19)."""

    ok: Literal[True]
    data: list[T]
    meta: ListMeta


class ErrorBody(Schema):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    fields: absent(dict[str, str]) = None


class ErrorEnvelope(Schema):
    """``{ok: false, error: {code, message, fields?}}`` (SPEC §19)."""

    ok: Literal[False]
    error: ErrorBody
