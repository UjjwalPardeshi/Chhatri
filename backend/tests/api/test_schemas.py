"""The §19.2 mirror itself: strictness rules, and that every canned fake payload conforms (SPEC §19.2)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

import chhatri.api.schemas as schemas
from chhatri.api.requests import VoiceDemoKey
from chhatri.integrations.demo_voice import DEMO_UTTERANCES
from chhatri.replay import views
from tests.api import canned
from tests.api.fake_views import FAKES

VIEW_NAMES = (
    "clock_view",
    "zone_snapshot",
    "kpis_view",
    "snapshot",
    "zone_panel",
    "alert_view",
    "trigger_view",
    "decision_view",
    "payout_view",
    "pause_view",
    "merchant_summary",
    "merchant_detail",
    "message_view",
    "case_view",
    "audit_view",
    "policy_view",
    "integrations_view",
    "cover_view",
    "claims_view",
    "receipt_view",
)


def test_stream_event_types_match_the_event_bus() -> None:
    from chhatri.events import EVENT_TYPES

    assert set(schemas.StreamEventType.__args__) == set(EVENT_TYPES)


def test_replay_views_expose_every_spec_24_6_name() -> None:
    assert all(callable(getattr(views, name, None)) for name in VIEW_NAMES)
    assert set(FAKES) <= set(VIEW_NAMES)


def test_voice_demo_keys_match_the_canned_utterances() -> None:
    assert set(VoiceDemoKey.__args__) == set(DEMO_UTTERANCES)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (schemas.ZoneSnapshot, canned.zone_snapshot("Z7")),
        (schemas.ZoneSnapshot, canned.zone_snapshot("Z9")),
        (schemas.Kpis, canned.kpis()),
        (schemas.Alert, canned.alert()),
        (schemas.AreaTrigger, canned.trigger("Z12")),
        (schemas.FeatureCollection, canned.rain_band()),
        (schemas.ZonePanel, canned.zone_panel("Z7")),
        (schemas.ZonePanel, canned.zone_panel("Z9")),
        (schemas.PolicyView, canned.policy_view()),
        (schemas.BacktestReport, canned.backtest_report()),
        (schemas.FeatureCollection, canned.geojson("zones")),
        (schemas.FeatureCollection, canned.geojson("hexes")),
    ],
)
def test_canned_payloads_validate(model: type[BaseModel], payload: dict[str, Any]) -> None:
    model.model_validate(payload)


def test_canned_feed_and_preflight_validate() -> None:
    assert all(schemas.FeedItem.model_validate(item) for item in canned.feed())
    assert all(schemas.PreflightItem.model_validate(item) for item in canned.preflight())


def pause() -> dict[str, Any]:
    return {
        "id": "IP-000001",
        "loan_id": "L-0142",
        "merchant_id": "S-0142",
        "instalment_date": "2025-08-20",
        "amount_paise": 60_000,
        "amount_label": "₹600",
        "reason": "area payout",
        "decision_id": "D-000001",
        "created_at": canned.ts("17:05"),
    }


def test_labels_must_equal_format_inr() -> None:
    schemas.InstalmentPause.model_validate(pause())
    with pytest.raises(ValidationError, match="amount_label must equal"):
        schemas.InstalmentPause.model_validate(pause() | {"amount_label": "Rs 600"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("created_at", "2025-08-19T17:05:00+00:00"),
        ("created_at", "2025-08-19T17:05:00"),
        ("instalment_date", "2025-8-20"),
        ("instalment_date", "20250820"),
        ("amount_paise", "60000"),
        ("amount_paise", 0),
        ("extra", 1),
    ],
)
def test_strict_types_offsets_and_extras(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        schemas.InstalmentPause.model_validate(pause() | {field: value})


def test_optional_typescript_fields_may_be_absent_but_not_null() -> None:
    schemas.FeedItem.model_validate(canned.feed()[0])
    with pytest.raises(ValidationError, match="omitted but not null"):
        schemas.FeedItem.model_validate(canned.feed()[0] | {"merchant_id": None})
    with pytest.raises(ValidationError):
        schemas.MessageMeta.model_validate({"voice_source": "robot"})


def test_backtest_timestamp_only_needs_a_timezone() -> None:
    schemas.BacktestReport.model_validate(
        canned.backtest_report() | {"generated_at": "2026-09-28T04:30:00+00:00"}
    )
    with pytest.raises(ValidationError, match="timezone-aware"):
        schemas.BacktestReport.model_validate(
            canned.backtest_report() | {"generated_at": "2026-09-28T04:30:00"}
        )


def test_envelopes() -> None:
    schemas.ErrorEnvelope.model_validate(
        {"ok": False, "error": {"code": "not_found", "message": "not found"}}
    )
    with pytest.raises(ValidationError):
        schemas.ErrorEnvelope.model_validate({"ok": True, "error": {"code": "x", "message": "y"}})
    listed = schemas.ListEnvelope[schemas.Kpis].model_validate(
        {"ok": True, "data": [canned.kpis()], "meta": {"total": 1, "limit": 1, "offset": 0}}
    )
    assert listed.data[0].shops_paid == 312
