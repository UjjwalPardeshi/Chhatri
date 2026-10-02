# 0004: LIVE / SIMULATED / FALLBACK labels

| | |
|---|---|
| Status | Accepted |
| Owner | Ujjwal Pardeshi |
| Date | 2026-10-02 |
| Related | [SPEC §0.1, §24.5](../../SPEC.md) · [System architecture §2.3](../system-architecture.md) |

## TL;DR

Every component reports its status at startup (`GET /api/integrations`) and in the console header. Today the components are the Sarvam services, WhatsApp, Paytm, n8n, Cognee and the weather feed, plus sales data, alerts, the payout rail, the lender and KYC, which are always SIMULATED. The status is LIVE or SIMULATED, set by whether the component's keys or settings are present. Gemini joins when N2 and N3 land, and fix X6 adds a FALLBACK state for a secondary provider that stepped in. No simulated data is ever presented as live. This transparency is essential for judges to understand what is live vs prototype.

## Context

A hackathon demo naturally mixes live (what the judges see working) and simulated (what is mocked). Without labels, judges cannot distinguish:

- Is the payout real, or does the console just show a number?
- Is WhatsApp actually sending a message, or is it a local phone simulator?
- Does Gemini really read the slip, or does it read JSON embedded in the image?

The SPEC (§0.1) commits to labelling. This ADR documents the mechanism and ensures consistency.

## Decision

**Status determination** (backend/chhatri/integrations/registry.py, SPEC §0.1):

| Component | LIVE when | Otherwise |
|---|---|---|
| Sarvam (STT, TTS, chat, vision) | `SARVAM_API_KEY` set and reachable | SIMULATED |
| Gemini (Chat, Vision, PLANNED N2/N3) | PLANNED: integration pending 2–3 Oct; will require `GOOGLE_API_KEY` | SIMULATED (until integration ships) |
| WhatsApp | all four env vars set AND `WHATSAPP_DEMO_RECIPIENT` set (SPEC §14.2) | SIMULATED (in-console phone) |
| Paytm (payment link, settlement, EDI) | `PAYTM_MCP_URL` or `PAYTM_MID`+`PAYTM_KEY_SECRET` set | SIMULATED link |
| n8n | `N8N_BASE_URL` reachable | FALLBACK (in-process runner) |
| Cognee | `COGNEE_ENABLED=true` and installed and LLM configured | FALLBACK (networkx graph) |
| Weather (Open-Meteo) | always allowed | demo uses cached real fixtures |
| Sales, alerts, KYC, payout rail, lender | never live | always SIMULATED and labelled |

**Startup reporting** (GET /api/integrations):

```json
{
  "sarvam": {"status": "LIVE", "latency_ms": 250, "last_call": "2026-10-03T17:04:05Z"},
  "gemini": {"status": "PLANNED", "reason": "integration pending (N2, N3)"},
  "whatsapp": {"status": "SIMULATED", "reason": "WHATSAPP_DEMO_RECIPIENT not set"},
  "paytm": {"status": "SIMULATED"},
  "n8n": {"status": "FALLBACK", "reason": "in-process runner active"},
  "cognee": {"status": "FALLBACK", "reason": "disabled"}
}
```

**Console display** (H7 provider panel):

A header badge shows each component's status:

```
Sarvam [LIVE] | Gemini [PLANNED] | WhatsApp [SIM] | Paytm [SIM] | n8n [FALLBACK]
```

Clicking a badge shows the reason, latency and time of last call.

**Merchant-facing labels:**

Every payout and slip decision shows:

```
Policy engine: LIVE (deterministic rules)
Slip reading: [LIVE|SIMULATED] at 17:04
AI explanations: [LIVE|SIMULATED]
Payout: SIMULATED (demo settlement)
```

**Commitment:** simulated data is never presented as live. If a component is SIMULATED or FALLBACK, it says so clearly in the UI.

## Alternatives considered

1. **No labels (rejected):** Hide the status; judges assume everything is live. Pro: demo looks more polished. Con: deceptive; judges feel misled; violates SPEC §0.1; no transparency on what was real.

2. **Verbose explanations (considered):** For each simulated component, explain why it is simulated. Pro: educational. Con: clutters the UI; too much text during a timed demo.

3. **Single "DEMO MODE" badge (rejected):** One label for the entire system. Pro: simple. Con: loses granularity; a judge cannot tell if Gemini is really running or if WhatsApp is simulated.

## Consequences

**Positive:**

- **Transparency:** judges know exactly what is live and what is mocked; no surprises.
- **Honest positioning:** the team is not claiming the prototype is production-ready; it is a working demonstration with some simulated parts.
- **Debuggability:** once X6 lands, a component that fails mid-demo shows FALLBACK, so the team knows what happened.
- **Regulatory readiness:** a regulator can check the status logs and see which integrations were live on the demo date.

**Negative:**

- **Perception risk:** judges may downgrade the score if they see "SIMULATED WhatsApp" instead of a real integration. Mitigate: the narrative is "the AI builds the case; code decides the money" (K1); the simulated parts are the fintech plumbing, not the core logic.
- **Console complexity:** more UI space for badges and explanations.

**Risks:**

- **Latency info leaks merchant behavior:** if the console shows "Sarvam latency 4.2 s", it reveals call timings. Mitigate: show latency only in the provider panel (not in the merchant-facing receipt); round to nearest 500 ms.
- **Status churn:** if a key is set but the service goes down mid-demo, status flips from LIVE to SIMULATED. Mitigate: set a 30-s timeout; if Sarvam is reachable 3 s ago, keep showing LIVE (don't re-check every call).

## How we will know it was right

**Signals:**

1. GET /api/integrations returns accurate status for all components at startup (tested before demo).
2. Console header shows status badges; judges can see what is LIVE / SIMULATED / FALLBACK before the demo starts.
3. No judge says "I thought that was real" about a simulated component after the demo.
4. If a component fails, status correctly changes to FALLBACK and the backup runs (tested with a network block).
5. Audit log shows every integration call with its status at the time (fact from SPEC §11).

## Follow-ups

- **Task:** Test provider-panel UI and badge placement on the demo laptop.
- **Task:** Document status-check logic in a runbook for the on-site demo.
- **Task:** Set up monitoring for key expiration and reachability checks (post-launch).

## Open questions

1. Should the status badge include a "last checked" timestamp, or is "last call" enough? Owner: Ujjwal Pardeshi.
2. If Sarvam is LIVE but slow (>5 s latency), should the UI switch to showing browser Speech API as active? Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v1.4 · status today is LIVE or SIMULATED; Gemini and the FALLBACK state are planned (N2/N3, X6)
- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly describes LIVE/SIMULATED/FALLBACK labeling and Gemini PLANNED status.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: status table row for Gemini updated to show PLANNED (integration pending 2–3 Oct) with details on future `GOOGLE_API_KEY` requirement.
- 2026-10-02 · v1.1 · fact-check pass: clarified Gemini status as PLANNED (integration pending N2/N3), not SIMULATED with a nonexistent API key.
- 2026-10-02 · v1 · first draft.
