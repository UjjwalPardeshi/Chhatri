"""The deck's demo, driven through the SPEC §19 routes, observed as named values (SPEC §13.6, §17.2).

Each flow loads its scenario (fresh ids, so the first case is C-2291, SPEC §3), moves the replay
clock with ``/api/replay/seek`` and ``/step``, talks as the merchant through the phone-simulator
routes (``/messages``, ``/voice-demo``, ``/photo``), acts as the officer with the bearer token, and
records what the console would show as ``{check name: value}``. Values are plain JSON (strings,
numbers, booleans, lists) so they can be compared with `chhatri.api.demo.golden` and printed.

Timeline (binding decisions B1, B2): payout workflows execute at the decision minute, credit and
notify 4 simulated minutes later and pause the instalment after 5, so the personal flows step the
clock to see the money arrive, exactly as the presenter's clock would.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any, Final

from chhatri.api.demo.client import DemoApi
from chhatri.api.demo.observe import (
    SKIPPED,
    Observed,
    audit_times,
    hhmm,
    load,
    message_lines,
    replies_en,
    zone_order,
)

__all__ = [
    "ANIL",
    "COVER_TEXT",
    "FLOWS",
    "RAMESH",
    "WHY_TEXT",
    "buy_cover",
    "illness",
    "illness_mismatch",
    "monsoon",
]

ANIL: Final = "S-0142"  # SPEC §5.4, B5
RAMESH: Final = "S-0907"
MAP_ZONES: Final = ("Z3", "Z7", "Z9", "Z12")
WHY_TEXT: Final = "मुझे इतने ही पैसे क्यों मिले?"  # SPEC §13.6 EXPLAINED
COVER_TEXT: Final = "Red alert tomorrow. Cover me today."  # SPEC §13.6 BLOCKED
PAYOUT_WAIT_MINUTES: Final = 4  # B1: credit_payout / notify_merchant offset
PAUSE_WAIT_MINUTES: Final = 1  # B1: pause_instalment is one minute after the credit
SIMULATED_LINK_PREFIX: Final = "https://paytm.me/sim-"  # SPEC §14.3 simulated links


async def monsoon(api: DemoApi) -> Observed:
    """SPEC §17.2 monsoon at 17:00 and 17:10, then the EXPLAINED live test (SPEC §13.6)."""
    clock = await load(api, "monsoon", "17:00")
    observed: Observed = {"clock at 17:00": clock["label"]}
    await api.post("/api/replay/seek", {"to": "17:10"})
    state = await api.get("/api/state")
    observed |= _map(state)
    observed |= await _timeline(api, clock["now"][:10])
    observed["Z7 panel"] = [f"{r['label']}: {r['value']}" for r in (await api.get("/api/zones/Z7"))["rows"]]
    observed |= await _anil_paid(api)
    observed |= await _explained(api)
    observed["audit chain valid"] = (await api.get("/api/audit/verify"))["valid"]
    return observed


def _map(state: Mapping[str, Any]) -> Observed:
    zones = {z["zone_id"]: z for z in state["zones"]}
    triggers = sorted(state["triggers"], key=lambda t: zone_order(t["zone_id"]))
    kpis = state["kpis"]
    observed: Observed = {
        "demo merchant": state["demo_merchant_id"],
        "triggers": [
            f"{t['zone_id']} · {t['index_pct']}% · {t['shops_in_index']} shops · {hhmm(t['fired_at'])}"
            for t in triggers
        ],
        "Z9 status": zones["Z9"]["status"],
        "Z9 explanation": state["explanations"].get("Z9"),
        "KPI zones triggered": kpis["zones_triggered"],
        "KPI shops paid": kpis["shops_paid"],
        "KPI trigger to money (min)": kpis["trigger_to_money_min"],
    }
    for zone_id in MAP_ZONES:
        observed[f"{zone_id} map label"] = zones[zone_id]["label"]
    return observed


async def _timeline(api: DemoApi, day: str) -> Observed:
    audit = await api.audit()
    decisions = [e for e in audit if e["action"] == "decision.area"]
    payouts = await api.get_all("/api/payouts", date=day)
    return {
        "area decisions at": audit_times(decisions),
        "area decisions approved": sum(e["data"]["outcome"] == "APPROVED" for e in decisions),
        "payouts credited at": sorted({hhmm(p["credited_at"]) for p in payouts if p["credited_at"]}),
        "payouts credited": sum(p["status"] == "CREDITED" for p in payouts),
        "instalments paused at": audit_times([e for e in audit if e["action"] == "instalment.pause"]),
    }


async def _anil_paid(api: DemoApi) -> Observed:
    detail = await api.get(f"/api/merchants/{ANIL}")
    messages = await api.get_all(f"/api/merchants/{ANIL}/messages")
    card = next((m["card"] for m in messages if m["kind"] == "PAYOUT_CARD"), None)
    by_kind = {m["kind"]: m for m in reversed(messages)}
    texts = [m for m in messages if m["kind"] == "TEXT"]
    payout = detail["payouts"][0] if detail["payouts"] else None
    decision = detail["decisions"][0] if detail["decisions"] else None
    return {
        "Anil payout": f"{payout['amount_label']} · {payout['status']} {hhmm(payout['credited_at'] or '')}"
        if payout
        else None,
        "Anil formula": decision["explanation"]["formula_en"] if decision else None,
        "Anil messages": message_lines(messages),
        "Anil rain message": [texts[0]["text_hi"], texts[0]["text_en"]] if texts else None,
        "Anil payout card": [card["amount_label"], card["subtitle_en"], card["badge"]] if card else None,
        "Anil Soundbox": [by_kind["SOUNDBOX"]["text_hi"], by_kind["SOUNDBOX"]["text_en"]]
        if "SOUNDBOX" in by_kind
        else None,
        "Anil instalment message": [texts[-1]["text_hi"], texts[-1]["text_en"]] if len(texts) > 1 else None,
    }


async def _explained(api: DemoApi) -> Observed:
    """EXPLAINED (SPEC §13.6): the why question by text, the dispute by voice note."""
    why = await api.post(f"/api/merchants/{ANIL}/messages", {"text": WHY_TEXT})
    dispute = await api.post(f"/api/merchants/{ANIL}/voice-demo", {"key": "dispute"})
    cases = await api.get_all("/api/cases")
    answer = why[1:]
    return {
        "EXPLAINED why reply": [answer[0]["text_hi"], answer[0]["text_en"]] if answer else None,
        "EXPLAINED dispute heard": dispute[0]["meta"].get("transcript"),
        "EXPLAINED dispute reply": replies_en(dispute),
        "EXPLAINED case": [f"{c['id']} · {c['kind']} · {c['status']}" for c in cases],
    }


async def illness(api: DemoApi) -> Observed:
    """SPEC §17.2 illness: 11:20 check-in, voice reply, one slip photo, ₹1,500 the same day."""
    observed = await _silent_shop(api, "illness")
    photo = await api.post(f"/api/merchants/{ANIL}/photo", {})
    decision = (await api.get(f"/api/merchants/{ANIL}"))["decisions"][-1]
    observed["slip reply"] = replies_en(photo)
    observed["slip decision"] = f"{decision['outcome']} · {decision['amount_label']} · {hhmm(decision['decided_at'])}"
    observed |= await _paid_later(api, "paid")
    await api.post("/api/replay/step", {"minutes": PAUSE_WAIT_MINUTES})
    detail = await api.get(f"/api/merchants/{ANIL}")
    messages = await api.get_all(f"/api/merchants/{ANIL}/messages")
    observed["instalment message"] = messages[-1]["text_en"]
    observed["loan"] = detail["loan"]["daily_instalment_label"] if detail["loan"] else None
    observed["audit chain valid"] = (await api.get("/api/audit/verify"))["valid"]
    return observed


async def _silent_shop(api: DemoApi, scenario: str) -> Observed:
    """Load at 11:21: the 11:20 check-in has gone out; Anil answers with the 'ill' voice note."""
    await load(api, scenario, "11:21")
    state = await api.get("/api/state")
    messages = await api.get_all(f"/api/merchants/{ANIL}/messages")
    voice = await api.post(f"/api/merchants/{ANIL}/voice-demo", {"key": "ill"})
    return {
        "demo merchant": state["demo_merchant_id"],
        "check-in": message_lines(messages, with_text=True),
        "voice reply heard": voice[0]["meta"].get("transcript"),
        "voice reply answer": replies_en(voice),
    }


async def _paid_later(api: DemoApi, prefix: str) -> Observed:
    """Step to the credit minute (B1 +4) and read the payout and the message it produced."""
    await api.post("/api/replay/step", {"minutes": PAYOUT_WAIT_MINUTES})
    detail = await api.get(f"/api/merchants/{ANIL}")
    messages = await api.get_all(f"/api/merchants/{ANIL}/messages")
    texts = [m for m in messages if m["kind"] == "TEXT"]
    payout = detail["payouts"][-1] if detail["payouts"] else None
    return {
        f"{prefix} payout": f"{payout['amount_label']} · {payout['status']} {hhmm(payout['credited_at'] or '')}"
        if payout
        else None,
        f"{prefix} message": texts[-1]["text_en"] if texts else None,
    }


async def illness_mismatch(api: DemoApi) -> Observed:
    """HUMAN (SPEC §13.6): a slip in another name is REFERRED; the officer approves ₹1,500."""
    observed = await _silent_shop(api, "illness_mismatch")
    photo = await api.post(f"/api/merchants/{ANIL}/photo", {})
    detail = await api.get(f"/api/merchants/{ANIL}")
    referred = detail["decisions"][-1]
    cases = await api.get_all("/api/cases", status="OPEN")
    observed |= {
        "slip reply": replies_en(photo),
        "slip decision": referred["outcome"],
        "failed checks": sorted(c["code"] for c in referred["checks"] if c["status"] != "PASS"),
        "payouts before the officer": len(detail["payouts"]),
        "open case": [f"{c['id']} · {c['kind']} · {c['status']}" for c in cases],
        "slip patient": cases[0]["evidence"].get("slip", {}).get("patient_name") if cases else None,
    }
    if cases:
        result = await api.post(f"/api/cases/{cases[0]['id']}/approve", {"note": "same person"}, officer=True)
        officer = result["decision"]
        observed["officer decision"] = f"{officer['outcome']} · {officer['amount_label']} · {officer['decided_by']}"
        observed["case after the officer"] = result["case"]["status"]
    observed |= await _paid_later(api, "officer")
    observed["audit chain valid"] = (await api.get("/api/audit/verify"))["valid"]
    return observed


async def buy_cover(api: DemoApi) -> Observed:
    """BLOCKED (SPEC §13.6, §17.2 buy_cover): Ramesh asks for cover the evening before the storm."""
    clock = await load(api, "buy_cover", "18:10")
    state = await api.get("/api/state")
    z3 = next(z for z in state["zones"] if z["zone_id"] == "Z3")
    covered = (await api.get(f"/api/merchants/{RAMESH}"))["covered"]
    reply = await api.post(f"/api/merchants/{RAMESH}/messages", {"text": COVER_TEXT})
    link = await api.post("/api/premium/link", {"merchant_id": RAMESH}, officer=True)
    quote, premium = link["quote"], link["premium"]
    observed: Observed = {
        "clock": clock["label"],
        "demo merchant": state["demo_merchant_id"],
        "alert in the feed": f"{z3['alert']['id']} · {z3['alert']['level']}" if z3["alert"] else None,
        "Ramesh covered before": covered,
        "cover reply": [m["text_en"] for m in reply[1:2]],
        "cover link sent": any("http" in (m["text_en"] or "") for m in reply[1:]),
        "quote": f"{quote['outcome']} · starts {quote['starts_on']}",
        "premium link": bool(premium and premium["link_url"]),
    }
    observed |= await _pay_premium(api, premium)
    observed["audit chain valid"] = (await api.get("/api/audit/verify"))["valid"]
    return observed


async def _pay_premium(api: DemoApi, premium: Mapping[str, Any] | None) -> Observed:
    """Simulated links only: Paytm's paid callback activates the future cover (SPEC §10, §14.3)."""
    if premium is None or not premium["link_url"].startswith(SIMULATED_LINK_PREFIX):
        return {"premium paid": SKIPPED, "cover after payment": SKIPPED}
    form = {"linkId": premium["link_id"], "STATUS": "TXN_SUCCESS", "TXNID": f"DEMO-{premium['id']}"}
    paid = await api.post_form("/api/webhooks/paytm", form)
    cover = (await api.get(f"/api/merchants/{RAMESH}"))["cover"]
    return {
        "premium paid": paid["status"],
        "cover after payment": f"{cover['status']} · starts {cover['starts_on']}" if cover else None,
    }


FLOWS: Final[Mapping[str, Callable[[DemoApi], Awaitable[Observed]]]] = MappingProxyType(
    {"monsoon": monsoon, "illness": illness, "illness_mismatch": illness_mismatch, "buy_cover": buy_cover}
)


def flow_names() -> Sequence[str]:
    """Scenario order of the rehearsal (the deck's order)."""
    return tuple(FLOWS)
