"""Hospital slips for backtest personal claims, read by the simulated slip reader (SPEC §13.5, §14.1).

The simulator models *why* a shop closes (a personal closure, SPEC §6.3) but not the photo the
merchant sends. The backtest assumes, as a documented modelling choice, that most slips are clean
(owner's name, admitted on the first silent day) and a fixed share are doubtful in one of the three
ways the policy engine must send to a human (SPEC §9.2, §9.4): an unreadable photo, a slip in
another person's name, or an admission date after the first silent day. The kind is drawn per claim
from a generator keyed by (seed, merchant, first silent day), so it is reproducible.

Every slip is a real PNG (rendered on a few threads, `render_claim_slips`) from `sim.slips` (`render_slip` / `render_unreadable_slip`) and is read by
`SimulatedSlipReader`, the same reader the replay uses offline.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from enum import StrEnum
from typing import Final

import numpy as np

from chhatri.domain.models import Merchant, SlipExtraction
from chhatri.integrations.sarvam_sim import SimulatedSlipReader
from chhatri.sim.slips import render_slip, render_unreadable_slip

SLIP_STREAM: Final = 1801  # backtest-only RNG stream id (distinct from the simulator's streams)
PNG_MIME: Final = "image/png"
OTHER_PATIENT_NAME: Final = "Sunil Pawar"  # the SPEC §17.2 mismatch patient; no pilot owner has it
HOSPITALS: Final = (
    "KEM Hospital, Parel",
    "Sion Hospital",
    "Nair Hospital, Mumbai Central",
    "Cooper Hospital, Juhu",
    "JJ Hospital, Byculla",
)
DIAGNOSES: Final = ("Viral fever", "Dengue", "Typhoid", "Gastroenteritis", "Leg fracture")


class SlipKind(StrEnum):
    CLEAN = "clean"
    UNREADABLE = "unreadable"
    OTHER_NAME = "other_name"
    LATE_ADMISSION = "late_admission"


# Modelling assumption (module docstring): 82 % clean slips, 6 % of each doubtful kind.
SLIP_MIX: Final = (
    (SlipKind.CLEAN, 0.82),
    (SlipKind.UNREADABLE, 0.06),
    (SlipKind.OTHER_NAME, 0.06),
    (SlipKind.LATE_ADMISSION, 0.06),
)


def _generator(seed: int, merchant_number: int, first_day: date) -> np.random.Generator:
    return np.random.default_rng(
        np.random.SeedSequence([seed, SLIP_STREAM, merchant_number, first_day.toordinal()])
    )


def _merchant_number(merchant: Merchant) -> int:
    return int(merchant.id.removeprefix("S-"))


def slip_kind(seed: int, merchant: Merchant, first_day: date) -> SlipKind:
    """The slip kind for a claim, drawn from `SLIP_MIX`."""
    kinds = [kind for kind, _share in SLIP_MIX]
    shares = np.array([share for _kind, share in SLIP_MIX], dtype=np.float64)
    draw = _generator(seed, _merchant_number(merchant), first_day).random()
    return kinds[int(np.searchsorted(np.cumsum(shares), draw, side="right"))]


def render_claim_slip(seed: int, merchant: Merchant, first_day: date) -> bytes:
    """The PNG the merchant sends for a claim whose first silent day is `first_day`."""
    rng = _generator(seed, _merchant_number(merchant), first_day)
    rng.random()  # the first draw chose the kind
    hospital = HOSPITALS[int(rng.integers(len(HOSPITALS)))]
    diagnosis = DIAGNOSES[int(rng.integers(len(DIAGNOSES)))]
    kind = slip_kind(seed, merchant, first_day)
    if kind is SlipKind.UNREADABLE:
        return render_unreadable_slip(merchant.owner_name, first_day, hospital, diagnosis)
    patient = OTHER_PATIENT_NAME if kind is SlipKind.OTHER_NAME else merchant.owner_name
    admitted = first_day + timedelta(days=1) if kind is SlipKind.LATE_ADMISSION else first_day
    return render_slip(patient, admitted, hospital, diagnosis)


def render_claim_slips(
    seed: int, claims: Sequence[tuple[Merchant, date]], *, workers: int
) -> tuple[bytes, ...]:
    """`render_claim_slip` for many (merchant, first silent day) pairs, in order.

    PNG encoding dominates and releases the GIL, so a small thread pool renders the batch several
    times faster; each image depends only on its own arguments, so the output is identical.
    """
    if workers < 1:
        raise ValueError("workers must be >= 1")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return tuple(pool.map(lambda claim: render_claim_slip(seed, claim[0], claim[1]), claims))


async def _read_all(images: Sequence[bytes]) -> tuple[SlipExtraction, ...]:
    reader = SimulatedSlipReader()
    return tuple([await reader.read_slip(image, PNG_MIME) for image in images])


def read_slips(images: Sequence[bytes]) -> tuple[SlipExtraction, ...]:
    """Read every slip with the simulated reader (synchronous entry point for the batch run)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_read_all(images))
    raise RuntimeError("read_slips runs its own event loop; call it from synchronous code")
