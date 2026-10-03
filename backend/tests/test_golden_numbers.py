"""Golden numbers of the demo, recomputed from the committed artefacts (SPEC §17.2, §17.4, §22).

Slow (``make test-slow``): needs ``backend/artifacts/model`` and ``calibration.json`` written by
``make data`` and FAILS when they are missing (it never skips and never rebuilds them, B6, B8).
Every number comes from the SPEC §24 functions the replay uses — ``sim`` (city, scenario, shock
calendar, sales), `ExpectedSalesModel.predict` / ``day_ranges_paise``, ``detect.evaluate_hour`` /
``find_silent`` / ``silent_this_morning`` and the pure policy engine — without the API and without
the pipeline's own helpers, so it cross-checks the calibration independently. An evaluation at the
hour boundary t only sees the day's actual sales in [00:00, t) (decision B4). The numbers below are
the SPEC's, written out literally on purpose.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
import pytest

from chhatri.clock import at, ist
from chhatri.config import BACKEND_DIR, DATA_DIR, Settings
from chhatri.detect.silent import find_silent, silent_this_morning
from chhatri.detect.triggers import evaluate_hour
from chhatri.detect.types import ZoneState
from chhatri.directory import default_directory
from chhatri.domain.enums import (
    CheckCode,
    CheckStatus,
    ClaimKind,
    CoverQuoteOutcome,
    DecisionOutcome,
    VerificationStatus,
)
from chhatri.domain.models import (
    AreaTrigger,
    Claim,
    Decision,
    Doctor,
    DoctorVerification,
    Hospital,
    SlipExtraction,
)
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.ids import IdFactory
from chhatri.integrations.base import DoctorNoResponse, DoctorVerificationRequest
from chhatri.integrations.doctor import SimulatedDoctor
from chhatri.integrations.doctor_register import STAGE_ATTENDANCE, STAGE_DOCTOR_NAMES
from chhatri.integrations.sarvam_sim import SimulatedSlipReader
from chhatri.money import format_inr, rupees
from chhatri.policy.engine import (
    AreaClaimFacts,
    PersonalClaimFacts,
    evaluate_area_claim,
    evaluate_cover_purchase,
    evaluate_personal_claim,
    publish_expected_day,
)
from chhatri.policy.rules import PolicyRules, default_rules
from chhatri.sim.calibration import load_calibration
from chhatri.sim.city import build_city
from chhatri.sim.sales import SalesSimulator
from chhatri.sim.scenarios import get_scenario
from chhatri.sim.types import Calibration, City, SalesPanel, Scenario
from chhatri.sim.weather import ShockCalendar, build_shocks

pytestmark = pytest.mark.slow

ARTIFACTS = BACKEND_DIR / "artifacts"
ANIL, RAMESH = "S-0142", "S-0907"  # SPEC §5.4, B5
MONSOON_DAY = date(2025, 8, 19)  # Tue (SPEC §17.2)
SILENT_DAY = date(2025, 8, 20)  # Wed (SPEC §17.2 illness)
ALERT_ID = "A-20250818-01"
TRIGGER_HOUR = 17
TRIGGERED = {"Z7": (37, 46), "Z3": (38, 141), "Z12": (47, 125)}  # zone -> (index %, shops) §5.1, §17.2
SLOW_ZONE, SLOW_INDEX = "Z9", 61
HOURS = 24
P50 = 1


@dataclass(frozen=True, slots=True)
class Loaded:
    seed: int
    rules: PolicyRules
    model: ExpectedSalesModel
    calibration: Calibration
    city: City


@dataclass(frozen=True, slots=True)
class Day:
    scenario: Scenario
    shocks: ShockCalendar
    history: SalesPanel  # history_start .. scenario day (whole days)

    def visible(self, moment: datetime) -> SalesPanel:
        """Actual sales strictly before `moment` (B4)."""
        return self.history.window(self.history.start, moment)


@dataclass(frozen=True, slots=True)
class Monsoon:
    day: Day
    hours: Mapping[int, tuple[tuple[AreaTrigger, ...], Mapping[str, ZoneState]]]
    decisions: tuple[tuple[AreaTrigger, Decision], ...]


@pytest.fixture(scope="module")
def loaded() -> Loaded:
    missing = [p for p in (ARTIFACTS / "model", ARTIFACTS / "calibration.json") if not p.exists()]
    if missing:
        pytest.fail(f"golden artefacts missing {missing}: run `make data` (SPEC §23)")
    seed = Settings().chhatri_seed
    model = ExpectedSalesModel.load(ARTIFACTS / "model")
    assert model.manifest.seed == seed, "the replay model was trained for another seed"
    calibration = load_calibration(DATA_DIR, artifacts_dir=ARTIFACTS)
    city = build_city(seed, DATA_DIR, calibration, scale="full")
    return Loaded(seed, default_rules(), model, calibration, city)


def _day(loaded: Loaded, name: str) -> Day:
    scenario = get_scenario(name, loaded.city, loaded.calibration)
    shocks = build_shocks(loaded.city, DATA_DIR, loaded.seed, overrides=scenario.overrides)
    simulator = SalesSimulator(loaded.city, shocks, loaded.seed)
    return Day(scenario, shocks, simulator.generate(scenario.history_start, scenario.day))


def _evaluate(loaded: Loaded, day: Day, p50: np.ndarray) -> dict[int, tuple]:
    """`evaluate_hour` at every hour boundary of the replay (08:00 .. 20:00), carrying (d) of §8.2."""
    today = day.scenario.day
    actual_day = day.history.day(today)
    alerts = day.shocks.alerts_between(at(today, 0), at(today + timedelta(days=1), 0))
    done: frozenset[tuple[str, date]] = frozenset()
    out: dict[int, tuple] = {}
    for hour in range(day.scenario.start.hour, day.scenario.end.hour + 1):
        visible = actual_day.window(at(today, 0), at(today, hour))
        triggers, states = evaluate_hour(
            at(today, hour), loaded.city, visible, p50, alerts,
            loaded.model.manifest.lower_bound_pct, loaded.rules, done,
        )  # fmt: skip
        done |= {(t.zone_id, today) for t in triggers}
        out[hour] = (triggers, states)
    return out


def _area_decisions(loaded: Loaded, day: Day, triggers: tuple[AreaTrigger, ...]) -> tuple:
    """One AREA claim per covered merchant of each triggered zone, decided by the engine (§9.3)."""
    city, today, ids = loaded.city, day.scenario.day, IdFactory()
    alerts = {a.id: a for a in day.shocks.alerts_between(at(today, 0), at(today + timedelta(days=1), 0))}
    out = []
    for trigger in triggers:
        covered = [m for m in city.merchants_in_zone(trigger.zone_id) if m.id in city.covers]
        ranges = loaded.model.day_ranges_paise(city, day.history, today, [m.id for m in covered])
        for merchant in covered:
            claim = Claim(
                id=ids.next("claim"), kind=ClaimKind.AREA, merchant_id=merchant.id,
                created_at=trigger.fired_at, event_date=today, trigger_id=trigger.id,
                expected_day_paise=publish_expected_day(ranges[merchant.id][P50]),
                drop_pct=trigger.drop_pct,
            )  # fmt: skip
            facts = AreaClaimFacts(
                claim=claim, merchant=merchant, cover=city.covers[merchant.id], trigger=trigger,
                alert=alerts.get(trigger.alert_id), paid_last_365_days_paise=0, already_paid=False,
                weekday=today.weekday(),
            )  # fmt: skip
            decision = evaluate_area_claim(
                facts, loaded.rules, decision_id=ids.next("decision"), now=trigger.fired_at
            )
            out.append((trigger, decision))
    return tuple(out)


@pytest.fixture(scope="module")
def monsoon(loaded: Loaded) -> Monsoon:
    day = _day(loaded, "monsoon")
    expected = loaded.model.predict(loaded.city, day.history, at(day.scenario.day, 0), HOURS)
    hours = _evaluate(loaded, day, expected[:, :, P50])
    triggers = tuple(t for fired, _ in hours.values() for t in fired)
    return Monsoon(day, hours, _area_decisions(loaded, day, triggers))


# ---- monsoon (SPEC §17.2) -------------------------------------------------------------------


def test_replay_model_is_trained_up_to_the_day_before(loaded: Loaded) -> None:
    manifest = loaded.model.manifest  # SPEC §7.4: train_end 2025-08-18, last 4 of 26 weeks held out
    assert (manifest.train_start, manifest.calib_start, manifest.train_end) == (
        date(2025, 2, 18),
        date(2025, 7, 22),
        date(2025, 8, 18),
    )
    assert set(manifest.lower_bound_pct) == {z.id for z in loaded.city.zones}


def test_scenario_is_the_replay_tuesday(monsoon: Monsoon) -> None:
    scenario = monsoon.day.scenario
    assert (scenario.day, scenario.day.weekday()) == (MONSOON_DAY, 1)
    assert (scenario.start, scenario.end) == (ist(2025, 8, 19, 8, 0), ist(2025, 8, 19, 20, 0))
    assert scenario.demo_merchant_id == ANIL


def test_anil_usual_tuesday_is_4380(loaded: Loaded, monsoon: Monsoon) -> None:
    expected = loaded.model.expected_day_paise(loaded.city, monsoon.day.history, ANIL, MONSOON_DAY)
    assert publish_expected_day(expected) == 438_000  # "Your usual Tuesday: ₹4,380" (§4.3)


def test_triggers_fire_only_at_17_for_z3_z7_z12(monsoon: Monsoon) -> None:
    fired = {h: sorted(t.zone_id for t in triggers) for h, (triggers, _) in monsoon.hours.items() if triggers}
    assert fired == {TRIGGER_HOUR: ["Z12", "Z3", "Z7"]}
    for hour in (15, 16):
        assert monsoon.hours[hour][0] == ()


@pytest.mark.parametrize("zone_id", sorted(TRIGGERED))
def test_trigger_numbers(monsoon: Monsoon, zone_id: str) -> None:
    index, shops = TRIGGERED[zone_id]
    (trigger,) = [t for t in monsoon.hours[TRIGGER_HOUR][0] if t.zone_id == zone_id]
    assert (trigger.index_pct, trigger.drop_pct, trigger.shops_in_index) == (index, 100 - index, shops)
    assert trigger.alert_id == ALERT_ID
    assert (trigger.window_start, trigger.window_end) == (ist(2025, 8, 19, 14, 0), ist(2025, 8, 19, 17, 0))
    assert len(trigger.hourly_index_pct) == 3
    assert all(h < 50 for h in trigger.hourly_index_pct), trigger.hourly_index_pct
    assert trigger.index_pct < trigger.lower_bound_pct
    assert trigger.id == f"E-{zone_id}-20250819"


def test_z9_is_a_slow_day_without_payout(monsoon: Monsoon) -> None:
    state = monsoon.hours[TRIGGER_HOUR][1][SLOW_ZONE]
    assert (state.status, state.index_pct, state.alert_id) == ("slow_day", SLOW_INDEX, None)
    assert all(t.zone_id != SLOW_ZONE for triggers, _ in monsoon.hours.values() for t in triggers)
    assert all(t.zone_id != SLOW_ZONE for t, _ in monsoon.decisions)


def test_312_shops_are_approved(monsoon: Monsoon) -> None:
    outcomes = [d.outcome for _, d in monsoon.decisions]
    assert len(outcomes) == 312
    assert set(outcomes) == {DecisionOutcome.APPROVED}
    per_zone = {z: sum(1 for t, _ in monsoon.decisions if t.zone_id == z) for z in TRIGGERED}
    assert per_zone == {z: shops for z, (_, shops) in TRIGGERED.items()}


def test_anil_is_paid_1380_with_the_spec_explanation(monsoon: Monsoon) -> None:
    (decision,) = [d for _, d in monsoon.decisions if d.merchant_id == ANIL]
    assert decision.amount_paise == 138_000
    explanation = decision.explanation
    assert explanation is not None
    assert explanation.formula_en == "½ × ₹4,380 × 63% = ₹1,380"  # SPEC §9.6
    assert explanation.formula_hi == "₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380"
    assert (explanation.weekday_en, explanation.expected_day_paise, explanation.drop_pct) == (
        "Tuesday",
        438_000,
        63,
    )


def test_z7_total_is_58900(monsoon: Monsoon) -> None:
    z7 = [d.amount_paise for t, d in monsoon.decisions if t.zone_id == "Z7"]
    assert len(z7) == 46
    assert sum(z7) == 5_890_000  # "Total ₹58,900 · instalments paused" (§17.2)


def test_ramesh_gets_nothing(loaded: Loaded, monsoon: Monsoon) -> None:
    assert RAMESH not in loaded.city.covers  # SPEC §5.4: not covered, never in a zone index
    assert all(d.merchant_id != RAMESH for _, d in monsoon.decisions)
    z3 = next(t for triggers, _ in monsoon.hours.values() for t in triggers if t.zone_id == "Z3")
    claim = Claim(
        id="CL-999999", kind=ClaimKind.AREA, merchant_id=RAMESH, created_at=z3.fired_at,
        event_date=MONSOON_DAY, trigger_id=z3.id, expected_day_paise=438_000, drop_pct=z3.drop_pct,
    )  # fmt: skip
    facts = AreaClaimFacts(
        claim=claim, merchant=loaded.city.merchant(RAMESH), cover=None, trigger=z3,
        alert=next(a for a in monsoon.day.shocks.alerts if a.id == z3.alert_id),
        paid_last_365_days_paise=0, already_paid=False, weekday=MONSOON_DAY.weekday(),
    )  # fmt: skip
    decision = evaluate_area_claim(facts, loaded.rules, decision_id="D-999999", now=z3.fired_at)
    assert (decision.outcome, decision.amount_paise) == (
        DecisionOutcome.DECLINED,
        0,
    )  # even if a claim were raised
    assert {c.code: c.status for c in decision.checks}[CheckCode.COVER_IN_FORCE] is CheckStatus.FAIL


def test_ramesh_cover_is_blocked_until_the_25th(loaded: Loaded) -> None:
    day = _day(loaded, "buy_cover")
    now = ist(2025, 8, 18, 18, 10)  # "Red alert tomorrow. Cover me today." (§17.2 buy_cover)
    quote = evaluate_cover_purchase(
        loaded.city.merchant(RAMESH), None, now=now,
        alerts=day.shocks.alerts_between(now, now + timedelta(days=3)),
        premium_per_day_paise=rupees(loaded.rules.premium.min_per_day_rupees), rules=loaded.rules, quote_id="Q-000001",
    )  # fmt: skip
    assert (day.scenario.demo_merchant_id, quote.outcome, quote.starts_on) == (
        RAMESH,
        CoverQuoteOutcome.BLOCKED,
        date(2025, 8, 25),
    )


# ---- illness (SPEC §8.3, §17.2) -------------------------------------------------------------


def _personal(loaded: Loaded, name: str) -> tuple[Day, Decision, int]:
    """File Anil's personal claim at 11:30 on Thu with the scenario's slip; (day, decision, E_wed)."""
    day = _day(loaded, name)
    city, today, now = loaded.city, day.scenario.day, at(day.scenario.day, 11) + timedelta(minutes=30)
    assert (today, day.scenario.demo_merchant_id) == (SILENT_DAY + timedelta(days=1), ANIL)
    ranges = loaded.model.day_ranges_paise(city, day.history, SILENT_DAY, sorted(city.covers))
    findings = find_silent(SILENT_DAY, city, day.visible(now), ranges, frozenset())
    assert ANIL in {f.merchant_id for f in findings}
    assert silent_this_morning(ANIL, today, city, day.visible(at(today, 11)), 11)
    assert day.scenario.slip_sample is not None
    png = (DATA_DIR / "slips" / day.scenario.slip_sample).read_bytes()
    slip = _read_slip(png)
    expected = publish_expected_day(ranges[ANIL][P50])
    claim = Claim(
        id="CL-000001", kind=ClaimKind.PERSONAL, merchant_id=ANIL, created_at=now, event_date=SILENT_DAY,
        silent_dates=(SILENT_DAY,), slip=slip, expected_day_paise=expected,
    )  # fmt: skip
    kyc_name = city.merchant(ANIL).kyc_name
    hospital, doctor, verification = _confirm(claim, kyc_name, now)
    facts = PersonalClaimFacts(
        claim=claim, merchant=city.merchant(ANIL), cover=city.covers[ANIL],
        verified_silent_dates=(SILENT_DAY,), kyc_name=kyc_name,
        paid_last_365_days_paise=0, already_paid_dates=(), weekday=SILENT_DAY.weekday(),
        hospital=hospital, doctor=doctor,
        verification_consent=True, verification_consent_at=now, verification=verification,
    )  # fmt: skip
    return day, evaluate_personal_claim(facts, loaded.rules, decision_id="D-000001", now=now), expected


def _confirm(
    claim: Claim, kyc_name: str, now: datetime
) -> tuple[Hospital | None, Doctor | None, DoctorVerification | None]:
    """The doctor confirmation the pipeline would gather for this slip (SPEC §9.2).

    The hospital and the doctor are looked up in the independent directory, and the stage register
    is asked the same question the pipeline asks: did *the merchant* attend, by KYC name, never the
    name read off the photograph. A doctor with nothing to say gives NO_ANSWER, not a denial.
    """
    slip = claim.slip
    directory = default_directory()
    hospital = None if slip is None else directory.find_hospital(slip.hospital_name)
    doctor = None if slip is None else directory.find_doctor(hospital, slip.doctor_registration_no)
    if hospital is None or doctor is None or doctor.verify_chat_id is None:
        return hospital, doctor, None
    request = DoctorVerificationRequest(
        request_id="DR-000001", claim_id=claim.id, hospital_id=hospital.id,
        doctor_registration_no=doctor.registration_no, verify_chat_id=doctor.verify_chat_id,
        patient_name=kyc_name, visit_date=claim.event_date, requested_at=now,
    )  # fmt: skip
    stand_in = SimulatedDoctor(register=STAGE_ATTENDANCE, doctor_names=STAGE_DOCTOR_NAMES)
    try:
        answer = asyncio.run(stand_in.ask(request))
        status, answered_by, answered_at = answer.status, answer.answered_by, now
    except DoctorNoResponse:
        status, answered_by, answered_at = VerificationStatus.NO_ANSWER, None, None
    return hospital, doctor, DoctorVerification(
        id="DV-000001", claim_id=claim.id, hospital_id=hospital.id,
        doctor_registration_no=doctor.registration_no, status=status,
        requested_at=now, answered_at=answered_at, answered_by=answered_by,
    )  # fmt: skip


def _read_slip(png: bytes) -> SlipExtraction:
    """The offline vision reader the replay uses (reads the slip data embedded in the sample PNG)."""
    return asyncio.run(SimulatedSlipReader().read_slip(png, "image/png"))


def test_illness_pays_1500_with_anils_slip(loaded: Loaded) -> None:
    _, decision, expected = _personal(loaded, "illness")
    assert decision.outcome is DecisionOutcome.APPROVED
    assert decision.amount_paise == 150_000
    assert expected >= 300_000  # ½ × the usual Wednesday is above the ₹1,500 daily cap (§4.3)
    assert decision.explanation is not None
    formula = (
        f"½ × {format_inr(expected)} = {format_inr(expected // 2)} a day, capped at ₹1,500 × 1 day = ₹1,500"
    )
    assert decision.explanation.formula_en == formula  # SPEC §9.6, from the published Wednesday
    assert decision.explanation.weekday_en == "Wednesday"


def test_illness_mismatch_is_referred(loaded: Loaded) -> None:
    _, decision, _ = _personal(loaded, "illness_mismatch")
    assert decision.outcome is DecisionOutcome.REFERRED
    assert decision.amount_paise == 150_000  # computed, not paid (§9.3)
    statuses = {c.code: c.status for c in decision.checks}
    assert statuses[CheckCode.NAME_MATCHES_KYC] is CheckStatus.FAIL  # "Sunil Pawar" vs Anil's KYC
    assert statuses[CheckCode.SILENCE_VERIFIED] is CheckStatus.PASS
    # The name alone refers it. The doctor was asked about Anil, the man insured, not about the
    # name on the slip, so the misread confirms rather than provoking a denial that would decline
    # a claim the officer goes on to approve (SPEC §9.2).
    assert statuses[CheckCode.DOCTOR_CONFIRMED] is CheckStatus.PASS
    assert statuses[CheckCode.DOCTOR_NOT_DENIED] is CheckStatus.PASS
    assert decision.referral_reason is not None
