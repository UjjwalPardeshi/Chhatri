"""SPEC §9.2 — every check's applicability, severity and status semantics."""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.clock import ist
from chhatri.domain.enums import CheckCode, CheckStatus, CoverStatus, Severity
from chhatri.money import rupees
from chhatri.policy import checks as ck
from chhatri.policy.catalogue import AUTHORITY_TABLE, CHECK_ORDER, Applies, codes_for, spec
from chhatri.policy.rules import default_rules
from tests.policy import builders as b

RULES = default_rules()
P, F, U = CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.UNSURE
DAY = b.MONSOON_DAY


def test_catalogue_matches_spec_table() -> None:
    assert tuple(CheckCode) == CHECK_ORDER
    soft = {c for c in CheckCode if spec(c).severity is Severity.SOFT}
    assert soft == {
        CheckCode.SLIP_READABLE,
        CheckCode.NAME_MATCHES_KYC,
        CheckCode.DATES_MATCH,
        CheckCode.WITHIN_AUTO_LIMIT,
    }
    assert len(codes_for(Applies.AREA)) == 9
    assert len(codes_for(Applies.PERSONAL)) == 9
    assert CheckCode.SILENCE_VERIFIED not in codes_for(Applies.AREA)
    assert CheckCode.BELOW_FLOOR not in codes_for(Applies.PERSONAL)
    assert [r.alone for r in AUTHORITY_TABLE] == ["Pays", "Pays up to the daily cap", "Never", "Never"]


def test_cover_in_force() -> None:
    assert ck.cover_in_force(b.cover(), DAY).status is P
    assert ck.cover_in_force(None, DAY).status is F
    assert ck.cover_in_force(b.cover(status=CoverStatus.WAITING), DAY).status is F
    assert ck.cover_in_force(b.cover(starts_on=date(2025, 8, 20)), DAY).status is F
    assert ck.cover_in_force(b.cover(starts_on=DAY), DAY).status is P
    r = ck.cover_in_force(b.cover(), DAY)
    assert (r.severity, r.label_en) == (Severity.HARD, "Cover in force")
    assert r.observed == "Active cover from 8 Jun 2025"
    assert r.required == "Active cover starting on or before 19 Aug 2025"


def test_premium_prepaid() -> None:
    assert ck.premium_prepaid(b.cover(prepaid_through=DAY), DAY).status is P
    assert ck.premium_prepaid(b.cover(prepaid_through=date(2025, 8, 18)), DAY).status is F
    assert ck.premium_prepaid(b.cover(prepaid_through=None), DAY).status is F
    assert ck.premium_prepaid(None, DAY).status is F


def test_cover_before_alert_strict() -> None:
    a = b.alert()
    assert ck.cover_before_alert(b.cover(), a).status is P
    assert ck.cover_before_alert(b.cover(purchased_at=a.issued_at), a).status is F
    assert ck.cover_before_alert(b.cover(purchased_at=ist(2025, 8, 18, 18, 10)), a).status is F
    assert ck.cover_before_alert(None, a).status is F
    assert ck.cover_before_alert(b.cover(), None).status is F


def test_alert_active_whole_window() -> None:
    t = b.trigger()
    assert ck.alert_active(b.alert(), t).status is P
    assert ck.alert_active(b.alert(valid_from=ist(2025, 8, 19, 15)), t).status is F
    assert ck.alert_active(b.alert(valid_to=ist(2025, 8, 19, 16, 59)), t).status is F
    assert ck.alert_active(b.alert(zone_ids=("Z3",)), t).status is F
    assert ck.alert_active(b.alert(id="A-20250818-02"), t).status is F
    assert ck.alert_active(None, t).status is F


def test_index_quorum() -> None:
    assert ck.index_quorum(b.trigger(shops_in_index=20), RULES).status is P
    assert ck.index_quorum(b.trigger(shops_in_index=19), RULES).status is F


def test_below_floor_strict_all_hours() -> None:
    assert ck.below_floor(b.trigger(hourly_index_pct=(49, 30, 10)), RULES).status is P
    assert ck.below_floor(b.trigger(hourly_index_pct=(50, 30, 10)), RULES).status is F
    assert ck.below_floor(b.trigger(hourly_index_pct=(30, 30)), RULES).status is F
    r = ck.below_floor(b.trigger(hourly_index_pct=()), RULES)
    assert (r.status, r.observed) == (F, "No hourly index")


def test_below_model_range_strict() -> None:
    assert ck.below_model_range(b.trigger(index=37, lower_bound_pct=38)).status is P
    assert ck.below_model_range(b.trigger(index=38, lower_bound_pct=38)).status is F


def test_silence_verified() -> None:
    d1, d2 = date(2025, 8, 20), date(2025, 8, 21)
    assert ck.silence_verified((d1,), (d1, d2)).status is P
    assert ck.silence_verified((d1, d2), (d1,)).status is F
    assert ck.silence_verified((), (d1,)).status is F


def test_slip_readable() -> None:
    assert ck.slip_readable(b.slip(), RULES).status is P
    assert ck.slip_readable(None, RULES).status is F
    assert ck.slip_readable(b.slip(document_type="selfie"), RULES).status is F
    assert ck.slip_readable(b.slip(document_type=None), RULES).status is F
    assert ck.slip_readable(b.slip(confidence=0.79), RULES).status is U
    assert ck.slip_readable(b.slip(confidence=0.80), RULES).status is P
    for kind in ("admission_slip", "discharge_summary", "prescription", "bill"):
        assert ck.slip_readable(b.slip(document_type=kind), RULES).status is P


def test_name_matches_kyc() -> None:
    assert ck.name_matches_kyc(b.slip(), b.ANIL_KYC, RULES).status is P
    r = ck.name_matches_kyc(b.slip(patient_name="Sunil Pawar"), b.ANIL_KYC, RULES)
    assert r.status is F
    assert r.observed == "Sunil Pawar (score 28)"
    assert r.required == "Score ≥ 85 against KYC ANIL RAMESH JADHAV"
    assert ck.name_matches_kyc(b.slip(patient_name=None), b.ANIL_KYC, RULES).status is U
    assert ck.name_matches_kyc(b.slip(patient_name="  "), b.ANIL_KYC, RULES).status is U
    assert ck.name_matches_kyc(b.slip(patient_name="अनिल जाधव"), b.ANIL_KYC, RULES).status is U
    assert ck.name_matches_kyc(None, b.ANIL_KYC, RULES).status is U


def test_dates_match() -> None:
    d20, d21, d22 = date(2025, 8, 20), date(2025, 8, 21), date(2025, 8, 22)
    assert ck.dates_match(b.slip(), (d20, d21)).status is P
    assert ck.dates_match(b.slip(admission_date=d21), (d20,)).status is F
    assert ck.dates_match(b.slip(discharge_date=d21), (d20, d21)).status is P
    assert ck.dates_match(b.slip(discharge_date=d21), (d20, d22)).status is F
    assert ck.dates_match(b.slip(admission_date=None), (d20,)).status is U
    assert ck.dates_match(None, (d20,)).status is U


def test_within_auto_limit() -> None:
    assert ck.within_auto_limit(b.days_from(date(2025, 8, 20), 3), RULES).status is P
    assert ck.within_auto_limit(b.days_from(date(2025, 8, 20), 4), RULES).status is F


def test_not_already_paid() -> None:
    assert ck.not_already_paid_area(False, DAY).status is P
    assert ck.not_already_paid_area(True, DAY).status is F
    d = date(2025, 8, 20)
    assert ck.not_already_paid_personal((d,), ()).status is P
    assert ck.not_already_paid_personal((d,), (d,)).status is F


def test_within_annual_limit_boundary() -> None:
    assert ck.within_annual_limit(rupees(28620), rupees(1380), RULES).status is P
    r = ck.within_annual_limit(rupees(28621), rupees(1380), RULES)
    assert r.status is F
    assert r.observed == "₹28,621 paid + ₹1,380 = ₹30,001"
    assert r.required == "At most ₹30,000 in 365 days"


@pytest.mark.parametrize("code", list(CheckCode))
def test_every_check_has_readable_label(code: CheckCode) -> None:
    row = spec(code)
    assert row.label_en and row.label_en[0].isupper()
    assert row.passes_when
