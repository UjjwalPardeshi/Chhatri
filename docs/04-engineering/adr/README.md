# Architecture Decision Records

| | |
|---|---|
| Status | Index · 2 Oct 2026 |
| Owner | Ujjwal Pardeshi |
| Audience | Engineers, architects, product leads |
| Related | [System architecture](../system-architecture.md) · [Data model and API](../data-model-and-api.md) · [AI architecture and guardrails](../ai-architecture-and-guardrails.md) |

## TL;DR

These ADRs document the key architectural, product and technical decisions in Chhatri. Each record covers the decision, why it was chosen, alternatives considered and signals to know it was right. All decisions are **Accepted** as of 2 Oct 2026.

## ADRs

| ADR | Title | Decider | Status | Summary |
|---|---|---|---|---|
| 0001 | Policy engine is the only payout authority | Ujjwal Pardeshi | Accepted | Code, not AI, produces all APPROVED decisions; the policy engine is the single enforcement point (SPEC §0.2). |
| 0002 | Area sales index trigger | Ujjwal Pardeshi | Accepted | A zone-level sales index below 50% for 3 hours, below the model's quantile bound, and during an alert, with ≥20 shops, replaces weather-only triggers and measures loss from the merchant's live data. |
| 0003 | Free AI provider chain | Ujjwal Pardeshi | Accepted | Gemini Flash free tier (PLANNED N2/N3) → Sarvam credits (LIVE) → deterministic templates; Tesseract for OCR (PLANNED P1); Cognee and n8n kept optional (roadmap). |
| 0004 | LIVE / SIMULATED / FALLBACK labels | Ujjwal Pardeshi | Accepted | Every component reports its status at startup and in the console header; simulated data is never presented as live. |
| 0005 | Mini-app inside the console | Omkar Kadam | Accepted | A phone-sized merchant mini-app, "Chhatri in Paytm for Business", beside the WhatsApp simulator (N1); not a separate PWA or WhatsApp-only. |
| 0006 | EDI holiday is the lender's decision | Omkar Kadam | Accepted | Chhatri requests pre-agreed EDI holidays; the lender's rule decides (active loan, not in arrears, allowance available); reframed from "instalment pause" (K3). |
| 0007 | Hospital-cash framing | Omkar Kadam | Accepted | Personal claims are reframed as hospital-cash income claims that demonstrate the health insurance track example end to end, not a separate family health assistant. |
| 0008 | In-process workflows on stage | Ujjwal Pardeshi | Accepted | The in-process workflow runner is used for the demo and the console; n8n is shown as the production orchestration (it holds the 30–60 s clock). |
| 0009 | Synthetic data only to free-tier AI | Ujjwal Pardeshi | Accepted | Demo merchants, sample slips and simulated sales are sent to Gemini free tier and Sarvam; never real personal data, to comply with terms and privacy rules. |

## Open questions

None.

## Changelog

- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; all ADRs correctly describe TODAY vs PLAN and use accepted status appropriately.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: ADR 0003 summary updated to show Gemini PLANNED status, Sarvam LIVE, and Tesseract PLANNED.
- 2026-10-02 · v1 · initial index of nine ADRs.
