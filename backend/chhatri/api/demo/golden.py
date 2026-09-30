"""What the demo must show, as the deck and SPEC write it (SPEC §13.4, §13.6, §17.2; B1, B2, B5).

`DemoNumbers` holds the few free numbers of the story; `expectations` spells out every string,
time and count the flows observe, built from those numbers with the same formats the product uses
(``format_inr``, SPEC §9.6 formulas, §13.4 templates). `GOLDEN` are the SPEC §17.2 numbers the full
artefacts must reproduce. The small test city is not calibrated, so its tests build `DemoNumbers`
from their own run and check every other string, time and count against it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, Final

from chhatri.money import format_inr

__all__ = ["GOLDEN", "DemoNumbers", "expectations"]

ALERT_ID: Final = "A-20250818-01"  # SPEC §17.2
FIRST_CASE: Final = "C-2291"  # SPEC §3, §12
TRIGGER_TIME: Final = "17:00"
CREDIT_TIME: Final = "17:04"  # B1: +payout_rail_delay_minutes
PAUSE_TIME: Final = "17:05"  # B1: +instalment_pause_delay_minutes
CLAIM_TIME: Final = "11:21"  # the personal flows answer the 11:20 check-in a minute later
CLAIM_CREDIT_TIME: Final = "11:25"
TRIGGERED_ZONES: Final = ("Z3", "Z7", "Z12")
MAP_ZONES: Final = ("Z3", "Z7", "Z9", "Z12")
MONTHS_EN: Final = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip
Expected = dict[str, Any]


@dataclass(frozen=True, slots=True)
class DemoNumbers:
    """The free numbers of the demo; every other expectation is derived from them."""

    zone_index: Mapping[str, int]
    zone_shops: Mapping[str, int]
    z9_index: int
    shops_paid: int
    anil_expected_paise: int
    anil_payout_paise: int
    z7_total_paise: int
    instalment_paise: int
    personal_paise: int
    cover_starts_on: date

    @property
    def anil_drop_pct(self) -> int:
        """Anil is in Z7: drop = 100 − Z7's window index (SPEC §4.3)."""
        return 100 - self.zone_index["Z7"]


GOLDEN: Final = DemoNumbers(
    zone_index=MappingProxyType({"Z3": 38, "Z7": 37, "Z12": 47}),
    zone_shops=MappingProxyType({"Z3": 141, "Z7": 46, "Z9": 64, "Z12": 125}),
    z9_index=61,
    shops_paid=312,
    anil_expected_paise=438_000,
    anil_payout_paise=138_000,
    z7_total_paise=5_890_000,
    instalment_paise=60_000,
    personal_paise=150_000,
    cover_starts_on=date(2025, 8, 25),
)


def _zone_label(n: DemoNumbers, zone_id: str) -> str:
    pct = n.z9_index if zone_id == "Z9" else n.zone_index[zone_id]
    return f"{zone_id} · {pct}% · {n.zone_shops[zone_id]} shops"


def _monsoon_map(n: DemoNumbers) -> Expected:
    expected: Expected = {
        "clock at 17:00": "Mumbai · monsoon replay · 17:00 · simulated",
        "demo merchant": "S-0142",
        "triggers": [
            f"{z} · {n.zone_index[z]}% · {n.zone_shops[z]} shops · {TRIGGER_TIME}" for z in TRIGGERED_ZONES
        ],
        "Z9 status": "slow_day",
        "Z9 explanation": (
            f"Why Zone 9 got nothing: its sales fell to {n.z9_index}% on a day with no weather alert. "
            "That's a slow day, not a loss event, so Chhatri doesn't pay."
        ),
        "KPI zones triggered": len(TRIGGERED_ZONES),
        "KPI shops paid": n.shops_paid,
        "KPI trigger to money (min)": 4,
        "area decisions at": [TRIGGER_TIME],
        "area decisions approved": n.shops_paid,
        "payouts credited at": [CREDIT_TIME],
        "payouts credited": n.shops_paid,
        "instalments paused at": [PAUSE_TIME],
    }
    for zone_id in MAP_ZONES:
        expected[f"{zone_id} map label"] = _zone_label(n, zone_id)
    return expected


def _monsoon_anil(n: DemoNumbers) -> Expected:
    drop, paid, instalment = n.anil_drop_pct, format_inr(n.anil_payout_paise), format_inr(n.instalment_paise)
    usual = format_inr(n.anil_expected_paise)
    return {
        "Z7 panel": [
            "Alert: Red alert from 14:00",
            f"Sales: {n.zone_index['Z7']}% of expected for 3 hours",
            f"Cover: {n.zone_shops['Z7']} of {n.zone_shops['Z7']} prepaid",
            f"Paid: {CREDIT_TIME}, with the settlement",
            f"Total: {format_inr(n.z7_total_paise)} · instalments paused",
        ],
        "Anil payout": f"{paid} · CREDITED {CREDIT_TIME}",
        "Anil formula": f"½ × {usual} × {drop}% = {paid}",
        "Anil messages": [
            f"{CREDIT_TIME} OUTBOUND TEXT",
            f"{CREDIT_TIME} OUTBOUND PAYOUT_CARD",
            f"{CREDIT_TIME} OUTBOUND SOUNDBOX",
            f"{PAUSE_TIME} OUTBOUND TEXT",
        ],
        "Anil rain message": [
            f"अनिल जी, आज भारी बारिश से आपके इलाके की बिक्री {drop}% गिरी।",
            f"Anil ji, heavy rain cut your area's sales by {drop}% today.",
        ],
        "Anil payout card": [paid, "Credited with today's settlement", "No claim needed"],
        "Anil Soundbox": [f"Paytm par {paid} prapt hue — Chhatri se", f"{paid} received on Paytm, from Chhatri"],
        "Anil instalment message": [
            f"कल की {instalment} की किस्त रोक दी गई है।",
            f"Tomorrow's {instalment} instalment is paused.",
        ],
        "EXPLAINED why reply": [
            f"आपका आम मंगलवार: {usual}। आज आपके इलाके की बिक्री {drop}% गिरी। छतरी खोई हुई बिक्री का आधा देती है।",
            f"Your usual Tuesday: {usual}. Your area fell {drop}%. Chhatri pays half the lost sales.",
        ],
        "EXPLAINED dispute heard": "मेरा नुकसान ज़्यादा हुआ।",
        "EXPLAINED dispute reply": [
            "Okay, I'm sending this to our team. You'll hear back within 24 hours.",
            f"Sent to a claims officer · case {FIRST_CASE}",
        ],
        "EXPLAINED case": [f"{FIRST_CASE} · DISPUTE · OPEN"],
        "audit chain valid": True,
    }


def _silent_shop() -> Expected:
    return {
        "demo merchant": "S-0142",
        "check-in": [
            "11:20 OUTBOUND TEXT अनिल जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है? | "
            "Your shop has been closed since yesterday. Is everything okay?"
        ],
        "voice reply heard": "मैं अस्पताल में हूँ, बुखार है।",
        "voice reply answer": ["Get well soon. Please send one photo of the hospital slip."],
    }


def _illness(n: DemoNumbers) -> Expected:
    paid = format_inr(n.personal_paise)
    return _silent_shop() | {
        "slip reply": [],
        "slip decision": f"APPROVED · {paid} · {CLAIM_TIME}",
        "paid payout": f"{paid} · CREDITED {CLAIM_CREDIT_TIME}",
        "paid message": f"Anil ji, your claim is approved. {paid} credited with today's settlement.",
        "instalment message": f"Today's {format_inr(n.instalment_paise)} instalment is paused.",
        "loan": format_inr(n.instalment_paise),
        "audit chain valid": True,
    }


def _illness_mismatch(n: DemoNumbers) -> Expected:
    paid = format_inr(n.personal_paise)
    return _silent_shop() | {
        "slip reply": [
            "Thank you. The name on the slip doesn't match your KYC, so our team will check it. "
            "You'll hear back within 24 hours.",
            f"Sent to a claims officer · case {FIRST_CASE}",
        ],
        "slip decision": "REFERRED",
        "failed checks": ["NAME_MATCHES_KYC"],
        "payouts before the officer": 0,
        "open case": [f"{FIRST_CASE} · PERSONAL_CLAIM_REVIEW · OPEN"],
        "slip patient": "Sunil Pawar",
        "officer decision": f"APPROVED · {paid} · officer:officer",
        "case after the officer": "APPROVED",
        "officer payout": f"{paid} · CREDITED {CLAIM_CREDIT_TIME}",
        "officer message": f"Anil ji, our team approved your claim. {paid} credited.",
        "audit chain valid": True,
    }


def _buy_cover(n: DemoNumbers) -> Expected:
    starts = n.cover_starts_on
    starts_en = f"{starts.day} {MONTHS_EN[starts.month - 1]}"
    return {
        "clock": "Mumbai · buy cover replay · 18:10 · simulated",
        "demo merchant": "S-0907",
        "alert in the feed": f"{ALERT_ID} · RED",
        "Ramesh covered before": False,
        "cover reply": [
            f"New cover starts after the waiting period — from {starts_en}. It won't apply to tomorrow's alert."
        ],
        "cover link sent": True,
        "quote": f"BLOCKED · starts {starts.isoformat()}",
        "premium link": True,
        "premium paid": "paid",
        "cover after payment": f"WAITING · starts {starts.isoformat()}",
        "audit chain valid": True,
    }


def expectations(n: DemoNumbers) -> Mapping[str, Mapping[str, Any]]:
    """Scenario → check name → expected value, in the order the report prints them."""
    return MappingProxyType(
        {
            "monsoon": MappingProxyType(_monsoon_map(n) | _monsoon_anil(n)),
            "illness": MappingProxyType(_illness(n)),
            "illness_mismatch": MappingProxyType(_illness_mismatch(n)),
            "buy_cover": MappingProxyType(_buy_cover(n)),
        }
    )
