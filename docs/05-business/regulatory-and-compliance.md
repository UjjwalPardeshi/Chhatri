# Regulatory and compliance

| | |
|---|---|
| Status | Draft v2.2 · 3 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Insurer partners, lender partners, compliance counsel, regulators |
| Related | [Facts and sources](../01-strategy/facts-and-sources.md) · [Policy wording](../02-product/policy-wording-and-cis.md) · [Business model](business-model-and-unit-economics.md) · [Go-to-market and pilot plan](go-to-market-and-pilot-plan.md) |

## TL;DR

- **Disclaimer:** This document is not legal advice. All regulatory positions must be confirmed with the partner insurer's compliance team and counsel.
- **Roles:** A partner general insurer underwrites. Paytm Insurance Broking (IRDAI-licensed broker, A4) distributes. Paytm does not underwrite.
- **Core framework:** s.64VB (cash before cover), parametric product filing, zero-document area claims, one-document hospital-cash claims with human review for doubt, 24-hour dispute SLA.
- **Lending:** RBI (Digital Lending) Directions 2025 (A25) apply. EDI holidays are the lender's decision, requested by Chhatri. The lender defers the instalment to the loan's end; or alternatively, the insurer funds it from the payout.
- **Data protection:** DPDP Act and Rules 2025 (A22) apply. Substantive obligations begin 14 May 2027. Design now for purpose-specific, withdrawable consent.
- **AI governance:** Map the design to RBI FREE-AI's 7 sutras (A23). LLM never decides money; human review for doubtful cases; everything audited. The AI evaluation harness is BUILT behind a flag (H25) and nothing is measured yet.
- **Messaging:** WhatsApp Business API (A18) — opt-in required, templates outside the 24-hour window. WhatsApp is SIMULATED in the prototype.
- **Status words:** BUILT means in the code today. Every feature named here is BUILT behind a feature flag that is off by default, and AI paths are tested against fakes only (no live key has been run). Anything still not written is marked NOT BUILT.

---

## 1. Disclaimer and scope

This document describes the regulatory positions on which Chhatri is being built as a hackathon prototype. It is **not legal advice**. Every position stated here must be confirmed with the following before a live pilot:

1. The partner general insurer's compliance team and counsel.
2. The partner lender's compliance team (for EDI holiday mechanics).
3. External regulatory counsel, as appropriate (e.g. on parametric product filing with IRDAI).

The prototype is built to demonstrate the architecture. No position in this document overrides counsel's advice to the insurer or lender.

---

## 2. Roles and licences

### 2.1 Insurance underwriting and distribution

**Underwriter:** A partner general insurer (to be approached after the hackathon) will underwrite the Chhatri product. The insurer:
- Assumes the risk of claims.
- Holds IRDAI-issued underwriting licence for general insurance.
- Decides on product filing (see section 3.2).
- Establishes grievance redressal and claims processes (see section 4).

**Distributor:** Paytm Insurance Broking Pvt Ltd (A4, IRDAI broker licence renewed to 16 Feb 2029) distributes the product:
- Would sell cover to merchants through the Paytm for Business app (the mini-app is BUILT behind a flag, N1). Today cover is bought through a payment link in the chat.
- Handles the simulated payment link in the demo (see docs/SPEC.md §0.1). The team has no Paytm keys.
- Collects standing consent for daily settlement deductions (the premium) from merchants.

**Paytm's role:** Paytm does not underwrite. Paytm:
- Provides merchant data (sales, KYC, settlement account).
- Provides the settlement rail (daily deduction for premium; payout credit with the settlement).
- Operates the Soundbox (transaction log).
- Would host the merchant mini-app and Ask Chhatri (both BUILT behind flags).
- Does not approve or modify claim decisions.

---

## 3. Insurance positions

### 3.1 Cash before cover (Insurance Act 1938, s.64VB)

**Regulatory requirement (B):** An insurer may not assume risk until the premium is received, or held in escrow or deposited in the prescribed manner (per the Insurance Act, s.64VB). This is the "cash before cover" principle.

**Chhatri's design:**
- Cover for a day starts only when that day's premium has been received.
- For the first purchase: a 30-day prepayment is collected via a SIMULATED Paytm payment link (a real link needs Paytm keys, which the team does not have). The 30 days run from the cover start date, which is 7 days after the request. The merchant must complete this before cover starts.
- For subsequent days: the premium is deducted from the evening's settlement (the prototype runs it at 21:00 simulated time, and a deduction on day N prepays day N+1). The deduction is made under explicit standing consent given at cover purchase (see section 6.2).
- A day whose collections are below the premium (because the shop had few or no sales) does not advance the prepaid date, and cover lapses after the prepaid date. The prototype has no standalone payment or deferral for this case. A payment link for it is a possible design, not built.

**Compliance:** Every claim is checked for premium received through the event date (the PREMIUM_PREPAID check), and the decision is audited (see section 7 on audit).

### 3.2 Parametric product filing

**Regulatory background:** Parametric (index-based) insurance already exists in India (A8, crop insurance under RWBCIS; state disaster covers). It is filed as a product with IRDAI. Chhatri is a parametric income product: the payout is triggered by the area sales index and hospital silencing, not by individual loss assessment.

**Filing approach:** The insurer will file the product with IRDAI as:
- A new merchant-income parametric cover (type: general insurance, class: miscellaneous).
- Possibly through IRDAI's regulatory sandbox (open to selected innovators; timelines and terms managed by IRDAI and the insurer's legal team).

**Chhatri's role:** Chhatri provides:
- The policy rules and formula (rules.yaml pilot-0.1; section 3.4 below).
- The claims logic (policy engine; docs/SPEC.md §9).
- The backtest and any evidence of performance or basis risk (docs/04-engineering/ml-model-card.md). The backtest uses simulated sales and real rainfall, and its calibration is circular by design, so it checks the specification and is not evidence about real merchants.

The insurer and counsel manage the filing.

### 3.3 Precedents and basis risk

Parametric insurance inherently carries basis risk: the payout trigger (area index and hospital silence) may not perfectly match the merchant's actual loss (Clarke et al. 2012, A8). Chhatri explicitly accepts this:

- The payout is 50% of the loss, not 100%, to acknowledge moral hazard and basis risk.
- The area trigger uses the shops' own sales in the zone (not weather alone), which should reduce basis risk compared with a weather-only trigger. On simulated sales the backtest paid 89 of 148 simulated real drops against 49 of 148 for a weather-only trigger. That is a specification check, not a result on real merchants.
- But the shop-level loss may still differ from the area index, which is why there is a dispute mechanism (section 4.3).

### 3.4 Policy rules and limits

Policy rules are stored in `backend/chhatri/policy/rules.yaml` (version pilot-0.1). Every payout is logged (section 7). The table lists the substantive thresholds. The complete rule set is in `rules.yaml`. Rules are:

| Rule | Value | Notes |
|---|---|---|
| **Payout share** | 50% | Covers half the computed loss. The other 50% is the merchant's deductible, to manage moral hazard. |
| **Area trigger** | Index < 50% in each of 3 consecutive hours AND the 3-hour index below the zone's conformal lower bound, during a RAIN or CIVIC alert (any colour), with ≥ 20 shops in the index | Reduces false positives vs a weather-only trigger. |
| **Area daily cap** | ₹2,500 per merchant per day | Limits concentration risk. |
| **Hospital-cash trigger** | Silent day (no sales in business hours) + hospital slip with readable patient name and dates covering the silent day(s) | Checks for authenticity: name match ≥ 85 (rapidfuzz token_set_ratio); slip confidence ≥ 0.80. |
| **Hospital-cash daily cap** | ₹1,500 per merchant per day, for up to 3 days automatically | More than 3 silent days sends the whole claim to a claims officer. |
| **Annual limit** | ₹30,000 per merchant over any rolling 365 days (a hard check) | Caps total exposure per merchant. |
| **Waiting period** | 7 days | Cover starts 7 days after the request. Prevents abuse. |
| **Alert look-ahead** | 72 hours | A quote while an alert is valid or starts within 72 hours is BLOCKED: the new cover will not apply to it. The link is still offered. |
| **Name match threshold** | ≥ 85 (token_set_ratio) | A SOFT check. Below 85 sends the claim to a claims officer (REFERRED). |
| **Slip confidence** | ≥ 0.80 | A SOFT check. The lower of the reader's name and admission-date confidences must be at least 0.80. |
| **Dispute SLA** | 24 hours | Time to respond to a dispute (section 4.1). Each case has a due time and records whether it was resolved in time. |
| **Premium loading** | 35% (expected loss ÷ 0.65) | Used to calculate the premium for each zone. |
| **Minimum daily premium** | ₹2 | Floor below which the product is not economical. |
| **First payment prepay** | 30 days | The initial premium payment covers 30 days from the cover start date. |
| **Payout rail delay** | 4 minutes | The simulated rail credits an approved payout 4 minutes after the decision. |
| **EDI request delay** | 5 minutes | Today the simulated step pauses the next instalment 5 minutes after the decision. X4 turns it into a request to the lender. |

### 3.5 Claims: zero-document area claims

**Trigger:** The area sales index falls below 50% in each of 3 consecutive hours during a RAIN or CIVIC alert (any colour; a Red alert is only the demo case) and the 3-hour index is below the zone's lower bound.

**Decision:** Every insured shop in that zone is checked:
- Is the merchant covered on that date?
- Has the waiting period ended?
- Was the cover bought before the alert was issued?
- Is the premium paid (s.64VB)?

**Payout:** Automatic. No documents from the merchant. Amount = 50% × expected day × drop %, capped at ₹2,500. In the prototype the simulated rail credits it 4 minutes after the decision.

**Explanation (BUILT, K5):** The merchant sees the formula: expected day amount (₹), drop % (from the area index), the half-of-the-loss rule and the cap when it applies. Showing the source of each number (H13) and a reference to clause C2 are BUILT behind flags (N1, H17). The explanation is reproducible from the numbers shown (see docs/SPEC.md §4.3).

### 3.6 Claims: one-document hospital-cash claims with human review for doubt

**Trigger:** A silent day: a completed day with no sales in the shop's business hours, still none by 11:00 the next morning (the shop is not on its weekly off and its zone had no area event).

**Process:**
1. Chhatri sends a check-in message at 11:20 (BUILT, in Hindi and English): "Your shop has been closed since yesterday. Is everything okay?" A voice version (Sarvam TTS and STT, browser speech as a fallback) is BUILT behind `n4_voice` (N4). The merchant replies by voice note or tap.
2. Merchant sends a photo of a hospital document (admission slip, discharge summary, prescription or bill).
3. Chhatri extracts the patient name, admission and discharge dates, hospital name (Sarvam Vision today, live only with a key and otherwise the simulated reader; Gemini vision is BUILT behind `n3_slip_precheck` and tested against fakes only, N3).
4. The policy engine runs the checks:
   - SOFT checks: does the extracted name match the KYC name at ≥ 85? Do the slip dates cover the silent day(s)? Is the slip readable (confidence ≥ 0.80)? Is the claim for 3 days or fewer?
   - HARD checks: cover in force, premium prepaid, silence verified from sales, not already paid, annual limit.

**Decision:**
- **APPROVED (every check passes):** Automatic payout. Amount = 50% × expected day, capped at ₹1,500 per day, for up to 3 days automatically.
- **REFERRED (a SOFT check fails or is unsure):** A claims officer (Rajesh, persona) reviews the slip image, the extracted name, the KYC name, the match score, the silent days and the checks. The officer re-runs all checks and can approve or decline. A SOFT check the officer approves is recorded as WAIVED_BY_OFFICER. A HARD fail still declines.
- **DECLINED (a HARD check fails, for example cover not in force, premium not prepaid, silence not verified, already paid, annual limit):** No payout. Merchant sees a reason and can dispute.

**SLA:** We tell the merchant to expect an answer within 24 hours. IRDAI's Master Circular (A24) sets 1 hour for cashless requests and 3 hours for discharge authorisation in health insurance. Chhatri is an income cover, not a health policy, so A24 may not apply. If it did, the 24-hour target would be slower than the rule. This is a question for counsel.

**Explanation:** The decision shows the reason and the checks that passed or failed. A link to clause C3 and an extracted-fields screen for the merchant are BUILT behind flags (H17, N3).

---

## 4. Claims, disputes and grievances

### 4.1 Dispute mechanics and 24-hour SLA

**Trigger:** A merchant disagrees with a payout amount (BUILT: "My loss was bigger" in the chat). A dispute of a decline is not built.

**Process:**
1. Merchant tells Chhatri in the chat. A "Dispute" button in the claims tracker is BUILT behind the mini-app flag (N1, H1).
2. Chhatri replies "Okay, I'm sending this to our team. You'll hear back within 24 hours." and shows "Sent to a claims officer · case C-2291" (case number as an example).
3. A case of kind DISPUTE is opened with a due time 24 hours later.

**Resolution (BUILT):**
- A claims officer reviews the decision's numbers and either confirms the payout or rejects the dispute. The reason shown is, for example, "Your area's numbers support the amount paid."
- A dispute never changes the amount, and the case is then CLOSED. It records whether it was closed within the 24 hours.
- There is no path yet to correct an amount if the engine itself was wrong. A correction would need a new decision by the insurer (open question).

**Outcome:** The case status is CLOSED. DISPUTE and REFERRED are different case kinds: a REFERRED claim is decided by an officer (section 3.6), and a DISPUTE is a challenge to a decision already made.

### 4.2 Grievance ladder (per B)

If a merchant is unhappy with Chhatri's dispute resolution, the grievance ladder is:

1. **Insurer's Grievance Redressal Officer (GRO):** The merchant files a formal grievance with the insurer (via Chhatri or directly). The insurer's GRO responds per its SLA (to be confirmed with the insurer's compliance team). The merchant is notified of the outcome (upheld, partially upheld, or rejected) and the reason.

2. **IRDAI's Bima Bharosa portal:** If the merchant is unhappy with the GRO's response, they can lodge a complaint on the Bima Bharosa portal (https://bimabharosa.irdai.gov.in). IRDAI's team investigates and directs the insurer if an error is found. The portal says complaints are attended within 14 days.

3. **Insurance Ombudsman:** If the complaint is still unresolved or the merchant disagrees with IRDAI's direction, they can approach the Insurance Ombudsman (free to the policyholder, under the Insurance Ombudsman Rules, 2017). The Ombudsman can award compensation up to the amount specified in their rules (check current limits with counsel).

**Chhatri's role:** Chhatri shows this ladder, with response clocks only where a source states one and a router for who owns the complaint (Paytm, the insurer or the lender), in the merchant mini-app (BUILT behind `n5_grievances`; feature spec fs-06). Chhatri logs every escalation and decision.

---

## 5. Lending: RBI Digital Lending Directions 2025

### 5.1 Scope

The RBI (Digital Lending) Directions, 2025 (A25, issued 8 May 2025) apply to lending relationships involving digital platforms (including Paytm). As we read them, and subject to counsel, the Directions require:
- Transparent terms and conditions.
- Clear disclosure of charges and repayment schedules.
- No deceptive practices.
- An in-built grievance redressal mechanism.
- Any credit relief measures (e.g. loan restructuring, payment deferrals) must be board-approved by the lender and offered fairly (no cherry-picking).

### 5.2 EDI holiday as a pre-agreed policy

**Chhatri's design:** After a payout, Chhatri requests the lender to defer the next instalment (EDI). The lender applies a pre-agreed policy rule (the four conditions of X4, [fs-03](../02-product/feature-specs/fs-03-edi-holiday.md)):
- Loan is active (not repaid, defaulted or cancelled).
- Borrower is not in arrears.
- Holiday allowance is not exhausted (the allowance is a lender setting; the number is not fixed here).
- The loan is in the holiday scheme (the borrower has opted in).

**RBI position (to be confirmed with the lender's counsel):** The deferral is the **lender's decision**, made under its board-approved policy. Chhatri is the initiator (via a structured request), but the lender holds the authority. The design aims to be consistent with the Directions: no unilateral Chhatri pause, a board-approved lender policy, and the same benefit for all eligible borrowers. Whether a pre-agreed holiday counts as a restructuring is for the lender's compliance team.

**Two settlement models:**
1. **Lender-deferred model (default):** The lender defers the instalment to the end of the loan tenure with no penalty. The merchant's loan duration does not change; the last instalment date extends by 1 day (or more if several deferrals apply). The merchant is told what the lender decided. Proposed wording (X4, fs-03 section 8.2): "Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty."
2. **Insurer-funded model (alternative):** The insurer pays the instalment directly to the lender from the payout, so the loan terms never change. This is similar to an EMI-protection cover. The merchant message would be agreed with the insurer.

The insurer and lender will agree on the model during the pilot.

### 5.3 Code implementation and audit

- **Today (BUILT):** `backend/chhatri/ledger/instalments.py`, method `pause_next()`, pauses the next instalment 5 minutes after the decision. It has no lender check and no lender answer: the simulated lender always grants. The message "Tomorrow's ₹600 instalment is paused." reads as if Chhatri did it. The audit entry is `instalment.pause`.
- **BUILT behind the x4 flag (X4):** the step becomes a request to a simulated lender that applies the four conditions above. A refusal creates no pause, and the payout is never touched. The audit entries become `instalment.holiday_request` and `instalment.holiday_decision` with a reason code. In production, the lender's API provides the decision.

---

## 6. Data protection: DPDP Act and Rules 2025

### 6.1 DPDP Act applicability and timeline (A22)

The DPDP Rules, 2025 were notified on 13 Nov 2025 (published 14 Nov) under the Digital Personal Data Protection Act, 2023. The rollout is phased (A22):
- **14 Nov 2025:** The first phase begins.
- **14 Nov 2026:** Consent managers (intermediaries that help manage consent) come in, for example.
- **14 May 2027:** Substantive obligations apply: consent, notices, breach reporting within 72 hours, and more.

**Chhatri's timeline:** Chhatri is being designed now (Oct 2026) with the May 2027 substantive obligations in mind, to limit rework at go-live. Counsel must confirm the detail.

**Status today:** The consent centre, the consent activity log and slip deletion are BUILT behind `n6_consents` (N6 and H23); with the flag off there is no consent centre and no deletion path. The original slip image is kept in memory so an officer can see it. Sections 6.2 to 6.5 describe the design; check each against fs-07 before relying on a detail.

### 6.2 Purpose-specific, withdrawable consent

**Sales data (area claims):**
- **Purpose:** Decide area income-loss claims and calculate premiums.
- **Consent:** Collected at cover purchase ("I consent to Paytm and Chhatri using my daily sales data for the purpose of deciding claims and calculating premiums").
- **Duration:** Valid for the cover period. On renewal, re-collected.
- **Withdrawal:** Merchant can withdraw anytime. Once withdrawn, no new sales data is collected. Existing data is kept for 7 years (for claim disputes, if any), then deleted.

**Hospital slip data (hospital-cash claims):**
- **Purpose:** Verify hospital admission and match the patient name with KYC.
- **Consent:** Collected when the merchant submits a hospital-cash claim ("I consent to Chhatri reading and storing this hospital document for the purpose of deciding my claim").
- **Duration:** Valid for the claim period (until the dispute SLA expires and the claim is closed).
- **Withdrawal:** Merchant can request deletion of the slip data after the claim is closed. Chhatri deletes it within 30 days.

**Settlement account (payout):**
- **Purpose:** Credit the payout to the merchant's account.
- **Consent:** Implicit in the cover purchase (necessary to settle payouts).
- **Duration:** For the cover period.

### 6.3 Data minimisation and masking

**Chhatri collects:**
- Merchant ID, phone number, KYC name (for settlement and KYC matching).
- Daily sales (for area claims and premium calculation).
- Soundbox transactions (silent-day detection).
- Hospital slip: patient name, admission and discharge dates, hospital name, document type.

**Chhatri does not collect:**
- The merchant's personal email or home address.
- The merchant's personal health records (only the admission dates).
- Family or dependant data.
- Location data beyond the zone.

**Masking:**
- In the consent centre (BUILT behind `n6_consents`, feature spec fs-07), the merchant can view their slip data. Patient names are masked, for example "P**** J****", to prevent unintended data exposure.
- In reports shared with the insurer, merchant names are replaced with merchant IDs.

### 6.4 Children

Chhatri is only for merchants (adults, age ≥ 18). No data is collected on children. Dependants are not in scope.

### 6.5 Notices and requests

**Initial notice (at cover purchase, BUILT in the mini-app buy flow):**
Chhatri shows a data notice in the mini-app buy flow:
- What data is collected (sales, Soundbox, hospital slips).
- Why (claims and premium calculation).
- How long it is kept (7 years for claims disputes; slip data deleted 30 days after claim closure).
- The merchant's rights (view, correct, delete, withdraw consent).
- Contact for data requests (support phone and email).

**Data subject requests (proposed process, not built):**
- Merchant can ask "What data do you have on me?" → Chhatri sends a CSV of all data in 30 days.
- Merchant can ask "Fix my KYC name." → Chhatri updates it and confirms in 7 days.
- Merchant can ask "Delete my slip." → After the claim is closed, Chhatri deletes it in 30 days.

---

## 7. AI governance: RBI FREE-AI framework (A23)

### 7.1 The 7 sutras and Chhatri's design

RBI released the FREE-AI committee report on 13 Aug 2025. It is advisory (not yet binding directions) but sets out 7 sutras for responsible AI in the financial sector:

| Sutra | Meaning | Chhatri's design |
|---|---|---|
| **Trust** | AI systems must be trustworthy and auditable. | (1) Policy engine is pure code (no LLM); (2) Audit log is hash-chained; (3) `GET /api/audit/verify` lets an auditor with API access recompute the chain. |
| **People First** | AI must respect human autonomy and protect vulnerable groups. | (1) A merchant can dispute a payout amount (BUILT); (2) A human reviews doubtful hospital-cash claims (REFERRED); (3) Premium is deducted from settlement only under standing consent, and only when the day's collections cover it; (4) No loan offers or cross-sell during distress (X8, BUILT behind `x8_distress_guard`). |
| **Innovation** | AI can improve financial inclusion and efficiency. | (1) In the prototype the payout is credited 4 minutes after the decision (a simulated rail; earlier plans took 30–60 days, A3); (2) The area trigger uses the zone's shops' own sales; (3) Hospital-cash reads one photo (Sarvam today when keyed; Gemini PLANNED). |
| **Fairness** | AI decisions must not discriminate. All eligible merchants are paid the same formula. | (1) Formula is identical for all merchants in the same zone; (2) Name-match threshold (85) is uniform; (3) Dispute SLA (24 hours) is uniform; (4) The backtest shows basis risk (not all losses are caught, and some payouts have no real drop), on simulated sales; (5) Exclusions are clear (e.g. a HEATWAVE alert does not trigger cover). |
| **Accountability** | Developers and institutions must take responsibility. | (1) Chhatri logs every decision and its reasoning; (2) Insurer (not Paytm) is accountable for underwriting; (3) Paytm (distributor) and insurer (underwriter) are both liable under insurance law (to be confirmed by counsel). (4) Tests: backend 1,711 fast and 36 slow tests at 99.7% coverage, frontend 262 of 264 passing (X1 fixes the other 2), measured on 2 Oct. The AI parts are not measured yet (H25). |
| **Explainability** | Merchants must understand why a decision was made. | (1) Every decision shows the formula: expected day, drop %, cap when it applies, and final amount (BUILT, K5); (2) Every check result is shown to the officer (e.g. "Name match: 100, passes the threshold of 85"); (3) Ask Chhatri answers coverage questions grounded in clauses C1–C12 (PLANNED, N2, Wave 2); (4) No black-box numbers. |
| **Resilience** | Systems must fail gracefully and recover. | (1) A fallback chain for AI providers (Gemini, then Sarvam, then templates or a person) is BUILT (ADR 0003) and tested against fakes only; with no keys it is the simulators and templates; (2) Browser speech as a fallback is BUILT behind `n4_voice` (N4); (3) BUILT: the in-process workflow runner needs no network (n8n is optional). |

### 7.2 LLM authority

**Principle (docs/SPEC.md §0.2):** "The AI builds the case; code decides the money."

**Implementation:**
- **Ask Chhatri (N2, BUILT behind `n2_ask_chhatri`; tested against fakes only):** An LLM (Gemini or Sarvam) answers coverage and claims questions. But:
  - The answer is grounded only in the policy wording (clauses C1–C12) and the merchant's own decision facts (from the decision table).
  - The LLM is guarded (design in docs/SPEC.md §13.3; the guard is BUILT with N2 and H17): no digit that is not in the decision facts; no promises of money.
  - Any money figure shown to the merchant must have a corresponding check in the decision record.
  - If the LLM cannot find a grounded answer, it says "I don't know; let me connect you to a person."
  - Today the chat model sees only text the word-list classifier cannot place (UNKNOWN), and the merchant's money messages are templates filled from decision facts.
- **Slip reading (N3):** Sarvam Vision (BUILT, live only with a key; otherwise the simulated reader) extracts patient name, admission/discharge dates and hospital. Gemini Vision is BUILT behind a flag and tested against fakes only. But:
  - The slip reader's confidence is shown to the officer today. The merchant-facing pre-check (extracted fields, retake, confirm) is BUILT behind flags (N3, H5, H15).
  - Below the confidence gate (0.80), the case is referred to a human (BUILT).
  - The merchant will be able to see the extracted fields and retake the photo if it is unclear (BUILT behind a flag).

**No LLM payout authority:** The policy engine (`backend/chhatri/policy/engine.py`) is the only code that can produce an APPROVED decision. The LLM has no authority over money.

### 7.3 Human involvement

Humans are involved in:
- **REFERRED hospital-cash claims:** When a slip does not pass the automatic checks (e.g. the name scores below 85), a claims officer reviews and approves or declines.
- **Disputes:** When a merchant disputes a payout, a claims officer re-checks the numbers and confirms the payout or rejects the dispute.
- **Escalations:** When a merchant escalates to the insurer or IRDAI, a person handles it.

### 7.4 Evals and guardrails

**AI evaluation (H25, BUILT behind `h25_evals`).** The [AI evaluation plan](../04-engineering/ai-evaluation-plan.md) defines six suites: intent routing, the guard against unsupported figures and promises, end-to-end Ask answers, slip reading with the confidence gate, voice, and the labels and fallback behaviour of every chain. Nothing has been measured. The console page `/evals` reads NOT MEASURED until a stored run exists. A target such as "at least 95% factual accuracy for Ask Chhatri" is a target, not a result.

**Guard tests (X7, BUILT):** A test suite enforces honest wording:
- Merchant-facing templates are rejected if they use absolute language ("guaranteed", "100%", "always").
- No payout amount is shown unless it is in the decision facts.
- No "paid" message appears before a payout record exists.

**Model card:** See `docs/04-engineering/ml-model-card.md` for the expected-sales model (LightGBM quantile). Backtest and basis risk are published.

---

## 8. Messaging: WhatsApp and in-app

### 8.1 WhatsApp Business API (A18)

**Setup:** The prototype has a WhatsApp Cloud API adapter, but the team has no WhatsApp keys, so WhatsApp is SIMULATED (the in-console phone) on stage. A Meta developer test number works without business verification (A18). In production, Paytm would use its verified business number.

**Rules (A18):**
- **Free-form replies (inside 24-hour window):** No cost. If the merchant replies to any message from Chhatri within 24 hours, Chhatri can send a free-form reply (e.g. "Hi, I received your message. Let me check that for you").
- **Proactive messages (outside 24-hour window):** Must use an approved template. Template examples (proposed, not in the message catalogue):
  - "Hi [name], a heavy-rain alert is issued for your zone."
  - "[name], your claim of ₹1,380 has been approved and credited with today's settlement."

**Chhatri's approach:** Merchant-facing copy is in `backend/chhatri/conversation/messages.py`. Money messages are templates filled from the decision facts (no free-generation; see docs/SPEC.md §4.1). Opt-in capture and opt-out are proposed and belong with the consent centre (N6, BUILT; opt-in capture for WhatsApp is not built).

### 8.2 In-app messaging

Claims decisions, disputes, EDI holidays and grievance updates will be shown in the merchant mini-app (N1, BUILT behind a flag) in Hindi and English, and in the chat (the phone simulator). WhatsApp would be the secondary channel (opt-in backup).

---

## 9. Compliance checklist

This table summarizes the regulatory requirements and Chhatri's design responses.

| # | Requirement | Source | Chhatri design | Status | Owner | Evidence |
|---|---|---|---|---|---|---|
| 1 | Insurer underwrites; broker distributes. | Insurance Act 1938 | Partner general insurer underwrites; Paytm Insurance Broking distributes. Paytm does not underwrite. | Design | Omkar Kadam | fs-* docs, commercial discussions (pilot plan) |
| 2 | Cover starts only when premium is received (cash before cover). | Insurance Act 1938, s.64VB | First 30 days: prepayment via link. Then: daily settlement deduction under standing consent. Every claim runs the PREMIUM_PREPAID check (prepaid through the event date). | BUILT (link SIMULATED); legal confirmation PLANNED | Omkar Kadam | docs/SPEC.md §9.6; policy-wording-and-cis.md C6 |
| 3 | Parametric product must be filed with IRDAI. | IRDAI guidelines | Insurer files via standard process or regulatory sandbox. Chhatri provides rules, logic and backtest evidence. | Planned (post-hackathon) | Omkar Kadam | docs/01-strategy/current-state-audit.md; docs/02-product/feature-specs/fs-01-area-auto-claim.md |
| 4 | Area claims processed transparently with a formula. | General best practice (transparency) | Formula shown to merchant: expected day × drop % × 0.5, capped at ₹2,500. All numbers are in the decision and audit log. | BUILT (K5) | Ujjwal Pardeshi | backend/chhatri/policy/explain.py; docs/02-product/prd.md |
| 5 | Health-claim timelines (1 hour for cashless, 3 hours for discharge authorisation). | IRDAI Master Circular (A24), for health insurance | Chhatri's decision: automatic if checks pass; human review (REFERRED) with a 24-hour target. That is slower than A24, which is written for health insurance and may not apply to an income cover. Counsel to confirm. | BUILT (decision and review); applicability to confirm | Ujjwal Pardeshi | backend/chhatri/policy/engine.py; docs/SPEC.md §9 |
| 6 | Grievance ladder: GRO → Bima Bharosa → Ombudsman. | Insurance Ombudsman Rules 2017 | Chhatri shows the ladder in the mini-app. Insurer GRO is the entry point. | BUILT behind `n5_grievances` (N5, H22) | Omkar Kadam | docs/02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md |
| 7 | Dispute response within a stated time. | Chhatri's own target (no IRDAI rule cited here) | 24-hour target for a dispute response. Each case has a due time (opened + 24 hours) and records whether it closed in time. | BUILT | Ujjwal Pardeshi | backend/chhatri/cases/service.py; policy-wording-and-cis.md C9 |
| 8 | Lending: EDI holiday is the lender's decision, not Chhatri's. | RBI Digital Lending Directions 2025 (A25) | Chhatri requests; lender decides via pre-agreed rule (X4: active loan, not in arrears, holiday allowance, flag enabled). Lender decision is logged and audited. With the x4 flag off the simulated lender grants with no check. | BUILT behind the x4 flag (X4) | Omkar Kadam | docs/02-product/feature-specs/fs-03-edi-holiday.md; backend/chhatri/ledger/instalments.py |
| 9 | No unilateral loan restructuring without board approval. | RBI Digital Lending Directions 2025 (A25) | EDI holiday is the lender's board-approved policy. Chhatri initiates the request; lender executes. All merchants are treated equally. | Design | Omkar Kadam | docs/02-product/feature-specs/fs-03-edi-holiday.md |
| 10 | Purpose-specific consent for data use. | DPDP Act 2023, DPDP Rules 2025 (A22) | Sales data: purpose "claims and premium"; withdrawable. Slip data: purpose "claim verification"; deleted after closure. Both collected in the mini-app with explicit consent. | BUILT behind `n6_consents` (N6, H23) | Omkar Kadam | docs/02-product/feature-specs/fs-07-cover-purchase-and-consent.md; policy-wording-and-cis.md C11 |
| 11 | Data minimisation; no unnecessary PII collection. | DPDP Act 2023 (A22) | Chhatri collects only: merchant ID, phone, KYC name, sales, Soundbox, hospital slip (name, dates, hospital). No personal email, home address, dependant data or detailed health records. | Design | Omkar Kadam | docs/04-engineering/data-model-and-api.md |
| 12 | No data on children; no automated decisions affecting children. | DPDP Act 2023 (A22) | Cover is for merchants (age ≥ 18) only. No data on children collected. Merchant's own coverage is limited by policy (e.g. hospital claims only for the merchant, not dependants). | Design | Omkar Kadam | policy-wording-and-cis.md (scope) |
| 13 | DPDP compliance timeline and phased obligations. | DPDP Rules 2025 (A22) | Timeline: 14 May 2027 for substantive obligations. Chhatri is designed with the May 2027 requirements in mind (to confirm with counsel). | Design | Omkar Kadam | Section 6 (DPDP Act applicability and timeline); docs/02-product/feature-specs/fs-07-cover-purchase-and-consent.md |
| 14 | AI governance: LLM does not decide money. | RBI FREE-AI report (A23) | Policy engine is pure code; LLM (Ask Chhatri) is a grounded assistant only. Human review for doubtful cases. Audit log records all decisions. | BUILT (engine, review, audit); Ask Chhatri BUILT behind `n2_ask_chhatri` (N2), tested against fakes only | Ujjwal Pardeshi | docs/04-engineering/ai-architecture-and-guardrails.md; docs/02-product/feature-specs/fs-09-policy-engine-and-audit.md |
| 15 | AI: Trust, People First, Innovation, Fairness, Accountability, Explainability, Resilience. | RBI FREE-AI report (A23) | Mapped in section 7.1 above. The audit log is in place. The evaluations (H25) and the fallback chain (ADR 0003) are BUILT (H25 behind `h25_evals`; ADR 0003 chain tested against fakes). Nothing is measured. | Design | Omkar Kadam | docs/04-engineering/ai-architecture-and-guardrails.md; docs/04-engineering/ai-evaluation-plan.md; Section 7 (AI governance) |
| 16 | Opt-in for WhatsApp messaging; approval of templates. | WhatsApp Business API (A18) | The message catalogue is in backend/chhatri/conversation/messages.py. Outside the 24-hour window only approved templates may be sent. Opt-in capture for WhatsApp is not built. The team has no WhatsApp keys, so WhatsApp is SIMULATED. | BUILT (catalogue and adapter); opt-in NOT BUILT | Ujjwal Pardeshi | docs/SPEC.md §16 |
| 17 | Audit trail: every decision is logged and tamper-evident. | General best practice; DPDP (breach reporting requires audit trail). | Hash-chained audit log in SQLite. `GET /api/audit/verify` recomputes hashes. Wall-clock times are excluded from the hash (only simulated time). | BUILT | Ujjwal Pardeshi | docs/04-engineering/system-architecture.md; backend/chhatri/audit/log.py |
| 18 | No hardcoded secrets; secret management. | General best practice | All secrets from environment (`.env`). `make env` generates random keys. `.env.example` lists the keys but has no values. Demo mode generates a demo token if none is set. | BUILT | Ujjwal Pardeshi | docs/SECURITY.md; backend/chhatri/config.py |
| 19 | Rate limiting and fraud prevention. | General best practice | In-memory sliding window (60 s): webhooks 60/min, uploads 20/min, phone messages 60/min. Type validation by magic bytes (images, audio). File size limits (5 MB images, 5 MB and 30 s audio). | BUILT | Ujjwal Pardeshi | docs/SECURITY.md |
| 20 | CORS and cross-origin security. | General best practice | Only `CHHATRI_CONSOLE_ORIGIN` allowed, no credentials. Console is same-origin via nginx. | BUILT | Ujjwal Pardeshi | docs/SECURITY.md |

---

## Open questions

1. **Insurer and counsel confirmation (immediate):** Can we confirm the s.64VB design (section 3.1) and the cash-before-cover mechanics with your compliance team? Owner: Omkar Kadam.

2. **Parametric product filing (post-hackathon):** Is the regulatory sandbox route the insurer's preference, or is a standard filing acceptable? What is the expected timeline for product filing? Owner: Omkar Kadam.

3. **EDI holiday: deferral vs insurer-funded (immediate):** Which settlement model for the EDI holiday does the lender prefer — deferral to the end of the loan tenure, or insurer funding from the payout? Are there board-approval requirements or regulatory approvals needed? Owner: Omkar Kadam.

4. **Lending partner agreement:** Which partner lender will confirm the pre-agreed rule (X4) and the EDI-holiday mechanics? Owner: Omkar Kadam.

5. **Hospital network:** Which hospitals are eligible for hospital-cash claims? Should Chhatri keep an approved-hospital list, or is any government or registered private hospital acceptable? The prototype checks neither. Owner: Omkar Kadam.

6. **DPDP consent manager:** Will Paytm or the insurer use a DPDP consent manager, or handle consent directly? Timeline? Owner: Omkar Kadam.

7. **Grievance redressal:** Where is the insurer's GRO located, and what is the escalation process? How are REFERRED cases and disputes routed to the GRO? Owner: Omkar Kadam.

8. **Messaging and notifications:** Are there additional regulatory requirements or sector-specific guidelines (e.g. RBI or IRDAI) for WhatsApp notifications about payouts or claims? Owner: Omkar Kadam.

9. **Audit and compliance reporting:** What is the insurer's reporting cadence to IRDAI (e.g. monthly, quarterly)? What metrics or KPIs are required (e.g. claim acceptance rate, dispute rate, basis-risk metrics)? Owner: Omkar Kadam.

10. **Regulatory sandbox timeline:** If the insurer chooses the sandbox route, when can an application be filed, and what is the expected sandbox period? Are there specific caps on payouts during the sandbox phase? Owner: Omkar Kadam.

11. **Correcting an engine error:** A dispute cannot change an amount today. If the engine itself was wrong, what is the correction route (a new decision by the insurer, a goodwill payment, a grievance)? Owner: Ujjwal Pardeshi.

12. **Applicability of A24:** Do the health-claim timelines apply to an income cover with a hospital-slip trigger, or only to health policies? Owner: Omkar Kadam.

---

## Changelog

- 2026-10-03 · v2.2 · feature statuses changed from PLANNED to BUILT behind flags where the code has them; AI paths tested against fakes only; WhatsApp opt-in capture is not built
- 2026-10-02 · v2.1 · fixed against the code: name, dates and slip confidence are SOFT checks (REFERRED, with WAIVED_BY_OFFICER), HARD failures DECLINE; the annual limit is a rolling 365 days; disputes never change an amount and close the case; today's EDI pause has no lender check (X4 PLANNED) and the lender-decides wording is proposed; any RAIN or CIVIC alert triggers (not Red only); rules table gains the 4-minute payout and 5-minute pause delays and points to rules.yaml for the full set; unbuilt items (mini-app, consent centre, grievance ladder, Ask Chhatri, evals, slip deletion, Gemini) marked PLANNED; WhatsApp and the Paytm link marked SIMULATED; the AI evaluation is linked and NOT MEASURED; the A24 comparison corrected.
- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; all regulatory positions correctly use future tense for partnerships and future obligations.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.2 · corrections after a second read against the code.
- 2026-10-02 · v1.1 · fact-check pass.
- 2026-10-02 · v1 · first draft, covering roles, insurance positions, claims mechanics, lending, DPDP, AI governance, messaging, compliance checklist and open questions.
