"""The backtest report: SPEC §19.2 `BacktestReport` JSON, its Markdown twin and premiums.json (§18).

Outputs (decision B6, written only by `chhatri.backtest`):
- `<artifacts>/backtest/report.json` — exactly the §19.2 shape, UTF-8, 2-space indent;
- `<artifacts>/backtest/report.md` — the same numbers for humans;
- `<artifacts>/premiums.json` — `{zone_id: premium_per_day_paise}` for every zone (SPEC §9.1).
Files are written to a temporary name and renamed, so a reader never sees half a file.
`generated_at` is the simulated time the data ends (midnight after the last season), never the wall
clock, so the same seed and inputs give byte-identical files (SPEC §0.2).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from chhatri.backtest.config import DOCUMENTS_PER_AREA_CLAIM, REPORT_LABEL
from chhatri.backtest.metrics import PersonalMetrics, TriggerMetrics, ZoneEconomics
from chhatri.money import format_inr

logger = logging.getLogger(__name__)

REPORT_DIR: Final = "backtest"
REPORT_JSON: Final = "report.json"
REPORT_MD: Final = "report.md"
PREMIUMS_JSON: Final = "premiums.json"
JSON_INDENT: Final = 2
PCT: Final = 100
TRIGGER_TITLES: Final = {"chhatri": "Chhatri", "weather_only": "Weather-only"}


@dataclass(frozen=True, slots=True)
class ReportInputs:
    seasons: tuple[str, ...]
    generated_at: str
    chhatri: TriggerMetrics
    chhatri_to_money: str
    weather: TriggerMetrics
    weather_to_money: str
    zones: tuple[ZoneEconomics, ...]
    personal: PersonalMetrics
    notes: tuple[str, ...]


def _trigger(metrics: TriggerMetrics, to_money: str) -> dict[str, Any]:
    return {
        "name": metrics.name,
        "real_drops": metrics.real_drops,
        "real_drops_paid": metrics.real_drops_paid,
        "recall": metrics.recall,
        "payouts": metrics.payouts,
        "payouts_no_real_drop": metrics.payouts_no_real_drop,
        "false_positive_rate": metrics.false_positive_rate,
        "paid_paise": metrics.paid_paise,
        "trigger_to_money": to_money,
        "documents_per_area_claim": DOCUMENTS_PER_AREA_CLAIM,
    }


def _zone(zone: ZoneEconomics) -> dict[str, Any]:
    return {
        "zone_id": zone.zone_id,
        "premium_per_day_label": format_inr(zone.premium_per_day_paise),
        "premiums_paise": zone.premiums_paise,
        "payouts_paise": zone.payouts_paise,
        "loss_ratio": zone.loss_ratio,
        "chhatri_fp": zone.chhatri_fp,
        "chhatri_fn": zone.chhatri_fn,
    }


def build_report(inputs: ReportInputs) -> dict[str, Any]:
    """The SPEC §19.2 BacktestReport dict (key order fixed)."""
    personal = inputs.personal
    return {
        "label": REPORT_LABEL,
        "seasons": list(inputs.seasons),
        "generated_at": inputs.generated_at,
        "triggers": [
            _trigger(inputs.chhatri, inputs.chhatri_to_money),
            _trigger(inputs.weather, inputs.weather_to_money),
        ],
        "zones": [_zone(z) for z in inputs.zones],
        "personal": {
            "claims": personal.claims,
            "auto_paid": personal.auto_paid,
            "referred": personal.referred,
            "referred_share": personal.referred_share,
        },
        "notes": list(inputs.notes),
    }


def _pct(value: float) -> str:
    return f"{round(value * PCT)}%"


def _trigger_rows(triggers: Sequence[Mapping[str, Any]]) -> list[str]:
    header = "| Measure | " + " | ".join(TRIGGER_TITLES[t["name"]] for t in triggers) + " |"
    rows = [header, "|---|" + "---|" * len(triggers)]
    cells = {
        "Real sales drops that get paid": lambda t: (
            f"{t['real_drops_paid']} of {t['real_drops']} ({_pct(t['recall'])})"
        ),
        "Payouts with no real drop": lambda t: (
            f"{t['payouts_no_real_drop']} of {t['payouts']} ({_pct(t['false_positive_rate'])})"
        ),
        "Trigger to money": lambda t: t["trigger_to_money"],
        "Documents per area claim": lambda t: str(t["documents_per_area_claim"]),
        "Total paid": lambda t: format_inr(t["paid_paise"]),
    }
    for label, cell in cells.items():
        rows.append(f"| {label} | " + " | ".join(cell(t) for t in triggers) + " |")
    return rows


def _zone_rows(zones: Sequence[Mapping[str, Any]]) -> list[str]:
    rows = [
        "| Zone | Premium / day | Premiums | Payouts | Loss ratio | False + | Missed |",
        "|---|---|---|---|---|---|---|",
    ]
    for z in zones:
        rows.append(
            f"| {z['zone_id']} | {z['premium_per_day_label']} | {format_inr(z['premiums_paise'])} | "
            f"{format_inr(z['payouts_paise'])} | {_pct(z['loss_ratio'])} | {z['chhatri_fp']} | {z['chhatri_fn']} |"
        )
    return rows


def render_markdown(report: Mapping[str, Any]) -> str:
    """report.md: the same numbers as report.json."""
    personal = report["personal"]
    lines = [
        "# Chhatri backtest · two past monsoons",
        "",
        f"*{report['label']}* · {' · '.join(report['seasons'])} · data to {report['generated_at']}",
        "",
        "## Chhatri vs a weather-only trigger",
        "",
        *_trigger_rows(report["triggers"]),
        "",
        "## Doubtful personal claims seen by a human",
        "",
        f"{personal['referred']} of {personal['claims']} personal claims referred to a claims officer "
        f"({_pct(personal['referred_share'])}); {personal['auto_paid']} paid automatically.",
        "",
        "## Premiums vs payouts, per zone",
        "",
        *_zone_rows(report["zones"]),
        "",
        "## Notes",
        "",
        *(f"- {note}" for note in report["notes"]),
        "",
    ]
    return "\n".join(lines)


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        logger.exception("cannot write %s", path)
        tmp.unlink(missing_ok=True)
        raise


def to_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=JSON_INDENT) + "\n"


def write_outputs(
    artifacts_dir: Path, report: Mapping[str, Any], premiums: Mapping[str, int]
) -> tuple[Path, ...]:
    """Write report.json, report.md and premiums.json (module docstring); returns the paths."""
    report_dir = Path(artifacts_dir) / REPORT_DIR
    paths = (report_dir / REPORT_JSON, report_dir / REPORT_MD, Path(artifacts_dir) / PREMIUMS_JSON)
    _write_atomic(paths[0], to_json(report))
    _write_atomic(paths[1], render_markdown(report))
    _write_atomic(paths[2], to_json(dict(premiums)))
    for path in paths:
        logger.info("wrote %s", path)
    return paths
