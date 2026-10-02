"""One-tap officer decisions (SPEC §9.4, §12, §13.6 HUMAN, §17.2 illness_mismatch).

- A case with a REFERRED decision: `apply_officer_decision` re-runs every check on fresh facts
  (cover, premium, silence re-verified from sales, payouts so far) and returns a new decision that
  supersedes the referred one. Only personal claims are ever REFERRED (area claims carry HARD checks
  only, SPEC §9.2-§9.3), so any other case decision is a ValueError. It is recorded (audit
  ``decision.officer`` with every check and the note), the case is resolved APPROVED or DECLINED,
  an approval starts the payout workflow and the merchant is told through `notify_officer_result`
  (a decline now; an approval at credit time).
- A DISPUTE case (documented choice; SPEC §9.4 only defines officer decisions on REFERRED claims):
  the code decides the money, so an officer answers a dispute without a new payout — the case is
  CLOSED with the officer's note (approve = payout confirmed, decline = dispute rejected), the
  merchant gets the answer (`notify_officer_result`, keeping DISPUTE_ACK's "you'll hear back") and
  the disputed decision is returned unchanged. An officer can always close a dispute: one that names
  no decision is closed the same way, the merchant is told there is no amount to change and ``None``
  is returned (K5). Any other case without a decision still cannot be decided.
- Only OPEN cases can be decided (ValueError otherwise, the API answers 409).
"""

from __future__ import annotations

from typing import Final

from chhatri.domain.enums import CaseKind, CaseStatus, ClaimKind, DecisionOutcome
from chhatri.domain.models import Case, Claim, Decision
from chhatri.policy.engine import OFFICER_ID_PATTERN, apply_officer_decision
from chhatri.policy.facts import PersonalClaimFacts
from chhatri.replay.claim_facts import personal_facts
from chhatri.replay.decisions import DecisionRecorder
from chhatri.replay.memory_facts import case_fact
from chhatri.replay.personal import PersonalFlow
from chhatri.replay.publish import Publisher, RuntimeLink
from chhatri.replay.runs import start_payout

__all__ = ["OfficerFlow"]

OFFICER_ACTOR: Final = "officer:{officer_id}"
DISPUTE_CONFIRMED: Final = "Payout confirmed by a claims officer"
DISPUTE_REJECTED: Final = "Dispute declined by a claims officer"
DISPUTE_NO_DECISION: Final = "Closed by a claims officer: no payout on record"


class OfficerFlow:
    """Applies officer decisions to open cases."""

    def __init__(
        self, link: RuntimeLink, publisher: Publisher, recorder: DecisionRecorder, personal: PersonalFlow
    ) -> None:
        self._link = link
        self._publisher = publisher
        self._recorder = recorder
        self._personal = personal

    async def decide(self, case_id: str, *, approve: bool, officer_id: str, note: str) -> Decision | None:
        """Approve or decline an OPEN case; returns the decision that now stands (None: a dispute with none)."""
        rt = self._link.rt
        case = rt.store.case(case_id)
        if case.status is not CaseStatus.OPEN:
            raise ValueError(f"case {case_id} is {case.status.value}; only OPEN cases can be decided")
        if not OFFICER_ID_PATTERN.fullmatch(officer_id):
            raise ValueError("officer_id must be a short token of letters, digits, '.', '_', '@' or '-'")
        if case.kind is CaseKind.DISPUTE:
            return await self._close_dispute(case, approve, officer_id, note)
        if case.decision_id is None:
            raise ValueError(f"case {case_id} has no decision to review")
        return await self._resolve_referred(case, approve, officer_id, note)

    def _fresh_facts(self, claim: Claim) -> PersonalClaimFacts:
        """The claim's facts as they are now: silence re-verified from sales, payouts so far."""
        rt = self._link.rt
        merchant = rt.static.city.merchant(claim.merchant_id)
        first = claim.silent_dates[0] if claim.silent_dates else claim.event_date
        verified = self._personal.verified_days(claim.merchant_id, first, rt.clock.now())
        return personal_facts(rt, claim, merchant, verified)

    async def _resolve_referred(self, case: Case, approve: bool, officer_id: str, note: str) -> Decision:
        rt = self._link.rt
        referred = rt.store.decision(case.decision_id or "")
        claim = rt.store.claim(referred.claim_id)
        if referred.outcome is not DecisionOutcome.REFERRED or claim.kind is not ClaimKind.PERSONAL:
            raise ValueError(  # checked before a decision id is drawn, so errors leave no id gap (SPEC §3)
                f"case {case.id}: decision {referred.id} is a {referred.outcome.value} {claim.kind.value} "
                "decision; only REFERRED personal claims go to an officer"
            )
        facts = self._fresh_facts(claim)
        decision = apply_officer_decision(
            referred,
            facts,
            approve=approve,
            officer_id=officer_id,
            note=note,
            rules=rt.static.rules,
            decision_id=rt.ids.next("decision"),
            now=rt.clock.now(),
        )
        actor = OFFICER_ACTOR.format(officer_id=officer_id)
        decision = await self._recorder.record(
            decision, action="decision.officer", actor=actor, extra={"note": note}, facts=facts
        )
        status = CaseStatus.APPROVED if decision.outcome is DecisionOutcome.APPROVED else CaseStatus.DECLINED
        resolved = await self._resolve(case, status, actor, note, decision)
        if decision.outcome is DecisionOutcome.APPROVED:
            await start_payout(rt, decision.id, decision.merchant_id)
        await rt.conversation.notify_officer_result(decision, resolved)
        return decision

    async def _close_dispute(self, case: Case, approve: bool, officer_id: str, note: str) -> Decision | None:
        """CLOSED with the officer's note; the merchant hears back (DISPUTE_ACK promised it, §13.4)."""
        rt = self._link.rt
        disputed = rt.store.decision(case.decision_id) if case.decision_id is not None else None
        default = (
            DISPUTE_NO_DECISION if disputed is None else DISPUTE_CONFIRMED if approve else DISPUTE_REJECTED
        )
        actor = OFFICER_ACTOR.format(officer_id=officer_id)
        resolved = await self._resolve(case, CaseStatus.CLOSED, actor, note.strip() or default, disputed)
        await rt.conversation.notify_officer_result(disputed, resolved)
        return disputed

    async def _resolve(
        self, case: Case, status: CaseStatus, actor: str, resolution: str, decision: Decision | None
    ) -> Case:
        rt = self._link.rt
        resolved = rt.cases.resolve(
            case.id, status=status, by=actor, resolution=resolution, at=rt.clock.now()
        )
        self._publisher.case(resolved)
        zone_id = rt.static.city.merchant(case.merchant_id).zone_id
        await rt.integrations.memory.remember(case_fact(resolved, zone_id, decision))
        shop = rt.static.city.merchant(case.merchant_id).shop_name
        rt.feed.add(
            rt.clock.now(), "case", f"Case {case.id} ({shop}) {status.value.lower()} by a claims officer"
        )
        return resolved
