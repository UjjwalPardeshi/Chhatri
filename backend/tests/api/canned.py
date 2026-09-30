"""Canned SPEC §19.2-shaped payloads with the deck's numbers (slides 1, 3, 6, 7, 8).

The fake views (``tests/api/fake_views.py``) serve these; ``test_schemas.py`` proves every one of
them validates against ``chhatri.api.schemas``.
"""

from __future__ import annotations

import hashlib
from types import MappingProxyType
from typing import Any, Final

from chhatri.money import format_inr

MONSOON_DAY: Final = "2025-08-19"
ALERT_ID: Final = "A-20250818-01"


def ts(hhmm: str, day: str = MONSOON_DAY) -> str:
    """ISO IST timestamp for ``HH:MM`` on ``day``."""
    return f"{day}T{hhmm}:00+05:30"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


ZONE_ALERT: Final = MappingProxyType(
    {
        "id": ALERT_ID,
        "level": "RED",
        "kind": "RAIN",
        "valid_from": ts("14:00"),
        "valid_to": ts("20:00"),
        "headline_en": "Red alert: extremely heavy rain",
    }
)

# zone id → (ward, name, shops, index %, status, hours below, alerted)
ZONES: Final = MappingProxyType(
    {
        "Z3": ("G/S", "Worli · Lower Parel", 141, 38, "triggered", 3, True),
        "Z7": ("F/S", "Parel · Lalbaug", 46, 37, "triggered", 3, True),
        "Z9": ("M/W", "Chembur", 25, 61, "slow_day", 3, False),
        "Z12": ("E", "Byculla", 125, 47, "triggered", 3, True),
    }
)
Z9_EXPLANATION: Final = (
    "Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. "
    "That's a slow day, not a loss event, so Chhatri doesn't pay."
)
Z7_TOTAL_PAISE: Final = 5_890_000
TOTAL_PAID_PAISE: Final = 41_234_500


def zone_snapshot(zone_id: str) -> dict[str, Any]:
    ward, name, shops, index, status, below, alerted = ZONES[zone_id]
    return {
        "zone_id": zone_id,
        "ward": ward,
        "name": name,
        "shops": shops,
        "index_pct": index,
        "live_index_pct": index,
        "lower_bound_pct": 50,
        "status": status,
        "hours_below": below,
        "alert": dict(ZONE_ALERT) if alerted else None,
        "label": f"{zone_id} · {index}% · {shops} shops",
    }


def kpis() -> dict[str, Any]:
    return {
        "zones_triggered": 3,
        "shops_paid": 312,
        "trigger_to_money_min": 4,
        "total_paid_paise": TOTAL_PAID_PAISE,
        "total_paid_label": format_inr(TOTAL_PAID_PAISE),
        "instalments_paused": 298,
    }


def alert() -> dict[str, Any]:
    return {
        "id": ALERT_ID,
        "kind": "RAIN",
        "level": "RED",
        "zone_ids": ["Z3", "Z7", "Z12"],
        "issued_at": ts("17:30", "2025-08-18"),
        "valid_from": ts("14:00"),
        "valid_to": ts("20:00"),
        "source": "IMD Mumbai (simulated)",
        "headline_en": "Red alert: extremely heavy rain",
        "headline_hi": "रेड अलर्ट: अत्यधिक भारी बारिश",
    }


def trigger(zone_id: str = "Z7") -> dict[str, Any]:
    index = ZONES[zone_id][3]
    return {
        "id": f"E-{zone_id}-20250819",
        "zone_id": zone_id,
        "alert_id": ALERT_ID,
        "window_start": ts("14:00"),
        "window_end": ts("17:00"),
        "index_pct": index,
        "drop_pct": 100 - index,
        "hourly_index_pct": [index + 2, index, index - 2],
        "lower_bound_pct": 50,
        "shops_in_index": ZONES[zone_id][2],
        "fired_at": ts("17:00"),
    }


def rain_band() -> dict[str, Any]:
    ring = [[72.83, 19.0], [72.85, 19.0], [72.85, 19.02], [72.83, 19.0]]
    feature = {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {"id": "Z7"},
    }
    return {"type": "FeatureCollection", "features": [feature]}


def feed() -> list[dict[str, Any]]:
    return [
        {
            "id": 41,
            "at": ts("17:00"),
            "type": "trigger",
            "text_en": "Zone 7 triggered at 37%",
            "zone_id": "Z7",
        },
        {
            "id": 57,
            "at": ts("17:04"),
            "type": "payout",
            "text_en": "₹1,380 paid to Anil",
            "merchant_id": "S-0142",
        },
    ]


def snapshot(clock: dict[str, Any], demo_merchant_id: str) -> dict[str, Any]:
    return {
        "clock": clock,
        "zones": [zone_snapshot(zone_id) for zone_id in ZONES],
        "hexes": {"883c9e0a21fffff": 37, "883c9e0a23fffff": 41.5, "883c9e0a25fffff": None},
        "kpis": kpis(),
        "triggers": [trigger(zone_id) for zone_id in ("Z3", "Z7", "Z12")],
        "explanations": {"Z9": Z9_EXPLANATION},
        "feed": feed(),
        "demo_merchant_id": demo_merchant_id,
        "rain_band": rain_band(),
    }


def zone_panel(zone_id: str) -> dict[str, Any]:
    triggered = ZONES[zone_id][4] == "triggered"
    rows = [
        {"label": "Alert", "value": "Red alert from 14:00" if triggered else "No weather alert"},
        {"label": "Sales", "value": f"{ZONES[zone_id][3]}% of expected for 3 hours"},
        {"label": "Cover", "value": f"{ZONES[zone_id][2]} of {ZONES[zone_id][2]} prepaid"},
        {"label": "Paid", "value": "17:04, with the settlement" if triggered else "Not paid"},
        {"label": "Total", "value": f"{format_inr(Z7_TOTAL_PAISE)} · instalments paused"},
    ]
    total = Z7_TOTAL_PAISE if zone_id == "Z7" else 0
    return {
        "zone": zone_snapshot(zone_id),
        "triggered": triggered,
        "rows": rows,
        "explanation": None if triggered else Z9_EXPLANATION,
        "shops_paid": ZONES[zone_id][2] if triggered else 0,
        "total_paid_paise": total,
        "total_paid_label": format_inr(total),
        "hourly": [{"hour": f"{hour:02d}:00", "index_pct": 96 - hour} for hour in range(8, 17)],
    }


def policy_view() -> dict[str, Any]:
    return {
        "rules": {"version": "2025.08-pilot", "share_pct": 50, "area_daily_cap_paise": 250_000},
        "authority": [
            {
                "case": "Area drop during an alert, index clear",
                "alone": "Pays",
                "human": "Only if the merchant disputes",
            },
            {"case": "Cover bought after an alert", "alone": "Never", "human": "Waiting period applies"},
        ],
        "checks": [
            {
                "code": "COVER_IN_FORCE",
                "severity": "HARD",
                "applies": "all",
                "passes_when": "cover is active",
            },
            {
                "code": "NAME_MATCHES_KYC",
                "severity": "SOFT",
                "applies": "personal",
                "passes_when": "score ≥ 85",
            },
        ],
    }


def backtest_report() -> dict[str, Any]:
    return {
        "label": "simulated sales · real Open-Meteo rainfall",
        "seasons": ["2024", "2025"],
        "generated_at": "2026-09-28T10:00:00+05:30",
        "triggers": [
            {
                "name": "chhatri",
                "real_drops": 40,
                "real_drops_paid": 36,
                "recall": 0.9,
                "payouts": 38,
                "payouts_no_real_drop": 2,
                "false_positive_rate": 0.05,
                "paid_paise": 12_000_000,
                "trigger_to_money": "same day",
                "documents_per_area_claim": 0,
            }
        ],
        "zones": [
            {
                "zone_id": "Z7",
                "premium_per_day_label": "₹1.80",
                "premiums_paise": 3_000_000,
                "payouts_paise": 1_800_000,
                "loss_ratio": 0.6,
                "chhatri_fp": 0,
                "chhatri_fn": 1,
            }
        ],
        "personal": {"claims": 20, "auto_paid": 15, "referred": 5, "referred_share": 0.25},
        "notes": ["Weather data by Open-Meteo.com"],
    }


def preflight() -> list[dict[str, Any]]:
    return [
        {"name": "artefacts", "ok": True, "detail": "model and calibration loaded"},
        {"name": "scenario", "ok": True, "detail": "monsoon loadable"},
        {"name": "integrations", "ok": True, "detail": "15 components reported"},
        {"name": "clock", "ok": True, "detail": "paused at 08:00"},
    ]


def geojson(kind: str) -> dict[str, Any]:
    ring = [[72.8, 19.0], [72.9, 19.0], [72.9, 19.1], [72.8, 19.0]]
    props = {"id": "Z7", "ward": "F/S", "name": "Parel", "shops": 46, "waterlogging_prone": True}
    if kind == "hexes":
        props = {"h3": "883c9e0a21fffff", "zone_id": "Z7", "shops": 12}
    feature = {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": props}
    return {"type": "FeatureCollection", "features": [feature]}
