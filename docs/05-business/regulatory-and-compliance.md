# Regulatory and compliance

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Insurer partners, lender partners, compliance counsel, regulators |
| Related | [Facts and sources](../01-strategy/facts-and-sources.md) · [Policy wording](../02-product/policy-wording-and-cis.md) · [Business model](business-model-and-unit-economics.md) · [Go-to-market and pilot plan](go-to-market-and-pilot-plan.md) |

## TL;DR

- **Disclaimer:** This document is not legal advice. All regulatory positions must be confirmed with the partner insurer's compliance team and counsel.
- **Roles:** A partner general insurer underwrites. Paytm Insurance Broking (IRDAI-licensed broker, A4) distributes. Paytm does not underwrite.
- **Core framework:** s.64VB (cash before cover), parametric product filing, zero-document area claims, one-document hospital-cash claims with human review for doubt, 24-hour dispute SLA.
- **Lending:** RBI (Digital Lending) Directions 2025 (A25) apply. EDI holidays are the lender's decision, requested by Chhatri. The lender defers the instalment to the loan's end; or alternatively, the insurer funds it from the payout.
- **Data protection:** DPDP Act and Rules 2025 (A22) apply. Substantive obligations begin 14 May 2027. Design now for purpose-specific, withdrawable consent.
- **AI governance:** Map the design to RBI FREE-AI's 7 sutras (A23). LLM never decides money; human review for doubtful cases; everything audited; eval set exists.
- **Messaging:** WhatsApp Business API (A18) — opt-in required, templates outside the 24-hour window.

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
- Sells cover to merchants through the Paytm for Business app.
- Handles the simulated payment link in the demo (see docs/SPEC.md §0.1).
- Collects standing consent for daily settlement deductions (premium and dispute data) from merchants.

**Paytm's role:** Paytm does not underwrite. Paytm:
- Provides merchant data (sales, KYC, settlement account).
- Provides the settlement rail (daily deduction for premium; next-day credit for payout).
- Operates the Soundbox (transaction log).
- Hosts the merchant mini-app and Ask Chhatri.
- Does not approve or modify claim decisions.

---

## 3. Insurance positions

### 3.1 Cash before cover (Insurance Act 1938, s.64VB)

**Regulatory requirement (B):** An insurer may not assume risk until the premium is received, or held in escrow or deposited in the prescribed manner (per the Insurance Act, s.64VB). This is the "cash before cover" principle.

**Chhatri's design:**
- Cover for a day starts only when that day's premium has been received.
- For the first purchase: a 30-day prepayment is collected via a simulated Paytm payment link (demo), or a real link if the insurer chooses live integration. The merchant must complete this before cover starts.
- For subsequent days: the premium is deducted from the previous evening's settlement (e.g. 17:00 deduction on day N grants cover for day N+1). The deduction is made under explicit standing consent given at cover purchase (see section 6.1).
- A day with no settlement (because the shop had zero sales or is closed) still requires a premium payment. In that case, Chhatri can request a standalone premium payment, or the lender can allow it to be deferred to the next settlement.

**Compliance:** Every payout is audited to confirm the premium was received before the claim date (see section 7 on audit).

### 3.2 Parametric product filing

**Regulatory background:** Parametric (index-based) insurance already exists in India (A8, crop insurance under RWBCIS; state disaster covers). It is filed as a product with IRDAI. Chhatri is a parametric income product: the payout is triggered by the area sales index and hospital silencing, not by individual loss assessment.

**Filing approach:** The insurer will file the product with IRDAI as:
- A new merchant-income parametric cover (type: general insurance, class: miscellaneous).
- Possibly through IRDAI's regulatory sandbox (open to selected innovators; timelines and terms managed by IRDAI and the insurer's legal team).

**Chhatri's role:** Chhatri provides:
- The policy rules and formula (rules.yaml pilot-0.1; section 3.4 below).
- The claims logic (policy engine; docs/SPEC.md §9).
- The backtest and any evidence of performance or basis risk (docs/01-strategy/current-state-audit.md).

The insurer and counsel manage the filing.

### 3.3 Precedents and basis risk

Parametric insurance inherently carries basis risk: the payout trigger (area index and hospital silence) may not perfectly match the merchant's actual loss (Clarke et al. 2012, A8). Chhatri explicitly accepts this:

- The payout is 50% of the loss, not 100%, to acknowledge moral hazard and basis risk.
- The area trigger uses the merchant's own sales data (not area-wide weather alone), reducing basis risk vs weather-only triggers.
- But the shop-level loss may still differ from the area index, which is why there is a dispute mechanism (section 4.3).

### 3.4 Policy rules and limits

Policy rules are stored in `backend/chhatri/policy/rules.yaml` (version pilot-0.1). Every payout is logged (section 7). Rules are:

| Rule | Value | Notes |
|---|---|---|
| **Payout share** | 50% | Covers half the computed loss. The other 50% is the merchant's deductible, to manage moral hazard. |
| **Area trigger** | Index < 50% for 3 consecutive hours AND below model's conformal lower bound, during an alert, with ≥ 20 shops in the index | Reduces false positives vs a weather-only trigger. |
| **Area daily cap** | ₹2,500 per merchant per day | Limits concentration risk. |
| **Hospital-cash trigger** | Silent day (zero Soundbox sales) + hospital slip with readable patient name and dates matching the silent day(s) | Two checks for authenticity: name match ≥ 85 (rapidfuzz token_set_ratio); slip confidence ≥ 80. |
| **Hospital-cash daily cap** | ₹1,500 per merchant per day, for up to 3 days automatically | Automated decisions for 3 days; 4+ days go to a claims officer for review. |
| **Annual limit** | ₹30,000 per merchant per year (calendar year) | Caps total exposure per merchant. |
| **Waiting period** | 7 days | Standard waiting period to prevent abuse. |
| **Alert look-ahead** | 72 hours | Prevents buying cover just before an alert. |
| **Name match threshold** | ≥ 85 (token_set_ratio) | Balances false accepts vs false rejects. Below 85 triggers human review (REFERRED). |
| **Slip confidence** | ≥ 0.80 | Extracted fields (patient name, dates, hospital) must have ≥ 80% confidence. |
| **Dispute SLA** | 24 hours | Time to decide a dispute (section 4.3). |
| **Premium loading** | 35% (expected loss ÷ 0.65) | Used to calculate the premium for each zone. |
| **Minimum daily premium** | ₹2 | Floor below which the product is not economical. |
| **First payment prepay** | 30 days | The initial premium payment covers 30 days. |

### 3.5 Claims: zero-document area claims

**Trigger:** The area sales index falls below 50% for 3 consecutive hours during a Red alert and is below the AI model's lower bound.

**Decision:** Every insured shop in that zone is checked:
- Is the merchant covered on that date?
- Has the waiting period ended?
- Is the premium paid (s.64VB)?

**Payout:** Automatic. No documents from the merchant. Amount = 50% × expected day × drop %, capped at ₹2,500. Paid via settlement (next 4 minutes).

**Explanation:** The merchant sees a breakdown of the calculation: expected day amount (₹), drop % (from the area index), the cap applied, and a reference to clause C2 in the policy wording. The explanation is reproducible from the numbers shown (see docs/SPEC.md §4.3).

### 3.6 Claims: one-document hospital-cash claims with human review for doubt

**Trigger:** The Soundbox records zero sales (silent day).

**Process:**
1. Chhatri sends a voice check-in to the merchant (Sarvam TTS/STT or fallback to browser speech). "Are you okay?" The merchant replies by voice or tap.
2. Merchant sends a photo of a hospital document (admission proof, discharge summary, hospital ID).
3. Chhatri extracts the patient name, admission and discharge dates, hospital name (Gemini vision or Sarvam Vision).
4. The policy engine checks (HARD checks):
   - Does the extracted name match the KYC name at ≥ 85%?
   - Do the dates match the silent day(s)?
   - Is the extraction confidence ≥ 80%?

**Decision:**
- **APPROVED (all HARD checks pass):** Automatic payout. Amount = 50% × expected day, capped at ₹1,500 per day, for up to 3 days automatically.
- **REFERRED (all HARD checks pass but any SOFT check is uncertain or fails):** A claims officer (Rajesh, persona) reviews the extracted fields, the raw slip, and the merchant's explanation. The officer can approve or decline. Outcome is the same as APPROVED or declined.
- **DECLINED (clear failure, e.g. wrong hospital, dates are 3 months old):** No payout. Merchant sees a reason and can dispute.

**SLA:** The officer reviews within 24 hours (IRDAI Master Circular A24 requires 1 hour for cashless, 3 hours for discharge authorisation; Chhatri's 24-hour SLA for a pre-claim document is gentler).

**Explanation:** Merchant sees the decision reason, the extracted fields, the checks that passed or failed, and a link to clause C3 in the policy wording.

---

## 4. Claims, disputes and grievances

### 4.1 Dispute mechanics and 24-hour SLA

**Trigger:** A merchant disagrees with a payout amount or a decline.

**Process:**
1. Merchant taps "Dispute" in the claims tracker.
2. Merchant explains the disagreement (optional text input or voice note).
3. A case is opened (case ID in the tracker).
4. A 24-hour clock starts.

**Resolution:**
- Chhatri (or the claims officer, if REFERRED) re-runs every check on the facts shown to the merchant.
- If an error is found (e.g. the expected day was miscalculated), the correct payout is paid immediately.
- If the facts are correct, a message explains why (e.g. "Your hospital slip showed 20 Aug, but the silent day was 19 Aug; we cannot approve for 20 Aug").
- The merchant is notified of the resolution within 24 hours.

**Outcome:** Dispute is marked as resolved (accepted, partially approved, or clarified). The 24-hour clock is closed.

### 4.2 Grievance ladder (per B)

If a merchant is unhappy with Chhatri's dispute resolution, the grievance ladder is:

1. **Insurer's Grievance Redressal Officer (GRO):** The merchant files a formal grievance with the insurer (via Chhatri or directly). The insurer's GRO responds per its SLA (to be confirmed with the insurer's compliance team). The merchant is notified of the outcome (upheld, partially upheld, or rejected) and the reason.

2. **IRDAI's Bima Bharosa portal:** If the merchant is unhappy with the GRO's response, they can lodge a complaint on the Bima Bharosa portal (https://bimabharosa.irdai.gov.in). IRDAI's team investigates and directs the insurer if an error is found. The portal says complaints are attended within 14 days.

3. **Insurance Ombudsman:** If the complaint is still unresolved or the merchant disagrees with IRDAI's direction, they can approach the Insurance Ombudsman (free to the policyholder, under the Insurance Ombudsman Rules, 2017). The Ombudsman can award compensation up to the amount specified in their rules (check current limits with counsel).

**Chhatri's role:** Chhatri shows this ladder in the merchant's claims tracker (H5, feature spec fs-06). Chhatri logs every escalation and decision.

---

## 5. Lending: RBI Digital Lending Directions 2025

### 5.1 Scope

The RBI (Digital Lending) Directions, 2025 (A25, issued 8 May 2025) apply to all lending relationships involving digital platforms (including Paytm). The Directions require:
- Transparent terms and conditions.
- Clear disclosure of charges and repayment schedules.
- No deceptive practices.
- An in-built grievance redressal mechanism.
- Any credit relief measures (e.g. loan restructuring, payment deferrals) must be board-approved by the lender and offered fairly (no cherry-picking).

### 5.2 EDI holiday as a pre-agreed policy

**Chhatri's design:** After a payout, Chhatri requests the lender to defer the next day's loan instalment (EDI). The lender applies a pre-agreed policy rule:
- Loan is active (not REPAID, DEFAULTED, CANCELLED).
- Borrower is not in arrears (zero or pending-resolution arrears).
- Holiday allowance is not exhausted (e.g. 2 of 3 holidays used this year).
- Lender flag is enabled (borrower has opted into EDI-holiday benefit).

**RBI compliance:** The deferral is the **lender's decision**, made under its board-approved policy. Chhatri is the initiator (via a structured request), but the lender holds the authority. This complies with the Directions: no unilateral Chhatri pause; the lender's policy is board-approved; the benefit is offered to all eligible borrowers fairly.

**Two settlement models:**
1. **Lender-deferred model (default):** The lender defers the instalment to the end of the loan tenure. The merchant's loan duration does not change; the last instalment date extends by 1 day (or multiple days if multiple deferrals apply). The merchant is told "Your ₹600 instalment is deferred to 31 December 2026" (as an example).
2. **Insurer-funded model (alternative):** Chhatri (or the insurer) pays the deferred instalment directly to the lender from the payout, so the loan terms never change. The merchant is told "Your ₹600 instalment is covered by your insurance payout" or not told at all (depending on the insurer's choice). This is similar to an EMI-protection cover.

The insurer and lender will agree on the model during the pilot.

### 5.3 Code implementation and audit

- **Request:** `backend/chhatri/ledger/instalments.py`, method `pause_next()` (X4 guard added).
- **Lender decision:** Simulated in the demo, via a pre-agreed rule in `backend/chhatri/sim/city.py`. In production, the lender's API provides this decision.
- **Audit:** Every EDI holiday request and lender decision is logged in `backend/chhatri/audit/log.py` with the request id, lender decision (granted/not granted), reason code and timestamp.

---

## 6. Data protection: DPDP Act and Rules 2025

### 6.1 DPDP Act applicability and timeline (A22)

The Digital Personal Data Protection Act, 2023 came into force on 14 Nov 2025 (phased rollout):
- **14 Nov 2025:** The Act applies. Most entities must begin preparing for the DPDP Rules.
- **14 Nov 2026:** Consent managers (intermediaries that help manage consent) must register.
- **14 May 2027:** Substantive obligations apply: consent, notices, breach reporting within 72 hours, data minimisation, deletion on request, etc.

**Chhatri's timeline:** Chhatri is being designed now (Oct 2026) to meet the May 2027 substantive obligations, so there is no rework at go-live.

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
- In the consent centre (N6, feature spec fs-07), the merchant can view their slip data. Patient names are masked as "P**** J**** (92% match)" to prevent unintended data exposure.
- In reports shared with the insurer, merchant names are replaced with merchant IDs.

### 6.4 Children

Chhatri is only for merchants (adults, age ≥ 18). No data is collected on children. Dependants are not in scope.

### 6.5 Notices and requests

**Initial notice (at cover purchase):**
Chhatri shows a data notice in the mini-app:
- What data is collected (sales, Soundbox, hospital slips).
- Why (claims and premium calculation).
- How long it is kept (7 years for claims disputes; slip data deleted 30 days after claim closure).
- The merchant's rights (view, correct, delete, withdraw consent).
- Contact for data requests (support phone and email).

**Data subject requests:**
- Merchant can ask "What data do you have on me?" → Chhatri sends a CSV of all data in 30 days.
- Merchant can ask "Fix my KYC name." → Chhatri updates it and confirms in 7 days.
- Merchant can ask "Delete my slip." → After the claim is closed, Chhatri deletes it in 30 days.

---

## 7. AI governance: RBI FREE-AI framework (A23)

### 7.1 The 7 sutras and Chhatri's design

RBI released the FREE-AI committee report on 13 Aug 2025. It is advisory (not yet binding directions) but sets out 7 sutras for responsible AI in the financial sector:

| Sutra | Meaning | Chhatri's design |
|---|---|---|
| **Trust** | AI systems must be trustworthy and auditable. | (1) Policy engine is pure code (no LLM); (2) Audit log is hash-chained; (3) `GET /api/audit/verify` allows anyone to verify a decision's authenticity. |
| **People First** | AI must respect human autonomy and protect vulnerable groups. | (1) Every merchant can dispute a decision; (2) A human reviews doubtful hospital-cash claims (REFERRED); (3) No automated collection or wage deduction (decisions are settled via Paytm only). |
| **Innovation** | AI can improve financial inclusion and efficiency. | (1) Area claims are decided in 4 minutes (vs 30–60 days today); (2) Area trigger uses the merchant's own sales data (novel); (3) Hospital-cash uses live document reading (Gemini or Sarvam). |
| **Fairness** | AI decisions must not discriminate. All eligible merchants are paid the same formula. | (1) Formula is identical for all merchants in the same zone; (2) Name-match threshold (85%) is uniform; (3) Dispute SLA (24 hours) is uniform; (4) Backtest shows basis risk (not all losses are caught, and some false positives occur); (5) Exclusions are clear (e.g. non-Red alerts are not covered). |
| **Accountability** | Developers and institutions must take responsibility. | (1) Chhatri logs every decision and its reasoning; (2) Insurer (not Paytm) is accountable for underwriting; (3) Paytm (distributor) and insurer (underwriter) are both liable under insurance law. (4) Every test is named and measured (1,711 backend tests, 262 frontend tests). |
| **Explainability** | Merchants must understand why a decision was made. | (1) Every decision shows the formula: expected day, drop %, cap, and final amount; (2) Every check result is shown (e.g. "Name match: 92% (passes threshold of 85%)"); (3) Ask Chhatri answers coverage questions grounded in clauses C1–C12; (4) No black-box numbers. |
| **Resilience** | Systems must fail gracefully and recover. | (1) Fallback AI providers (Gemini → Sarvam → deterministic templates); (2) Fallback messengers (Sarvam → browser Web Speech); (3) In-process workflows on the demo laptop (no network required). |

### 7.2 LLM authority

**Principle (docs/SPEC.md §0.2):** "The AI builds the case; code decides the money."

**Implementation:**
- **Ask Chhatri (N2):** An LLM (Gemini or Sarvam) answers coverage and claims questions. But:
  - The answer is grounded only in the policy wording (clauses C1–C12) and the merchant's own decision facts (from the decision table).
  - The LLM is guarded (docs/SPEC.md §13.3): no digit that is not in the decision facts; no promises of money.
  - Any money figure shown to the merchant must have a corresponding check in the decision record.
  - If the LLM cannot find a grounded answer, it says "I don't know; let me connect you to a person."
- **Slip reading (N3):** Gemini Vision or Sarvam Vision extracts patient name, admission/discharge dates and hospital. But:
  - The extracted confidence scores are shown to the merchant.
  - Below the confidence gate (0.80), the case is referred to a human.
  - The merchant can see the extracted fields and retake the photo if it is unclear.

**No LLM payout authority:** The policy engine (`backend/chhatri/policy/engine.py`) is the only code that can produce an APPROVED decision. The LLM has no authority over money.

### 7.3 Human involvement

Humans are involved in:
- **REFERRED hospital-cash claims:** When a slip does not quite pass the automatic checks (e.g. name is 88% match), a claims officer reviews and approves or declines.
- **Disputes:** When a merchant disputes a decision, a person re-checks the numbers.
- **Escalations:** When a merchant escalates to the insurer or IRDAI, a person handles it.

### 7.4 Evals and guardrails

**Ask Chhatri eval set (N2):**
- 30+ test questions covering coverage, claims, disputes, premiums, EDI holidays, exclusions.
- Each question has a ground-truth answer from the policy wording.
- The LLM's answer is scored on factuality (exact match or near-match) and grounding (all claims backed by policy text or decision facts).
- Target: ≥ 95% factual accuracy.

**Guard tests (X7):** A test suite enforces honest wording:
- Merchant-facing templates are rejected if they use absolute language ("guaranteed", "100%", "always").
- No payout amount is shown unless it is in the decision facts.
- No "paid" message appears before a payout record exists.

**Model card:** See `docs/04-engineering/ml-model-card.md` for the expected-sales model (LightGBM quantile). Backtest and basis risk are published.

---

## 8. Messaging: WhatsApp and in-app

### 8.1 WhatsApp Business API (A18)

**Setup:** Chhatri uses the WhatsApp Cloud API. In the demo, a test number is used (no business verification required). In production, Paytm will use its verified business number.

**Rules (A18):**
- **Free-form replies (inside 24-hour window):** No cost. If the merchant replies to any message from Chhatri within 24 hours, Chhatri can send a free-form reply (e.g. "Hi, I received your message. Let me check that for you").
- **Proactive messages (outside 24-hour window):** Must use an approved template. Template examples:
  - "Hi [name], a Red alert is issued for your zone. Your cover is active. Stay safe."
  - "[name], Your claim of ₹1,380 has been approved and will be credited today."

**Chhatri's approach:** Merchant-facing copy is in `backend/chhatri/conversation/messages.py`. Every message is templated (no free-generation; see docs/SPEC.md §4.1). Opt-in consent is collected at cover purchase. Opt-out is available anytime.

### 8.2 In-app messaging

All claims decisions, disputes, EDI holidays and grievance updates are shown in the merchant mini-app (N1) in Hindi and English. WhatsApp is the secondary channel (opt-in backup).

---

## 9. Compliance checklist

This table summarizes the regulatory requirements and Chhatri's design responses.

| # | Requirement | Source | Chhatri design | Status | Owner | Evidence |
|---|---|---|---|---|---|---|
| 1 | Insurer underwrites; broker distributes. | Insurance Act 1938 | Partner general insurer underwrites; Paytm Insurance Broking distributes. Paytm does not underwrite. | Design | Omkar Kadam | fs-* docs, commercial discussions (pilot plan) |
| 2 | Cover starts only when premium is received (cash before cover). | Insurance Act 1938, s.64VB | First 30 days: prepayment via link. Then: daily settlement deduction under standing consent. Every payout is audited to confirm premium receipt before claim date. | Design | Omkar Kadam | docs/SPEC.md §9.6; policy-wording.md C6 |
| 3 | Parametric product must be filed with IRDAI. | IRDAI guidelines | Insurer files via standard process or regulatory sandbox. Chhatri provides rules, logic and backtest evidence. | Planned (post-hackathon) | Omkar Kadam | docs/01-strategy/current-state-audit.md; docs/02-product/feature-specs/fs-01-area-auto-claim.md |
| 4 | Area claims processed transparently with a formula. | IRDAI health insurance circular (A24) | Formula shown to merchant: expected day × drop % × 0.5, capped at ₹2,500. All numbers are in the decision and audit log. | Live (demo) | Ujjwal Pardeshi | backend/chhatri/policy/explain.py; docs/02-product/prd.md |
| 5 | Hospital-cash claims with ≤ 1-hour decision (cashless). | IRDAI Master Circular (A24) | Chhatri's decision: automatic if checks pass; human review (REFERRED) within 24 hours if borderline. More generous SLA than IRDAI's 1 hour (design choice for a hackathon). | Live (demo) | Ujjwal Pardeshi | backend/chhatri/policy/engine.py; docs/SPEC.md §9 |
| 6 | Grievance ladder: GRO → Bima Bharosa → Ombudsman. | Insurance Ombudsman Rules 2017 | Chhatri shows the ladder in the tracker. Insurer GRO is the entry point. | Design (N5) | Omkar Kadam | docs/02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md |
| 7 | Dispute resolution SLA. | IRDAI guidelines | 24-hour SLA for a dispute response. | Live (demo) | Ujjwal Pardeshi | backend/chhatri/policy/engine.py; policy-wording.md C9 |
| 8 | Lending: EDI holiday is the lender's decision, not Chhatri's. | RBI Digital Lending Directions 2025 (A25) | Chhatri requests; lender decides via pre-agreed rule (X4: active loan, not in arrears, holiday allowance, flag enabled). Lender decision is logged and audited. | Design (X4 planned) | Omkar Kadam | docs/02-product/feature-specs/fs-03-edi-holiday.md; backend/chhatri/ledger/instalments.py |
| 9 | No unilateral loan restructuring without board approval. | RBI Digital Lending Directions 2025 (A25) | EDI holiday is the lender's board-approved policy. Chhatri initiates the request; lender executes. All merchants are treated equally. | Design | Omkar Kadam | docs/02-product/feature-specs/fs-03-edi-holiday.md |
| 10 | Purpose-specific consent for data use. | DPDP Act 2023, DPDP Rules 2025 (A22) | Sales data: purpose "claims and premium"; withdrawable. Slip data: purpose "claim verification"; deleted after closure. Both collected in the mini-app with explicit consent. | Design (N6 consent centre) | Omkar Kadam | docs/02-product/feature-specs/fs-07-cover-purchase-and-consent.md; policy-wording.md C11 |
| 11 | Data minimisation; no unnecessary PII collection. | DPDP Act 2023 (A22) | Chhatri collects only: merchant ID, phone, KYC name, sales, Soundbox, hospital slip (name, dates, hospital). No personal email, home address, dependant data or detailed health records. | Design | Omkar Kadam | docs/04-engineering/data-model-and-api.md |
| 12 | No data on children; no automated decisions affecting children. | DPDP Act 2023 (A22) | Cover is for merchants (age ≥ 18) only. No data on children collected. Merchant's own coverage is limited by policy (e.g. hospital claims only for the merchant, not dependants). | Design | Omkar Kadam | policy-wording.md (scope) |
| 13 | DPDP compliance timeline and phased obligations. | DPDP Rules 2025 (A22) | Timeline: 14 May 2027 for substantive obligations. Chhatri is designed to meet May 2027 requirements now (phased compliance feasible by then). | Design | Omkar Kadam | Section 6 (DPDP Act applicability and timeline); docs/02-product/feature-specs/fs-07-cover-purchase-and-consent.md |
| 14 | AI governance: LLM does not decide money. | RBI FREE-AI report (A23) | Policy engine is pure code; LLM (Ask Chhatri) is a grounded assistant only. Human review for doubtful cases. Audit log records all decisions. | Live (N2 backend) | Ujjwal Pardeshi | docs/04-engineering/ai-architecture-and-guardrails.md; policy-engine.md (K4, K5) |
| 15 | AI: Trust, People First, Innovation, Fairness, Accountability, Explainability, Resilience. | RBI FREE-AI report (A23) | Mapped in section 7.1 above. Audit log and evals are in place. Fallback providers and messengers reduce reliance on a single AI service. | Design | Omkar Kadam | docs/04-engineering/ai-architecture-and-guardrails.md; Section 7 (AI governance) |
| 16 | Opt-in for WhatsApp messaging; approval of templates. | WhatsApp Business API (A18) | Consent collected at cover purchase. Templates are in the message catalogue (backend/chhatri/conversation/messages.py). Outside 24-hour window, templates only. | Live (demo, with test number) | Ujjwal Pardeshi | docs/SPEC.md §16 |
| 17 | Audit trail: every decision is logged and tamper-evident. | General best practice; DPDP (breach reporting requires audit trail). | Hash-chained audit log in SQLite. `GET /api/audit/verify` recomputes hashes. Wall-clock times are excluded from the hash (only simulated time). | Live | Ujjwal Pardeshi | docs/04-engineering/system-architecture.md; backend/chhatri/audit/log.py |
| 18 | No hardcoded secrets; secret management. | General best practice | All secrets from environment (`.env`). `make env` generates random keys. `.env.example` lists the keys but has no values. Demo mode generates a demo token if none is set. | Live | Ujjwal Pardeshi | docs/SECURITY.md; backend/chhatri/config.py |
| 19 | Rate limiting and fraud prevention. | General best practice | In-memory sliding window (60 s): webhooks 60/min, uploads 20/min, phone messages 60/min. Type validation by magic bytes (images, audio). File size limits (5 MB images, 30 s audio). | Live | Ujjwal Pardeshi | docs/SECURITY.md |
| 20 | CORS and cross-origin security. | General best practice | Only `CHHATRI_CONSOLE_ORIGIN` allowed, no credentials. Console is same-origin via nginx. | Live | Ujjwal Pardeshi | docs/SECURITY.md |

---

## Open questions

1. **Insurer and counsel confirmation (immediate):** Can we confirm the s.64VB design (section 3.1) and the cash-before-cover mechanics with your compliance team? Owner: Omkar Kadam.

2. **Parametric product filing (post-hackathon):** Is the regulatory sandbox route the insurer's preference, or is a standard filing acceptable? What is the expected timeline for product filing? Owner: Omkar Kadam.

3. **EDI holiday: deferral vs insurer-funded (immediate):** Which settlement model for the EDI holiday does the lender prefer — deferral to the end of the loan tenure, or insurer funding from the payout? Are there board-approval requirements or regulatory approvals needed? Owner: Omkar Kadam.

4. **Lending partner agreement:** Which partner lender will confirm the pre-agreed rule (X4) and the EDI-holiday mechanics? Owner: Omkar Kadam.

5. **Hospital network:** Which hospitals are eligible for hospital-cash claims? Should Chhatri maintain a whitelist, or is any government or registered private hospital acceptable? Owner: Omkar Kadam.

6. **DPDP consent manager:** Will Paytm or the insurer use a DPDP consent manager, or handle consent directly? Timeline? Owner: Omkar Kadam.

7. **Grievance redressal:** Where is the insurer's GRO located, and what is the escalation process? How are REFERRED cases and disputes routed to the GRO? Owner: Omkar Kadam.

8. **Messaging and notifications:** Are there additional regulatory requirements or sector-specific guidelines (e.g. RBI or IRDAI) for WhatsApp notifications about payouts or claims? Owner: Omkar Kadam.

9. **Audit and compliance reporting:** What is the insurer's reporting cadence to IRDAI (e.g. monthly, quarterly)? What metrics or KPIs are required (e.g. claim acceptance rate, dispute rate, basis-risk metrics)? Owner: Omkar Kadam.

10. **Regulatory sandbox timeline:** If the insurer chooses the sandbox route, when can an application be filed, and what is the expected sandbox period? Are there specific caps on payouts during the sandbox phase? Owner: Omkar Kadam.

---

## Changelog

- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; all regulatory positions correctly use future tense for partnerships and future obligations.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.2 · logic and truth audit fixes.
- 2026-10-02 · v1.1 · fact-check pass.
- 2026-10-02 · v1 · first draft, covering roles, insurance positions, claims mechanics, lending, DPDP, AI governance, messaging, compliance checklist and open questions.
