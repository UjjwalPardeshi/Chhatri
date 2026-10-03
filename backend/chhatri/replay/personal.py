"""Silent shops, check-ins and personal claims (SPEC §8.3, §9.2, §13.5, §17.2 illness).

- Outreach (SPEC §8.3): every replayed day at 11:20 the covered merchants that were silent
  yesterday (`find_silent` with their P10-P90 day range and the zones in an area event) and still
  have no transaction this morning (`silent_this_morning`, by 11:00) get CHECKIN_SILENT. The first
  silent day of the streak (looking back up to `SILENCE_LOOKBACK_DAYS`) is remembered as the open
  check-in (`open_silence`) until a personal claim is filed.
- A zone is "in an area event" on day d when an alert that can trigger (RAIN or CIVIC), already
  issued, is in force for it at some time of d, or when it triggered on d (documented reading of
  SPEC §8.3: a shop shut by a storm is not a personal loss).
- Personal claim (SPEC §8.3): its silent dates are the completed days from the first silent day up
  to yesterday that the sales data verify; the expected day is that of the first silent day, rounded
  to ₹10 (SPEC §4.3); the event date is the last silent day, so the paused instalment is the one of
  the day after it (SPEC §17.2: Wednesday silent → Thursday's instalment paused). APPROVED → payout
  workflow; REFERRED → PERSONAL_CLAIM_REVIEW case, opened before this returns (the CASE_CHIP needs
  it) plus the human-review and follow-up workflows; DECLINED → nothing is paid.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import MappingProxyType
from typing import Final

from chhatri.clock import at as at_time
from chhatri.consent.ledger import consent_book, consent_gate_open
from chhatri.consent.notice import DOCTOR, SALES
from chhatri.conversation.message_guard import MessageSuppressed
from chhatri.detect.silent import find_silent, silent_this_morning
from chhatri.detect.triggers import TRIGGER_ALERT_KINDS
from chhatri.detect.types import SilentFinding
from chhatri.domain.enums import (
    Channel,
    ClaimKind,
    DecisionOutcome,
    PreferredChannel,
    VerificationStatus,
)
from chhatri.domain.models import Claim, Decision, DoctorVerification, SlipExtraction
from chhatri.integrations.base import DoctorVerificationRequest, IntegrationError
from chhatri.policy.engine import evaluate_personal_claim, publish_expected_day
from chhatri.replay.cases_flow import CaseFlow
from chhatri.replay.claim_facts import personal_facts, resolve_care
from chhatri.replay.decisions import DecisionRecorder
from chhatri.replay.fmt import weekday_day_month
from chhatri.replay.publish import RuntimeLink
from chhatri.replay.runs import start_payout

CHANNEL_LABEL: Final[Mapping[Channel, str]] = MappingProxyType(
    {
        Channel.WHATSAPP: "WhatsApp",
        Channel.TELEGRAM: "Telegram",
        Channel.SOUNDBOX: "the Soundbox",
    }
)
PREFERRED_LABEL: Final[Mapping[PreferredChannel, str]] = MappingProxyType(
    {PreferredChannel.WHATSAPP: "WhatsApp", PreferredChannel.TELEGRAM: "Telegram"}
)
__all__ = ["OUTREACH_UNTIL_HOUR", "SILENCE_LOOKBACK_DAYS", "PersonalFlow"]

logger = logging.getLogger(__name__)

ONE_DAY: Final = timedelta(days=1)
OUTREACH_UNTIL_HOUR: Final = 11  # SPEC §8.3: "zero transactions that morning (by 11:00)"
SILENCE_LOOKBACK_DAYS: Final = 7
DETECTION_ACTOR: Final = "model"


@dataclass(frozen=True, slots=True)
class _Confirmation:
    """What the doctor-confirmation step produced, and when the claim can therefore be decided."""

    consent: bool | None
    consent_at: datetime | None
    verification: DoctorVerification | None
    decided_at: datetime


class PersonalFlow:
    """Silence check-ins and personal claims."""

    def __init__(self, link: RuntimeLink, recorder: DecisionRecorder, cases: CaseFlow) -> None:
        self._link = link
        self._recorder = recorder
        self._cases = cases
        self._checkins: Mapping[str, date] = MappingProxyType({})

    def open_silence(self, merchant_id: str) -> date | None:
        """First silent day of the open check-in, if any (SPEC §24.4 ClaimsPort)."""
        return self._checkins.get(merchant_id)

    def area_event_zones(self, day: date, now: datetime) -> frozenset[str]:
        """Zones in an area event on `day`, as known at `now` (see module docstring)."""
        rt = self._link.rt
        alerts = rt.world.shocks.alerts_between(at_time(day, 0), at_time(day + ONE_DAY, 0))
        zones = {
            z for a in alerts if a.kind in TRIGGER_ALERT_KINDS and a.issued_at <= now for z in a.zone_ids
        }
        zones |= {zone for zone, triggered_on in rt.board.triggered if triggered_on == day}
        return frozenset(zones)

    def silent_on(self, merchant_id: str, day: date, now: datetime) -> SilentFinding | None:
        """The SPEC §8.3 finding for one merchant on one completed day, or None."""
        rt = self._link.rt
        ranges = {
            merchant_id: rt.world.model.day_range_paise(rt.static.city, rt.world.history, merchant_id, day)
        }
        visible = rt.world.completed_history(now)
        found = find_silent(day, rt.static.city, visible, ranges, self.area_event_zones(day, now))
        return found[0] if found else None

    def verified_days(self, merchant_id: str, first: date, now: datetime) -> tuple[date, ...]:
        """Completed days from `first` to yesterday that the sales data show as silent."""
        yesterday = now.date() - ONE_DAY
        days = [first + timedelta(days=i) for i in range((yesterday - first).days + 1)]
        return tuple(d for d in days if self.silent_on(merchant_id, d, now) is not None)

    async def outreach(self, now: datetime) -> None:
        """The 11:20 check-in round (SPEC §8.3)."""
        rt = self._link.rt
        today, city = now.date(), rt.static.city
        yesterday = today - ONE_DAY
        candidates = [
            m.id
            for m in city.merchants
            if rt.store.cover(m.id)
            and m.id not in self._checkins
            and consent_gate_open(rt.store, m.id, SALES)
        ]
        if not candidates:
            return
        ranges = rt.world.model.day_ranges_paise(city, rt.world.history, yesterday, candidates)
        visible = rt.world.completed_history(now)
        findings = find_silent(yesterday, city, visible, ranges, self.area_event_zones(yesterday, now))
        for finding in findings:
            if silent_this_morning(finding.merchant_id, today, city, visible, OUTREACH_UNTIL_HOUR):
                await self._check_in(
                    finding, self._first_silent_day(finding.merchant_id, yesterday, now), now
                )

    def _first_silent_day(self, merchant_id: str, yesterday: date, now: datetime) -> date:
        first = yesterday
        for back in range(1, SILENCE_LOOKBACK_DAYS):
            day = yesterday - timedelta(days=back)
            if self.silent_on(merchant_id, day, now) is None:
                break
            first = day
        return first

    async def _check_in(self, finding: SilentFinding, first: date, now: datetime) -> None:
        rt = self._link.rt
        merchant_id = finding.merchant_id
        self._checkins = MappingProxyType({**self._checkins, merchant_id: first})
        rt.audit.append(
            at=now,
            actor=DETECTION_ACTOR,
            action="silence.detected",
            subject_type="merchant",
            subject_id=merchant_id,
            data={
                "silent_day": finding.day.isoformat(),
                "first_silent_day": first.isoformat(),
                "expected_day_paise": finding.expected_day_paise,
                "p10_day_paise": finding.p10_day_paise,
            },
        )
        shop = rt.static.city.merchant(merchant_id).shop_name
        try:
            sent = await rt.conversation.checkin_silent(merchant_id, first)
        except (
            MessageSuppressed
        ) as held:  # X8: the daily cap; the audit holds the reason, the feed says so too
            rt.feed.add(
                now, "checkin", f"Check-in with {shop} held back ({held.reason})", merchant_id=merchant_id
            )
            return
        # The channel the message actually went out on, not an assumption: a merchant on the
        # Telegram bot was being told, on stage, that we had reached them on WhatsApp. SIMULATOR
        # is how the demo delivers, not a channel a merchant has, so it reads as whichever of the
        # two they are on.
        where = CHANNEL_LABEL.get(sent.channel) or PREFERRED_LABEL[rt.store.preferred_channel(merchant_id)]
        text = f"Checked in with {shop} on {where} · no sales since {weekday_day_month(first)}"
        rt.feed.add(now, "checkin", text, merchant_id=merchant_id)

    async def submit(self, merchant_id: str, slip: SlipExtraction, media_id: str) -> Decision:
        """Decide a personal claim for the open check-in (SPEC §24.4 submit_personal_claim)."""
        rt = self._link.rt
        now = rt.clock.now()
        merchant = rt.static.city.merchant(merchant_id)
        first = self.open_silence(merchant_id)
        if first is None:
            raise ValueError(f"merchant {merchant_id} has no open silence check-in")
        verified = self.verified_days(merchant_id, first, now)
        claim = self._claim(merchant_id, slip, media_id, first, verified, now)
        confirmation = await self._confirm_with_doctor(claim, merchant_id, now)
        facts = personal_facts(
            rt,
            claim,
            merchant,
            verified,
            consent=confirmation.consent,
            consent_at=confirmation.consent_at,
            verification=confirmation.verification,
        )
        decided_at = confirmation.decided_at
        decision = evaluate_personal_claim(
            facts, rt.static.rules, decision_id=rt.ids.next("decision"), now=decided_at
        )
        decision = await self._recorder.record(decision, action="decision.personal", claim=claim, facts=facts)
        self._checkins = MappingProxyType({k: v for k, v in self._checkins.items() if k != merchant_id})
        self._feed(decision, claim, decided_at)
        if decision.outcome is DecisionOutcome.APPROVED:
            await start_payout(rt, decision.id, merchant_id)
        elif decision.outcome is DecisionOutcome.REFERRED:
            await self._cases.open_review(claim, decision)
        return decision

    def _doctor_consent(self, merchant_id: str) -> bool:
        """Whether Chhatri may contact this merchant's doctor at all (SPEC §9.2, DPDP Act).

        An answer the merchant actually gave binds, even when the consent feature is switched off:
        once we have asked "may we check with your doctor?", a "no" has to mean no. Only when
        nothing was ever recorded do we fall back to the ordinary gate, which is open while the
        consent book is disabled.
        """
        book = consent_book(self._link.rt.store)
        if book is not None and book.latest(merchant_id, DOCTOR) is not None:
            return book.is_active(merchant_id, DOCTOR)
        return consent_gate_open(self._link.rt.store, merchant_id, DOCTOR)

    async def _confirm_with_doctor(self, claim: Claim, merchant_id: str, now: datetime) -> _Confirmation:
        """Ask the treating doctor whether the patient really attended (SPEC §9.2).

        Chhatri only asks, and only with the merchant's consent. The doctor is reached on the chat
        id in the directory, never on anything printed on the slip. A doctor who does not answer
        leaves the claim for a person: silence is not a denial, and it is never a confirmation.

        The patient asked about is the merchant's KYC name, never the name an AI read off the
        photograph. The insured person is the merchant, so that is who the doctor is asked about;
        and asking about the slip's name would hand a misread one of its own a way to decline a
        claim, through a denial it provoked. A slip whose name does not match is still caught, by
        NAME_MATCHES_KYC, which is SOFT and sends the claim to a person.
        """
        rt = self._link.rt
        rules = rt.static.rules.personal
        if not rules.require_doctor_confirmation:
            return _Confirmation(consent=None, consent_at=None, verification=None, decided_at=now)
        consent = self._doctor_consent(merchant_id)
        if not consent:
            return _Confirmation(consent=False, consent_at=None, verification=None, decided_at=now)
        hospital, doctor = resolve_care(claim)
        if hospital is None or doctor is None or doctor.verify_chat_id is None:
            # The HARD checks name which of the three is missing; there is nobody to ask.
            return _Confirmation(consent=True, consent_at=now, verification=None, decided_at=now)

        request = DoctorVerificationRequest(
            request_id=rt.ids.next("doctor_request"),
            claim_id=claim.id,
            hospital_id=hospital.id,
            doctor_registration_no=doctor.registration_no,
            verify_chat_id=doctor.verify_chat_id,
            patient_name=rt.static.city.merchant(merchant_id).kyc_name,
            visit_date=claim.event_date,
            requested_at=now,
        )
        rt.audit.append(
            at=now,
            actor="system",
            action="doctor.asked",
            subject_type="claim",
            subject_id=claim.id,
            data={"hospital_id": hospital.id, "doctor_registration_no": doctor.registration_no},
        )
        answered_at = now
        try:
            answer = await rt.integrations.doctor.ask(request)
            status, answered_by = answer.status, answer.answered_by
        except IntegrationError:
            logger.info("doctor %s did not answer for claim %s", doctor.registration_no, claim.id)
            status, answered_by = VerificationStatus.NO_ANSWER, None

        verification = DoctorVerification(
            id=rt.ids.next("doctor_verification"),
            claim_id=claim.id,
            hospital_id=hospital.id,
            doctor_registration_no=doctor.registration_no,
            status=status,
            requested_at=now,
            answered_at=None if status is VerificationStatus.NO_ANSWER else answered_at,
            answered_by=answered_by,
        )
        # NO_ANSWER covers an unreachable doctor and the X6 force. Chhatri wrote that row by
        # giving up waiting, so it is a system record; attributing it to the doctor would put
        # words in the mouth of someone who never spoke.
        answered = status is not VerificationStatus.NO_ANSWER
        rt.audit.append(
            at=answered_at,
            actor=f"doctor:{doctor.registration_no}" if answered else "system",
            action="doctor.answered",
            subject_type="claim",
            subject_id=claim.id,
            data={"status": status.value},
        )
        rt.feed.add(
            answered_at,
            "checkin",
            f"{doctor.name} at {hospital.name}: {status.value.lower().replace('_', ' ')}",
            merchant_id=merchant_id,
        )
        return _Confirmation(consent=True, consent_at=now, verification=verification, decided_at=answered_at)

    def _claim(
        self,
        merchant_id: str,
        slip: SlipExtraction,
        media_id: str,
        first: date,
        verified: tuple[date, ...],
        now: datetime,
    ) -> Claim:
        rt = self._link.rt
        paid_day = verified[0] if verified else first
        expected = rt.world.model.day_range_paise(rt.static.city, rt.world.history, merchant_id, paid_day)[1]
        return Claim(
            id=rt.ids.next("claim"),
            kind=ClaimKind.PERSONAL,
            merchant_id=merchant_id,
            created_at=now,
            event_date=verified[-1] if verified else first,
            silent_dates=verified,
            slip=slip,
            slip_media_id=media_id,
            expected_day_paise=publish_expected_day(expected),
        )

    def _feed(self, decision: Decision, claim: Claim, now: datetime) -> None:
        rt = self._link.rt
        shop = rt.static.city.merchant(decision.merchant_id).shop_name
        days = ", ".join(weekday_day_month(d) for d in claim.silent_dates) or "no verified silent day"
        text = f"Personal claim of {shop} for {days}: {decision.outcome.value}"
        rt.feed.add(now, "decision", text, merchant_id=decision.merchant_id)
