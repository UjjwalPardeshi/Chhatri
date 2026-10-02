# 0007: Hospital-cash framing

| | |
|---|---|
| Status | Accepted |
| Owner | Omkar Kadam |
| Date | 2026-10-02 |
| Related | [SPEC §9.3](../../SPEC.md) · [PRD, K2](../../02-product/prd.md) · [Feature spec fs-02](../../02-product/feature-specs/fs-02-hospital-cash-claim.md) · [Facts and sources (A16)](../../01-strategy/facts-and-sources.md) |

## TL;DR

The personal claim (when a merchant is hospitalized and silent) is reframed as a **hospital-cash income claim**: the merchant was hospitalized, lost sales income for those days, and submits one hospital discharge slip as proof. This walks the track's health-insurance example (Track 2: "simplify health insurance claims") end to end. The alternative of a separate family health-insurance assistant is out of scope and dilutes the income-cover narrative.

## Context

**Track example:** "How might we simplify the Health Insurance claims journey using AI—from understanding policy coverage and submitting documents to tracking claims and resolving customer queries?"

**Two interpretations:**

1. **Health insurance for the merchant's family:** cover hospitalizations of spouse, children, etc. Claim: "My wife was hospitalized; approve a ₹2 lakh claim." Complexity: family member KYC, multiple slips, benefit limits per person, waiting periods per condition.

2. **Hospital cash for lost merchant income:** when the merchant is hospitalized, income stops. Claim: "I was hospitalized; cover my lost income during those days." Proof: hospital discharge slip with admission/discharge dates. Payout: ₹X/day × days in hospital, income-loss style.

**Choice:** the team chose (2) because:

- It stays within the **income cover** narrative (Chhatri's core product).
- It demonstrates the full track example in 3 minutes (hospital slip reading → income proof → decision → payout).
- It integrates with the area-income trigger: a merchant's silent day flags a possible hospitalization, which triggers a proactive check-in (K2).
- It avoids the complexity of family KYC and multiple benefit limits.

**Standard product analogy:** hospital daily cash is a standard insurance product (A16). It pays a fixed amount per 24 h in hospital, regardless of the bill. Chhatri's variant ties it to income: it replaces lost income during the hospitalization.

## Decision

**Personal claim scope (K2):**

1. **Trigger:** merchant is silent (zero sales) for one full day.
2. **Proactive check-in (N4):** Chhatri sends a voice WhatsApp: "Hi Anil, haven't seen you since yesterday. All okay?" (in Hindi, via Sarvam TTS).
3. **Merchant reply:** "I was in the hospital" (detected via intent classifier).
4. **Slip submission:** merchant sends a photo of the hospital discharge slip.
5. **Extraction (N3):** Gemini or Sarvam vision reads: patient name, admission date, discharge date, hospital name, document type.
6. **Pre-check (H5):** the extracted fields are shown to the merchant with a readiness checklist:
   - Photo readable? (no blur, crop)
   - Name matches KYC? (≥85% rapidfuzz token-set ratio)
   - Dates are within the silent days? (e.g., admitted 20 Aug, discharged 21 Aug, merchant was silent 20–21 Aug)
7. **Decision (policy engine, K2):**
   - HARD checks: cover is active, premium has been paid, at least one day of silence is verified.
   - SOFT checks: slip is readable (confidence ≥80%), name matches KYC (≥85%), dates align.
   - APPROVED: 50% of expected daily income × days in hospital, capped at ₹1,500/day and 3 auto days.
   - SOFT fail: REFERRED to a human (officer reviews, can override confidence thresholds).
   - HARD fail: DECLINED (cover not active, premium not paid).
8. **Payout:** if APPROVED, credit in 4 minutes (simulated payout rail), then request EDI holiday (K3) at 5 minutes.

**Claim form: minimal.**

The merchant submits only:
- One hospital slip (photo).

No requirement for:
- Multiple documents (bill, prescription, doctor note).
- Income proof (Chhatri already has sales data).
- Deductible or copay calculation.

**Product framing:**

In the policy wording (C3, K2):

> **Hospital-cash income claim:** If you are hospitalized for one or more consecutive days, we cover the income you lost during those days. Submit a hospital discharge slip showing your admission and discharge dates, and we will cover 50% of your expected daily income (capped at ₹1,500/day) for each day in the hospital, up to 3 days automatically. Beyond 3 days, we will review with you.

**Not covered:**

- Hospitalizations for pre-existing conditions (waiting period applies).
- Intentional self-harm or substance abuse (standard exclusions).
- Outpatient claims (we cover days the merchant was not in the hospital only if area income trigger fires).

## Alternatives considered

1. **Family health-insurance assistant (rejected):** a separate product for merchant's dependents. Pro: broader coverage; attracts health-focused insurance partners. Con: requires family KYC, multiple slips per claim, higher complexity; dilutes income-cover message; does not fit a 3-minute demo; opens new regulatory questions (family health vs income).

2. **Merchant disability insurance (considered):** instead of hospitalization, cover temporary disability (merchant cannot sell due to injury). Pro: broader relevance. Con: hard to verify without documentation (no discharge slip); easier to fake; requires doctor's note; less standard.

3. **Hospital reimburser (rejected):** cover actual hospital bills instead of income. Pro: standard product. Con: requires bill submission, itemization, policy limits per condition, deductible; medical underwriting is complex; goes beyond Paytm's risk model.

## Consequences

**Positive:**

- **Track alignment:** the claim demonstrates the full health-insurance track example, demonstrating AI's role in claim resolution.
- **Simplicity:** one document (slip); minimal form; no family KYC.
- **Income focus:** consistent with Chhatri's core narrative (income cover for merchants).
- **Deterministic validation:** hospital discharge slip is a standard document; date ranges and name matching are checkable.
- **Pilot-ready:** a partner insurer can underwrite this quickly; it is a subset of standard health insurance (hospital daily cash).

**Negative:**

- **Scope risk:** judges may expect "family health insurance" since the track mentions health. Mitigate: in the pitch, clearly say "hospital-cash **income** claim" and explain the link to income protection.
- **Coverage gaps:** a merchant hospitalized for 5 days can only auto-claim 3 days. This may feel incomplete. Mitigate: explain it is a limit to keep payouts predictable; beyond 3 days, a human reviews.

**Risks:**

- **Fraud:** merchants could submit fake discharge slips. Mitigate: implement signature verification (future) or partner with a hospital verification service; for now, the human review for edge cases (REFERRED) catches obvious fakes.
- **Medical privacy:** hospital slips contain medical details. Mitigate: comply with DPDP (A22) by storing slip images only while a claim is open, then delete; mask non-relevant fields; get explicit consent for each slip.

## How we will know it was right

**Signals:**

1. In the 3-minute demo, the merchant submits a slip, Chhatri reads it in <3 s, and the payout is decided in <5 s (end-to-end).
2. The claim tracker shows the steps (Detected → Checked → Decided → Paid) with plain reasons.
3. A judge can verify the ₹1,500 payout from the expected daily income and the days in hospital (formula shown in the decision).
4. The policy wording (C3) is accepted by a partner insurer as within their underwriting guidelines.
5. Ask Chhatri correctly answers: "Can I claim if I'm hospitalized for 5 days?" with "Yes, up to 3 days auto; beyond that, we review with you."

## Follow-ups

- **Task:** Build the slip pre-check UI (H5) showing extracted fields and the readiness checklist (Omkar, N3).
- **Task:** Implement Gemini/Sarvam vision integration with fallback to Tesseract (Ujjwal, N3).
- **Task:** Write tests for the personal claim policy engine, including edge cases (date mismatches, name fuzzy match, low confidence).
- **Task:** Add REFERRED cases to the officer console queue with a "review slip confidence" action.

## Open questions

1. Should the 3-day auto limit be per calendar year, per rolling 12 months, or per policy year? Owner: Omkar Kadam.
2. If a merchant has multiple hospitalizations in the same calendar day (unlikely but possible), how are they aggregated? Owner: Ujjwal Pardeshi.
3. Is the slip confidence threshold (80%) and name-match threshold (85%) calibrated against real slip data, or should they be adjusted post-launch? Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly frames hospital-cash as income claim with proper decision outcomes.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: verified ADR 0007 correctly frames hospital-cash as income claim and scopes extraction to Sarvam/Gemini/Tesseract with fallback order; no changes needed (compliant with canonical framing).
- 2026-10-02 · v1.1 · fact-check pass: fixed HARD fail outcome from BLOCKED to DECLINED (claim outcomes are APPROVED/REFERRED/DECLINED only); reworded "verify" to note the formula is shown; removed overclaiming risk on the backtest.
- 2026-10-02 · v1 · first draft.
