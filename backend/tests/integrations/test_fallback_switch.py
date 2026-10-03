"""X6 (card 4.5): the fallback switch, the adapter wrappers and the panel rows (fs-08 section 9, ADR 0004)."""

from __future__ import annotations

from typing import Any

import pytest

from chhatri.ai.labels import AiMode, AiProvider, FallbackReason
from chhatri.clock import ist
from chhatri.config import DATA_DIR, Settings
from chhatri.domain.enums import IntegrationMode
from chhatri.integrations import registry
from chhatri.integrations.base import IntegrationError, LenderNoResponse, LenderRequest
from chhatri.integrations.chat_chain import build_chat_chain
from chhatri.integrations.panel import panel_rows
from chhatri.integrations.retry import HttpStatusError
from chhatri.integrations.statuses import GEMINI_STATUS_NAMES, STATUS_NAMES
from chhatri.integrations.switch import FallbackSwitch
from chhatri.integrations.telegram_health import TELEGRAM_HEALTH
from chhatri.store.doctor_chats import DoctorDesk
from chhatri.store.telegram_bindings import TelegramBindings

from ..workflows.fakes import FakeScheduler, RecordingHandlers

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
}


def settings(**values: Any) -> Settings:
    base: dict[str, Any] = {
        "google_api_key": None,
        "gemini_model": "",
        "gemini_vision_model": "",
        "sarvam_api_key": None,
        "chhatri_data_is_synthetic": True,
        "chhatri_internal_secret": "internal-SECRET",
        "chhatri_demo_mode": True,
    }
    return Settings(_env_file=None, **(base | values))  # type: ignore[arg-type]


def build(
    settings_: Settings, switch: FallbackSwitch, desk: DoctorDesk | None = None
) -> registry.Integrations:
    return registry.build_integrations(
        settings_,
        scheduler=FakeScheduler(ist(2025, 8, 19, 8, 0)),
        step_handlers=RecordingHandlers(),
        data_dir=DATA_DIR,
        env={},
        switch=switch,
        telegram_bindings=TelegramBindings(),
        doctor_desk=desk or DoctorDesk(),
    )


def rows_by_name(
    integrations: registry.Integrations, settings_: Settings, switch: FallbackSwitch
) -> dict[str, Any]:
    return {row["name"]: row for row in panel_rows(integrations, settings_, switch)}


# ------------------------------------------------------------------ the switch itself


def test_switch_force_release_and_clear_are_idempotent() -> None:
    switch = FallbackSwitch()
    assert switch.force("lender") is True
    assert switch.force("lender") is False  # already forced: nothing changed
    switch.force("n8n")
    assert switch.forced == ("lender", "n8n")  # sorted
    assert switch.is_forced("lender")
    assert switch.release("lender") is True
    assert switch.release("lender") is False
    switch.clear()
    assert switch.forced == ()


def test_switch_rejects_a_name_that_has_no_fallback_path() -> None:
    with pytest.raises(ValueError, match="kyc"):
        FallbackSwitch().force("kyc")


# ------------------------------------------------------------------ rows


def test_the_panel_lists_seventeen_rows_and_the_doctor_with_the_x6_fields() -> None:
    switch, conf = FallbackSwitch(), settings()
    rows = panel_rows(build(conf, switch), conf, switch)
    assert [row["name"] for row in rows] == [*STATUS_NAMES, *GEMINI_STATUS_NAMES, "doctor"]
    assert len(rows) == 18
    assert set(rows[0]) == {
        "name", "mode", "detail", "provider", "model", "fallback_reason", "switchable", "forced", "last_call",
    }  # fmt: skip
    kyc = {row["name"]: row for row in rows}["kyc"]
    assert (kyc["mode"], kyc["switchable"], kyc["forced"], kyc["provider"]) == (
        "SIMULATED",
        False,
        False,
        "simulated",
    )


def test_forced_component_reports_fallback_with_reason_forced() -> None:
    switch, conf = FallbackSwitch(), settings(sarvam_api_key="k")
    integrations = build(conf, switch)
    before = rows_by_name(integrations, conf, switch)["sarvam_chat"]
    assert (before["mode"], before["switchable"], before["forced"]) == ("LIVE", True, False)
    assert before["model"] == conf.sarvam_chat_model
    switch.force("sarvam_chat")
    after = rows_by_name(integrations, conf, switch)["sarvam_chat"]
    assert (after["mode"], after["fallback_reason"], after["forced"]) == ("FALLBACK", "FORCED", True)
    assert after["provider"] == "template"
    assert after["switchable"] is True  # a forced row can be released


def test_a_simulated_component_cannot_be_forced() -> None:
    switch, conf = FallbackSwitch(), settings()
    row = rows_by_name(build(conf, switch), conf, switch)["sarvam_chat"]
    assert (row["mode"], row["switchable"], row["fallback_reason"]) == ("SIMULATED", False, "NO_KEY")


def test_switchable_is_false_outside_demo_mode() -> None:
    switch, conf = FallbackSwitch(), settings(chhatri_demo_mode=False)
    row = rows_by_name(build(conf, switch), conf, switch)["lender"]
    assert row["switchable"] is False


def test_the_lender_is_always_switchable_and_forcing_it_mutes_it() -> None:
    switch, conf = FallbackSwitch(), settings()
    integrations = build(conf, switch)
    row = rows_by_name(integrations, conf, switch)["lender"]
    assert (row["mode"], row["switchable"]) == ("SIMULATED", True)
    switch.force("lender")
    row = rows_by_name(integrations, conf, switch)["lender"]
    assert (row["mode"], row["provider"], row["fallback_reason"]) == ("FALLBACK", "simulated", "FORCED")
    assert row["detail"] == "Simulated lender (NBFC partner), not answering: forced for the demo"


async def test_lender_forced_gives_no_response() -> None:
    switch, conf = FallbackSwitch(), settings()
    integrations = build(conf, switch)
    request = LenderRequest(
        request_id="HR-000001", merchant_id="S-0142", loan_id="LN-0142", decision_id="D-000001",
        payout_id="P-000001", payout_credited_at=ist(2025, 8, 19, 17, 0), instalment_date=ist(2025, 8, 20, 0, 0).date(),
        instalment_paise=10_000, requested_at=ist(2025, 8, 19, 17, 5),
    )  # fmt: skip
    switch.force("lender")
    with pytest.raises(LenderNoResponse):
        await integrations.lender.request_holiday(request)
    switch.release("lender")
    assert (await integrations.lender.request_holiday(request)).request_id == "HR-000001"  # answers again


# ------------------------------------------------------------------ wrappers


async def test_a_forced_live_adapter_is_replaced_by_its_simulator_on_the_next_call() -> None:
    switch, conf = FallbackSwitch(), settings(sarvam_api_key="k")
    integrations = build(conf, switch)
    switch.force("sarvam_tts")
    audio = await integrations.tts.synthesize("namaste", "hi")  # type: ignore[arg-type]
    assert audio.audio is None and audio.source == "simulated"  # browser speech, labelled
    switch.force("sarvam_chat")
    with pytest.raises(IntegrationError):
        assert integrations.chat is not None
        await integrations.chat.complete_json("s", "u", SCHEMA, schema_name="x")


async def test_forced_sarvam_link_of_the_chat_chain_is_skipped_with_forced() -> None:
    class Sarvam:
        async def complete_json(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise AssertionError("a forced link is never called")

    switch, conf = FallbackSwitch(), settings()
    chain = build_chat_chain(conf, gemini=None, sarvam=Sarvam(), forced_source=lambda: switch.forced)
    switch.force("sarvam_chat")
    result = await chain.complete_json("s", "u", SCHEMA, schema_name="x", timeout_s=1.0)
    assert result.label.mode is AiMode.FALLBACK
    assert result.label.fallback_reason is FallbackReason.FORCED
    assert result.label.provider is AiProvider.TEMPLATE


# ------------------------------------------------------------------ the treating doctor (design 2.9)

TOKEN = "123456:TEST-token-never-print-me"  # noqa: S105 - a fixture, not a credential
DOCTOR_FLAGS = "telegram_channel,x6_provider_panel"


@pytest.fixture
def _healthy_telegram() -> Any:
    TELEGRAM_HEALTH.reset()
    yield
    TELEGRAM_HEALTH.reset()


def test_the_doctor_row_follows_telegram_and_is_simulated_without_a_chat() -> None:
    switch, conf = FallbackSwitch(), settings(chhatri_features=DOCTOR_FLAGS)
    rows = panel_rows(build(conf, switch), conf, switch)
    assert [row["name"] for row in rows][-2:] == ["telegram", "doctor"] and len(rows) == 19
    doctor = rows[-1]
    assert (doctor["mode"], doctor["provider"], doctor["fallback_reason"], doctor["switchable"]) == (
        "SIMULATED",
        "simulated",
        None,
        True,
    )
    assert doctor["detail"] == "simulated doctor (attendance register) · Telegram not live"


@pytest.mark.usefixtures("_healthy_telegram")
def test_an_enrolled_doctor_on_live_telegram_reads_live() -> None:
    switch, desk = FallbackSwitch(), DoctorDesk()
    conf = settings(chhatri_features=DOCTOR_FLAGS, telegram_bot_token=TOKEN)
    integrations = build(conf, switch, desk)
    assert rows_by_name(integrations, conf, switch)["doctor"]["detail"] == (
        "simulated doctor (attendance register) · no doctor chat enrolled"
    )
    desk.enrol(4242, "MMC-2011-45817")
    row = rows_by_name(integrations, conf, switch)["doctor"]
    assert (row["mode"], row["provider"], row["detail"]) == (
        "LIVE",
        "telegram",
        "Telegram · Dr S. Rao enrolled · waits up to 90 s for a tap",
    )
    assert TOKEN not in repr(row)


def test_forcing_the_doctor_reads_fallback_forced_and_a_person_decides() -> None:
    switch, conf = FallbackSwitch(), settings()
    integrations = build(conf, switch)
    switch.force("doctor")
    row = rows_by_name(integrations, conf, switch)["doctor"]
    assert (row["mode"], row["fallback_reason"], row["forced"], row["switchable"], row["provider"]) == (
        "FALLBACK",
        "FORCED",
        True,
        True,
        "simulated",
    )
    assert row["detail"] == "Treating doctor not answering: forced for the demo; the claim goes to a person"


def test_the_doctor_is_not_switchable_outside_demo_mode() -> None:
    switch, conf = FallbackSwitch(), settings(chhatri_demo_mode=False)
    assert rows_by_name(build(conf, switch), conf, switch)["doctor"]["switchable"] is False


@pytest.mark.usefixtures("_healthy_telegram")
def test_a_live_telegram_row_reads_fallback_during_an_outage_and_recovers() -> None:
    switch = FallbackSwitch()
    conf = settings(chhatri_features=DOCTOR_FLAGS, telegram_bot_token=TOKEN)
    integrations = build(conf, switch)
    assert rows_by_name(integrations, conf, switch)["telegram"]["mode"] == "LIVE"
    TELEGRAM_HEALTH.record_poll_failure(HttpStatusError("telegram", 409))
    row = rows_by_name(integrations, conf, switch)["telegram"]
    assert (row["mode"], row["provider"], row["fallback_reason"], row["forced"], row["switchable"]) == (
        "FALLBACK",
        "simulated",
        "PROVIDER_ERROR",
        False,
        True,
    )
    assert "409" in row["detail"] and TOKEN not in row["detail"]
    TELEGRAM_HEALTH.record_send_failure(HttpStatusError("telegram", 429))
    TELEGRAM_HEALTH.record_poll_ok()
    assert rows_by_name(integrations, conf, switch)["telegram"]["fallback_reason"] == "RATE_LIMITED"
    TELEGRAM_HEALTH.record_send_ok()
    assert rows_by_name(integrations, conf, switch)["telegram"]["mode"] == "LIVE"


def test_the_default_registry_switch_is_the_process_wide_one() -> None:
    from chhatri.integrations.switch import PROCESS_SWITCH

    conf = settings()
    integrations = registry.build_integrations(
        conf,
        scheduler=FakeScheduler(ist(2025, 8, 19, 8, 0)),
        step_handlers=RecordingHandlers(),
        data_dir=DATA_DIR,
        env={},
    )
    assert integrations.switch is PROCESS_SWITCH
    assert IntegrationMode.FALLBACK.value == "FALLBACK"
