# Problem statement analysis

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Judges, mentors, the team, stakeholders evaluating Chhatri against the track |
| Related | [Facts and sources](facts-and-sources.md) · [Executive summary](../00-executive-summary.md) · [Vision and positioning](../02-product/vision-and-positioning.md) · [User journeys](../02-product/user-journeys.md) |

## TL;DR

- The track asks for AI-powered financial journeys across insurance, lending and fintech. Chhatri answers it through a single merchant's story: a rain day triggers automatic insurance payouts and a loan holiday.
- Seven atomic requirements trace into seven feature IDs (K1–K7, N1–N5), each mapped to code, status and acceptance evidence.
- Three interpretation decisions (hospital-cash framing, merchant income as the critical journey, EDI holiday as the lending journey) explain why we reframe the problem from "health claims" to "income claims with instalment protection".
- Five beyond-the-brief additions (grievance ladder, consent centre, Marathi, voice-first, no offers during distress) tie each to a merchant's real need.
- The prototype is strong on backend engineering and determinism. Gaps are merchant-facing UI (mini-app screens not yet visible), AI depth (most components simulated without keys), and regulatory documentation (compliance roadmap missing).

## 1. The track problem statement (verbatim)

> **AI-Powered Financial Journeys (Track 2, Paytm Build for India AI Hackathon, Mumbai Edition)**
>
> Make Insurance, Lending and Fintech simpler, faster and more human.
>
> Reimagine customer-facing journeys across Insurance, Lending and Fintech using AI. Focus on removing friction, reducing complexity, and helping customers complete critical financial journeys faster and with greater confidence.
>
> Example: How might we simplify the Health Insurance claims journey using AI—from understanding policy coverage and submitting documents to tracking claims and resolving customer queries?

## 2. Atomic requirements and traceability

We decompose the track statement into seven atomic requirements. Each traces to Chhatri's answer, feature IDs, status and evidence.

| Req | Requirement | Chhatri answers | Feature IDs | Status | Evidence | Remaining gap | Fix ID |
|---|---|---|---|---|---|---|---|
| **PS-1** | Three verticals: insurance, lending, fintech in one customer journey | Insurance: claim payouts (K1, K2). Lending: EDI holiday (K3). Fintech: settlement payout, Soundbox, consent (N1, N6). All in one story per merchant. | K1, K2, K3, N1, N6 | LIVE (K1, K2, K3) + PLANNED (N1, N6) | SPEC §3–4 (area claims + personal claims); SPEC §10 (EDI pause); settlement via Paytm (A5) | Fintech surface (settlement UI) not merchant-visible | N1 mini-app tracker shows settlement |
| **PS-2** | Customer-facing journeys (not ops-only) | Merchant mini-app (N1): cover card, coverage explainer, claim tracker, help, grievance. Ask Chhatri (N2) in Hindi and English, voice-first. | N1, N2, N4 | PLANNED (P0 on 2–3 Oct) | Deck slide 2 promise; /02-product/feature-specs/fs-04 and fs-05 | Console-only today; merchant surface missing | N1 build on 3 Oct |
| **PS-3** | Using AI (responsibly, safely) | LightGBM quantile sales forecasting (real ML). Sarvam vision for slip reading (real OCR). STT/TTS for voice (real). Policy engine is deterministic (no LLM payout authority). | K1 (forecasting), N3 (vision), N4 (voice), K4 (policy engine) | LIVE (K4) + SIMULATED (N3, N4) on demo | SPEC §7, §13; backend/chhatri/forecast/, /integrations/ | All integrations simulated in demo (no API keys) | N2–N4 with free Sarvam keys |
| **PS-4** | Removing friction (fewer steps, faster decisions) | Area claim: zero merchant action (automatic). Personal claim: one step (send slip). Cover purchase: 3 taps. Payout: same day. | K1, K2, K6 | LIVE | SPEC §4.3, §9.2, §9.6; monsoon replay (4 min trigger-to-money) | "Same day" is simulated time; real settlement is T+1 | Reframe demo as architecture validation |
| **PS-5** | Reducing complexity (simple, clear explanations) | Why this amount: formula + numbers shown (K5). Coverage explainer: examples + caps + exclusions (N1). Ask Chhatri: answer with clause citations (N2). | K5, N1, N2 | LIVE (K5) + PLANNED (N1, N2) | SPEC §4.3 ("₹1,380 = ½ × ₹4,380 × 63%"); conversation/messages.py | Explanations only in officer console today, not merchant-visible | N1 dashboard shows payout + formula |
| **PS-6** | Completing critical financial journeys faster (hours vs. weeks) | Insurance: 4 min from alert to payout (vs. 30–60 days, A3). Lending: instalment holiday decided same-day. | K1, K2, K3 | LIVE | DEMO.md monsoon scenario: 17:00 trigger → 17:04 payout; 17:05 pause | Speed is simulated clock; real wall-clock is 30–60 sec + T+1 settlement | Honest framing: "simulated time for repeatability" |
| **PS-7** | With greater confidence (auditable, explainable, non-arbitrary) | Hash-chained audit log, deterministic policy engine, all decisions reproducible. | K4, K7 | LIVE | SPEC §11 (audit log), §0.2 (deterministic); 70/70 demo-check pass; `/api/audit/verify` | Audit is ops-visible; not merchant-visible | N1 receipt (H3) shows audit hash prefix |

## 3. Health claims example walkthrough

The track gives a health insurance example: understand coverage → submit documents → track claims → resolve queries.

Chhatri walks this end-to-end using hospital-cash income claims (K2, from interpretation IC-1):

1. **Understand coverage (N1 coverage explainer):** Merchant sees: "Chhatri covers your lost income when you're hospitalized. We pay you ₹1,500/day for up to 3 days, no deductible, with a 7-day waiting period." Example: "If you earn ₹4,300 daily and are hospitalized for 2 days, we pay ₹1,500 × 2 = ₹3,000."
2. **Submit document (N3 live slip reading):** Merchant uploads a hospital discharge summary or admission slip. AI extracts patient name, dates, hospital. Pre-check shows fields and asks for retake if blurry. One submission, no forms.
3. **Track claims (N1 claim tracker):** Merchant sees timeline: "Aug 20–21 · Hospital stay detected from slip · Awaiting approval" → "Aug 21, 11:20 · Approved ₹1,500 · Paid today" with a reason card showing the formula.
4. **Resolve queries (N2 Ask Chhatri, N5 grievance ladder):** Merchant asks (voice or text): "Why only ₹1,500?" System responds: "Clause C3: daily cap is ₹1,500 (half your usual ₹4,300). If you believe this is wrong, file a dispute with case C-2291." If unsatisfied, escalate to insurer GRO → IRDAI Bima Bharosa → Insurance Ombudsman.

This journey maps to K2, N1, N3, N4, N5, N6 and demonstrates that the track example is addressable end-to-end via Chhatri's hospital-cash and support features.

## 4. Interpretation decisions and reasoning

We made three decisions that reframe the track problem:

### IC-1: Hospital-cash framing, not a generic health assistant

**Decision:** K2 is a hospital-cash income claim (income replacement during hospitalisation), not a family health insurance assistant (diagnostics, treatment auth, pre-auth).

**Reasoning:**
- The track example focuses on claims, not health guidance. (Doctor selection, treatment authorization, etc., are out of scope.)
- Merchant data available: KYC (name, ID), sales history (earnings), slip images. No treatment history, no diagnostic codes.
- Insurance product fit: hospital-cash is a real product (Tata AIG, ManipalCigna; A16). Merchants face hospitalization shocks. This is a known need.
- Risk: health-insurance assistants (like Praman, Claim Advocate) are conversation-heavy; we focus on one-document claims (faster, more certain).

**Validity:** K2 answers the "health claims" example by solving the income-loss variant (hospital-triggered absence from work).

### IC-2: Merchant income as the critical financial journey, not health insurance literacy

**Decision:** Chhatri's primary journey is merchant income protection (area loss + hospital illness), not health literacy. Insurance is a vehicle; income is the need.

**Reasoning:**
- Merchant persona (Anil): earns daily, has daily obligations (₹600 EDI). A day of zero income = default risk and inventory stockouts.
- Health (illness) is one trigger; weather (monsoon) is another. Both cause income loss.
- Insurance solutions exist for both; the merchant cares about payout speed and clarity, not medical definitions.
- Risk: If we over-emphasize "health", judges may expect Chhatri to handle non-income health claims (cosmetic surgery, chronic care). Out of scope.

**Validity:** K1 (area) + K2 (personal illness) cover two income-loss triggers. EDI holiday (K3) protects the lending side. Together, they solve "protecting merchant income and loan stability."

### IC-3: EDI holiday as the lending journey, not a separate product

**Decision:** K3 (instalment pause, reframed as EDI holiday) is the lending journey. It is not a standalone product; it is the lender's credit-protection response to an insurance payout.

**Reasoning:**
- Track asks for "insurance, lending and fintech." K3 makes the linkage explicit: insurance payout triggers a lender-authorized loan holiday.
- Instalment pause is RBI-compliant under Digital Lending Directions 2025 (A25) if the lender pre-authorizes it.
- Risk: If we oversell instalment pause as "Chhatri deciding to pause loans", judges will flag that as unilateral (lender pushback). The correct framing: "Chhatri requests; lender decides under pre-agreed rules" (X4).

**Validity:** K3, properly framed as a lender-authorized credit-protection measure, is the lending angle of the Track-2 journey.

## 5. Beyond-the-brief additions

Five features address merchant needs beyond the track statement:

| Feature | Need | Addition |
|---|---|---|
| **N5 Grievance ladder** | Merchant uncertainty: "Is ₹1,380 fair? I think I lost more." Standard insurance escalation path. | Insurer GRO → IRDAI Bima Bharosa (attended within 14 days per the portal) → Insurance Ombudsman (free to the policyholder) |
| **N6 Consent centre** | DPDP compliance: merchants want control over their data. | View consents granted (sales data, slip images); withdraw on demand. Health data on slips is masked and deleted 24h after claim decision. |
| **N8 Marathi** | Mumbai merchant audience: 40% of users prefer Marathi. | Mini-app and Ask Chhatri in Marathi (via bilingual message catalogue + Web Speech API) |
| **Voice-first (N4)** | Low literacy: merchants prefer voice replies over text forms. | Sarvam STT for replies, browser Web Speech API fallback. No typing burden. |
| **X8: No offers during distress** | Ethical AI: when a merchant is claiming a loss, Paytm should not cross-sell loans. | Suppress all proactive messages (loan offers, top-up, insurance cross-sell) while an alert is active or a claim is open. Daily message cap (except confirmations, replies). |

## 6. Self-assessment against generic judging criteria

The following is **our own internal assessment** (not official criteria or judge scoring). We evaluate Chhatri against common fintech/insurance hackathon dimensions.

| Criterion | Self-Assessment | Today | After Plan | Why the gap | Evidence |
|---|---|---|---|---|---|
| **Problem fit** | How well does this solve the track? | 7/10 | 8/10 | Area claims are unique but not explicitly asked (track asks "health claims example"). Personal illness claim is health-adjacent but framed as income, not health insurance. | SPEC §3 (area trigger is sales-based, not health). K2 hospital-cash is income claim, not health insurance. |
| **Innovation** | Is the core idea genuinely new? | 8/10 | 8/10 | Sales-data trigger (not just weather), auto-claim (not assistant-guided), same-day payout + loan pause (trio is novel). Existing: parametric insurance (SEWA, Riskwolf; A9, A14). New: trigger on live sales inside payments app, lender integration. | vision-and-positioning.md positioning line: "area index + settlement-linked payout + EDI holiday." No competitor found combining all three. |
| **AI depth** | Real, visible, safe AI? | 6/10 | 7–8/10 | LightGBM (real ML, live in the engine), policy engine (deterministic, no LLM payout authority; live). Free-tier APIs (Gemini vision for slip reading, Sarvam speech for voice) are live when keys are configured, else SIMULATED and labelled. Without keys, all vision/speech components fall back to offline deterministic templates or Tesseract. After plan: set free-tier API keys for live demo. | All integrations labelled in the console header: LIVE (key configured), SIMULATED (key not set), FALLBACK (primary failed). LightGBM model: backend/chhatri/forecast/ (always live). Policy engine: only APPROVED authority, per SPEC §0.2. |
| **Technical execution** | Production-grade code? | 9/10 | 9.5/10 | 99.7% backend test coverage, 262/264 frontend tests pass (2 failing tests, fixable in 1h), 70/70 demo checks pass, deterministic replay, hash-chained audit log. After plan: fix 2 frontend tests. | facts-and-sources.md §D: 1,711 fast + 36 slow tests pass; `make demo-check` 70/70; git history clean; immutable pydantic models, no secrets. |
| **UX & humanity** | Are merchants and humans centered? | 5/10 | 8/10 | Bilingual messages (Hindi/English), voice replies, merchant-friendly explanations. Missing: merchant-facing UI (cover card, claim tracker, dispute form not shown to judges). After plan: add merchant dashboard mockups (4 screens). | Prototype has console (ops), WhatsApp sim (customer sim only). Missing: /merchant/ routes. DEMO.md shows Anil's WhatsApp flow but judges don't see merchant's own app. |
| **Business impact** | Does this create value for Paytm? | 6/10 | 7/10 | Reduces merchant churn (same-day payout), reduces defaults (EDI holiday), enables insurance revenue (₹2/day × merchants). Unit economics not shown. Paytm's FS revenue ₹814 cr (A2) growing 45%; Chhatri is a rider. | vision-and-positioning.md "Why Paytm" section: Paytm already has sales data, settlement rail, merchant audience, insurance broking arm. Chhatri fills insurance claims friction gap (30–60 days today, A3). Business model: [05-business/business-model-and-unit-economics.md]. |
| **Feasibility & compliance** | Can this launch? Are regulatory risks clear? | 5/10 | 8/10 | Insurance Act §64VB (cash before cover) addressed; RBI credit-protection guidance exists (A25); policy engine is deterministic (IRDAI-defensible). Missing: no named insurer partner, DPDP consent screens, WhatsApp template pre-filing. After plan: add COMPLIANCE_ROADMAP.md. | SPEC §14 mentions §64VB but no compliance roadmap. facts-and-sources.md §B: hedges on all regulatory claims. Missing docs: insurer name, lender authorization in code (X4), DPDP consent flow. |
| **Demo wow & reliability** | Does the on-stage demo work? Is it impressive? | 8/10 | 9/10 | Monsoon replay is slick (hex map, 312 shops, 4-min trigger-to-money, Soundbox). Three live tests (dispute, slip mismatch, blocked cover) demonstrate logic. All 70 scenarios deterministic. After plan: add merchant mockups to show full product, record backup video, rehearse tight script. | DEMO.md: 7-min walkthrough with golden numbers; all 70 checks pass. Risks: n8n may hold clock 30–60s (mitigated by in-process fallback); Sarvam timeout risk (pre-test slip). |
| **Journey completeness** | Does merchant see the full journey? | 4/10 | 7/10 | Area claim and personal claim flows are complete in code and demo (trigger → decision → payout → explanation). Missing: buy cover screen (where does merchant see T&Cs and caps?), claim tracker timeline (where does merchant track payout status?), grievance escalation (how does merchant escalate if unhappy?). After plan: add 4-screen merchant dashboard (cover, explainer, tracker, dispute form). | Prototype has console (all ops views) + WhatsApp simulator (customer replies only). No merchant-facing purchase, tracking or escalation screens. fs-04-merchant-mini-app.md: N1 mini-app is P0 on 2–3 Oct. |

**Summary:** The prototype is strong on backend engineering, testing and determinism. Key gaps are (1) merchant-facing UI and journey completeness, (2) regulatory and compliance documentation, (3) honest reframing of the backtest and the accelerated demo clock. Planned fixes (N1–N4, compliance docs, errata in the pitch) address these gaps before the final.

## 7. What we deliberately do NOT do (and why)

| What we avoid | Why |
|---|---|
| **Health insurance (diagnostics, treatment auth, pre-auth)** | Out of Chhatri's scope. Merchant data (KYC, sales, slip image) is insufficient for treatment decisions. Health guidance is a separate product. Chhatri focuses on income-loss response, not health literacy. |
| **Multi-agent orchestration or vector-DB RAG for policy** | Our policy wording is small (~500 words). Clause-ID grounding (K5, N2) is simpler, testable and compliant than LLM RAG. Roadmap only (post-pilot). |
| **LLM deciding payouts** | Non-negotiable. Policy engine (code) is the only authority. IRDAI compliance + audit defensibility + merchant trust. LLM is fallback-only for intent classification. |
| **Blockchain proof-of-life** | Out of scope. Hash-chained audit log (SQLite + SHA256) is sufficient for tamper-evidence and regulator audit. Blockchain adds no value here. |
| **Fintech product expansion (loans, savings, credit scoring)** | Chhatri is insurance + credit protection. Lending is partner's domain (Paytm NBFC, banks). No new loan products. |
| **Paid AI or APIs** | Hackathon constraint: free tools only (Gemini, Sarvam starter, Tesseract). Production would use insurer's preferred vendors (Sarvam, Gemini, or proprietary models). |
| **Flat-UI or design system upgrade from the deck** | Keep current: plain CSS tokens, react-leaflet, Ubuntu + Noto Sans Devanagari. No Recharts, Tailwind or premium design. Signals lean, focused build. |

## Open questions

1. **Insurer partnership:** Should we name a prospective insurer partner in the pitch, or say "in exploratory discussions"? (Owner: Omkar Kadam)
2. **Merchant sign-up journey:** How do merchants discover and onboard to Chhatri? Is it via an SMS link, via the Paytm for Business app, or via field sales (Amit)? The on-site demo should show the path clearly. (Owner: Omkar Kadam)
3. **Merchant journey priority:** Is 4-screen merchant app mockup (cover, tracker, dispute, escalation) feasible on-site in 3 hours, or should we prioritize code fixes and demo polish? (Owner: Ujjwal Pardeshi)
4. **Backtest framing:** Should we reframe the backtest as "specification validation" or "architecture proof" in the pitch? And should we disclose the circular calibration to judges proactively or only if asked? (Owner: Omkar Kadam) [DECIDED: proactively disclose in executive summary and demo runbook hook.]

## Changelog

- 2026-10-02 · v1.4 · second fact-check pass: clarified PS-1 status (LIVE for K1–K3, PLANNED for N1, N6)
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.1 · fact-check pass: renamed the interpretation choices to IC-1–IC-3; removed numeric self-assessment totals; qualitative gaps now emphasized
- 2026-10-02 · v1 · first draft; traceability matrix and interpretation decisions mapped; self-assessment calibrated to judge notes
