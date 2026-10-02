# 0004: LIVE / SIMULATED / FALLBACK labels

| | |
|---|---|
| Status | Accepted |
| Owner | Ujjwal Pardeshi |
| Date | 2026-10-02 |
| Related | [SPEC §0.1, §24.5](../../SPEC.md) · [System architecture §2.3](../system-architecture.md) · [Provider panel spec (fs-08 §9)](../../02-product/feature-specs/fs-08-claims-officer-console.md) |

## TL;DR

Every component reports its status through `GET /api/integrations` and in the console header. Today there are 15 components: Sarvam speech-to-text, text-to-speech, chat and vision, WhatsApp, the Paytm link, n8n, Cognee memory and the weather feed, which can be LIVE, plus Soundbox, sales data, alerts, the payout rail, the lender and KYC, which are always SIMULATED. The status is LIVE or SIMULATED, set by whether the component's keys or settings are present (nothing is called to check). BUILT today. Gemini joins as `gemini_chat` and `gemini_vision` (17 rows with the flag `x6_provider_panel`), and X6 adds a FALLBACK state for a link that failed, was blocked or was forced off. BUILT in Wave 2. No simulated data is ever presented as live. This lets judges see what is live and what is a prototype.

## Context

A hackathon demo naturally mixes live (what the judges see working) and simulated (what is mocked). Without labels, judges cannot distinguish:

- Is the payout real, or does the console just show a number?
- Is WhatsApp actually sending a message, or is it a local phone simulator?
- Does a vision model really read the slip, or does the simulator read data embedded in the sample image?

The SPEC (§0.1) commits to labelling. This ADR documents the mechanism and ensures consistency.

## Decision

**Status determination** (backend/chhatri/integrations/registry.py, SPEC §0.1):

| Component | LIVE when | Otherwise |
|---|---|---|
| Sarvam (STT, TTS, chat, vision) | `SARVAM_API_KEY` set | SIMULATED (deterministic simulators) |
| Gemini (chat and vision, N2/N3, Wave 2) | LIVE with `GOOGLE_API_KEY`, `GEMINI_MODEL` and an open data gate (`CHHATRI_DATA_IS_SYNTHETIC=true`); BUILT, tested against fakes only | SIMULATED with the reason NO_KEY, MODEL_NOT_SET or FREE_TIER_BLOCKED; templates or the simulated reader answer |
| WhatsApp | all four `WHATSAPP_*` keys set AND `WHATSAPP_DEMO_RECIPIENT` set (SPEC §14.2) | SIMULATED (in-console phone) |
| Paytm link | `PAYTM_MCP_URL` or `PAYTM_MID`+`PAYTM_KEY_SECRET` set | SIMULATED links |
| n8n | `N8N_BASE_URL` set | SIMULATED (in-process runner, same steps) |
| Cognee memory | `COGNEE_ENABLED=true`, installed and an LLM configured | SIMULATED (networkx graph) |
| Weather (Open-Meteo) | `OPENMETEO_LIVE` set (live rain widget only) | SIMULATED (cached real rainfall; the replay always reads it) |
| Soundbox, sales, alerts, KYC, payout rail, lender | never live | always SIMULATED and labelled |

The team has no WhatsApp Cloud API or Paytm staging keys, so WhatsApp and the Paytm link are SIMULATED on stage.

**Startup reporting** (`GET /api/integrations`, BUILT). Each row is `{name, mode, detail}`; an excerpt with no keys set:

```json
{
  "ok": true,
  "data": [
    {"name": "sarvam_chat", "mode": "SIMULATED", "detail": "rule-based intents (no SARVAM_API_KEY)"},
    {"name": "whatsapp", "mode": "SIMULATED", "detail": "in-console phone simulator"},
    {"name": "paytm", "mode": "SIMULATED", "detail": "simulated links paytm.me/sim-…"},
    {"name": "n8n", "mode": "SIMULATED", "detail": "in-process workflow runner (same steps)"}
  ],
  "meta": {"total": 15, "limit": 15, "offset": 0}
}
```

**Console display.** BUILT: the header shows up to three green chips for what is LIVE (for example Sarvam, WhatsApp, Paytm) and then a grey "+N simulated". With nothing live it reads "Simulated · 15". Clicking it opens a popover that lists every component with its detail. PLANNED (X6, H7, Wave 2): an amber FALLBACK state for a link that failed, was blocked or was forced off, a "forced" chip, the provider, model, reason and last call for each row, and a demo switch ([fs-08 §9](../../02-product/feature-specs/fs-08-claims-officer-console.md)). Gemini adds the names `gemini_chat` and `gemini_vision` (proposed) there.

**Merchant-facing labels (BUILT, H26 and the N1 receipt, proposed wording).** Every AI reply and every receipt carries the mode, the provider and the reason when it is not LIVE:

```
Decision: policy engine, rules pilot-0.1 (deterministic)
Slip reading: LIVE | SIMULATED | FALLBACK, with provider
AI answer: LIVE | SIMULATED | FALLBACK, with provider
Payout: SIMULATED (demo settlement)
```

**Commitment:** simulated data is never presented as live. If a component is SIMULATED or FALLBACK, it says so clearly in the UI.

## Alternatives considered

1. **No labels (rejected):** Hide the status; judges assume everything is live. Pro: demo looks more polished. Con: deceptive; judges feel misled; violates SPEC §0.1; no transparency on what was real.

2. **Verbose explanations (considered):** For each simulated component, explain why it is simulated. Pro: educational. Con: clutters the UI; too much text during a timed demo.

3. **Single "DEMO MODE" badge (rejected):** One label for the entire system. Pro: simple. Con: loses granularity; a judge cannot tell if the Sarvam voice is really running or if WhatsApp is simulated.

## Consequences

**Positive:**

- **Transparency:** judges know exactly what is live and what is mocked; no surprises.
- **Honest positioning:** the team is not claiming the prototype is production-ready; it is a working demonstration with some simulated parts.
- **Debuggability:** once X6 lands, a component that fails mid-demo shows FALLBACK, so the team knows what happened.
- **Regulatory readiness:** with H26 (BUILT), every AI reply carries its mode and provider, so a reviewer can see which components were live for a given answer.

**Negative:**

- **Perception risk:** judges may downgrade the score if they see "SIMULATED WhatsApp" instead of a real integration. Mitigate: the narrative is "the AI builds the case; code decides the money" (ADR 0001); the simulated parts are the fintech plumbing, not the core logic.
- **Console complexity:** more UI space for badges and explanations.

**Risks:**

- **Latency numbers mislead:** a latency figure from one call says little. Mitigate: the panel shows latency only when it was measured and promises none ([fs-08 §9.1](../../02-product/feature-specs/fs-08-claims-officer-console.md)). Latency never appears on a merchant-facing receipt.
- **Status churn:** with X6, a LIVE link that fails mid-demo turns FALLBACK with its reason, and returns to LIVE when a later call succeeds. Today the status comes from the settings alone, so a key that is set but rejected still reads LIVE until X6 lands. Mitigate: run `make check-keys` and a live smoke test before the demo.

## How we will know it was right

**Signals:**

1. GET /api/integrations returns accurate status for all components at startup (tested before demo).
2. Console header shows status badges; judges can see what is LIVE / SIMULATED / FALLBACK before the demo starts.
3. No judge says "I thought that was real" about a simulated component after the demo.
4. With X6 (BUILT, flag `x6_provider_panel`): if a component fails, its status changes to FALLBACK and the backup answers (tested with a network block and with the demo switch).
5. With X6 (BUILT): flipping a demo switch writes the audit entry `integration.fallback_set`, so a forced fallback is never hidden.

## Follow-ups

- **Task:** Test the header chips and the popover on the demo laptop (BUILT today). Test the provider panel and badge placement once X6 lands.
- **Task:** Document the status logic in the on-site runbook, and run `make check-keys` before the demo. It prints each key as SET or NOT SET and never the value.
- **Task:** After the hackathon, add monitoring for key expiry and reachability.

## Open questions

1. Should the status badge include a "last checked" timestamp, or is "last call" enough? Owner: Ujjwal Pardeshi.
2. If Sarvam is LIVE but slow, should the UI switch to browser speech (N4, BUILT) and say so? The slow threshold is not set yet. Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · status synced with the working tree at the end of the build: the PLANNED parts named here are BUILT behind their flags
- 2026-10-02 · v2.1 · aligned with the registry and the X6 spec: 15 components, status from settings (no reachability call), n8n and Cognee are SIMULATED today (FALLBACK arrives with X6), real `{name, mode, detail}` response and header chips, Weather needs `OPENMETEO_LIVE`, Soundbox always SIMULATED, merchant labels and the audit entry marked PLANNED, invented latency and timeout rules removed.
- 2026-10-02 · v1.4 · status today is LIVE or SIMULATED; Gemini and the FALLBACK state are planned (N2/N3, X6)
- 2026-10-02 · v2 · consistency check against the code: no changes needed; ADR correctly describes LIVE/SIMULATED/FALLBACK labeling and Gemini PLANNED status.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: status table row for Gemini updated to show PLANNED (integration pending 2–3 Oct) with details on future `GOOGLE_API_KEY` requirement.
- 2026-10-02 · v1.1 · corrections: clarified Gemini status as PLANNED (integration pending N2/N3), not SIMULATED with a nonexistent API key.
- 2026-10-02 · v1 · first draft.
