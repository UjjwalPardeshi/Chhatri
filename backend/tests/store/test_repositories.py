"""SPEC §24.3 Store: duplicates, replace semantics, queries, rolling limit, thread safety."""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta

import pytest

from chhatri.clock import ist
from chhatri.domain.enums import (
    CaseKind,
    CaseStatus,
    Channel,
    ClaimKind,
    DecisionOutcome,
    Direction,
    MessageKind,
    PayoutStatus,
    PremiumMethod,
    PremiumStatus,
)
from chhatri.domain.models import Case, Decision, InstalmentPause, Message, Payout, PremiumPayment
from chhatri.money import rupees
from chhatri.store.protocols import MessageLog
from chhatri.store.repositories import Store
from tests.policy import builders as b

AT = ist(2025, 8, 19, 17)


@pytest.fixture
def store() -> Store:
    return Store(b.city())


def decision(
    did: str = "D-000001", outcome: DecisionOutcome = DecisionOutcome.APPROVED, **kw: object
) -> Decision:
    base = {
        "id": did,
        "claim_id": "CL-000001",
        "merchant_id": "S-0142",
        "outcome": outcome,
        "amount_paise": rupees(1380),
        "checks": (),
        "rules_version": "pilot-0.1",
        "decided_at": AT,
        "decided_by": "policy-engine",
    }
    return Decision(**{**base, **kw})


def payout(pid: str = "P-000001", did: str = "D-000001", **kw: object) -> Payout:
    base = {
        "id": pid,
        "decision_id": did,
        "merchant_id": "S-0142",
        "amount_paise": rupees(1380),
        "status": PayoutStatus.PENDING,
        "rail": "Paytm settlement (simulated)",
        "created_at": AT,
        "reference": f"REF-{pid}",
    }
    return Payout(**{**base, **kw})


def premium(pid: str = "PR-000001", link: str | None = "LNK-1", **kw: object) -> PremiumPayment:
    base = {
        "id": pid,
        "cover_id": None,
        "merchant_id": "S-0907",
        "amount_paise": rupees(90),
        "method": PremiumMethod.PAYMENT_LINK,
        "covers_from": date(2025, 8, 25),
        "covers_to": date(2025, 9, 23),
        "status": PremiumStatus.PENDING,
        "link_id": link,
        "source": "simulated",
        "created_at": AT,
    }
    return PremiumPayment(**{**base, **kw})


def case(cid: str = "C-2291", **kw: object) -> Case:
    base = {
        "id": cid,
        "kind": CaseKind.DISPUTE,
        "merchant_id": "S-0142",
        "status": CaseStatus.OPEN,
        "opened_at": AT,
        "due_by": AT + timedelta(hours=24),
        "summary_en": "Merchant says the loss was bigger",
    }
    return Case(**{**base, **kw})


def message(mid: str, merchant: str = "S-0142") -> Message:
    return Message(
        id=mid,
        merchant_id=merchant,
        direction=Direction.OUTBOUND,
        channel=Channel.SIMULATOR,
        kind=MessageKind.TEXT,
        text_en="hi",
        created_at=AT,
    )


def test_seeded_with_city_covers(store: Store) -> None:
    assert store.cover("S-0142") == b.cover()
    assert store.cover("S-0907") is None
    assert set(store.covers()) == {"S-0142"}
    with pytest.raises(TypeError):
        store.covers()["S-0907"] = b.cover("S-0907")  # type: ignore[index]


def test_put_cover_replaces_and_requires_known_merchant(store: Store) -> None:
    new = b.cover("S-0907")
    store.put_cover(new)
    assert store.cover("S-0907") is new
    with pytest.raises(KeyError):
        store.put_cover(b.cover("S-9999"))


def test_claims(store: Store) -> None:
    claim = b.area_claim()
    store.add_claim(claim)
    assert store.claim(claim.id) is claim
    with pytest.raises(ValueError, match="already exists"):
        store.add_claim(claim)
    with pytest.raises(KeyError, match="unknown claim"):
        store.claim("CL-404")


def test_decisions_oldest_first(store: Store) -> None:
    d1, d2 = decision("D-000001"), decision("D-000002", claim_id="CL-000002")
    other = decision("D-000003", merchant_id="S-0907")
    for d in (d1, d2, other):
        store.add_decision(d)
    assert store.decisions_for("S-0142") == (d1, d2)
    assert store.decisions_for_claim("CL-000002") == (d2,)
    assert store.decision("D-000003") is other
    with pytest.raises(ValueError):
        store.add_decision(d1)
    with pytest.raises(KeyError):
        store.decision("D-404")


def test_latest_paid_decision_requires_approved_and_credited(store: Store) -> None:
    assert store.latest_paid_decision("S-0142") is None
    d1, d2 = decision("D-000001"), decision("D-000002")
    store.add_decision(d1)
    store.add_decision(d2)
    store.add_decision(decision("D-000003", DecisionOutcome.REFERRED))
    store.add_payout(payout("P-000001", "D-000001", status=PayoutStatus.CREDITED, credited_at=AT))
    store.add_payout(payout("P-000002", "D-000002"))  # still PENDING
    assert store.latest_paid_decision("S-0142") is d1
    store.replace_payout(payout("P-000002", "D-000002", status=PayoutStatus.CREDITED, credited_at=AT))
    assert store.latest_paid_decision("S-0142") is d2


def test_latest_final_decision_is_declined_or_approved_and_credited(store: Store) -> None:
    """K5: what a dispute is about. A REFERRED decision, and an approved one whose money is still on its way, are not final."""
    assert store.latest_final_decision("S-0142") is None
    paid = decision("D-000001")
    store.add_decision(paid)
    store.add_payout(payout("P-000001", "D-000001"))  # PENDING
    store.add_decision(decision("D-000002", DecisionOutcome.REFERRED))
    assert store.latest_final_decision("S-0142") is None
    store.replace_payout(payout("P-000001", "D-000001", status=PayoutStatus.CREDITED, credited_at=AT))
    assert store.latest_final_decision("S-0142") is paid
    declined = decision("D-000003", DecisionOutcome.DECLINED, amount_paise=0)
    store.add_decision(declined)
    assert store.latest_final_decision("S-0142") is declined, "the newest settled decision, paid or declined"
    store.add_decision(decision("D-000004", merchant_id="S-0907"))
    assert store.latest_final_decision("S-0907") is None


def test_payout_rules(store: Store) -> None:
    p = payout()
    store.add_payout(p)
    assert store.payout("P-000001") is p
    assert store.payout_for_decision("D-000001") is p
    assert store.payout_for_decision("D-404") is None
    with pytest.raises(ValueError, match="already has a payout"):
        store.add_payout(payout("P-000002", "D-000001"))
    with pytest.raises(ValueError, match="already exists"):
        store.add_payout(payout("P-000001", "D-000009"))
    with pytest.raises(KeyError):
        store.replace_payout(payout("P-000404"))
    with pytest.raises(ValueError, match="cannot move"):
        store.replace_payout(payout("P-000001", "D-000009"))
    with pytest.raises(KeyError):
        store.payout("P-404")
    with pytest.raises(KeyError):
        store.add_payout(payout("P-000005", "D-000005", merchant_id="S-9999"))


def test_payout_filters(store: Store) -> None:
    anil = payout("P-000001", "D-1")
    ramesh = payout("P-000002", "D-2", merchant_id="S-0907")
    tomorrow = payout("P-000003", "D-3", created_at=AT + timedelta(days=1))
    for p in (anil, ramesh, tomorrow):
        store.add_payout(p)
    assert store.payouts() == (anil, ramesh, tomorrow)
    assert store.payouts(zone_id="Z7") == (anil, tomorrow)
    assert store.payouts(zone_id="Z3") == (ramesh,)
    assert store.payouts(zone_id="Z99") == ()
    assert store.payouts(day=date(2025, 8, 19)) == (anil, ramesh)
    assert store.payouts(zone_id="Z7", day=date(2025, 8, 20)) == (tomorrow,)
    assert store.payouts(merchant_id="S-0907") == (ramesh,)


def test_payout_day_uses_ist() -> None:
    store = Store(b.city())
    utc_late = datetime.fromisoformat("2025-08-19T20:00:00+00:00")  # 01:30 IST on 20 Aug
    store.add_payout(payout(created_at=utc_late))
    assert store.payouts(day=date(2025, 8, 20)) != ()


def test_paid_last_365_days_window_and_statuses(store: Store) -> None:
    on = date(2025, 8, 19)
    rows = [
        ("P-1", AT, PayoutStatus.CREDITED, 100_000),
        ("P-2", AT - timedelta(days=364), PayoutStatus.PENDING, 20_000),
        ("P-3", AT - timedelta(days=365), PayoutStatus.CREDITED, 4_000),  # boundary: excluded
        ("P-4", AT + timedelta(days=1), PayoutStatus.CREDITED, 800),  # after `on`: excluded
        ("P-5", AT, PayoutStatus.FAILED, 60),
    ]
    for pid, created, status, amount in rows:
        store.add_payout(payout(pid, f"D-{pid}", created_at=created, status=status, amount_paise=amount))
    store.add_payout(payout("P-6", "D-6", merchant_id="S-0907", amount_paise=7))
    assert store.paid_last_365_days_paise("S-0142", on) == 120_000
    assert store.paid_last_365_days_paise("S-0907", on) == 7


def test_paid_event_dates(store: Store) -> None:
    area = b.area_claim()
    personal = b.personal_claim(days=(date(2025, 8, 20), date(2025, 8, 21)))
    store.add_claim(area)
    store.add_claim(personal)
    store.add_decision(decision("D-1", claim_id=area.id))
    store.add_decision(decision("D-2", claim_id=personal.id))
    store.add_decision(decision("D-3", claim_id="CL-missing"))
    store.add_decision(decision("D-4", DecisionOutcome.REFERRED, claim_id=personal.id))
    store.add_payout(payout("P-1", "D-1"))
    store.add_payout(payout("P-2", "D-2", status=PayoutStatus.CREDITED, credited_at=AT))
    store.add_payout(payout("P-3", "D-3"))
    assert store.paid_event_dates("S-0142", ClaimKind.AREA) == (date(2025, 8, 19),)
    assert store.paid_event_dates("S-0142", ClaimKind.PERSONAL) == (date(2025, 8, 20), date(2025, 8, 21))
    store.replace_payout(payout("P-1", "D-1", status=PayoutStatus.FAILED))
    assert store.paid_event_dates("S-0142", ClaimKind.AREA) == ()


def test_pauses(store: Store) -> None:
    pause = InstalmentPause(
        id="IP-000001",
        loan_id="L-S-0142",
        merchant_id="S-0142",
        instalment_date=date(2025, 8, 20),
        amount_paise=rupees(600),
        reason="payout",
        decision_id="D-1",
        created_at=AT,
    )
    store.add_pause(pause)
    assert store.pauses() == (pause,)
    assert store.pauses("S-0142") == (pause,)
    assert store.pauses("S-0907") == ()
    with pytest.raises(ValueError):
        store.add_pause(pause)


def test_premiums_and_links(store: Store) -> None:
    p = premium()
    store.add_premium(p)
    store.add_premium(premium("PR-000002", link=None, method=PremiumMethod.SETTLEMENT_DEDUCTION))
    assert store.premium_by_link("LNK-1") is p
    assert store.premium_by_link("LNK-404") is None
    with pytest.raises(ValueError, match="already recorded"):
        store.add_premium(premium("PR-000003", link="LNK-1"))
    with pytest.raises(ValueError, match="already exists"):
        store.add_premium(premium("PR-000001", link="LNK-2"))
    paid = p.model_copy(update={"status": PremiumStatus.PAID, "paid_at": AT})
    store.replace_premium(paid)
    assert store.premium_by_link("LNK-1") is paid
    with pytest.raises(ValueError, match="cannot change"):
        store.replace_premium(paid.model_copy(update={"link_id": "LNK-9"}))
    with pytest.raises(KeyError):
        store.replace_premium(premium("PR-404"))
    assert [x.id for x in store.premiums("S-0907")] == ["PR-000001", "PR-000002"]
    assert store.premiums("S-0142") == ()


def test_quotes(store: Store) -> None:
    from chhatri.policy.engine import evaluate_cover_purchase
    from chhatri.policy.rules import default_rules

    q = evaluate_cover_purchase(
        b.ramesh(),
        None,
        now=AT,
        alerts=(),
        premium_per_day_paise=300,
        rules=default_rules(),
        quote_id="Q-000001",
    )
    store.add_quote(q)
    assert store.quote("Q-000001") is q
    with pytest.raises(ValueError):
        store.add_quote(q)
    with pytest.raises(KeyError):
        store.quote("Q-404")


def test_cases(store: Store) -> None:
    c1, c2 = case("C-2291"), case("C-2292")
    store.add_case(c1)
    store.add_case(c2)
    closed = c1.model_copy(update={"status": CaseStatus.CLOSED})
    store.replace_case(closed)
    assert store.case("C-2291") is closed
    assert store.cases() == (closed, c2)
    assert store.cases(CaseStatus.OPEN) == (c2,)
    assert store.cases(CaseStatus.CLOSED) == (closed,)
    assert store.cases("OPEN") == (c2,)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        store.add_case(c1)
    with pytest.raises(KeyError):
        store.replace_case(case("C-9999"))
    with pytest.raises(ValueError, match="cannot change"):
        store.replace_case(closed.model_copy(update={"merchant_id": "S-0907"}))
    with pytest.raises(KeyError):
        store.case("C-1")


def test_messages_and_media(store: Store) -> None:
    assert isinstance(store, MessageLog)
    m1, m2, m3 = message("M-000001"), message("M-000002", "S-0907"), message("M-000003")
    for m in (m1, m2, m3):
        store.add_message(m)
    assert store.messages("S-0142") == (m1, m3)
    with pytest.raises(ValueError):
        store.add_message(m1)
    store.put_media(b"\x89PNG", "image/png", "MD-000001")
    store.put_media(b"\x89PNG", "image/png", "MD-000001")  # identical re-put is a no-op
    assert store.media("MD-000001") == (b"\x89PNG", "image/png")
    with pytest.raises(ValueError, match="different content"):
        store.put_media(b"other", "image/png", "MD-000001")
    with pytest.raises(ValueError, match="non-empty"):
        store.put_media(b"", "image/png", "MD-000002")
    with pytest.raises(KeyError):
        store.media("MD-404")


def test_triggers(store: Store) -> None:
    t = b.trigger()
    store.add_trigger(t)
    assert store.area_trigger(t.id) is t
    assert store.area_trigger("E-404") is None
    assert store.triggers() == (t,)
    with pytest.raises(ValueError):
        store.add_trigger(t)


def test_concurrent_adds_are_safe(store: Store) -> None:
    per_thread, threads = 200, 8

    def work(n: int) -> None:
        for i in range(per_thread):
            store.add_payout(payout(f"P-{n}-{i}", f"D-{n}-{i}", amount_paise=1))
            if i % 20 == 0:
                store.paid_last_365_days_paise("S-0142", date(2025, 8, 19))

    pool = [threading.Thread(target=work, args=(n,)) for n in range(threads)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    assert len(store.payouts()) == per_thread * threads
    assert store.paid_last_365_days_paise("S-0142", date(2025, 8, 19)) == per_thread * threads


def test_duplicate_race_only_one_wins(store: Store) -> None:
    errors: list[Exception] = []

    def add() -> None:
        try:
            store.add_payout(payout())
        except ValueError as exc:
            errors.append(exc)

    pool = [threading.Thread(target=add) for _ in range(10)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    assert len(store.payouts()) == 1 and len(errors) == 9


def test_claims_and_decisions_list_in_insertion_order(store: Store) -> None:
    """H8 reads every claim and every decision of the run, oldest first, as frozen snapshots."""
    assert store.claims() == () and store.decisions() == ()
    first, second = b.area_claim(id="CL-000009"), b.area_claim(id="CL-000001")
    for claim in (first, second):
        store.add_claim(claim)
    for did, claim_id in (("D-000007", "CL-000009"), ("D-000003", "CL-000001"), ("D-000005", "CL-000001")):
        store.add_decision(decision(did, claim_id=claim_id))
    assert store.claims() == (first, second)
    assert [d.id for d in store.decisions()] == ["D-000007", "D-000003", "D-000005"]
    assert isinstance(store.claims(), tuple) and isinstance(store.decisions(), tuple)
