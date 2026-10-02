# Product requirements document

| | |
|---|---|
| Status | Draft v1.6 · 3 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Product, engineering, design, compliance, judges |
| Related | [Personas and JTBD](personas-and-jtbd.md) · [User journeys](user-journeys.md) · [Facts and sources](../01-strategy/facts-and-sources.md) · [Metrics and impact](metrics-and-impact.md) · [SPEC.md](../SPEC.md) · [Build plan](../06-delivery/build-plan.md) · [Requirements traceability matrix](../01-strategy/requirements-traceability-matrix.md) · [Competitive landscape](../01-strategy/competitive-landscape.md) · [Risk register](../06-delivery/risk-register.md) |

## TL;DR

- **Problem:** Earlier merchant plans took 30–60 days per claim and needed multiple documents (A3). Paytm already processes a shop's payments on its devices (A1), so the sales signal exists, but a claim still starts with the merchant.
- **Solution:** Chhatri starts the claim itself. It detects two loss events from sales data (an area drop during a weather alert, and a shop that has gone silent). The policy engine decides and pays with at most one document, and none for an area claim. After a payout Chhatri asks the merchant's lender to defer the next instalment, and the lender decides. In the prototype the sales, alerts, KYC, payout and lender are simulated and labelled.
- **Scope:** 8 kept features (K1–K8), 8 new features (N1–N8), 8 fixes (X1–X8) and 26 ideas from other teams (H1–H26). All of it is P0 and all of it is BUILT: the new work was built in six waves behind feature flags, and a feature that is not rehearsed is hidden, never shown half-working (section 3.3). Not done, and human-only: rehearsals, the backup video, deploying the static demo, a native review of Marathi. The four stages of the track's health-claims example map to features in the [traceability matrix](../01-strategy/requirements-traceability-matrix.md).
- **Success (targets, none measured yet):** every decision explanation can be reproduced from the numbers shown, no unsupported money figure in Ask Chhatri, no loan offers while an alert covers the zone or a claim or dispute is open, and the three live tests of the demo pass. Backend coverage was 99.7% at the 2 Oct baseline against an 80% gate; it is measured again in the final run.

---

## 1. Problem and goals

### 1.1 Problem statement

Small shop-based merchants lose income to weather shocks, power cuts and illness. Paytm's merchant protection plan shows that merchants will buy cover: it costs under ₹2 a day, is bought in three taps and covers 2 lakh+ merchants. Earlier plans took 30–60 days per claim and needed multiple documents (A3). Across Indian health insurance, about 8% of claims were repudiated in IRDAI's 2024-25 data (A10). We have no such figure for merchant plans.

**Root cause:** Paytm processes the shop's payments and settlement (A1), so the sales signal exists, but a claim still starts with the merchant. The merchant has to notice the loss, gather documents, file and wait. On a rain day the daily loan instalment is still taken from the settlement, which is the story in our demo.

**Impact:** We have no measured data on adoption, claim rates or instalment arrears. A pilot would measure them ([Metrics and impact](metrics-and-impact.md)).

### 1.2 Goals

1. **Cut time-to-money from weeks to the same day** (north star, see [Metrics and impact](metrics-and-impact.md)). Chhatri starts the claim itself from sales data. In the replay the credit lands 4 simulated minutes after the decision.
2. **Lower claim barriers:** no document for an area income loss, one document (a hospital slip) for illness. The N3 pre-check (`n3_slip_precheck`) hands a bad photo back before a decision, and doubtful claims always reach a person.
3. **Ask the lender for an EDI holiday on shock days:** after an approved claim, Chhatri requests that the next instalment moves to the end of the loan with no penalty. The lender decides under its own rule (X4, `x4_lender_request`).
4. **Explain every decision in Hindi and English, reproducibly from the numbers shown.** A merchant can ask "why" and dispute, and we aim to answer a dispute within 24 hours.
5. **Span the track (insurance, lending, fintech) and the merchant journey:** understand, buy, track a claim, resolve a dispute, escalate a grievance.
6. **Build on free tools only:** the Gemini API free tier and Sarvam free credits are the only accounts, and browser speech is a fallback. Tesseract is a later option and is not in the reader chain. Every integration is labelled LIVE or SIMULATED, and X6 (`x6_provider_panel`) adds FALLBACK.

### 1.3 Non-goals

- Multi-branch chains, aggregators or corporate merchants (scope: shop-based, 1–3 staff).
- Family health insurance (scope: income loss during hospitalisation, not family coverage).
- Loan origination (scope: merchant loans pre-exist; Chhatri coordinates with the lender).
- Real-time lending (scope: an EDI holiday defers an instalment, and the lender decides under its policy).
- Multi-document claims (scope: one hospital slip per claim, by photo; no bank statements, proofs or forms).
- Proactive settlement (scope: payouts ride the evening settlement, not instant bank transfers).

---

## 2. Users and personas

| Persona | Role | Motivation | Context |
|---|---|---|---|
| **Anil Jadhav (S-0142)** | Tea-stall owner, Parel, Z7, Mumbai | Needs income protection on rainy days. Wants a fast claim without forms. Expects slow claims, because earlier plans took 30–60 days (A3). | ₹600 daily instalment. Expected ₹4,380 on the replay Tuesday. Z7 premium ₹18.62 a day (₹558.60 for 30 days), from the backtest, pricing decision pending. Speaks Hindi, uses WhatsApp and Soundbox. |
| **Ramesh (S-0907)** | Vada pav shop owner, Worli, Z3, not covered | Wants to buy cover, and needs the waiting-period rule explained. | Z3 premium ₹14.16 a day (₹424.80 for 30 days). Hears about alerts from the news. |
| **Priya** | Kirana owner, Delhi | Possible future user of heatwave cover (roadmap, not in the pilot). | (Roadmap) |
| **Rajesh** | Claims officer, partner insurer | Reviews REFERRED claims and disputes. Cannot change an amount, because the policy engine is the authority. | Uses the console (`/claims`). Sees the slip evidence and the KYC match. We aim to decide within 24 hours. |
| **Amit** | Paytm field sales and relationship executive | Onboards merchants and explains cover in person or by phone. | Uses the mini-app coverage explainer (N1) to show merchants. |

See [Personas and JTBD](personas-and-jtbd.md) for full details.

---

## 3. Scope: features and build waves

### 3.1 Legend

| Word | Meaning |
|---|---|
| BUILT | In the code and covered by tests. A feature behind a flag is off until `CHHATRI_FEATURES` and `VITE_FEATURES` name it. Sales, alerts, KYC, payouts, the lender, Soundbox, WhatsApp and the Paytm link are always SIMULATED and labelled. The AI paths are tested against fakes only: no key has been run |
| Not done | Needs a person (deploy, video, rehearsal, a native reviewer) or a real key. Every item was **P0** (team decision, 2 Oct 2026). The order of work was the **wave** |
| Wave | 0 setup · 1 demo spine · 2 live AI · 3 trust and rights · 4 judge wow · 5 ship. Section 3.3 has the goals and flags |
| Owner | Omkar: mini-app, console, design, copy, pitch. Ujjwal: backend, engine, AI adapters, evals. "Both" means screens by Omkar and backend by Ujjwal |
| Spec | The feature spec that holds the detail and the test plan |

### 3.2 Feature scope table

| ID | Feature | What it does | Wave | Owner | Status | Spec |
|---|---|---|---|---|---|---|
| **Keep (K)** | | | | | | |
| K1 | Area auto-claim | Triggered at area level with no action from the merchant. Pays ½ × the shop's expected day × the area drop %, capped at ₹2,500 a day. The index needs at least 20 shops | built | Ujjwal | BUILT | [fs-01](feature-specs/fs-01-area-auto-claim.md) |
| K2 | Hospital-cash claim | A silent day, a check-in at 11:20 the next day, one slip photo. Pays ½ of the usual day, capped at ₹1,500 a day, up to 3 days automatically | built | Ujjwal | BUILT | [fs-02](feature-specs/fs-02-hospital-cash-claim.md) |
| K3 | EDI holiday | After a payout, Chhatri asks the lender to defer the next instalment with no penalty. The lender decides | built, X4 in 1 | Ujjwal | BUILT as an unconditional simulated pause. X4 adds the request, the guard and the wording | [fs-03](feature-specs/fs-03-edi-holiday.md) |
| K4 | Policy engine and payout authority | Pure rules in `rules.yaml` (pilot-0.1). The only source of APPROVED decisions | built | Ujjwal | BUILT | [fs-09](feature-specs/fs-09-policy-engine-and-audit.md) |
| K5 | Explanations and disputes | "Why this amount" with the formula. A dispute opens a case with a 24 h clock. An officer confirms the payout or rejects the dispute, and the amount never changes | built | Ujjwal | BUILT | [fs-06](feature-specs/fs-06-explanations-disputes-and-grievance.md) |
| K6 | Cover purchase with waiting period | Cover starts 7 days after the request. The quote is OK or BLOCKED (an alert is valid now, or starts within 72 hours). The payment link is still offered | built | Ujjwal | BUILT | [fs-07](feature-specs/fs-07-cover-purchase-and-consent.md) |
| K7 | Tamper-evident audit log | A hash chain. `GET /api/audit/verify` checks it | built | Ujjwal | BUILT | [fs-09](feature-specs/fs-09-policy-engine-and-audit.md) |
| K8 | Claims-officer console and live map | Seven pages: overview, live map, claims, merchant phone, audit, backtest, policy | built | Omkar | BUILT | [fs-08](feature-specs/fs-08-claims-officer-console.md) |
| **New (N)** | | | | | | |
| N1 | Merchant mini-app "Chhatri in Paytm for Business" | Phone-sized and Hindi-first, inside the console: home, coverage explainer, claim tracker, receipt, cover and help. Consent and grievance screens come with N5 and N6, Marathi with N8 | 1 | Omkar | BUILT · `n1_miniapp` | [fs-04](feature-specs/fs-04-merchant-mini-app.md) |
| N2 | Ask Chhatri grounded assistant | Text, Hindi and English. Answers coverage and claim questions from policy wording (clause citations) and the merchant's own decision facts | 2 | Ujjwal | BUILT · `n2_ask_chhatri` | [fs-05](feature-specs/fs-05-ask-chhatri.md) |
| N3 | Live slip reading with a pre-check | The reader chain (Gemini, then Sarvam) extracts slip fields. The pre-check shows what was read, and the merchant confirms before the checks run | 2 | Ujjwal | BUILT · `n3_slip_precheck` | [fs-02](feature-specs/fs-02-hospital-cash-claim.md) |
| N4 | Real Hindi voice | Sarvam speech-to-text and text-to-speech when keyed, browser speech as a fallback | 2 | Ujjwal | BUILT · `n4_voice` | [fs-05](feature-specs/fs-05-ask-chhatri.md) |
| N5 | Grievance ladder with response clocks | Insurer grievance officer, then IRDAI's Bima Bharosa portal, then the Insurance Ombudsman. A clock only where a source states one | 3 | Both | BUILT · `n5_grievances` | [fs-06](feature-specs/fs-06-explanations-disputes-and-grievance.md) |
| N6 | Consent centre | View, turn off and log purpose-specific consents (DPDP). "Erase this slip" (proposed label) | 3 | Both | BUILT · `n6_consents` | [fs-07](feature-specs/fs-07-cover-purchase-and-consent.md) |
| N7 | Public static demo and backup video | A mock-mode build of the console. The repo owner deploys it to a free static host, so no address exists yet. A recorded backup video | 5 | Omkar (build, video), Ujjwal (deploy) | BUILT (static build). Deploying it and the backup video are not done | [fs-08 §9.7](feature-specs/fs-08-claims-officer-console.md), [build plan](../06-delivery/build-plan.md) |
| N8 | Marathi (mini-app and Ask Chhatri) | A third language through the same message catalogue, after native review | 4 | Omkar | BUILT as a draft, behind `n8_marathi` | [fs-04](feature-specs/fs-04-merchant-mini-app.md), [fs-05](feature-specs/fs-05-ask-chhatri.md) |
| **Fixes (X)** | | | | | | |
| X1 | Fix the 2 failing frontend tests | Cases panel and Overview live map | 0 | Ujjwal | BUILT | [build plan](../06-delivery/build-plan.md) |
| X2 | Validate the expected day at claim creation | Use the published value rounded to ₹10 and reject an unpublished one | 1 | Ujjwal | BUILT | [fs-01](feature-specs/fs-01-area-auto-claim.md) |
| X3 | Fail loudly when a zone is missing from the price table | Raise an error. Do not fall back to the ₹2 a day floor | 1 | Ujjwal | BUILT | [fs-07](feature-specs/fs-07-cover-purchase-and-consent.md) |
| X4 | EDI-holiday request and guard | Chhatri requests, the simulated lender decides: flag on, loan active, not in arrears, allowance left. A refusal creates no pause. The wording says the lender decided | 1 | Ujjwal | BUILT · `x4_lender_request` | [fs-03](feature-specs/fs-03-edi-holiday.md) |
| X5 | A clean 404 for an unknown merchant | Return the standard `not_found` envelope, not an error trace | 1 | Ujjwal | BUILT | [fs-06](feature-specs/fs-06-explanations-disputes-and-grievance.md) |
| X6 | Provider panel with LIVE, SIMULATED and FALLBACK | A panel with a status for each component, and a demo switch that forces fallback | 2 | Ujjwal | BUILT · `x6_provider_panel` | [fs-08](feature-specs/fs-08-claims-officer-console.md) |
| X7 | Honest-wording test | Fails if a template promises, shows a money figure that is not in the decision facts, or says "paid" before a payout record exists | 1 | Ujjwal | BUILT | [fs-09](feature-specs/fs-09-policy-engine-and-audit.md) |
| X8 | No loan offers during distress, and a message cap | No loan, top-up or cross-sell message while an alert covers the zone or a claim or dispute is open. A daily cap on proactive messages, with payment confirmations and replies exempt | 3 | Ujjwal | BUILT · `x8_distress_guard` | [fs-03](feature-specs/fs-03-edi-holiday.md) |
| **Ideas from other teams (H)** | Credits are in the [competitive landscape §4](../01-strategy/competitive-landscape.md#4-feature-harvest-what-we-learned-and-adopted) | | | | | |
| H1 | Step-by-step tracker with state badges | N1 claim tracker: Detected → Checked → Decided → Paid → EDI holiday. Each step shows state, simulated time and a one-line reason, including the REFERRED and DISPUTE paths | 1 | Omkar | BUILT · `n1_miniapp` | [fs-04](feature-specs/fs-04-merchant-mini-app.md) |
| H2 | "Why this amount" with source badges | K5 card (BUILT) plus the N1 view: rule, numbers and source badges (sales index, alert, KYC, slip) | 1 | Omkar | BUILT (K5 card; N1 view behind `n1_miniapp`) | [fs-04](feature-specs/fs-04-merchant-mini-app.md), [fs-06](feature-specs/fs-06-explanations-disputes-and-grievance.md) |
| H3 | Payout receipt | N1 receipt: decision id, rules version, formula, sources, audit hash prefix, grievance path. Printable | 1 | Omkar | BUILT | [fs-04](feature-specs/fs-04-merchant-mini-app.md), [fs-09](feature-specs/fs-09-policy-engine-and-audit.md) |
| H4 | Honest-wording test | X7 (same) | 1 | Ujjwal | BUILT | [fs-09](feature-specs/fs-09-policy-engine-and-audit.md) |
| H5 | The merchant confirms what was read | N3: the merchant confirms the fields before the checks run. A three-line checklist (photo readable, name on the slip, dates on the slip) with PASS or WARN and no number | 2 | Ujjwal | BUILT · `n3_slip_precheck` | [fs-02](feature-specs/fs-02-hospital-cash-claim.md) |
| H6 | Zero-login public demo | N7 (same) | 5 | Omkar | BUILT (static build). Not deployed | [build plan](../06-delivery/build-plan.md) |
| H7 | Glass-box provider panel with a fallback switch | X6 (same) | 2 | Ujjwal | BUILT · `x6_provider_panel` | [fs-08](feature-specs/fs-08-claims-officer-console.md) |
| H8 | Real operational counts | K8 ops strip of five numbers counted from the database. No projections | 4 | Omkar | BUILT · `h8_ops_strip` | [fs-08](feature-specs/fs-08-claims-officer-console.md) |
| H9 | No loan offers in distress; a frequency cap | X8 (same) | 3 | Ujjwal | BUILT · `x8_distress_guard` | [fs-03](feature-specs/fs-03-edi-holiday.md) |
| H10 | Deterministic core; the model has no authority over money | K4 (done). The AI builds the case, and code decides the money | built | Ujjwal | BUILT | [fs-09](feature-specs/fs-09-policy-engine-and-audit.md) |
| H11 | Bilingual templates, not model translation | The Hindi and English catalogue (done). N8 adds Marathi | built, 4 | Omkar | BUILT (Hindi, English). Marathi is a draft behind `n8_marathi` | [fs-04](feature-specs/fs-04-merchant-mini-app.md) |
| H12 | Visible, measured test counts | README and pitch show measured counts and never round up. X1 clears the 2 failing tests first | 5 | Ujjwal | Not done: measured counts are written after the final run | [build plan](../06-delivery/build-plan.md) |
| H13 | Verified-by badges | Every rule, number and clause shown to a merchant or officer carries its source and time | 1 (console chips 4) | Both | BUILT | [fs-09](feature-specs/fs-09-policy-engine-and-audit.md), [fs-08](feature-specs/fs-08-claims-officer-console.md) |
| H14 | Counterfactual in every explanation | What would have changed the outcome, produced by the engine re-running its own rule | 1 (console 4) | Both | BUILT | [fs-09](feature-specs/fs-09-policy-engine-and-audit.md), [fs-08](feature-specs/fs-08-claims-officer-console.md) |
| H15 | Slip pre-check | Document class, slot checklist and a confidence gate ("ask, don't assume") | 2 | Ujjwal | BUILT · `n3_slip_precheck` | [fs-02](feature-specs/fs-02-hospital-cash-claim.md) |
| H16 | Prompt-injection defence | Text from slips and chat is wrapped and never obeyed. Red-team tests | 2 | Ujjwal | BUILT | [fs-05](feature-specs/fs-05-ask-chhatri.md), [fs-02](feature-specs/fs-02-hospital-cash-claim.md) |
| H17 | Clause citations in answers | N2 cites C1 to C12 chips. Every number comes from engine facts. A guard blocks unsupported numbers and promises | 2 | Ujjwal | BUILT · `n2_ask_chhatri` | [fs-05](feature-specs/fs-05-ask-chhatri.md) |
| H18 | Voice confirmation chips | Amounts and dates are confirmed before they are used | 2 | Both | BUILT · `n4_voice` | [fs-05](feature-specs/fs-05-ask-chhatri.md) |
| H19 | Scam-message warning | In chat: OTP requests, advance fees, "guaranteed claim", urgency, short links | 2 | Ujjwal | BUILT · `n2_ask_chhatri` | [fs-05](feature-specs/fs-05-ask-chhatri.md) |
| H20 | Jargon lens | Tap any insurance term for a plain explanation with an example | 1 | Omkar | BUILT · `n1_miniapp` | [fs-04](feature-specs/fs-04-merchant-mini-app.md) |
| H21 | Next-best-action bar | Every screen and every chat reply ends with a clear next step | 1 (chat replies 2) | Omkar | BUILT · `n1_miniapp` | [fs-04](feature-specs/fs-04-merchant-mini-app.md), [fs-05](feature-specs/fs-05-ask-chhatri.md) |
| H22 | Grievance ladder with response clocks and a respondent router | Who owns this complaint: Paytm, the insurer or the lender | 3 | Both | BUILT · `n5_grievances` | [fs-06](feature-specs/fs-06-explanations-disputes-and-grievance.md) |
| H23 | Consent activity log and "forget my slip" | What was used, for what and when. Erase a slip on request | 3 | Both | BUILT · `n6_consents` | [fs-07](feature-specs/fs-07-cover-purchase-and-consent.md) |
| H24 | What-if panel for judges | Change the alert, the hourly indices or the shop count and watch the real trigger rule recompute. Read-only | 4 | Both | BUILT · `h24_whatif` | [fs-08](feature-specs/fs-08-claims-officer-console.md) |
| H25 | Published AI evaluation | Intent accuracy, the guard's red-team block rate and slip-field accuracy on synthetic labelled data. Shown only once measured | 3 | Ujjwal | BUILT (offline harness and page, behind `h25_evals`). No run is stored | [AI evaluation plan](../04-engineering/ai-evaluation-plan.md) |
| H26 | Mode, provider and reason on every AI reply | LIVE, SIMULATED or FALLBACK, the provider and the fallback reason | 2 | Ujjwal | BUILT | [fs-05](feature-specs/fs-05-ask-chhatri.md), [fs-08](feature-specs/fs-08-claims-officer-console.md) |

### 3.3 Waves and flags

Everything is P0, so we do not cut scope. We build in waves, each closed at a checkpoint with written pass criteria. Every new feature sits behind a flag that starts off. A feature that is not finished at its checkpoint is hidden, never shown half-working. If time runs out, features are hidden in a fixed order ([build plan §7](../06-delivery/build-plan.md#7-hide-order-if-time-runs-out)).

| Wave | Goal | Flags that turn on |
|---|---|---|
| 0 setup | Everything later waves stand on. Nothing visible turns on | none |
| 1 demo spine | Anil's story end to end in the mini-app: home, tracker, receipt, cover. The lender request and its wording | `n1_miniapp`, `x4_lender_request` |
| 2 live AI | Slip pre-check, Ask Chhatri, voice, and the labels that make live AI honest | `n3_slip_precheck`, `n2_ask_chhatri`, `n4_voice`, `x6_provider_panel` |
| 3 trust and rights | Grievances, consent, the distress guard, the evaluation harness | `n5_grievances`, `n6_consents`, `x8_distress_guard`, `h25_evals` |
| 4 judge wow | Console polish, the trigger-to-payout moment, what-if, presenter mode, ops strip, Marathi | `h24_whatif`, `h8_ops_strip`, `console_polish`, `n8_marathi` |
| 5 ship | Static build, backup video, full test run, two rehearsals, freeze | the demo flag set is fixed |

---

## 4. Functional requirements

Each requirement names its feature, status and wave. Acceptance values come from the golden demo ([DEMO.md](../DEMO.md)) and the code. Where a quoted message is not in the catalogue yet, it is marked "proposed".

### 4.1 Area auto-claim (K1, BUILT)

**FR-area-001:** Fire the trigger when a zone's hourly sales index stays below 50% for 3 consecutive hours, below the model's conformal lower bound, with at least 20 shops in the index and an alert that covers the zone for the whole window.

- *Acceptance criteria:*
  - Given: alert A-20250818-01 is valid 14:00–20:00, Z7 sits at 37% for 3 hours, 46 shops are in the index and no claim exists.
  - When: the trigger check runs at 17:00.
  - Then: the trigger fires for Z7. Anil's decision is APPROVED for ₹1,380 and every check PASSES.

**FR-area-002:** Pay each insured shop ½ × its own expected day × the drop %, capped at ₹2,500 a day.

- *Acceptance criteria:*
  - Given: expected day ₹4,380, drop 63%.
  - When: the area amount is computed.
  - Then: ½ × ₹4,380 × 63% = ₹1,379.70, rounded to ₹1,380. The cap does not bind.

**FR-area-003:** Pay every insured shop in a triggered zone at the trigger time. The credit lands 4 simulated minutes later with the settlement.

- *Acceptance criteria:*
  - Given: Z3, Z7 and Z12 trigger at 17:00 simulated, with 312 covered shops (46 + 141 + 125).
  - When: the settlement posts.
  - Then: all 312 are credited at 17:04 simulated (`payout_rail_delay_minutes: 4` in `rules.yaml`).

### 4.2 Hospital-cash claim (K2, BUILT)

**FR-personal-001:** After a full business day with no sales, reach out first. Sales outside business hours do not count.

- *Acceptance criteria:*
  - Given: Anil's shop had no sales during business hours on Wednesday 20 Aug.
  - When: the outreach round runs at 11:20 on Thursday 21 Aug.
  - Then: Chhatri sends "अनिल जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है?" (*Your shop has been closed since yesterday. Is everything okay?*), as in DEMO.md.

**FR-personal-002:** Accept one hospital slip photo and read the patient name, the admission date and the hospital.

- *Acceptance criteria:*
  - Given: Anil sends `anil_admission_slip.png` (patient "Anil R. Jadhav", admitted 2025-08-20, KEM Hospital).
  - When: the slip reader reads it. It is Sarvam Vision when `SARVAM_API_KEY` is set and a labelled simulator otherwise. With `n3_slip_precheck` on, the Gemini reader heads the chain (tested against fakes only).
  - Then: it returns the name, the admission date, the hospital and a confidence of at least 0.80 for the sample slip.

**FR-personal-003:** The name on the slip must match the KYC name with a score of 85 or more. This is a SOFT check.

- *Acceptance criteria:*
  - Given: slip name "Anil R. Jadhav", KYC name "ANIL RAMESH JADHAV".
  - When: `name_match_score` runs. It uppercases, expands a single-letter initial when exactly one KYC token starts with it, and takes `rapidfuzz.fuzz.token_set_ratio`.
  - Then: the score is 100 and the check passes. For "Sunil Pawar" the score is 28 and the check fails.

**FR-personal-004:** Pay ½ × the usual day, capped at ₹1,500 a day, for up to 3 days automatically.

- *Acceptance criteria:*
  - Given: usual Wednesday ₹4,300, one silent day.
  - When: the personal amount is computed.
  - Then: ½ × ₹4,300 = ₹2,150 a day, capped at ₹1,500 × 1 day = ₹1,500.

**FR-personal-005:** A failed SOFT check, or an unsure read, sends the claim to a person (REFERRED). A failed HARD check is DECLINED.

- *Acceptance criteria:*
  - Given: slip name "Sunil Pawar", KYC name "ANIL RAMESH JADHAV" (score 28, below 85).
  - When: the policy engine evaluates the claim.
  - Then: the outcome is REFERRED, ₹1,500 is computed and not paid, and case C-2291 opens (the first case after a fresh load). Anil gets "धन्यवाद। पर्ची पर नाम आपके KYC से मेल नहीं खा रहा, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।", as in DEMO.md. An officer then approves, which re-runs every HARD check and pays ₹1,500, or declines.

### 4.3 EDI holiday (K3 BUILT as a pause; X4 BUILT behind `x4_lender_request`)

With the flag off the instalment step pauses the next instalment with no check, and the message reads as if Chhatri did it. The requirements below are the X4 behaviour with the flag on ([fs-03](feature-specs/fs-03-edi-holiday.md)).

**FR-edi-001:** After a payout is credited, send the lender an EDI-holiday request that quotes the decision id.

- *Acceptance criteria:*
  - Given: Anil's decision is APPROVED at 17:00 and credited at 17:04.
  - When: the request step runs at 17:05 simulated.
  - Then: a request carrying the decision id goes to the simulated lender, and the audit log records it. The payout is not affected by the answer.

**FR-edi-002:** The lender applies its own pre-agreed rule: the programme flag is on, the loan is active, the loan is not in arrears and the holiday allowance is not used up. All four must hold for a grant.

- *Acceptance criteria:*
  - Given: Anil's loan is active, with no arrears and allowance left.
  - When: the simulated lender evaluates the request.
  - Then: it grants, and the ₹600 instalment moves to the end of the loan with no penalty. If one condition fails, the lender refuses with a reason and no pause is created.

**FR-edi-003:** Tell the merchant what the lender decided.

- *Acceptance criteria:*
  - Given: the lender granted at 17:05.
  - When: the message is posted.
  - Then: Anil reads the lender-decides wording: "Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty." A refusal reads that the lender could not pause it, gives the reason, says the instalment is due as usual and that the payout is not affected (`HOLIDAY_REFUSED`).

### 4.4 Policy engine and payout authority (K4, BUILT)

**FR-policy-001:** The policy engine is the only layer that can produce an APPROVED decision.

- *Acceptance criteria:*
  - Given: a claim and its facts.
  - When: the engine evaluates.
  - Then: an APPROVED decision can come only from `evaluate_area_claim`, `evaluate_personal_claim` or an officer approval that re-runs every HARD check. No model output sets an amount or approves.

**FR-policy-002:** Every money figure shown to a merchant can be reproduced from the formula shown next to it.

- *Acceptance criteria:*
  - Given: decision amount ₹1,380, formula "½ × ₹4,380 × 63% = ₹1,380".
  - When: the merchant views the card.
  - Then: the numbers come from the decision's own explanation (expected day, drop, share, cap) and are not generated freely.

### 4.5 Explanations and disputes (K5, BUILT)

**FR-explain-001:** Answer "why this amount" with the formula, from a voice chip. Free questions come with N2 (`n2_ask_chhatri`).

- *Acceptance criteria:*
  - Given: Anil's ₹1,380 payout.
  - When: Anil taps "why" and says "मुझे इतने ही पैसे क्यों मिले?"
  - Then: the reply is "आपका आम मंगलवार: ₹4,380। आज आपके इलाके की बिक्री 63% गिरी। छतरी खोई हुई बिक्री का आधा देती है।", as in DEMO.md. After a personal payout the reply shows that claim's formula.

**FR-explain-002:** A dispute opens a case with a 24 h clock. A person confirms the payout or rejects the dispute. The amount never changes.

- *Acceptance criteria:*
  - Given: Anil taps "dispute" and says "मेरा नुकसान ज़्यादा हुआ।"
  - When: the case opens.
  - Then: the reply says the team will answer within 24 hours, the chip reads "Sent to a claims officer · case C-2291", and the case is OPEN with a 24 h clock and the original decision as evidence. The officer confirms the payout or rejects the dispute, and then the case is CLOSED.

### 4.6 Cover purchase with waiting period (K6, BUILT)

**FR-cover-001:** Cover for a day starts only when that day's premium has been received (cash before cover, the design behind Insurance Act s.64VB, to be confirmed with the insurer's compliance team).

- *Acceptance criteria:*
  - Given: Ramesh (Z3) pays the 30-day link of ₹424.80 on 18 Aug.
  - When: the payment is received.
  - Then: `prepaid_through` is 17 Sep and the cover starts on 25 Aug, 7 days after the request.

**FR-cover-002:** Quote BLOCKED when an alert for the zone is valid now, or was issued and starts within 72 hours. The payment link is still offered, for cover from the later date. A new cover always starts 7 days after the request, whatever the answer.

- *Acceptance criteria:*
  - Given: Ramesh asks for cover on 18 Aug at 18:00, and alert A-20250818-01 was issued at 17:30 and is valid 14:00–20:00 on 19 Aug.
  - When: the policy engine quotes the purchase.
  - Then: the outcome is BLOCKED, and the reply is "नया कवर वेटिंग पीरियड के बाद शुरू होता है — 25 अगस्त से। कल के अलर्ट पर यह लागू नहीं होगा।", as in DEMO.md. The link follows.

### 4.7 Ask Chhatri grounded assistant (N2, BUILT behind `n2_ask_chhatri`)

A guard for free-text replies (`conversation/guard.py`) is the base. N2 builds the answer path on it ([fs-05](feature-specs/fs-05-ask-chhatri.md)).

**FR-ask-001:** Answer coverage and claim questions in Hindi and English, grounded only in policy wording (C1 to C12) and the merchant's own records.

- *Acceptance criteria:*
  - Given: the question "क्या अस्पताल का खर्च भी मिलेगा?" (*Will hospital bills be covered?*).
  - When: N2 receives it.
  - Then: the answer cites C3 (hospital cash, not hospital bills) and explains the difference.

**FR-ask-002:** Fallback chain: Gemini free tier, then Sarvam chat, then a deterministic template. A provider that times out hands over to the next.

- *Acceptance criteria:*
  - Given: the Gemini free-tier limit is reached.
  - When: N2 tries Gemini.
  - Then: it falls back to Sarvam, and if Sarvam also fails it uses a template with a handoff to a person (proposed wording: "I don't have enough information to answer this. A team member will help you."). Every reply carries its mode, provider and fallback reason (H26).

**FR-ask-003:** Guard: no money figure that is not in the decision facts, and no promise.

- *Acceptance criteria:*
  - Given: a model output "Your claim of ₹2,000 is guaranteed to be approved."
  - When: the guard checks it.
  - Then: the output is rejected and the template is used.

### 4.8 Live slip reading and pre-check (N3, BUILT behind `n3_slip_precheck`)

**FR-slip-001:** Read the slip, show the merchant what was read and a three-line checklist, and ask the merchant to confirm before the checks run. The pre-check never decides and never shows a name-against-KYC match.

- *Acceptance criteria:*
  - Given: an uploaded slip photo.
  - When: the pre-check runs.
  - Then: the screen shows the fields read, a checklist of "The photo could be read", "The name is on the slip" and "The admission date is on the slip" (proposed wording, PASS or WARN, no number), and the actions "Yes, this is right" or another photo ([fs-02 §7.3](feature-specs/fs-02-hospital-cash-claim.md)).

**FR-slip-002:** A read with confidence below 0.80, or a document that is not a hospital document, is handed back for another photo, with one reason.

- *Acceptance criteria:*
  - Given: a blurry photo with confidence 0.6.
  - When: the pre-check gate runs.
  - Then: the merchant is asked to retake it, up to 3 photos per check-in (proposed limit), and then the claim goes to the team. A clear photo with confidence 0.92 passes the gate and waits for the merchant's confirmation.

### 4.9 Real Hindi voice (N4, BUILT behind `n4_voice`)

**FR-voice-001:** Speech to text: Sarvam when keyed, browser speech as a fallback.

- *Acceptance criteria:*
  - Given: Anil speaks "मैं अस्पताल में हूँ।"
  - When: speech to text runs.
  - Then: the transcript resolves to the "ill" intent, and an amount or date is confirmed with a chip before use (H18). Transcription accuracy is measured (H25), not promised.

**FR-voice-002:** Text to speech: Sarvam when keyed, browser speech as a fallback.

- *Acceptance criteria:*
  - Given: the message "Paytm par ₹1,380 prapt hue — Chhatri se".
  - When: text to speech runs.
  - Then: it is spoken in Hindi and is audible on the demo laptop.

### 4.10 Merchant mini-app (N1, BUILT behind `n1_miniapp`)

**FR-mini-001:** Home answers "am I covered, what is happening, what next?"

- *Acceptance criteria:*
  - Given: Anil's active cover in Z7.
  - When: the mini-app opens.
  - Then: the cover card shows a status sentence, "paid through {date}" and the amount used of the annual limit in the last 365 days. The expected-day line, the latest claim card and the shortcuts follow ([fs-04](feature-specs/fs-04-merchant-mini-app.md)).

**FR-mini-002:** Coverage explainer: what am I covered for, with examples, exclusions, the waiting period and caps, and a jargon lens (H20).

- *Acceptance criteria:*
  - Given: the merchant taps "What am I covered for?"
  - When: the explainer loads.
  - Then: it covers area income loss (an alert plus a sales drop), hospital cash (a silent day plus a slip), the caps (₹2,500 a day for area, ₹1,500 a day for hospital cash, ₹30,000 in any rolling 365 days), exclusions, the 7-day waiting period and the EDI holiday (a request the lender decides). Text follows policy clauses C1 to C12.

**FR-mini-003:** Buy flow: the quote (OK or BLOCKED with the reason), the start date, and a payment link. With `n6_consents` on, three consent switches come first.

- *Acceptance criteria:*
  - Given: the merchant taps "Get cover".
  - When: the quote screen loads.
  - Then: it shows OK or BLOCKED with the reason, a start date 7 days after the request, and a payment link labelled SIMULATED unless Paytm staging keys are set.

**FR-mini-004:** Claim tracker: Detected → Checked → Decided → Paid → EDI holiday, including the REFERRED and DISPUTE paths (H1).

- *Acceptance criteria:*
  - Given: Anil's area claim in the replay.
  - When: the tracker loads after 17:05.
  - Then: each step shows its state, its simulated time and a one-line reason. Detected, Checked and Decided read 17:00, Paid reads 17:04 and EDI holiday reads 17:05. The Paid and EDI holiday steps carry the SIMULATED label for the payout rail and the lender.

**FR-mini-005:** Help and grievance: ask a question (N2), dispute a decision, escalate (N5).

- *Acceptance criteria:*
  - Given: Anil opens "Help".
  - When: the screen loads.
  - Then: it offers "Ask a question" (shown with `n2_ask_chhatri`), "Dispute this decision" (opens a case with a 24 h clock) and the escalation ladder (shown with `n5_grievances`). A row whose flag is off is absent.

---

## 5. Non-functional requirements

### 5.1 Targets

Every number here is a target. We measure it in rehearsal and report what we measure.

- **Ask Chhatri (N2) answer time:** target 5 seconds or less. Templates are instant.
- **Slip reading (N3) time:** target 10 seconds or less.
- **Area claim decision:** the engine is pure code. `make demo-check` rehearses all 70 checks in about 10 seconds in-process ([DEMO.md](../DEMO.md)), and we set no separate latency target.
- **Payout credit:** 4 simulated minutes after the decision (`payout_rail_delay_minutes: 4`). Real timing depends on the settlement rail and is not measured by us.

### 5.2 Demo reliability

- **`make demo-check` passes 70 of 70** before the final.
- **Reset:** reload the scenario (`POST /api/replay/load`). It is deterministic ([DEMO.md](../DEMO.md)).
- **Fallbacks:** each AI component is labelled LIVE, SIMULATED or FALLBACK (X6, `x6_provider_panel`). A failed provider hands over to the next: Gemini, Sarvam, then templates for N2, a person for N3, and tap chips for N4.
- **Hide order:** an unfinished feature is hidden by its flag, in the order in [build plan §7](../06-delivery/build-plan.md#7-hide-order-if-time-runs-out).

### 5.3 Accessibility

Target: WCAG 2.2 AA for the mini-app ([design system](../03-design/design-system.md), [fs-04 §16.3](feature-specs/fs-04-merchant-mini-app.md)).

- **Touch targets:** 44 px in the mini-app, 48 px for the main button of a screen.
- **Contrast:** 4.5:1 for text, 3:1 for lines, icons and focus rings.
- **Keyboard:** every interactive element is reachable with Tab, Shift+Tab and Enter.
- **Screen reader:** labels on dynamic content such as chat and the live-map hexagons.
- **Motion:** animations respect `prefers-reduced-motion` (BUILT in the console CSS).
- **Checks:** the jsx-a11y lint rules run in `npm run lint`, `frontend/src/contrast.test.ts` computes the contrast of the console tokens, and an e2e test walks the tabs with the keyboard. There is no automated axe-style screen scan and no screen-reader review.

### 5.4 Security

See [SECURITY.md](../SECURITY.md) for the full list. In short:

- **Money path:** the policy engine is the only code that returns APPROVED. A free-text reply passes only if every number is a decision fact and it promises no money or approval.
- **Officer actions** need a bearer token, compared in constant time.
- **Uploads** are type-checked by magic bytes and size-limited. Webhooks, uploads and phone messages are rate-limited in memory, per process.
- **Keys** never reach the browser and are never logged.
- **Data:** only synthetic data goes to free-tier AI services ([ADR 0009](../04-engineering/adr/0009-synthetic-data-only-to-free-tier-ai.md)).

### 5.5 Internationalisation

- **BUILT:** Hindi (Devanagari) and English, from the message catalogue `backend/chhatri/conversation/messages.py`. It is the single source, and no model translates.
- **BUILT as a draft:** Marathi (N8, `n8_marathi`) for the mini-app text, until a native speaker reviews it. The backend catalogue messages have no Marathi and show in Hindi.
- **Number format:** Indian rupees (₹) with grouping commas, for example ₹1,380.
- **Voice:** Hindi and English through Sarvam when keyed, with browser speech as a fallback (N4, `n4_voice`). There is no Marathi voice.

### 5.6 Observability and audit

- **Audit log:** every payout, claim, case, dispute and officer decision is an `AuditEntry` in a hash chain. `GET /api/audit/verify` checks the chain.
- **Ops strip (H8, BUILT behind `h8_ops_strip`):** open cases by state, the oldest SLA clock, the share decided automatically and by a person, and today's payouts by zone, counted from the database.
- **Errors:** logged with merchant id, action and time on the server, and never shown to the merchant.
- **SLA clocks:** dispute and grievance clocks are tracked per case and shown in the UI (N1 tracker, N5 ladder).

---

## 6. Dependencies

### 6.1 Free AI accounts

- **Google AI Studio:** the Gemini API free tier (Flash models, rate-limited). Free-tier content may be used to improve Google products, so we send only synthetic demo data (A19, ADR 0009).
- **Sarvam AI:** free starter credits (the amount is not published, so check before the final). Used for speech to text, text to speech, chat and Sarvam Vision. Without a key the adapters are labelled simulators.
- **Tesseract OCR:** a later option for slip reading, with a Hindi model. It is not in the code and not in the reader chain.

### 6.2 Integrations (simulated and labelled)

- **Paytm payment link:** SIMULATED (`https://paytm.me/sim-…`) unless Paytm staging keys are set. The team has none.
- **Paytm settlement and the lender:** SIMULATED. There is no live access.
- **WhatsApp Cloud API:** SIMULATED by the in-console phone. The team has no WhatsApp keys.
- **n8n workflows:** the recommended stage set-up is the in-process runner, and the n8n badge then reads SIMULATED ([DEMO.md](../DEMO.md)).
- **Open-Meteo rainfall:** real rainfall cached in `backend/data/weather/`. The replay and the backtest never call the network. A live call serves only the rain widget when `OPENMETEO_LIVE=true`.

---

## 7. Release plan

All six waves are built in the code (3 Oct). Not done, and human-only: the backup video, deploying the static build, the rehearsals and the freeze. No checkpoint log is kept in the repository.

There are no clock times here. The slot time and length are not announced, so the freeze, which is 90 minutes before our slot, is worked out when the slot is known ([build plan §8](../06-delivery/build-plan.md)).

| Wave | What lands | Closes at |
|---|---|---|
| 0 setup | X1, the flag registry, the scoped Tailwind v4 and shadcn set-up, the key check for Gemini and Sarvam. Built | CP0 |
| 1 demo spine | N1 core (home, coverage explainer, claim tracker, receipt, cover), H1 to H3, H13, H14, H20, H21, X2, X3, X4, X5, X7 | CP1 |
| 2 live AI | N3 with H15 and H16, N2 with H17 and H19, N4 with H18, X6 with H26 | CP2 |
| 3 trust and rights | N5 with H22, N6 with H23, X8, the H25 evaluation harness | CP3 |
| 4 judge wow | Console polish and the trigger-to-payout moment, H24, presenter mode, H8, N8 | CP4 |
| 5 ship | N7 static build and backup video, the full test run, `make demo-check`, two rehearsals, the freeze | CP5 |

Owners: Omkar builds the mini-app, console, design, copy and pitch. Ujjwal builds the backend, engine, AI adapters and evals. The person who did not write the work runs each checkpoint.

**Freeze policy.** Code freezes 90 minutes before our slot, and only a hotfix for a demo crash goes in after that. Development stays on main with commits only. The repo owner decides when to publish, and N7 needs that step.

---

## 8. Success metrics and pass criteria

See [Metrics and impact](metrics-and-impact.md) for the full framework.

**Demo pass criteria:**
- The three live tests (EXPLAINED, HUMAN, BLOCKED) complete without errors.
- No unsupported money figure appears in Ask Chhatri output.
- Every decision explanation can be reproduced from the numbers shown.
- The credit lands 4 simulated minutes after the decision.
- Every merchant-facing template passes the honest-wording test (X7).

**Pilot targets (post-hackathon, none measured):**
- Test coverage stays at or above the 80% gate.
- Ask Chhatri grounded-answer rate of at least 95% on the evaluation set, and slip-field accuracy of at least 90% on a labelled sample (the targets in Metrics and impact).
- Disputes answered within 24 hours, our own aim.
- The other pilot targets, including lender acceptance of EDI holidays, are in Metrics and impact.

---

## 9. Traceability: FR to feature spec to test

The tests are files and functions that exist in the repository. The whole-statement view is the [requirements traceability matrix](../01-strategy/requirements-traceability-matrix.md). A frontend file name without a folder is under `frontend/src/miniapp/screens/`.

| FR ID | Feature spec | Tests | Status |
|---|---|---|---|
| FR-area-001 | [fs-01](feature-specs/fs-01-area-auto-claim.md) (K1) | `backend/tests/detect/test_triggers.py`: `test_seventeen_hundred` | BUILT |
| FR-area-002 | [fs-01](feature-specs/fs-01-area-auto-claim.md) (K1) | `backend/tests/policy/test_amounts.py`: `test_area_deck_example_1380` | BUILT |
| FR-area-003 | [fs-01](feature-specs/fs-01-area-auto-claim.md) (K1) | `backend/tests/replay/test_area_flow.py`: `test_payouts_are_executed_at_17_00_and_credited_at_17_04` | BUILT |
| FR-personal-001 | [fs-02](feature-specs/fs-02-hospital-cash-claim.md) (K2) | `backend/tests/detect/test_silent.py`: `test_closed_shop_is_silent` | BUILT |
| FR-personal-002 | [fs-02](feature-specs/fs-02-hospital-cash-claim.md) (K2, N3) | `backend/tests/integrations/test_sarvam_docai.py`<br>`backend/tests/integrations/test_slip_chain.py`, `test_gemini_vision.py` | BUILT (Sarvam reader; the Gemini reader is tested against fakes only) |
| FR-personal-003 | [fs-02](feature-specs/fs-02-hospital-cash-claim.md) (K2) | `backend/tests/policy/test_names.py`: `test_spec_pairs`, `test_initial_expands_to_full_score` | BUILT |
| FR-personal-004 | [fs-02](feature-specs/fs-02-hospital-cash-claim.md) (K2) | `backend/tests/policy/test_amounts.py`: `test_personal_deck_example_1500` | BUILT |
| FR-personal-005 | [fs-02](feature-specs/fs-02-hospital-cash-claim.md) (K2) | `backend/tests/policy/test_engine.py`: `test_personal_name_mismatch_referred_with_amount_and_explanation`<br>`backend/tests/conversation/test_live_tests.py`: `test_human_slip_with_a_different_name_is_referred_and_paid_only_after_the_officer` | BUILT |
| FR-edi-001 | [fs-03](feature-specs/fs-03-edi-holiday.md) (K3, X4) | `backend/tests/ledger/test_instalments.py`: `test_pauses_tomorrows_instalment` (the pause)<br>`backend/tests/integrations/test_lender.py` (the request) | K3 BUILT as a pause. The request is BUILT behind `x4_lender_request` |
| FR-edi-002 | [fs-03](feature-specs/fs-03-edi-holiday.md) (X4) | `backend/tests/integrations/test_lender.py`<br>`frontend/src/mock/lender.test.ts` | BUILT behind `x4_lender_request` |
| FR-edi-003 | [fs-03](feature-specs/fs-03-edi-holiday.md) (X4) | `backend/tests/conversation/test_notifications.py`: `test_instalment_wording_follows_the_date`<br>`frontend/tests/e2e/human-miniapp-lender.spec.ts` | BUILT behind `x4_lender_request` |
| FR-policy-001 | [fs-09](feature-specs/fs-09-policy-engine-and-audit.md) (K4) | `backend/tests/policy/test_engine.py`: `test_engine_is_deterministic`, `test_payout_authority_table` | BUILT |
| FR-policy-002 | [fs-09](feature-specs/fs-09-policy-engine-and-audit.md) (K4, K5) | `backend/tests/policy/test_explain.py`: `test_formulas_equal_spec_literals_character_for_character`<br>`backend/tests/conversation/test_honest_wording.py` (X7) | BUILT |
| FR-explain-001 | [fs-06](feature-specs/fs-06-explanations-disputes-and-grievance.md) (K5) | `backend/tests/conversation/test_live_tests.py`: `test_explained_why_then_dispute_opens_c2291`<br>`backend/tests/conversation/test_replies.py`: `test_why_after_a_personal_payout_shows_the_formula`<br>`backend/tests/ask/test_ask_service.py` (free questions) | BUILT. Free questions behind `n2_ask_chhatri` |
| FR-explain-002 | [fs-06](feature-specs/fs-06-explanations-disputes-and-grievance.md) (K5) | `backend/tests/cases/test_service.py`: `test_first_case_is_c2291_with_sla`<br>`backend/tests/replay/test_dispute_cover.py`: `test_explained_numbers_then_a_dispute_case_c_2291` | BUILT |
| FR-cover-001 | [fs-07](feature-specs/fs-07-cover-purchase-and-consent.md) (K6) | `backend/tests/ledger/test_premiums.py`: `test_mark_paid_creates_waiting_cover` | BUILT |
| FR-cover-002 | [fs-07](feature-specs/fs-07-cover-purchase-and-consent.md) (K6) | `backend/tests/policy/test_cover.py`: `test_ramesh_blocked_by_red_alert`, `test_alert_valid_now_blocks` | BUILT |
| FR-ask-001 | [fs-05](feature-specs/fs-05-ask-chhatri.md) (N2) | `backend/tests/ask/test_ask_service.py`, `backend/tests/ask/test_clauses.py`<br>`Ask.test.tsx` | BUILT behind `n2_ask_chhatri` |
| FR-ask-002 | [fs-05](feature-specs/fs-05-ask-chhatri.md) (N2) | `backend/tests/ask/test_fact_sheet.py`, `backend/tests/ask/test_injection.py`, `backend/tests/ask/test_scam.py` | BUILT behind `n2_ask_chhatri` |
| FR-ask-003 | [fs-05](feature-specs/fs-05-ask-chhatri.md) (N2) | `backend/tests/conversation/test_guard.py`: `test_ungrounded_numbers_fail`, `test_money_or_approval_promises_fail`<br>`backend/tests/conversation/test_guard_strict.py` | BUILT |
| FR-slip-001 | [fs-02](feature-specs/fs-02-hospital-cash-claim.md) (N3) | `backend/tests/replay/test_slip_precheck.py`, `backend/tests/api/test_slip_precheck_api.py`<br>`SlipPrecheck.test.tsx` | BUILT behind `n3_slip_precheck` |
| FR-slip-002 | [fs-02](feature-specs/fs-02-hospital-cash-claim.md) (N3) | `backend/tests/conversation/test_slip_flow.py`: `test_reader_failure_goes_to_a_human`<br>`backend/tests/precheck/test_untrusted_slip_text.py` | BUILT |
| FR-voice-001 | [fs-05](feature-specs/fs-05-ask-chhatri.md) (N4) | `backend/tests/ask/test_voice_service.py`, `backend/tests/api/test_voice.py` | BUILT behind `n4_voice` |
| FR-voice-002 | [fs-05](feature-specs/fs-05-ask-chhatri.md) (N4) | `backend/tests/ask/test_mentions.py`<br>`frontend/src/miniapp/components/voiceMentions.test.ts`<br>`frontend/tests/e2e/human-miniapp-voice.spec.ts` | BUILT behind `n4_voice` |
| FR-mini-001 | [fs-04](feature-specs/fs-04-merchant-mini-app.md) (N1) | `Home.test.tsx`<br>`backend/tests/api/test_cover_route.py` | BUILT behind `n1_miniapp` |
| FR-mini-002 | [fs-04](feature-specs/fs-04-merchant-mini-app.md) (N1) | `Coverage.test.tsx`<br>`frontend/src/miniapp/components/JargonSheet.test.tsx` | BUILT behind `n1_miniapp` |
| FR-mini-003 | [fs-04](feature-specs/fs-04-merchant-mini-app.md) (N1) | `Buy.test.tsx`<br>`backend/tests/api/test_consent_gates.py` (consent switches) | BUILT behind `n1_miniapp` (consent switches behind `n6_consents`) |
| FR-mini-004 | [fs-04](feature-specs/fs-04-merchant-mini-app.md) (N1) | `ClaimDetail.test.tsx`<br>`backend/tests/replay/test_view_claims.py`<br>`frontend/src/components/phone/whatHappened.test.tsx` (the console strip) | BUILT behind `n1_miniapp` |
| FR-mini-005 | [fs-04](feature-specs/fs-04-merchant-mini-app.md) (N1) | `Help.test.tsx`<br>`Grievances.test.tsx`<br>`backend/tests/api/test_grievances.py` | BUILT behind `n1_miniapp` (ladder behind `n5_grievances`) |

---

## 10. Out of scope

- Multi-branch chains, aggregators and corporate merchants (scope: one shop, 1–3 staff).
- Family health insurance and treatment claims (scope: income loss during hospitalisation).
- Loan origination and a lending marketplace (scope: existing merchant loans).
- EDI restructuring or permanent changes (scope: the lender's decision under its policy).
- Proactive settlement and instant bank transfers (scope: the settlement rail only).
- Multi-document claims (scope: one slip per claim).
- Merchant acquisition and signups (scope: assumes Paytm for Business adoption).
- Insurance product design and underwriting (scope: the insurer partner's role).

---

## Open questions

1. **Which free static host will the repo owner use for N7?** GitHub Pages or any free static host. Until the owner deploys, no document carries an address. Owner: Ujjwal Pardeshi.
2. **Slot time and length are not announced.** Both demo cuts stay ready ([demo runbook](../06-delivery/demo-runbook.md)), and the freeze time is worked out when the slot is known. Owner: Omkar Kadam.
3. **Hospital-cash price:** the premium covers area claims only. How should hospital cash be priced and loaded with a partner insurer? Owner: Omkar Kadam.
4. **Policy wording examples:** the C3 example in [policy wording](policy-wording-and-cis.md) quotes a 92% name match for the demo slip. The code scores that pair at 100. Which number should the wording show? Owner: Omkar Kadam.

## Changelog

- 2026-10-03 · v1.6 · statuses brought up to the code: every N, X and H item is BUILT behind its flag (N7 and H6 not deployed, H12 not done, Marathi a draft); the traceability table lists real tests; a Marathi voice is not built
- 2026-10-02 · v1.5 · scope table now has a legend, build waves and specs, with every item P0, and rows for H13 to H26; fixed the hospital-cash rules (a failed SOFT check or an unsure read is REFERRED, a failed HARD check is DECLINED, the real name scores, the 11:20 outreach), the EDI requirements (X4 design, with today's unconditional pause stated), the cover rules (BLOCKED means an alert valid now or starting within 72 hours), the slip pre-check checklist, the area acceptance values and the mini-app tracker times; removed unsourced numbers and claims (segment size, repudiation rate for merchant plans, "all endpoints rate-limited", a reset flag, the Open-Meteo live call, Tesseract in the chain, N10); release plan is by wave with no clock times; section 9 links the real specs and names real tests; open questions refreshed
- 2026-10-02 · v1.4 · second fact-check pass: remove invented latency and rate-limit numbers, remove demo slot times and confirmed freeze times
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.1 · fact-check pass: clarify annual limit IS implemented as HARD check WITHIN_ANNUAL_LIMIT (DECLINED, not REFERRED, not X8); delete answered open question
- 2026-10-02 · v1 · first draft, with 29 FRs across K, N, and X features; scope table; traceability.
