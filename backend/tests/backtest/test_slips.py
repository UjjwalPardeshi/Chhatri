"""Backtest hospital slips read by the simulated slip reader (SPEC §9.2, §14.1)."""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import date, timedelta

import pytest

from chhatri.backtest.slips import (
    OTHER_PATIENT_NAME,
    SLIP_MIX,
    SlipKind,
    read_slips,
    render_claim_slip,
    render_claim_slips,
    slip_kind,
)
from chhatri.domain.models import Merchant
from chhatri.policy.engine import name_match_score
from chhatri.sim.city import ANIL

SEED = 20251019
FIRST = date(2024, 7, 15)


def _merchant(number: int) -> Merchant:
    return ANIL.model_copy(update={"id": f"S-{number:04d}"})


def _first_of_kind(kind: SlipKind) -> tuple[Merchant, date]:
    for number in range(1, 2000):
        merchant = _merchant(number)
        if slip_kind(SEED, merchant, FIRST) is kind:
            return merchant, FIRST
    raise AssertionError(f"no {kind} slip in 2000 draws")


def test_slip_kind_is_deterministic_and_follows_the_mix() -> None:
    draws = [slip_kind(SEED, _merchant(n), FIRST) for n in range(1, 4001)]
    assert draws == [slip_kind(SEED, _merchant(n), FIRST) for n in range(1, 4001)]
    counts = Counter(draws)
    for kind, share in SLIP_MIX:
        assert counts[kind] / len(draws) == pytest.approx(share, abs=0.02)
    assert slip_kind(SEED + 1, _merchant(1), FIRST) in {k for k, _ in SLIP_MIX}


def test_clean_slip_reads_back_owner_and_first_silent_day() -> None:
    merchant, first = _first_of_kind(SlipKind.CLEAN)
    (slip,) = read_slips([render_claim_slip(SEED, merchant, first)])
    assert slip.patient_name == merchant.owner_name
    assert slip.admission_date == first
    assert slip.document_type == "admission_slip"
    assert slip.confidence >= 0.80 and slip.source == "simulated"
    assert name_match_score(slip.patient_name, merchant.kyc_name) >= 85


def test_doubtful_slips() -> None:
    other, first = _first_of_kind(SlipKind.OTHER_NAME)
    late, _ = _first_of_kind(SlipKind.LATE_ADMISSION)
    blurry, _ = _first_of_kind(SlipKind.UNREADABLE)
    images = [render_claim_slip(SEED, m, first) for m in (other, late, blurry)]
    other_slip, late_slip, blurry_slip = read_slips(images)
    assert other_slip.patient_name == OTHER_PATIENT_NAME
    assert name_match_score(OTHER_PATIENT_NAME, other.kyc_name) < 85
    assert late_slip.admission_date == first + timedelta(days=1)
    assert blurry_slip.patient_name is None and blurry_slip.confidence < 0.80


def test_batch_rendering_matches_one_by_one() -> None:
    claims = [(_merchant(n), FIRST + timedelta(days=n % 3)) for n in range(1, 7)]
    batch = render_claim_slips(SEED, claims, workers=3)
    assert batch == tuple(render_claim_slip(SEED, m, d) for m, d in claims)
    with pytest.raises(ValueError, match="workers"):
        render_claim_slips(SEED, claims, workers=0)


def test_read_slips_refuses_a_running_loop() -> None:
    async def inside() -> None:
        read_slips([])

    with pytest.raises(RuntimeError, match="synchronous"):
        asyncio.run(inside())
