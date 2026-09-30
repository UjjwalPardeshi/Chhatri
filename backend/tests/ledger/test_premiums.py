"""SPEC §9.7, §10 PremiumService and the premiums.json table (binding decision B6)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from chhatri.audit.log import AuditLog
from chhatri.clock import ist
from chhatri.domain.enums import CoverStatus, PremiumMethod, PremiumStatus
from chhatri.ids import IdFactory
from chhatri.integrations.base import IntegrationError
from chhatri.ledger import premium_table
from chhatri.ledger.premium_table import PREMIUMS_PATH, load_premiums, parse_premiums, premium_per_day_paise
from chhatri.ledger.premiums import PremiumService
from chhatri.money import rupees
from chhatri.policy.engine import evaluate_cover_purchase
from chhatri.policy.rules import default_rules
from chhatri.store.repositories import Store
from tests.ledger.conftest import FakeLinks
from tests.policy import builders as b

RULES = default_rules()
ASK = ist(2025, 8, 18, 18, 10)
PAID = ist(2025, 8, 18, 18, 20)
EVENING = ist(2025, 8, 19, 21)
PREMIUMS = {"Z3": 300, "Z7": 450}


def make(store: Store, audit: AuditLog, ids: IdFactory, links: FakeLinks | None = None) -> PremiumService:
    return PremiumService(store, audit, ids, RULES, links or FakeLinks(), premiums=PREMIUMS)


def ramesh_quote(premium: int = 300):
    return evaluate_cover_purchase(
        b.ramesh(),
        None,
        now=ASK,
        alerts=(b.alert(),),
        premium_per_day_paise=premium,
        rules=RULES,
        quote_id="Q-1",
    )


# --- premium table --------------------------------------------------------------------------


def test_default_path_is_backend_artifacts() -> None:
    assert PREMIUMS_PATH.parts[-3:] == ("backend", "artifacts", "premiums.json")


def test_load_premiums_from_file(tmp_path: Path) -> None:
    path = tmp_path / "premiums.json"
    path.write_text(json.dumps({"Z7": 450, "Z3": 300}), encoding="utf-8")
    table = load_premiums(RULES, path)
    assert dict(table) == {"Z3": 300, "Z7": 450}
    with pytest.raises(TypeError):
        table["Z9"] = 1  # type: ignore[index]


def test_missing_file_falls_back_to_minimum(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    table = load_premiums(RULES, tmp_path / "absent.json")
    assert dict(table) == {}
    assert premium_per_day_paise("Z7", table, RULES) == rupees(2)
    assert "minimum premium" in caplog.text


def test_zone_without_entry_uses_minimum() -> None:
    assert premium_per_day_paise("Z9", PREMIUMS, RULES) == rupees(2)
    assert premium_per_day_paise("Z7", PREMIUMS, RULES) == 450


@pytest.mark.parametrize("raw", [[1], {"Z7": 199}, {"Z7": 2.5}, {"Z7": True}, {"": 300}, {"Z7": "300"}])
def test_malformed_premiums_rejected(raw: object) -> None:
    with pytest.raises(ValueError):
        parse_premiums(raw, RULES)


def test_corrupt_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "premiums.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_premiums(RULES, path)


def test_service_loads_default_artifact_when_no_table_given(
    store: Store, audit: AuditLog, ids: IdFactory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "premiums.json"
    path.write_text(json.dumps({"Z7": 510}), encoding="utf-8")
    monkeypatch.setattr(
        "chhatri.ledger.premiums.load_premiums", lambda rules: premium_table.load_premiums(rules, path)
    )
    service = PremiumService(store, audit, ids, RULES, FakeLinks())
    assert service.premium_per_day("Z7") == 510
    assert service.premium_per_day("Z3") == rupees(2)


# --- payment links --------------------------------------------------------------------------


async def test_create_link_records_pending_payment(store: Store, audit: AuditLog, ids: IdFactory) -> None:
    links = FakeLinks()
    service = make(store, audit, ids, links)
    payment = await service.create_link(b.ramesh(), ramesh_quote(), ASK)
    assert links.calls == [("S-0907", 9000, "Chhatri cover premium, 30 days from 2025-08-25")]
    assert (payment.id, payment.status, payment.method) == (
        "PR-000001",
        PremiumStatus.PENDING,
        PremiumMethod.PAYMENT_LINK,
    )
    assert (payment.amount_paise, payment.covers_from, payment.covers_to) == (
        9000,
        date(2025, 8, 25),
        date(2025, 9, 23),
    )
    assert (payment.link_id, payment.link_url, payment.source) == (
        "LNK-1",
        "https://paytm.example/link/1",
        "simulated",
    )
    assert payment.cover_id is None
    assert store.premium_by_link("LNK-1") is payment
    assert [e.action for e in audit.entries()] == ["premium.link_created"]


async def test_create_link_validates(store: Store, audit: AuditLog, ids: IdFactory) -> None:
    service = make(store, audit, ids)
    with pytest.raises(ValueError, match="is for"):
        await service.create_link(b.merchant(), ramesh_quote(), ASK)
    bad = ramesh_quote().model_copy(update={"first_payment_paise": 1})
    with pytest.raises(ValueError, match="first payment"):
        await service.create_link(b.ramesh(), bad, ASK)
    with pytest.raises(ValueError, match="amount differs"):
        await make(store, audit, ids, FakeLinks(skew=1)).create_link(b.ramesh(), ramesh_quote(), ASK)


async def test_create_link_integration_error_propagates(
    store: Store, audit: AuditLog, ids: IdFactory
) -> None:
    with pytest.raises(IntegrationError):
        await make(store, audit, ids, FakeLinks(fail=True)).create_link(b.ramesh(), ramesh_quote(), ASK)
    assert store.premiums() == () and len(audit) == 0


async def test_mark_paid_creates_waiting_cover(store: Store, audit: AuditLog, ids: IdFactory) -> None:
    service = make(store, audit, ids)
    await service.create_link(b.ramesh(), ramesh_quote(), ASK)
    paid = service.mark_paid("LNK-1", PAID, "TXN-42")
    cover = store.cover("S-0907")
    assert cover is not None
    assert (cover.status, cover.starts_on, cover.prepaid_through) == (
        CoverStatus.WAITING,
        date(2025, 8, 25),
        date(2025, 9, 23),
    )
    assert (cover.premium_per_day_paise, cover.purchased_at) == (300, PAID)
    assert (paid.status, paid.paid_at, paid.cover_id) == (PremiumStatus.PAID, PAID, cover.id)
    assert service.mark_paid("LNK-1", PAID + timedelta(hours=1), "TXN-43") is paid
    entry = audit.entries()[-1]
    assert (entry.action, entry.data["txn_id"], entry.data["cover_status"]) == (
        "premium.paid",
        "TXN-42",
        "WAITING",
    )


async def test_mark_paid_after_start_is_active(store: Store, audit: AuditLog, ids: IdFactory) -> None:
    service = make(store, audit, ids)
    await service.create_link(b.ramesh(), ramesh_quote(), ASK)
    service.mark_paid("LNK-1", ist(2025, 8, 25, 9), None)
    assert store.cover("S-0907").status is CoverStatus.ACTIVE  # type: ignore[union-attr]


async def test_mark_paid_extends_live_cover(store: Store, audit: AuditLog, ids: IdFactory) -> None:
    service = make(store, audit, ids)
    quote = evaluate_cover_purchase(
        b.merchant(),
        store.cover("S-0142"),
        now=ASK,
        alerts=(),
        premium_per_day_paise=450,
        rules=RULES,
        quote_id="Q-2",
    )
    await service.create_link(b.merchant(), quote, ASK)
    paid = service.mark_paid("LNK-1", PAID, "TXN-1")
    cover = store.cover("S-0142")
    assert cover is not None and cover.prepaid_through == date(2025, 10, 30)  # 30 Sep + 30 days
    assert (paid.covers_from, paid.covers_to, paid.cover_id) == (
        date(2025, 10, 1),
        date(2025, 10, 30),
        cover.id,
    )
    assert cover.status is CoverStatus.ACTIVE and cover.starts_on == date(2025, 6, 8)


async def test_mark_paid_pending_payment_cover_becomes_active(
    store: Store, audit: AuditLog, ids: IdFactory
) -> None:
    store.put_cover(b.cover("S-0907", status=CoverStatus.PENDING_PAYMENT, prepaid_through=None))
    service = make(store, audit, ids)
    await service.create_link(b.ramesh(), ramesh_quote(), ASK)
    service.mark_paid("LNK-1", PAID, None)
    cover = store.cover("S-0907")
    assert cover is not None and cover.status is CoverStatus.ACTIVE
    assert cover.prepaid_through == date(2025, 6, 8) + timedelta(days=29)


async def test_mark_paid_errors(store: Store, audit: AuditLog, ids: IdFactory) -> None:
    service = make(store, audit, ids)
    with pytest.raises(KeyError):
        service.mark_paid("LNK-404", PAID, None)
    payment = await service.create_link(b.ramesh(), ramesh_quote(), ASK)
    store.replace_premium(payment.model_copy(update={"status": PremiumStatus.EXPIRED}))
    with pytest.raises(ValueError, match="only PENDING"):
        service.mark_paid("LNK-1", PAID, None)


async def test_mark_paid_rejects_uneven_amount(store: Store, audit: AuditLog, ids: IdFactory) -> None:
    service = make(store, audit, ids)
    payment = await service.create_link(b.ramesh(), ramesh_quote(), ASK)
    store.replace_premium(payment.model_copy(update={"amount_paise": 9001}))
    with pytest.raises(ValueError, match="whole number"):
        service.mark_paid("LNK-1", PAID, None)


# --- evening settlement ---------------------------------------------------------------------


def test_settle_evening_prepays_next_day(store: Store, audit: AuditLog, ids: IdFactory) -> None:
    day = date(2025, 8, 19)
    store.put_cover(b.cover(prepaid_through=day))
    service = make(store, audit, ids)
    [payment] = service.settle_evening(day, {"S-0142": rupees(2)}, EVENING)
    assert (payment.method, payment.status, payment.amount_paise) == (
        PremiumMethod.SETTLEMENT_DEDUCTION,
        PremiumStatus.PAID,
        rupees(2),
    )
    assert (payment.covers_from, payment.covers_to, payment.source) == (
        date(2025, 8, 20),
        date(2025, 8, 20),
        "settlement (simulated)",
    )
    assert store.cover("S-0142").prepaid_through == date(2025, 8, 20)  # type: ignore[union-attr]
    assert [e.action for e in audit.entries()] == ["premium.settled"]


def test_settle_evening_short_collections_do_not_advance(
    store: Store, audit: AuditLog, ids: IdFactory
) -> None:
    day = date(2025, 8, 19)
    store.put_cover(b.cover(prepaid_through=day))
    assert make(store, audit, ids).settle_evening(day, {"S-0142": rupees(2) - 1}, EVENING) == ()
    assert store.cover("S-0142").prepaid_through == day  # type: ignore[union-attr]
    [entry] = audit.entries()
    assert (entry.action, entry.data["reason"]) == ("premium.not_settled", "collections below premium")


def test_settle_evening_skips_prepaid_uncovered_and_lapsed(
    store: Store, audit: AuditLog, ids: IdFactory
) -> None:
    day = date(2025, 8, 19)
    service = make(store, audit, ids)
    assert service.settle_evening(day, {"S-0142": rupees(100), "S-0907": rupees(100)}, EVENING) == ()
    assert len(audit) == 0  # Anil already prepaid through 30 Sep; Ramesh has no cover
    store.put_cover(b.cover(prepaid_through=date(2025, 8, 10)))
    assert service.settle_evening(day, {"S-0142": rupees(100)}, EVENING) == ()
    assert audit.entries()[-1].data["reason"] == "cover lapsed before this day"
    store.put_cover(b.cover(status=CoverStatus.CANCELLED, prepaid_through=day))
    assert service.settle_evening(day, {"S-0142": rupees(100)}, EVENING) == ()


@pytest.mark.parametrize("bad", [-1, 1.5, True])
def test_settle_evening_validates_amounts(store: Store, audit: AuditLog, ids: IdFactory, bad: object) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        make(store, audit, ids).settle_evening(date(2025, 8, 19), {"S-0142": bad}, EVENING)  # type: ignore[dict-item]
