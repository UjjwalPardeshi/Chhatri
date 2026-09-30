"""Check catalogue and payout-authority table (SPEC §9.2, §9.4; PolicyView in §19.2).

The catalogue is the single source of each check's severity, applicability and human label; the
check functions in `checks.py` and the console's /policy page both read it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from chhatri.domain.enums import CheckCode, Severity


class Applies(StrEnum):
    """Which claim kinds a check applies to (SPEC §9.2 "Applies" column)."""

    AREA = "area"
    PERSONAL = "personal"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class CheckSpec:
    """One row of SPEC §9.2."""

    code: CheckCode
    severity: Severity
    applies: Applies
    label_en: str
    passes_when: str


@dataclass(frozen=True, slots=True)
class AuthorityRow:
    """One row of the payout-authority table (SPEC §9.4, deck slide 8)."""

    case: str
    alone: str
    human: str


_H, _S = Severity.HARD, Severity.SOFT
_SPECS: Final = (
    CheckSpec(CheckCode.COVER_IN_FORCE, _H, Applies.ALL, "Cover in force",
              "cover exists, starts_on ≤ event_date, status ACTIVE"),
    CheckSpec(CheckCode.PREMIUM_PREPAID, _H, Applies.ALL, "Premium prepaid",
              "prepaid_through ≥ event_date (Insurance Act s.64VB)"),
    CheckSpec(CheckCode.COVER_BEFORE_ALERT, _H, Applies.AREA, "Cover bought before the alert",
              "purchased_at < alert.issued_at"),
    CheckSpec(CheckCode.ALERT_ACTIVE, _H, Applies.AREA, "Alert active for the whole window",
              "alert valid over the whole trigger window"),
    CheckSpec(CheckCode.INDEX_QUORUM, _H, Applies.AREA, "Enough shops in the area index",
              "shops_in_index ≥ min_shops_in_index"),
    CheckSpec(CheckCode.BELOW_FLOOR, _H, Applies.AREA, "Every hour below the floor",
              "all 3 hourly indices < floor"),
    CheckSpec(CheckCode.BELOW_MODEL_RANGE, _H, Applies.AREA, "Drop below the model's range",
              "window index < zone lower bound"),
    CheckSpec(CheckCode.SILENCE_VERIFIED, _H, Applies.PERSONAL, "Silent days verified from sales",
              "every claimed day is a verified silent day (§8.3)"),
    CheckSpec(CheckCode.SLIP_READABLE, _S, Applies.PERSONAL, "Hospital slip readable",
              "slip present, document_type medical, confidence ≥ min"),
    CheckSpec(CheckCode.NAME_MATCHES_KYC, _S, Applies.PERSONAL, "Name on slip matches KYC",
              "name score ≥ min"),
    CheckSpec(CheckCode.DATES_MATCH, _S, Applies.PERSONAL, "Slip dates cover the silent days",
              "admission ≤ each silent day ≤ (discharge or ∞)"),
    CheckSpec(CheckCode.WITHIN_AUTO_LIMIT, _S, Applies.PERSONAL, "Within the automatic-payout limit",
              "silent days ≤ max_auto_days"),
    CheckSpec(CheckCode.NOT_ALREADY_PAID, _H, Applies.ALL, "Not already paid",
              "no approved payout for (merchant, date, kind)"),
    CheckSpec(CheckCode.WITHIN_ANNUAL_LIMIT, _H, Applies.ALL, "Within the annual limit",
              "paid this policy year + amount ≤ annual limit"),
)  # fmt: skip

CHECK_SPECS: Final = MappingProxyType({spec.code: spec for spec in _SPECS})
CHECK_ORDER: Final = tuple(spec.code for spec in _SPECS)

AUTHORITY_TABLE: Final = (
    AuthorityRow("Area drop during an alert, index clear", "Pays", "Only if the merchant disputes"),
    AuthorityRow("Personal claim, slip matches name and dates", "Pays up to the daily cap",
                 "Anything above the cap"),
    AuthorityRow("Slip unclear or dates don't match", "Never", "Always"),
    AuthorityRow("Cover bought after an alert", "Never", "Waiting period applies"),
)  # fmt: skip

MEDICAL_DOCUMENT_TYPES: Final = frozenset({"admission_slip", "discharge_summary", "prescription", "bill"})


def spec(code: CheckCode) -> CheckSpec:
    """Catalogue row for a check code (KeyError for an unknown code)."""
    return CHECK_SPECS[code]


def codes_for(applies: Applies) -> tuple[CheckCode, ...]:
    """Check codes that run for a claim kind, in SPEC §9.2 order (ALL rows included)."""
    return tuple(s.code for s in _SPECS if s.applies in (applies, Applies.ALL))
