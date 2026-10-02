"""GET /api/preflight rows (SPEC §19): artefacts loaded, scenario loadable, integrations, clock.

Each row is ``{name, ok, detail}``. ``ok`` is False only for something that stops the demo or is
wrong: a missing model (no scenario can load), no loaded scenario, a broken audit chain. Missing
calibration, premiums or backtest artefacts are reported with ``ok`` False and the fallback the
static context uses (a premiums row lists the zones with no price), so the presenter sees them before going on stage. Simulated integrations are
``ok`` (SPEC §0: every integration has a labelled simulation); the detail says LIVE or SIMULATED.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from chhatri.integrations.free_tier import free_tier_gate_detail
from chhatri.replay.static import StaticContext

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = ["preflight_rows"]


def _row(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def _premiums_row(static: StaticContext) -> dict[str, Any]:
    """Not ok when a city zone has no price (X3): a cover quote for it would fail, so the zones are listed."""
    unpriced = static.zones_without_premium
    if not unpriced:
        return _row("premiums", True, f"{len(static.premiums)} zone premiums loaded")
    missing_file = "" if static.premiums_path.is_file() else f"{static.premiums_path} missing; "
    return _row(
        "premiums",
        False,
        f"{missing_file}no premium for zones {', '.join(unpriced)}; a cover quote for them fails",
    )


def _artefact_rows(static: StaticContext) -> list[dict[str, Any]]:
    zones = len(static.city.zones)
    model = (
        _row("model", True, f"expected-sales model loaded for {zones} zones")
        if static.model is not None
        else _row("model", False, static.model_error or "model missing")
    )
    calibration = (
        _row("calibration", True, f"{static.calibration_path.name} loaded")
        if static.calibration_path.is_file()
        else _row("calibration", False, f"{static.calibration_path} missing; documented defaults in use")
    )
    premiums = _premiums_row(static)
    backtest = (
        _row("backtest", True, "backtest report loaded")
        if static.backtest_report is not None
        else _row("backtest", False, "backtest report missing; GET /api/backtest answers 404")
    )
    city = _row("city", True, f"{len(static.city.merchants)} merchants in {zones} zones")
    # ADR 0009: a closed gate is safe (templates and simulators answer), so the row is ok either way.
    gate = _row("free_tier_gate", True, free_tier_gate_detail(static.settings))
    return [model, calibration, premiums, backtest, city, gate]


def _runtime_rows(rt: Runtime | None) -> list[dict[str, Any]]:
    if rt is None:
        return [
            _row("scenario", False, "no scenario loaded; POST /api/replay/load"),
            _row("clock", False, "no scenario loaded"),
        ]
    rows = [_row("scenario", True, f"{rt.scenario.name} loaded ({rt.scenario.title})")]
    rows += [
        _row(f"integration:{s.name}", True, f"{s.mode.value} · {s.detail}")
        for s in (*rt.integrations.statuses, *rt.integrations.gemini_statuses)  # X6: 17 rows, like the panel
    ]
    state = "running" if rt.engine.running else "paused"
    rows.append(_row("clock", True, f"{rt.clock.now():%Y-%m-%d %H:%M} simulated, {state}"))
    chain = rt.audit.verify()
    detail = f"{chain['entries']} entries, chain " + ("valid" if chain["valid"] else "broken")
    rows.append(_row("audit", bool(chain["valid"]), detail))
    return rows


def preflight_rows(static: StaticContext, rt: Runtime | None) -> list[dict[str, Any]]:
    """Every preflight row, artefacts first."""
    return _artefact_rows(static) + _runtime_rows(rt)
