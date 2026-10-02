# Architecture Decision Records

| | |
|---|---|
| Status | Index · 2 Oct 2026 |
| Owner | Ujjwal Pardeshi |
| Audience | Engineers, architects, product leads |
| Related | [System architecture](../system-architecture.md) · [Data model and API](../data-model-and-api.md) · [AI architecture and guardrails](../ai-architecture-and-guardrails.md) |

## TL;DR

These ADRs document the key architectural, product and technical decisions in Chhatri. Each record covers the decision, why it was chosen, alternatives considered and signals to know it was right. All decisions are **Accepted** as of 2 Oct 2026. Accepting a decision is not evidence that its code exists: each ADR says what is BUILT and what is not, and the summaries below repeat that split (checked against the code on 3 Oct 2026).

## ADRs

| ADR | Title | Decider | Status | Summary |
|---|---|---|---|---|
| 0001 | Policy engine is the only payout authority | Ujjwal Pardeshi | Accepted | BUILT. Code, not AI, produces every APPROVED decision; the policy engine is the single enforcement point and the payout step refuses anything else (SPEC §0.2). |
| 0002 | Area sales index trigger | Ujjwal Pardeshi | Accepted | BUILT. A zone-level index (actual ÷ expected sales) below 50% in each of 3 hours and below the zone's conformal lower bound, during a RAIN or CIVIC alert, with at least 20 shops, replaces a weather-only trigger. All sales and alerts are simulated, and the backtest is a specification check. |
| 0003 | Free AI provider chain | Ujjwal Pardeshi | Accepted | One ordered chain per AI need, ending in something deterministic. BUILT: the Gemini and Sarvam links (each live only with its key and an open data gate), the simulators, the FALLBACK label and the switches. Tesseract is a later link, not built. |
| 0004 | LIVE / SIMULATED / FALLBACK labels | Ujjwal Pardeshi | Accepted | BUILT: 15 components report LIVE or SIMULATED in the console header, and nothing simulated is shown as live. With X6 (flag `x6_provider_panel`, BUILT): 17 rows, the FALLBACK state and a demo switch. |
| 0005 | Mini-app inside the console | Omkar Kadam | Accepted | BUILT (N1, flag `n1_miniapp`). A phone-sized merchant mini-app, "Chhatri in Paytm for Business", in a third column beside the WhatsApp simulator and as a standalone route. Tailwind v4 and shadcn are scoped to it. Not an iframe, a separate PWA or WhatsApp-only. |
| 0006 | EDI holiday is the lender's decision | Omkar Kadam | Accepted | Chhatri requests a pre-agreed EDI holiday and the lender decides. With X4 (Wave 1, BUILT, flag `x4_lender_request`) the simulated lender applies its rule (active loan, not in arrears, allowance left, in the scheme) and the wording says the lender decides. With the flag off it grants with no check, as before. |
| 0007 | Hospital-cash framing | Omkar Kadam | Accepted | BUILT as K2. Personal claims are hospital-cash income claims that walk the health insurance track example end to end, not a separate family health assistant. The slip pre-check is BUILT behind `n3_slip_precheck`, and the check-in is voiced like every outbound message. |
| 0008 | In-process workflows on stage | Ujjwal Pardeshi | Accepted | BUILT. The in-process runner drives the stage demo (n8n badge SIMULATED). With n8n LIVE the replay clock holds about 30 to 60 seconds at 17:00 while 312 payout runs go through n8n. |
| 0009 | Synthetic data only to free-tier AI | Ujjwal Pardeshi | Accepted | Only synthetic data goes to AI services on free tiers or credits. It holds because the whole prototype is synthetic, and the `CHHATRI_DATA_IS_SYNTHETIC` gate enforces it (BUILT, Wave 2). |

## Open questions

Each ADR lists its own open questions.

## Changelog

- 2026-10-03 · v2.2 · ADR 0005 is BUILT (the mini-app, the flags and every endpoint it names are in the code); the ADR bodies were checked against the code and their test counts and workflow step names updated.
- 2026-10-02 · v2.1 · summaries rewritten to match the corrected ADRs: BUILT and PLANNED split for each, Tesseract is a later link (the old "PLANNED P1" is gone), ADR 0002 no longer says "live data" (all data is simulated), ADR 0006 notes that today's lender always grants, ADR 0008 and 0009 match their rewrites. The earlier "no changes needed" claim in v2 was wrong.
- 2026-10-02 · v2 · consistency check against the code: no changes needed; all ADRs correctly describe TODAY vs PLAN and use accepted status appropriately.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: ADR 0003 summary updated to show Gemini PLANNED status, Sarvam LIVE, and Tesseract PLANNED.
- 2026-10-02 · v1 · initial index of nine ADRs.
