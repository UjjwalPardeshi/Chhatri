"""Officer queue, records, audit, policy, backtest and premium link (SPEC §19, §9, §11, §12, §14.3, §18)."""

from __future__ import annotations

import dataclasses

import pytest
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.api.schemas import (
    AuditEntry,
    AuditVerify,
    BacktestReport,
    Case,
    Decision,
    OfficerActionResult,
    Payout,
    PolicyView,
    PremiumLinkResult,
)
from chhatri.domain.enums import CaseStatus
from tests.api.fakes import FakeAppState
from tests.api.helpers import data_of, error_of, list_of


async def test_case_queue_and_detail(client: AsyncClient) -> None:
    cases, meta = list_of(await client.get("/api/cases"), Case)
    assert [(c.id, c.kind, c.status) for c in cases] == [("C-2291", "DISPUTE", "OPEN")]
    assert (meta.total, meta.limit, meta.offset) == (1, 100, 0)
    open_cases, _ = list_of(await client.get("/api/cases?status=OPEN"), Case)
    assert len(open_cases) == 1
    closed, meta = list_of(await client.get("/api/cases?status=APPROVED"), Case)
    assert (closed, meta.total) == ([], 0)
    detail = data_of(await client.get("/api/cases/C-2291"), Case)
    assert detail.decision is not None and detail.decision.amount_label == "₹1,380"


async def test_case_errors(client: AsyncClient) -> None:
    error_of(await client.get("/api/cases?status=MAYBE"), 422, "validation_error")
    error_of(await client.get("/api/cases/C-1"), 404, "not_found")
    error_of(await client.get("/api/cases/2291"), 422, "validation_error")


async def test_officer_approves_in_one_tap(
    client: AsyncClient, officer: dict[str, str], fake_state: FakeAppState
) -> None:
    response = await client.post("/api/cases/C-2291/approve", json={"note": "slip checked"}, headers=officer)
    result = data_of(response, OfficerActionResult)
    assert (result.decision.outcome, result.decision.supersedes, result.decision.amount_label) == (
        "APPROVED",
        "D-000001",
        "₹1,380",
    )
    assert (result.case.status, result.case.resolved_by, result.case.resolution) == (
        "APPROVED",
        "officer",
        "slip checked",
    )
    assert fake_state.runtime.orchestrator.calls == [
        ("officer_decide", ("C-2291", True, "officer", "slip checked"))
    ]
    again = await client.post("/api/cases/C-2291/decline", headers=officer)
    error_of(again, 409, "conflict")


async def test_officer_declines_without_a_note(client: AsyncClient, officer: dict[str, str]) -> None:
    result = data_of(await client.post("/api/cases/C-2291/decline", headers=officer), OfficerActionResult)
    assert (result.decision.outcome, result.case.status) == ("DECLINED", "DECLINED")


async def test_officer_closes_a_dispute_that_names_no_decision(
    client: AsyncClient,
    officer: dict[str, str],
    fake_state: FakeAppState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """K5: the orchestrator returns None for it, so the result has a null decision and the closed case."""
    runtime = fake_state.runtime

    async def close_with_no_decision(case_id: str, *, approve: bool, officer_id: str, note: str) -> None:
        case = runtime.store.case(case_id)
        resolved = {"status": CaseStatus.CLOSED, "resolution": note, "resolved_by": officer_id}
        runtime.store.replace_case(case.model_copy(update=resolved | {"resolved_at": runtime.clock.now()}))

    monkeypatch.setattr(runtime.orchestrator, "officer_decide", close_with_no_decision)
    response = await client.post("/api/cases/C-2291/approve", json={"note": "no payout yet"}, headers=officer)
    result = data_of(response, OfficerActionResult)
    assert result.decision is None
    assert (result.case.status, result.case.resolution) == ("CLOSED", "no payout yet")


async def test_officer_action_errors(client: AsyncClient, officer: dict[str, str]) -> None:
    error_of(await client.post("/api/cases/C-9/approve", headers=officer), 404, "not_found")
    long_note = {"note": "x" * 501}
    error_of(
        await client.post("/api/cases/C-2291/approve", json=long_note, headers=officer),
        422,
        "validation_error",
    )


async def test_decision_record(client: AsyncClient) -> None:
    decision = data_of(await client.get("/api/decisions/D-000001"), Decision)
    assert decision.explanation is not None
    assert (decision.explanation.expected_day_label, decision.explanation.drop_pct) == ("₹4,380", 63)
    error_of(await client.get("/api/decisions/D-000404"), 404, "not_found")
    error_of(await client.get("/api/decisions/42"), 422, "validation_error")


@pytest.mark.parametrize(
    ("query", "merchants"),
    [
        ("", ["S-0142", "S-0907"]),
        ("?zone_id=Z3", ["S-0907"]),
        ("?date=2025-08-19", ["S-0142", "S-0907"]),
        ("?date=2025-08-20", []),
        ("?limit=1&offset=1", ["S-0907"]),
    ],
)
async def test_payouts_filter(client: AsyncClient, query: str, merchants: list[str]) -> None:
    payouts, meta = list_of(await client.get(f"/api/payouts{query}"), Payout)
    assert [p.merchant_id for p in payouts] == merchants
    assert meta.total == (1 if "Z3" in query else 0 if "08-20" in query else 2)


@pytest.mark.parametrize("query", ["?date=19-08-2025", "?zone_id=Zone7", "?limit=1001"])
async def test_payouts_validate_query(client: AsyncClient, query: str) -> None:
    error_of(await client.get(f"/api/payouts{query}"), 422, "validation_error")


async def test_audit_paging_and_verify(client: AsyncClient) -> None:
    entries, meta = list_of(await client.get("/api/audit?after=1&limit=1"), AuditEntry)
    assert [e.seq for e in entries] == [2]
    assert (meta.total, meta.limit, meta.offset) == (3, 1, 1)
    verify = data_of(await client.get("/api/audit/verify"), AuditVerify)
    assert (verify.valid, verify.entries, verify.first_bad_seq) == (True, 3, None)
    error_of(await client.get("/api/audit?after=-1"), 422, "validation_error")


async def test_policy_and_backtest(client: AsyncClient) -> None:
    policy = data_of(await client.get("/api/policy"), PolicyView)
    assert policy.authority[1].alone == "Never"
    report = data_of(await client.get("/api/backtest"), BacktestReport)
    assert report.label == "simulated sales · real Open-Meteo rainfall"


async def test_backtest_missing_is_404(fake_state: FakeAppState, patched_views: None) -> None:
    fake_state.static = dataclasses.replace(fake_state.static, backtest_report=None)
    app = create_app(state=fake_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        error = error_of(await http.get("/api/backtest"), 404, "not_found")
    assert "make data" in error.message


async def test_premium_link_for_ramesh(
    client: AsyncClient, officer: dict[str, str], fake_state: FakeAppState
) -> None:
    result = data_of(
        await client.post("/api/premium/link", json={"merchant_id": "S-0907"}, headers=officer),
        PremiumLinkResult,
    )
    assert (result.quote.outcome, result.quote.starts_on) == ("BLOCKED", "2025-08-25")
    assert (result.quote.premium_per_day_label, result.quote.first_payment_label) == ("₹1.80", "₹54")
    assert result.premium is not None and result.premium.link_url == "https://paytm.me/sim-000001"
    assert result.premium.source == "simulated"
    assert fake_state.runtime.orchestrator.calls == [("quote_cover", "S-0907")]


async def test_premium_link_errors(
    client: AsyncClient, officer: dict[str, str], fake_state: FakeAppState
) -> None:
    error_of(
        await client.post("/api/premium/link", json={"merchant_id": "S-9999"}, headers=officer),
        404,
        "not_found",
    )
    error_of(
        await client.post("/api/premium/link", json={"merchant_id": "x"}, headers=officer),
        422,
        "validation_error",
    )
    fake_state.runtime.orchestrator.fail_links = True
    error_of(
        await client.post("/api/premium/link", json={"merchant_id": "S-0907"}, headers=officer),
        502,
        "upstream_error",
    )
