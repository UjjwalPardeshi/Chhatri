#!/usr/bin/env python3
"""Manual smoke test of the LIVE integrations (SPEC §0.1, §14). Never part of the automated suite.

Builds the adapters exactly as the app does (`build_integrations` from `.env` / the environment) and
exercises every component whose keys are present; components without keys are reported SKIPPED.
Calls with side effects outside Chhatri (a WhatsApp message to WHATSAPP_DEMO_RECIPIENT, a staging
Paytm link, an n8n run) happen only with `--send`.

    cd backend && . .venv/bin/activate && python scripts/live_smoke.py [--send]

Exit status 1 when any attempted check fails. Output never contains secrets.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chhatri.clock import IST  # noqa: E402
from chhatri.config import DATA_DIR, Settings, get_settings  # noqa: E402
from chhatri.domain.enums import IntegrationMode, Language, ShopType  # noqa: E402
from chhatri.domain.models import Merchant  # noqa: E402
from chhatri.integrations.base import IntegrationError, OutboundMessage  # noqa: E402
from chhatri.integrations.registry import Integrations, build_integrations  # noqa: E402

MUMBAI = (19.076, 72.8777)
SMOKE_AMOUNT_PAISE = 100
SLIP = DATA_DIR / "slips" / "anil_admission_slip.png"
INTENT_SCHEMA = {
    "type": "object",
    "properties": {"intent": {"type": "string", "enum": ["WHY_AMOUNT", "UNKNOWN"]}},
    "required": ["intent"],
}
SMOKE_MERCHANT = Merchant(
    id="S-0142",
    shop_name="Anil's Tea Stall",
    owner_name="Anil Jadhav",
    owner_name_hi="अनिल",
    kyc_name="ANIL RAMESH JADHAV",
    phone="+919900000142",
    language=Language.HI,
    zone_id="Z7",
    lat=19.0046,
    lng=72.8424,
    h3_cell="smoke",
    shop_type=ShopType.TEA_STALL,
    is_demo=True,
)


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    run: Callable[[], Awaitable[str]] | None
    skip_reason: str = ""


class _Clock:
    def now(self) -> datetime:
        return datetime.now(tz=IST)

    def schedule(self, at: datetime, name: str, fn: Callable[[], Awaitable[None]]) -> None:
        raise RuntimeError("the smoke test never schedules workflow steps")


class _NoSteps:
    async def run_step(self, workflow: str, step: str, payload: object) -> None:
        raise RuntimeError("the smoke test never runs workflow steps")


def _live(built: Integrations, name: str) -> bool:
    return any(s.name == name and s.mode is IntegrationMode.LIVE for s in built.statuses)


async def _sarvam_voice(built: Integrations) -> str:
    audio = await built.tts.synthesize("नमस्ते, मैं छतरी हूँ।", Language.HI)
    if audio.audio is None or audio.mime_type is None:
        raise IntegrationError("sarvam_tts", "no audio returned")
    heard = await built.stt.transcribe(audio.audio, audio.mime_type, language_hint="hi-IN")
    return f"TTS {len(audio.audio)} bytes → STT {heard.text!r}"


async def _sarvam_chat(built: Integrations) -> str:
    if built.chat is None:
        raise IntegrationError("sarvam_chat", "chat model missing")
    result = await built.chat.complete_json(
        "Classify the merchant message.", "मुझे इतने ही पैसे क्यों मिले?", INTENT_SCHEMA, schema_name="intent"
    )
    return f"intent {result['intent']}"


async def _sarvam_vision(built: Integrations) -> str:
    slip = await built.slips.read_slip(SLIP.read_bytes(), "image/png")
    return f"patient {slip.patient_name!r}, admitted {slip.admission_date}, confidence {slip.confidence:.2f}"


async def _weather(built: Integrations) -> str:
    today = datetime.now(tz=IST).date()
    series = await built.weather.hourly_rain(*MUMBAI, today, today)
    return f"{len(series.times)} hours, {sum(series.precipitation_mm):.1f} mm today ({series.source})"


async def _whatsapp(built: Integrations) -> str:
    message = OutboundMessage(
        SMOKE_MERCHANT.id,
        SMOKE_MERCHANT.phone,
        text="Chhatri smoke test",
        template_name="chhatri_checkin",
        template_params=(SMOKE_MERCHANT.owner_name_hi,),
    )
    receipt = await built.channel.send(message)
    return f"accepted={receipt.accepted} {receipt.detail}"


async def _paytm(built: Integrations) -> str:
    link = await built.payments.create_premium_link(SMOKE_MERCHANT, SMOKE_AMOUNT_PAISE, "Chhatri smoke test")
    return f"{link.source} link {link.url}"


async def _n8n(built: Integrations) -> str:
    run = await built.workflows.start("follow-up", {"case_id": "C-SMOKE"})
    return f"{run.engine} accepted={run.accepted} {run.detail}"


def plan(built: Integrations, send: bool) -> list[Check]:
    def gated(
        name: str, status: str, fn: Callable[[Integrations], Awaitable[str]], side_effect: bool
    ) -> Check:
        if not _live(built, status):
            return Check(name, None, "not configured (simulated)")
        if side_effect and not send:
            return Check(name, None, "needs --send")
        return Check(name, lambda: fn(built))

    return [
        gated("sarvam tts→stt", "sarvam_tts", _sarvam_voice, side_effect=False),
        gated("sarvam chat", "sarvam_chat", _sarvam_chat, side_effect=False),
        gated("sarvam doc-ai", "sarvam_vision", _sarvam_vision, side_effect=False),
        gated("open-meteo", "weather", _weather, side_effect=False),
        gated("whatsapp", "whatsapp", _whatsapp, side_effect=True),
        gated("paytm link", "paytm", _paytm, side_effect=True),
        gated("n8n", "n8n", _n8n, side_effect=True),
    ]


async def run_checks(settings: Settings, *, send: bool) -> list[tuple[str, str, str]]:
    built = build_integrations(
        settings, scheduler=_Clock(), step_handlers=_NoSteps(), data_dir=settings.chhatri_data_dir
    )
    rows: list[tuple[str, str, str]] = []
    for check in plan(built, send):
        if check.run is None:
            rows.append((check.name, "SKIPPED", check.skip_reason))
            continue
        try:
            rows.append((check.name, "OK", await check.run()))
        except (IntegrationError, ValueError, KeyError) as exc:
            detail = exc.safe_message if isinstance(exc, IntegrationError) else type(exc).__name__
            rows.append((check.name, "FAIL", detail))
    return rows


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test Chhatri's live integrations")
    parser.add_argument(
        "--send", action="store_true", help="also send WhatsApp, create a Paytm link, start n8n"
    )
    args = parser.parse_args(argv)
    rows = asyncio.run(run_checks(settings or get_settings(), send=args.send))
    for name, outcome, detail in rows:
        sys.stdout.write(f"{outcome:8} {name:16} {detail}\n")
    return 1 if any(outcome == "FAIL" for _, outcome, _ in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
