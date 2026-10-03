"""H13: where every check and every money number of a decision came from (fs-09 section 8). Pure: no I/O.

`build_sources(facts, decision, rules)` returns one `SourcedLine` for each check of the decision and, when the decision
has an explanation, one for each money fact (the usual day, the area index and drop, the share, the cap, the days and the
amount). A line carries its clause (C1 to C12 of the policy wording) and one or more `Source` objects that point at the
records the engine saw: an alert, a trigger, a cover, a slip, the merchant's sales for a day, the payout history, a
key of rules.yaml. This is the only module that creates a `Source`; the app and any language model only display them.

The label of a source comes from the catalogue (`SRC_*`; an alert's label is its own `source` text), and a label never
says that an outside body verified a value. The origin is read from the record: a slip read by the live reader is LIVE,
an alert whose own text does not say "simulated" is LIVE, the rules, clauses and zone bounds are CONFIG, and the rest of
the prototype's inputs are SIMULATED. A check always has a source: with no record to point at it cites its clause.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Final

from chhatri.conversation.messages import render
from chhatri.domain.enums import CheckCode, ClaimKind, SourceKind, SourceOrigin
from chhatri.domain.models import Claim, Decision, Source, SourcedLine
from chhatri.money import format_inr
from chhatri.policy.facts import AreaClaimFacts, PersonalClaimFacts
from chhatri.policy.rules import PolicyRules

__all__ = [
    "CHECK_CLAUSE",
    "CHECK_SOURCE_KINDS",
    "CLAUSES",
    "FACT_KEYS",
    "LIVE_SLIP_SOURCE",
    "build_sources",
    "clause_source",
    "rules_source",
    "slip_origin",
]

Facts = AreaClaimFacts | PersonalClaimFacts
Maker = Callable[["_Ctx", str], list[Source]]

CLAUSES: Final = tuple(f"C{n}" for n in range(1, 13))
LIVE_SLIP_SOURCE: Final = "sarvam-doc-ai"
LIVE_SLIP_SOURCES: Final = frozenset({LIVE_SLIP_SOURCE, "gemini-vision"})  # fs-09 8.3: both live readers
HALF_SHARE_PCT: Final = 50
SIMULATED_WORD: Final = "simulated"

_K, _C = SourceKind, CheckCode
# fs-09 8.4: the kinds of source each check cites, and the clause of the policy wording it belongs to.
CHECK_SOURCE_KINDS: Final[Mapping[CheckCode, tuple[SourceKind, ...]]] = MappingProxyType(
    {
        _C.COVER_IN_FORCE: (_K.COVER, _K.RULES),
        _C.PREMIUM_PREPAID: (_K.PREMIUM, _K.COVER),
        _C.COVER_BEFORE_ALERT: (_K.COVER, _K.ALERT),
        _C.ALERT_ACTIVE: (_K.ALERT, _K.SALES_INDEX),
        _C.INDEX_QUORUM: (_K.SALES_INDEX, _K.RULES),
        _C.BELOW_FLOOR: (_K.SALES_INDEX, _K.RULES),
        _C.BELOW_MODEL_RANGE: (_K.SALES_INDEX, _K.ZONE_BOUND),
        _C.SILENCE_VERIFIED: (_K.SALES_DAY,),
        _C.SLIP_READABLE: (_K.SLIP, _K.RULES),
        _C.NAME_MATCHES_KYC: (_K.SLIP, _K.KYC, _K.RULES),
        _C.DATES_MATCH: (_K.SLIP, _K.SALES_DAY),
        _C.HOSPITAL_IDENTIFIED: (_K.SLIP,),
        _C.DOCTOR_IDENTIFIED: (_K.SLIP,),
        _C.VERIFICATION_CONSENT: (_K.DOCTOR,),
        _C.DOCTOR_NOT_DENIED: (_K.DOCTOR,),
        _C.DOCTOR_CONFIRMED: (_K.DOCTOR,),
        _C.WITHIN_AUTO_LIMIT: (_K.RULES,),
        _C.NOT_ALREADY_PAID: (_K.PAYOUT_HISTORY,),
        _C.WITHIN_ANNUAL_LIMIT: (_K.PAYOUT_HISTORY, _K.RULES),
    }
)
CHECK_CLAUSE: Final[Mapping[CheckCode, str]] = MappingProxyType(
    {
        _C.COVER_IN_FORCE: "C5",
        _C.PREMIUM_PREPAID: "C6",
        _C.COVER_BEFORE_ALERT: "C5",
        _C.ALERT_ACTIVE: "C2",
        _C.INDEX_QUORUM: "C2",
        _C.BELOW_FLOOR: "C2",
        _C.BELOW_MODEL_RANGE: "C2",
        _C.SILENCE_VERIFIED: "C3",
        _C.SLIP_READABLE: "C3",
        _C.NAME_MATCHES_KYC: "C3",
        _C.DATES_MATCH: "C3",
        _C.HOSPITAL_IDENTIFIED: "C3",
        _C.DOCTOR_IDENTIFIED: "C3",
        _C.VERIFICATION_CONSENT: "C3",
        _C.DOCTOR_NOT_DENIED: "C3",
        _C.DOCTOR_CONFIRMED: "C3",
        _C.WITHIN_AUTO_LIMIT: "C3",
        _C.NOT_ALREADY_PAID: "C7",
        _C.WITHIN_ANNUAL_LIMIT: "C4",
    }
)
# The keys of rules.yaml a check cites when its kinds include RULES.
CHECK_RULE_KEYS: Final[Mapping[CheckCode, tuple[str, ...]]] = MappingProxyType(
    {
        _C.COVER_IN_FORCE: ("cover.waiting_period_days",),
        _C.INDEX_QUORUM: ("area.min_shops_in_index",),
        _C.BELOW_FLOOR: ("area.index_floor_pct", "area.consecutive_hours"),
        _C.SLIP_READABLE: ("personal.slip_confidence_min",),
        _C.NAME_MATCHES_KYC: ("personal.name_match_min_score",),
        _C.WITHIN_AUTO_LIMIT: ("personal.max_auto_days",),
        _C.WITHIN_ANNUAL_LIMIT: ("annual_limit_rupees",),
    }
)
AREA_FACT_KEYS: Final = ("expected_day", "area_index", "drop_pct", "share", "cap", "amount")
PERSONAL_FACT_KEYS: Final = ("expected_day", "share", "cap", "days", "amount")
FACT_KEYS: Final = frozenset(AREA_FACT_KEYS) | frozenset(PERSONAL_FACT_KEYS)
CAP_RULE_KEY: Final = {
    ClaimKind.AREA: "area.daily_cap_rupees",
    ClaimKind.PERSONAL: "personal.daily_cap_rupees",
}


def _share_text(share_pct: int) -> str:
    """ "half" for the pilot's 50 %, else the percentage."""
    return "half" if share_pct == HALF_SHARE_PCT else f"{share_pct}%"


def _days_text(days: int) -> str:
    return f"{days} day" if days == 1 else f"{days} days"


def slip_origin(source: str | None) -> SourceOrigin:
    """LIVE only for a slip the live reader read (fs-09 8.3); anything else is simulated."""
    return SourceOrigin.LIVE if source in LIVE_SLIP_SOURCES else SourceOrigin.SIMULATED


def alert_origin(own_source: str) -> SourceOrigin:
    """An alert says in its own `source` text when it is simulated."""
    return SourceOrigin.SIMULATED if SIMULATED_WORD in own_source.lower() else SourceOrigin.LIVE


def rules_source(rules: PolicyRules, key: str, clause: str) -> Source:
    """A key of rules.yaml, for example ``area.index_floor_pct`` (CONFIG, no time)."""
    label = render("SRC_RULES", "en", rules_version=rules.version)
    return Source(
        kind=_K.RULES,
        label=label,
        ref=f"rules:{rules.version}:{key}",
        as_of=None,
        origin=SourceOrigin.CONFIG,
        clause=clause,
    )


def clause_source(clause: str) -> Source:
    """A clause of the policy wording (CONFIG, no time)."""
    label = render("SRC_CLAUSE", "en", clause=clause)
    return Source(
        kind=_K.CLAUSE,
        label=label,
        ref=f"clause:{clause}",
        as_of=None,
        origin=SourceOrigin.CONFIG,
        clause=clause,
    )


def expected_day_of(claim: Claim) -> date:
    """The day whose usual sales the claim pays: the first silent day of a personal claim, else the event day."""
    if claim.kind is ClaimKind.PERSONAL and claim.silent_dates:
        return claim.silent_dates[0]
    return claim.event_date


@dataclass(frozen=True, slots=True)
class _Ctx:
    """What the makers read: the facts the engine saw, the decision it made and the rules."""

    facts: Facts
    decision: Decision
    rules: PolicyRules

    def make(
        self,
        kind: SourceKind,
        ref: str,
        clause: str,
        *,
        as_of: datetime | None,
        origin: SourceOrigin,
        **label: object,
    ) -> Source:
        return Source(
            kind=kind,
            label=render(f"SRC_{kind.value}", "en", **label),
            ref=ref,
            as_of=as_of,
            origin=origin,
            clause=clause,
        )

    @property
    def area(self) -> AreaClaimFacts | None:
        return self.facts if isinstance(self.facts, AreaClaimFacts) else None

    @property
    def claim(self) -> Claim:
        return self.facts.claim

    @property
    def merchant_id(self) -> str:
        return self.facts.merchant.id


def _alert(ctx: _Ctx, clause: str) -> list[Source]:
    area = ctx.area
    if area is None or area.alert is None:
        return []
    alert = area.alert
    source = Source(
        kind=_K.ALERT,
        label=alert.source,
        ref=f"alert:{alert.id}",
        as_of=alert.issued_at,
        origin=alert_origin(alert.source),
        clause=clause,
    )
    return [source]


def _sales_index(ctx: _Ctx, clause: str) -> list[Source]:
    area = ctx.area
    if area is None:
        return []
    trigger = area.trigger
    return [
        ctx.make(
            _K.SALES_INDEX,
            f"trigger:{trigger.id}",
            clause,
            as_of=trigger.fired_at,
            origin=SourceOrigin.SIMULATED,
        )
    ]


def _zone_bound(ctx: _Ctx, clause: str) -> list[Source]:
    zone = ctx.facts.merchant.zone_id
    return [ctx.make(_K.ZONE_BOUND, f"zone-bound:{zone}", clause, as_of=None, origin=SourceOrigin.CONFIG)]


def _forecast(ctx: _Ctx, clause: str) -> list[Source]:
    ref = f"forecast:{ctx.merchant_id}:{expected_day_of(ctx.claim).isoformat()}"
    return [ctx.make(_K.FORECAST, ref, clause, as_of=ctx.claim.created_at, origin=SourceOrigin.SIMULATED)]


def _cover(ctx: _Ctx, clause: str) -> list[Source]:
    cover = ctx.facts.cover
    if cover is None:
        return []
    return [
        ctx.make(
            _K.COVER, f"cover:{cover.id}", clause, as_of=cover.purchased_at, origin=SourceOrigin.SIMULATED
        )
    ]


def _premium(ctx: _Ctx, clause: str) -> list[Source]:
    cover = ctx.facts.cover
    if cover is None:
        return []
    ref = f"premium:{cover.id}"
    return [ctx.make(_K.PREMIUM, ref, clause, as_of=cover.purchased_at, origin=SourceOrigin.SIMULATED)]


def _kyc(ctx: _Ctx, clause: str) -> list[Source]:
    return [ctx.make(_K.KYC, f"kyc:{ctx.merchant_id}", clause, as_of=None, origin=SourceOrigin.SIMULATED)]


def _slip(ctx: _Ctx, clause: str) -> list[Source]:
    claim = ctx.claim
    if claim.kind is not ClaimKind.PERSONAL:
        return []
    origin = slip_origin(claim.slip.source if claim.slip is not None else None)
    ref = f"slip:{claim.slip_media_id or claim.id}"
    return [ctx.make(_K.SLIP, ref, clause, as_of=claim.created_at, origin=origin)]


def _sales_days(ctx: _Ctx, clause: str) -> list[Source]:
    claim = ctx.claim
    if claim.kind is not ClaimKind.PERSONAL:
        return []
    days = claim.silent_dates or (claim.event_date,)
    return [
        ctx.make(
            _K.SALES_DAY,
            f"sales:{ctx.merchant_id}:{day.isoformat()}",
            clause,
            as_of=claim.created_at,
            origin=SourceOrigin.SIMULATED,
        )
        for day in days
    ]


def _payout_history(ctx: _Ctx, clause: str) -> list[Source]:
    ref = f"payouts:{ctx.merchant_id}"
    return [
        ctx.make(_K.PAYOUT_HISTORY, ref, clause, as_of=ctx.decision.decided_at, origin=SourceOrigin.SIMULATED)
    ]


def _doctor(ctx: _Ctx, clause: str) -> list[Source]:
    """The directory record and the doctor's own answer — never anything printed on the slip."""
    facts = ctx.facts
    doctor = getattr(facts, "doctor", None)
    verification = getattr(facts, "verification", None)
    if doctor is None:
        return []
    status = verification.status.value if verification is not None else "NOT_ASKED"
    return [
        Source(
            kind=SourceKind.DOCTOR,
            label=f"{doctor.name}, {status.lower().replace('_', ' ')}",
            ref=f"doctor:{doctor.registration_no}",
            as_of=verification.answered_at if verification is not None else None,
            origin=SourceOrigin.SIMULATED,
            clause=clause,
        )
    ]


_MAKERS: Final[Mapping[SourceKind, Maker]] = MappingProxyType(
    {
        _K.DOCTOR: _doctor,
        _K.ALERT: _alert,
        _K.SALES_INDEX: _sales_index,
        _K.ZONE_BOUND: _zone_bound,
        _K.FORECAST: _forecast,
        _K.COVER: _cover,
        _K.PREMIUM: _premium,
        _K.KYC: _kyc,
        _K.SLIP: _slip,
        _K.SALES_DAY: _sales_days,
        _K.PAYOUT_HISTORY: _payout_history,
    }
)


def _check_line(ctx: _Ctx, code: CheckCode) -> SourcedLine:
    clause = CHECK_CLAUSE[code]
    sources: list[Source] = []
    for kind in CHECK_SOURCE_KINDS[code]:
        if kind is _K.RULES:
            sources += [rules_source(ctx.rules, key, clause) for key in CHECK_RULE_KEYS[code]]
        else:
            sources += _MAKERS[kind](ctx, clause)
    return SourcedLine(
        kind="CHECK", key=code.value, clause=clause, sources=tuple(sources or [clause_source(clause)])
    )


def _fact(
    key: str, label_key: str, value: str, clause: str, sources: list[Source], **label: object
) -> SourcedLine:
    return SourcedLine(
        kind="FACT",
        key=key,
        label_en=render(label_key, "en", **label),
        value=value,
        clause=clause,
        sources=tuple(sources or [clause_source(clause)]),
    )


def _fact_lines(ctx: _Ctx) -> list[SourcedLine]:
    """The money numbers of the explanation, each with the sources it came from (fs-09 8.4, second table)."""
    explanation, decision = ctx.decision.explanation, ctx.decision
    if explanation is None:
        return []
    area = explanation.drop_pct is not None
    lines = [
        _fact(
            "expected_day",
            "FACT_EXPECTED_DAY",
            format_inr(explanation.expected_day_paise),
            "C4",
            _forecast(ctx, "C4"),
            weekday_en=explanation.weekday_en,
            weekday_hi=explanation.weekday_hi,
        )
    ]
    if explanation.drop_pct is not None:
        index = [*_sales_index(ctx, "C2"), *_alert(ctx, "C2")]
        lines += [
            _fact("area_index", "FACT_AREA_INDEX", f"{100 - explanation.drop_pct}%", "C2", index),
            _fact("drop_pct", "FACT_DROP_PCT", f"{explanation.drop_pct}%", "C2", index),
        ]
    kind = ClaimKind.AREA if area else ClaimKind.PERSONAL
    lines += [
        _fact(
            "share",
            "FACT_SHARE",
            _share_text(explanation.share_pct),
            "C4",
            [rules_source(ctx.rules, "payout_share", "C4")],
        ),
        _fact(
            "cap",
            "FACT_CAP",
            format_inr(explanation.cap_paise),
            "C4",
            [rules_source(ctx.rules, CAP_RULE_KEY[kind], "C4")],
        ),
    ]
    if not area:
        lines.append(_fact("days", "FACT_DAYS", _days_text(explanation.days), "C3", _sales_days(ctx, "C3")))
    amount = Source(
        kind=_K.RULES,
        label=render("SRC_RULES", "en", rules_version=ctx.rules.version),
        ref=f"decision:{decision.id}",
        as_of=decision.decided_at,
        origin=SourceOrigin.CONFIG,
        clause="C4",
    )
    lines.append(_fact("amount", "FACT_AMOUNT", format_inr(explanation.amount_paise), "C4", [amount]))
    return lines


def build_sources(facts: Facts, decision: Decision, rules: PolicyRules) -> tuple[SourcedLine, ...]:
    """One line for each check of `decision`, then one for each money fact of its explanation."""
    ctx = _Ctx(facts, decision, rules)
    return (*(_check_line(ctx, check.code) for check in decision.checks), *_fact_lines(ctx))
