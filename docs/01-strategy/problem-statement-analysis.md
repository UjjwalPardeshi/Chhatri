# Problem statement analysis

| | |
|---|---|
| Status | Draft v1.6 · 3 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Judges, mentors, the team, stakeholders evaluating Chhatri against the track |
| Related | [Requirements traceability matrix](requirements-traceability-matrix.md) · [Facts and sources](facts-and-sources.md) · [Executive summary](../00-executive-summary.md) · [Vision and positioning](../02-product/vision-and-positioning.md) · [User journeys](../02-product/user-journeys.md) · [Competitive landscape](competitive-landscape.md) · [Demo script](../DEMO.md) |

## TL;DR

- The track asks for AI-powered financial journeys across insurance, lending and fintech. Chhatri answers it through one merchant's story: a rain day triggers an automatic insurance payout and a request for a loan holiday, and an illness is claimed with one photo.
- We split the statement into 14 requirements (PS-1 to PS-14) and add 7 that nobody wrote down (IR-1 to IR-7). Section 2 summarises them. The [traceability matrix](requirements-traceability-matrix.md) maps each one to features, status, demo moment and tests.
- Section 3 walks the track's own example, the health-claims journey, on Chhatri's hospital-cash claim: understand coverage, submit documents, track the claim, resolve queries. Every stage is BUILT: the deciding stages (check-in, one photo, decision, payout, explanation, dispute) run by default, and the merchant-facing stages (coverage explainer, slip pre-check, claim tracker, free questions, grievance ladder, consent centre) are built behind feature flags.
- Three interpretation decisions (IC-1 to IC-3) explain why we answer a health-claims example with an income claim and an instalment request.
- Every feature is P0 and sits behind a flag that is off until the build turns it on, so a screen that is not rehearsed can be hidden and is never shown half-working.
- Honest gaps today: the Gemini and Sarvam paths are tested against fakes only (no key has been run), Marathi is a draft, the static demo is not deployed, and sales, alerts, KYC, payouts, lender, WhatsApp and Paytm link are simulated.

## 1. The track problem statement (verbatim)

> **AI-Powered Financial Journeys (Track 2, Paytm Build for India AI Hackathon, Mumbai Edition)**
>
> About This Track
> Make Insurance, Lending and Fintech simpler, faster and more human.
>
> Reimagine customer-facing journeys across Insurance, Lending and Fintech using AI. Focus on removing friction, reducing complexity, and helping customers complete critical financial journeys faster and with greater confidence.
>
> Example - How might we simplify the Health Insurance claims journey using AI—from understanding policy coverage and submitting documents to tracking claims and resolving customer queries?

## 2. Atomic requirements

We split the statement by its own words into 14 requirements. Features, tests and demo moments for each are in the [traceability matrix](requirements-traceability-matrix.md). Status words: BUILT is in the code and covered by tests. "Behind a flag" means off until `CHHATRI_FEATURES` and `VITE_FEATURES` name it.

| ID | Requirement | Chhatri's answer | Status | Gap, and what closes it |
|---|---|---|---|---|
| PS-1 | Insurance | An area claim that starts from the merchant's area sales, and a hospital-cash claim that starts from a silent day. Both pay by rule (K1, K2), and cover is bought with a waiting period (K6) | BUILT | Hospital cash has no premium yet. The price covers area claims only |
| PS-2 | Lending | After a payout, the next instalment is paused (K3). The design is a request that the lender decides (X4) | K3 BUILT as an unconditional pause through the simulated lender. X4 BUILT behind `x4_lender_request` | With the flag off, no lender decides. With it on, the simulated lender decides, behind a guard. The lender is a simulator |
| PS-3 | Fintech | A payout that rides the evening settlement with a Soundbox line, and a Paytm payment link for cover (K1, K2, K6) | BUILT on simulated rails | Every rail is simulated and labelled. A pilot would replace them |
| PS-4 | Customer-facing journeys | A WhatsApp-style phone simulator, and the merchant mini-app (N1) | Simulator BUILT. N1 BUILT behind `n1_miniapp`. N7: static build BUILT | The static demo is not deployed (the repo owner has to) |
| PS-5 | Using AI | A LightGBM quantile forecast with a conformal zone bound (K1). Sarvam speech, chat and slip reading, live only with a key. A guard for free-text replies. N2, N3 and N4 run Gemini, then Sarvam, then templates, with H26 labels | BUILT. N2 to N4 behind `n2_ask_chhatri`, `n3_slip_precheck`, `n4_voice` | No key has been run: the provider chain is tested against fakes only. The H25 harness runs offline and no run is stored |
| PS-6 | Less friction | K1 needs no action from the merchant. K2 needs one photo. The N3 pre-check hands a bad photo back before it counts | BUILT. N3 behind `n3_slip_precheck` | None known |
| PS-7 | Less complexity | "Why this amount": the formula and the numbers (K5), and the N1 coverage explainer with a jargon lens | BUILT. N1 behind `n1_miniapp` | None known |
| PS-8 | Faster | The credit lands 4 simulated minutes after the decision (K1, K2) | BUILT on the replay's simulated clock | The speed shows the design. Real settlement timing is not measured by us |
| PS-9 | More confidence | A deterministic engine (K4), a hash-chained audit log (K7), numbers that can be reproduced (K5), and a receipt with sources and a counterfactual (H3, H13, H14) | BUILT | The audit log is tamper-evident, not durable: it lives in memory per scenario load |
| PS-10 | More human | Hindi and English templates, a check-in before any claim, a claims officer for every doubtful claim (K8), voice (N4) and Marathi (N8) | BUILT. N4 behind `n4_voice`. N8 a draft behind `n8_marathi` | Marathi needs a native speaker's review. Voice is untried with a key |
| PS-11 | Understand policy coverage | The policy wording and the `/policy` page, the N1 explainer and N2 Ask Chhatri with clause chips | BUILT. N1 and N2 behind their flags | Ask answers beyond the templates need a live key |
| PS-12 | Submit documents | One slip photo, read and checked by the engine. The N3 pre-check shows what was read | BUILT. N3 behind `n3_slip_precheck` | Live reading needs a key. Otherwise a labelled simulator reads the slip |
| PS-13 | Track claims | Messages at decision, credit and pause, a "What happened" strip, the officer queue, and the N1 claim tracker with the receipt | BUILT. N1 behind `n1_miniapp` | None known |
| PS-14 | Resolve customer queries | The "why" answer, a dispute that opens a case with a 24 h clock, an officer who confirms or rejects. N2 free questions and the N5 grievance ladder | BUILT. N2 and N5 behind their flags | The ladder's outside steps (insurer, Bima Bharosa, Ombudsman) are self-reported by the merchant: Chhatri records and never checks them |

The seven requirements we add are: IR-1 honest labels, IR-2 consent and data rights, IR-3 accessibility, IR-4 Hindi, English and Marathi, IR-5 auditability, IR-6 safe AI, and IR-7 a person for doubtful cases, and no selling to a merchant in distress. They are in section 3 of the matrix, with status and tests. Two are partly open today: the consent centre (N6) is built behind `n6_consents` but has not been rehearsed, and there is no automated screen-reader or axe-style accessibility check.

## 3. The health-claims example on Chhatri's hospital-cash journey

The track's example asks how AI could simplify a health insurance claims journey "from understanding policy coverage and submitting documents to tracking claims and resolving customer queries". Chhatri answers the same four stages on one product: hospital cash, an income benefit paid when a shop owner is in hospital (K2). We chose an income claim over a treatment claim on purpose (IC-1).

The walkthrough follows Anil Jadhav, who runs a tea stall in Parel. His shop had no sales all Wednesday 20 Aug 2025. His usual Wednesday is ₹4,300 and his daily instalment is ₹600. Everything below runs on simulated sales, KYC, payout and lender, and the console labels them. The scenes are in the [demo script](../DEMO.md).

| Stage in the track's words | What Anil meets with the flags off (BUILT) | What the app adds (BUILT behind flags) |
|---|---|---|
| 1. Understanding policy coverage | The policy wording ([C3](../02-product/policy-wording-and-cis.md)) says Chhatri pays half of a usual day's sales, up to ₹1,500 a day, for up to 3 days without a person looking. The console's `/policy` page shows who may decide money. Anil can ask for cover in chat and gets OK or BLOCKED with the reason. With the mini-app flag off there is no merchant-facing coverage screen | N1 coverage explainer with the H20 jargon lens (`n1_miniapp`). N2 Ask Chhatri answers questions such as whether hospital bills are covered, citing clause chips C1 to C12 (`n2_ask_chhatri`, H17) |
| 2. Submitting documents | After a full day with no sales, Chhatri checks in first: "Your shop has been closed since yesterday. Is everything okay?" Anil says he is in hospital and gets "Get well soon. Please send one photo of the hospital slip." He sends one photo. The slip reader takes the name and dates (Sarvam when `SARVAM_API_KEY` is set, otherwise a labelled simulator). The engine runs nine personal checks. Three are about the slip: it is readable (confidence 0.80 or more), the name matches his KYC name (score 85 or more) and the dates cover the silent day. If all pass, the claim is APPROVED. If one of the three fails or the read is unsure, it is REFERRED to a person and no money moves. A failed check on cover, prepayment, verified silence, duplicate payment or the annual limit is DECLINED | N3 pre-check (`n3_slip_precheck`, H5, H15, H16). It shows what was read and asks "is this right?", checks the document class and the slots, and sends a bad photo back with one reason while Anil still holds the paper. It never says that the name matches, because only the engine decides |
| 3. Tracking the claim | The decision comes at the minute of the photo: ₹1,500. Four simulated minutes later: "Anil ji, your claim is approved. ₹1,500 credited with today's settlement.", with the payout card and the Soundbox line. One minute after that: "Today's ₹600 instalment is paused." A "What happened" strip beside the phone lists the decision, the credit and the pause in order. A referred claim shows "Sent to a claims officer · case C-2291" and waits in the officer queue until the officer approves | N1 claim tracker (`n1_miniapp`): Detected, Checked, Decided, Paid, EDI holiday, with the REFERRED and DISPUTE paths, and a receipt with sources (H1, H3, H13). X4 (`x4_lender_request`) turns the pause into a request that the simulated lender decides |
| 4. Resolving customer queries | Anil taps "why" and gets the working: "How your claim was worked out: ½ × ₹4,300 = ₹2,150 a day, capped at ₹1,500 × 1 day = ₹1,500". If he thinks it is too low he taps "dispute" and gets "Okay, I'm sending this to our team. You'll hear back within 24 hours." The officer confirms the payout or rejects the dispute. The amount never changes | N2 free questions with clause chips (`n2_ask_chhatri`). N5 grievance ladder (`n5_grievances`): the insurer's grievance officer, then IRDAI's Bima Bharosa portal, then the Insurance Ombudsman, with a clock only where a source states one (H22). N6 consent centre (`n6_consents`): "forget my slip" (H23) |

**What the judge sees.** On stage, the personal claim runs from the check-in to the paid message and the paused instalment, then a name mismatch goes to an officer and is approved. The explanation and the dispute are the EXPLAINED scene. Where the flagged screens appear is in [runbook §4](../06-delivery/demo-runbook.md), and each is shown only if it passes rehearsal.

**What we do not claim.** The slip is a sample, the KYC name is a seeded record, and the lender and the payout are simulators. The 4 simulated minutes show the design. They are not a measured settlement time. Hospital cash has no premium yet.

## 4. Interpretation decisions and reasoning

We made three decisions that reframe the track problem.

### IC-1: Hospital-cash framing, not a generic health assistant

**Decision:** K2 is a hospital-cash income claim (income replacement during hospitalisation), not a family health insurance assistant (diagnostics, treatment authorisation, pre-authorisation).

**Reasoning:**
- The track example is about the claims journey, not health guidance. Doctor selection and treatment authorisation are out of scope.
- The merchant data we have is the KYC name, sales history and a slip image. We have no treatment history and no diagnostic codes.
- Hospital cash is a real product (Tata AIG and ManipalCigna pages, A16). Shop owners face hospital stays, and an income benefit is the part of the loss that a daily-sales signal can measure.
- Projects such as Praman and Claim Advocate help a person prepare, check or appeal a health claim ([competitive landscape](competitive-landscape.md)). We start and pay a one-document income claim. The two answer the example from different sides.

**Validity:** K2 answers the "health claims" example by solving the income-loss variant: a hospital stay that keeps a merchant away from the shop.

### IC-2: Merchant income as the critical financial journey, not health insurance literacy

**Decision:** Chhatri's primary journey is merchant income protection (area loss and hospital illness), not health literacy. Insurance is the vehicle. Income is the need.

**Reasoning:**
- The merchant persona (Anil) earns daily and has daily obligations (a ₹600 instalment). A day of no income raises default risk and stockouts.
- Illness is one trigger and weather is another. Both cause income loss.
- Our working assumption is that the merchant cares more about payout speed and clarity than about medical definitions. We have not tested this with merchants.
- If we stress "health", judges may expect Chhatri to handle non-income health claims. Those are out of scope.

**Validity:** K1 (area) and K2 (illness) cover two income-loss triggers. The EDI holiday request (K3) covers the lending side. Together they address merchant income and loan stability.

### IC-3: The EDI holiday as the lending journey, not a separate product

**Decision:** K3 (the instalment pause, reframed as an EDI holiday) is the lending journey. It is not a standalone product. It is a request to the lender after an insurance payout, and the lender decides.

**Reasoning:**
- The track asks for insurance, lending and fintech. K3 links them: an insurance payout leads to a request that a lender may grant.
- The correct framing is "Chhatri requests, the lender decides under a pre-agreed rule" (policy clause C10, X4). If we oversold it as Chhatri pausing a loan, judges would rightly call it unilateral. With `x4_lender_request` off the prototype pauses the instalment directly through the simulated lender. With it on, X4 sends a request and the simulated lender decides.
- The RBI (Digital Lending) Directions, 2025 (A25) apply to digital lending. How they apply to an EDI holiday is for the partner lender's compliance team to confirm ([regulatory and compliance §5](../05-business/regulatory-and-compliance.md)). We have taken no legal advice.

**Validity:** K3, framed as a lender's decision on a request, is the lending angle of the track journey.

## 5. Beyond-the-brief additions

Five features address merchant needs the track statement does not mention. All are BUILT behind flags and P0.

| Feature | Need | Addition |
|---|---|---|
| **N5 Grievance ladder** (`n5_grievances`) | A merchant may think ₹1,380 is unfair. The standard insurance escalation path should be one tap away. | The insurer's grievance officer, then IRDAI's Bima Bharosa portal, then the Insurance Ombudsman (free to the policyholder). A clock is shown only where a source states one: our own 24 hours, and the 14 days the portal states. Other times read "to be confirmed" |
| **N6 Consent centre** (`n6_consents`) | DPDP: merchants want control of their data | Three purposes with a switch each (sales data, hospital slip, premium from the daily settlement), an activity log, and "Erase this slip", which removes the photo, the fields read from it and the copied text. The audit log is append-only, so earlier entries can still quote a name, and the screen says so |
| **N8 Marathi** (`n8_marathi`) | The pilot city is Mumbai, and Marathi is the state language. Hindi and English leave some merchants out. We have not measured how many | The mini-app and Ask Chhatri in Marathi, through the same message catalogue that already serves Hindi and English. The text is a draft until a native speaker reviews it |
| **N4 Voice** (`n4_voice`) | Many merchants will find speaking easier than typing (our assumption) | Sarvam speech-to-text and text-to-speech when keyed, and browser speech as a fallback, with confirmation chips for amounts and dates (H18) |
| **X8 No offers in distress** (`x8_distress_guard`) | When a merchant is claiming a loss, Paytm should not sell a loan | No loan, top-up or cross-sell message while an alert covers the zone or a claim or dispute is open, and a daily cap on proactive messages. A test enforces it |

## 6. Self-assessment against generic judging dimensions

This is **our own internal view**. It is not the official criteria and it is not a score. Each row names what is strong today (BUILT), the gap, and what closes it.

| Dimension | Strong today (BUILT) | Gap today | What closes it |
|---|---|---|---|
| Problem fit | Insurance (K1, K2), lending (K3) and fintech (payout, Soundbox, cover link) in one story, and the health-claims example answered through hospital cash | The track example is a health claim. Ours is the income variant, so a judge may look for a treatment-claim assistant | Section 3 walks the four stages. N1, N2, N3 and N5, behind their flags, put them in a merchant's hands |
| Innovation | A trigger from the merchant's own area sales, a settlement-linked payout, and an instalment request. We found no other project or product with this combination ([competitive landscape](competitive-landscape.md)), and we may have missed one | The parts exist separately: parametric cover (A14) and claim assistants (Praman, Claim Advocate and others) | None needed. We keep the claim carefully worded |
| AI depth | A LightGBM quantile forecast with a conformal bound, Sarvam adapters live with a key, a guard on free-text replies, and a rule that code decides money | The Gemini and Sarvam chains are tested against fakes only: no key has been run. Intents still come from word lists. The H25 evaluation harness runs offline and no run is stored | A person sets the keys and runs the live smoke test. The `/evals` page shows a number only from a stored run |
| Technical execution | Backend 3,284 tests collected (63 of them slow), frontend and Playwright suites for the console and the mini-app (counts in the [facts page](facts-and-sources.md)), `make demo-check` 70 of 70 at 86575ea. Deterministic replay and a hash-chained audit log | The baseline counts of 86575ea are in the [current-state audit](current-state-audit.md); the README does not publish counts | H12: write the measured counts after the final run |
| UX and humanity | Hindi and English messages, voice chips, a check-in before any claim, a person for every doubtful claim, and the mini-app in Hindi, English and a Marathi draft | Nothing here has been tried with a real merchant. Marathi needs a native review | User testing in a pilot. A native reader for Marathi |
| Business impact | Paytm already has live sales, the settlement rail and an insurance broking licence (A1, A4). Its merchant plan shows merchants buy cover (A3) | We have no measured effect on churn or defaults. Unit economics are assumptions to test in a pilot ([business model](../05-business/business-model-and-unit-economics.md)) | A pilot with a partner insurer and lender. No partner has agreed to anything |
| Feasibility and compliance | A design that takes cash before cover (s.64VB, to be confirmed with the insurer's compliance team), and a [regulatory and compliance](../05-business/regulatory-and-compliance.md) plan | No named insurer or lender. The consent record and the lender decision are in code behind flags, and the lender is a simulator | The partner's compliance team after the hackathon |
| Demo reliability | A deterministic replay, 70 of 70 demo checks, three live tests (EXPLAINED, HUMAN, BLOCKED) | With n8n live, the clock holds at 17:00 for about 30 to 60 seconds, so the demo script recommends the in-process runner. Slip reading is live only with a Sarvam key | Rehearsals, deploying the static demo and recording the backup video (human-only) |
| Journey completeness | Area and personal claims run end to end in code and demo | The buy-cover, claim tracker, grievance and consent screens exist behind flags and have not been rehearsed | The beat drills and rehearsals in the [runbook](../06-delivery/demo-runbook.md) |

**Summary.** The prototype is strong on backend engineering, testing and determinism. The merchant-facing app, the AI chain, the consent centre and the grievance ladder are built behind flags. The main gaps are rehearsal, untried AI keys, and the honest framing of simulated rails and an accelerated demo clock.

## 7. What we deliberately do not do

| What we avoid | Why |
|---|---|
| **Health insurance (diagnostics, treatment authorisation, pre-authorisation)** | Out of scope. The KYC name, sales and a slip image are not enough for treatment decisions. Chhatri responds to income loss, not to health questions |
| **Multi-agent orchestration, or vector search over the policy** | Our policy wording is 12 clauses (C1 to C12). Clause ids with every number from decision facts (H17) are simpler and easier to test |
| **A model that decides payouts** | Non-negotiable. The policy engine, which is code, is the only authority, for audit and trust. Intents come from word lists, and the chat model sees only text they cannot place. N2 answers from policy clauses and decision facts, and a guard blocks unsupported numbers |
| **Blockchain registry or proof-of-life** | Out of scope. The hash-chained audit log (SQLite and SHA-256) gives tamper evidence |
| **Fintech product expansion (loans, savings, credit scoring)** | Chhatri is insurance and an instalment request. Lending is the partner's domain. No new loan products |
| **Paid AI or APIs** | Free tools only for the hackathon: the Gemini API free tier and Sarvam free credits. A pilot would choose its AI vendors with the partner insurer |
| **A UI framework for the whole product** | The console keeps its plain CSS tokens, react-leaflet and fonts. Only the merchant mini-app uses Tailwind CSS v4 and shadcn/ui, scoped under `.miniapp` and mapped to the same tokens. No charting library |

## Open questions

1. **Insurer partnership:** Should we name a prospective insurer partner in the pitch, or say "in exploratory discussions"? No partner has agreed to anything. Owner: Omkar Kadam.
2. **Merchant sign-up journey:** How do merchants discover and onboard to Chhatri? An SMS link, the Paytm for Business app, or field sales (Amit)? The demo should show the path. Owner: Omkar Kadam.
3. **Hospital-cash price:** The premium covers area claims only. How should hospital cash be priced with a partner insurer? Owner: Omkar Kadam.
4. **Backtest framing:** Should we call the backtest "specification validation" or "architecture proof" in the pitch? [DECIDED: disclose the circular calibration proactively, in the executive summary and the demo runbook hook.] Owner: Omkar Kadam.

## Changelog

- 2026-10-03 · v1.6 · statuses brought up to the code: N1 to N8 and X4, X6, X8 are BUILT behind flags; the self-assessment no longer lists fixed gaps; baseline counts replaced
- 2026-10-02 · v1.5 · restored the verbatim statement; 14 requirements plus 7 implicit ones, linked to the new traceability matrix; an explicit walkthrough of the track's health-claims example on the hospital-cash journey, BUILT and PLANNED by stage; removed numeric self-scores and unverified claims (a Marathi share, RBI compliance of the pause, Tesseract and Gemini as live, a one-hour fix); waves instead of priorities; mini-app stack note
- 2026-10-02 · v1.4 · second fact-check pass: clarified PS-1 status (LIVE for K1–K3, PLANNED for N1, N6)
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.1 · fact-check pass: renamed the interpretation choices to IC-1–IC-3; removed numeric self-assessment totals; qualitative gaps now emphasized
- 2026-10-02 · v1 · first draft; traceability matrix and interpretation decisions mapped; self-assessment first version
