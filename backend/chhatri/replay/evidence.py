"""Case evidence bundles (SPEC §12, §19.2 CaseEvidence).

- ``expected_vs_actual``: the merchant's business hours of the day in question that are complete
  (B4), with the P50 expectation (rounded half up to paise) and the actual sales;
- ``slip``: the extraction as read, with the stored photo's media URL;
- ``kyc_name`` and ``name_score`` (only when the slip name is in Latin script, SPEC §9.2);
- ``silent_days``, ``merchant_text`` and ``precedents`` (SPEC §16; empty → "No similar past cases yet").
Everything is JSON-ready so `views.case_view` passes it through unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from chhatri.clock import at, floor_hour
from chhatri.conversation.outbox import MEDIA_URL
from chhatri.domain.models import SlipExtraction
from chhatri.forecast.rounding import round_paise
from chhatri.policy.names import is_latin_name, name_match_score
from chhatri.replay.memory_facts import precedent_views
from chhatri.replay.view_records import iso
from chhatri.replay.world import P50

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = ["PRECEDENT_LIMIT", "hourly_evidence", "precedents", "slip_evidence"]

PRECEDENT_LIMIT: Final = 5
HOURS_PER_DAY: Final = 24


def _expected_hours(rt: Runtime, row: int, day: date) -> np.ndarray:
    """(24,) P50 paise of one merchant row on `day`."""
    if day in rt.world.days:
        offset = HOURS_PER_DAY * rt.world.days.index(day)
        return np.asarray(rt.world.p50[row, offset : offset + HOURS_PER_DAY], dtype=np.float64)
    return rt.world.model.predict(rt.static.city, rt.world.history, at(day, 0), HOURS_PER_DAY)[row, :, P50]


def hourly_evidence(rt: Runtime, merchant_id: str, day: date, now: datetime) -> list[dict[str, Any]]:
    """Expected vs actual for the completed business hours of `day` (SPEC §12)."""
    row = rt.static.city.row(merchant_id)
    profile = rt.static.city.profiles[merchant_id]
    last = min(profile.close_hour, _completed_hours(day, now))
    if last <= profile.open_hour:
        return []
    expected = _expected_hours(rt, row, day)
    actual = rt.world.history.day(day).amount_paise[row]
    return [
        {
            "hour": iso(at(day, hour)),
            "expected_paise": round_paise(float(expected[hour])),
            "actual_paise": int(actual[hour]),
        }
        for hour in range(profile.open_hour, last)
    ]


def _completed_hours(day: date, now: datetime) -> int:
    """How many hours of `day` are complete at `now` (0..24)."""
    boundary = floor_hour(now)
    if boundary.date() > day:
        return HOURS_PER_DAY
    if boundary.date() < day:
        return 0
    return boundary.hour


def slip_evidence(slip: SlipExtraction, media_id: str) -> dict[str, Any]:
    return {
        "media_url": MEDIA_URL.format(media_id=media_id),
        "patient_name": slip.patient_name,
        "admission_date": slip.admission_date.isoformat() if slip.admission_date else None,
        "discharge_date": slip.discharge_date.isoformat() if slip.discharge_date else None,
        "hospital_name": slip.hospital_name,
        "document_type": slip.document_type,
        "confidence": float(slip.confidence),
        "source": slip.source,
    }


def name_evidence(slip: SlipExtraction, kyc_name: str) -> dict[str, Any]:
    """KYC name, plus the SPEC §9.2 score when the slip name can be scored."""
    evidence: dict[str, Any] = {"kyc_name": kyc_name}
    if slip.patient_name and is_latin_name(slip.patient_name):
        evidence["name_score"] = float(name_match_score(slip.patient_name, kyc_name))
    return evidence


async def precedents(rt: Runtime, merchant_id: str, kind: str) -> list[dict[str, Any]]:
    """Similar past facts of `kind` for the officer (SPEC §16), newest-first within a score."""
    zone_id = rt.static.city.merchant(merchant_id).zone_id
    found = await rt.integrations.memory.precedents(
        merchant_id=merchant_id, zone_id=zone_id, kind=kind, limit=PRECEDENT_LIMIT
    )
    return precedent_views(found)


def iso_days(days: Sequence[date]) -> list[str]:
    return [d.isoformat() for d in days]
