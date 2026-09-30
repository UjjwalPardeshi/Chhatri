"""Workflow steps in process and through n8n callbacks (SPEC §14.5, §15, §24.5, §24.6; B1, B2)."""

from __future__ import annotations

import pytest

from chhatri.domain.enums import PayoutStatus
from chhatri.replay.state import Runtime
from chhatri.replay.static import StaticContext
from chhatri.workflows.definitions import FOLLOW_UP, HUMAN_REVIEW, PAYOUT, WORKFLOWS
from tests.replay.helpers import (
    ANIL,
    FailingWorkflows,
    RecordingWorkflows,
    integrations_with,
    loaded,
    monsoon_at,
)


def timeline(rt: Runtime) -> dict:
    return {
        "payouts": [p.model_dump() for p in rt.store.payouts()],
        "pauses": [p.model_dump() for p in rt.store.pauses()],
        "anil": [(m.id, m.kind, m.created_at, m.text_en, m.text_hi) for m in rt.store.messages(ANIL)],
        "audit": [
            (e.seq, e.at, e.actor, e.action, e.subject_id, e.hash) for e in rt.audit.entries(limit=5000)
        ],
    }


async def test_n8n_callbacks_replay_the_in_process_timeline_exactly(
    static: StaticContext, monsoon_1705: Runtime
) -> None:
    n8n = RecordingWorkflows()
    rt = await loaded(static, "monsoon", seek="16:59", integrations_factory=integrations_with(workflows=n8n))
    await rt.engine.step(1)
    assert n8n.started and {workflow for workflow, _, _ in n8n.started} == {PAYOUT}
    assert rt.store.payouts() == ()  # n8n has the runs; nothing moves until it calls back
    for workflow, run_id, payload in n8n.started:  # n8n calls back each step in WORKFLOWS order, no Waits
        for spec in WORKFLOWS[workflow]:
            answer = await rt.orchestrator.handle_callback(run_id, workflow, spec.name, payload)
            assert answer == {"step": spec.name, "status": "done"}
    assert {p.status for p in rt.store.payouts()} == {PayoutStatus.PENDING}
    workflow, run_id, payload = n8n.started[0]
    again = await rt.orchestrator.handle_callback(run_id, workflow, "credit_payout", payload)
    assert again == {"step": "credit_payout", "status": "skipped"}  # idempotent per (run_id, step)
    await rt.engine.step(5)
    assert timeline(rt) == timeline(monsoon_1705)
    assert rt.audit.head_hash() == monsoon_1705.audit.head_hash()


async def test_callbacks_for_steps_already_run_in_process_are_skipped_and_bad_ones_rejected(
    static: StaticContext,
) -> None:
    rt = await loaded(static, "monsoon", seek="17:00")
    decision = rt.store.decisions_for(ANIL)[0]
    payload = {"decision_id": decision.id, "merchant_id": ANIL}
    run_id = f"payout:{decision.id}"
    assert await rt.orchestrator.handle_callback(run_id, PAYOUT, "execute_payout", payload) == {
        "step": "execute_payout",
        "status": "skipped",
    }
    cases = [
        ((run_id, "refund", "execute_payout", payload), ValueError, "unknown workflow|not part of workflow"),
        ((run_id, PAYOUT, "open_case", payload), ValueError, "not part of workflow"),
        ((run_id, PAYOUT, "credit_payout", {"decision_id": decision.id}), ValueError, "merchant_id"),
        (("payout:D-000999", PAYOUT, "credit_payout", payload), ValueError, "does not match"),
        (
            ("payout:D-999999", PAYOUT, "credit_payout", {**payload, "decision_id": "D-999999"}),
            KeyError,
            "D-999999",
        ),
        (
            (run_id, PAYOUT, "credit_payout", {**payload, "merchant_id": "S-0001"}),
            ValueError,
            "not for merchant",
        ),
        (
            ("human-review:C-9999", HUMAN_REVIEW, "open_case", {"case_id": "C-9999", "merchant_id": ANIL}),
            KeyError,
            "C-9999",
        ),
    ]
    for args, error, match in cases:
        with pytest.raises(error, match=match):
            await rt.orchestrator.handle_callback(*args)


async def test_steps_raise_on_inconsistent_input_and_the_replay_records_it(static: StaticContext) -> None:
    rt = await loaded(static, "monsoon", seek="17:00")
    decision = rt.store.decisions_for(ANIL)[0]
    payload = {"decision_id": decision.id, "merchant_id": ANIL}
    with pytest.raises(ValueError, match="not part of workflow"):
        await rt.orchestrator.run_step(PAYOUT, "open_case", payload)
    with pytest.raises(ValueError, match="merchants hear about credits only"):
        await rt.orchestrator.run_step(PAYOUT, "notify_merchant", payload)
    with pytest.raises(ValueError, match="names merchant S-0001"):
        await rt.orchestrator.run_step(PAYOUT, "pause_instalment", {**payload, "merchant_id": "S-0001"})

    async def broken() -> None:
        await rt.orchestrator.run_step(
            PAYOUT, "credit_payout", {"decision_id": "D-999999", "merchant_id": ANIL}
        )

    rt.scheduler.schedule(monsoon_at(17, 1), "payout:D-999999:credit_payout", broken)
    await rt.engine.step(4)  # the failing job is isolated: 17:04's credits still happen
    failed = [e for e in rt.audit.entries(limit=5000) if e.action == "workflow.step_failed"]
    assert [(e.subject_id, e.at, e.data["error_type"]) for e in failed] == [
        ("payout:D-999999:credit_payout", monsoon_at(17, 1), "ValueError")
    ]
    assert rt.store.payout_for_decision(decision.id).status is PayoutStatus.CREDITED  # type: ignore[union-attr]
    assert any(item.type == "error" and "D-999999" in item.text_en for item in rt.feed.items())
    credits = len([e for e in rt.audit.entries(limit=5000) if e.action == "payout.credit"])
    await rt.orchestrator.run_step(PAYOUT, "credit_payout", payload)  # the rail credits a payout once
    assert len([e for e in rt.audit.entries(limit=5000) if e.action == "payout.credit"]) == credits


async def test_a_workflow_engine_outage_is_audited_and_does_not_stop_the_claims(
    static: StaticContext,
) -> None:
    down = FailingWorkflows()
    rt = await loaded(static, "monsoon", seek="17:00", integrations_factory=integrations_with(workflows=down))
    decided = [d for m in rt.static.city.merchants for d in rt.store.decisions_for(m.id)]
    assert decided and down.attempts == len(decided)
    failures = [e for e in rt.audit.entries(limit=5000) if e.action == "workflow.start_failed"]
    assert len(failures) == len(decided) and failures[0].data["error"] == "connection refused"
    assert rt.store.payouts() == ()
    assert any(i.type == "error" and i.text_en.startswith("Workflow payout for D-") for i in rt.feed.items())


def test_the_step_table_is_exactly_the_workflow_definitions() -> None:
    assert [s.name for s in WORKFLOWS[PAYOUT]] == [
        "execute_payout",
        "credit_payout",
        "notify_merchant",
        "pause_instalment",
    ]
    assert [(s.name, s.delay_minutes_from_start) for s in WORKFLOWS[PAYOUT]] == [
        ("execute_payout", 0),
        ("credit_payout", 4),
        ("notify_merchant", 4),
        ("pause_instalment", 5),
    ]
    assert [s.name for s in WORKFLOWS[HUMAN_REVIEW]] == ["open_case", "notify_officer"]
    assert [s.delay_minutes_from_start for s in WORKFLOWS[FOLLOW_UP]] == [24 * 60, 24 * 60]
