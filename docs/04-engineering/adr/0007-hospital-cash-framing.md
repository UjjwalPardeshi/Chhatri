# 0007: Hospital-cash framing

| | |
|---|---|
| Status | Accepted |
| Owner | Omkar Kadam |
| Date | 2026-10-02 |
| Related | [SPEC §9.3](../../SPEC.md) · [PRD, K2](../../02-product/prd.md) · [Feature spec fs-02](../../02-product/feature-specs/fs-02-hospital-cash-claim.md) · [Facts and sources (A16)](../../01-strategy/facts-and-sources.md) |

## TL;DR

The personal claim (when a merchant is hospitalized and silent) is reframed as a **hospital-cash income claim**: the merchant was hospitalized, lost sales income for those days, and submits one hospital discharge slip as proof. This walks the track's health-insurance example (Track 2: "simplify health insurance claims") end to end. The alternative of a separate family health-insurance assistant is out of scope and dilutes the income-cover narrative. The claim is BUILT as K2 (word-list intents, the Sarvam or simulated slip reader, the policy engine, the officer queue). The slip pre-check (N3, H5, H15), the voice check-in (N4) and the mini-app tracker (N1, H1) are PLANNED.

## Context

**Track example:** "How might we simplify the Health Insurance claims journey using AI—from understanding policy coverage and submitting documents to tracking claims and resolving customer queries?"

**Two interpretations:**

1. **Health insurance for the merchant's family:** cover hospitalizations of spouse, children, etc. Claim: "My wife was hospitalized; approve a ₹2 lakh claim." Complexity: family member KYC, multiple slips, benefit limits per person, waiting periods per condition.

2. **Hospital cash for lost merchant income:** when the merchant is hospitalized, income stops. Claim: "I was hospitalized; cover my lost income during those days." Proof: hospital discharge slip with admission/discharge dates. Payout: ₹X/day × days in hospital, income-loss style.

**Choice:** the team chose (2) because:

- It stays within the **income cover** narrative (Chhatri's core product).
- It demonstrates the full track example in one short demo (hospital slip reading → income proof → decision → payout).
- It reuses the sales data that drives the area trigger: a merchant's silent day (no sales in business hours, below the shop's own lowest usual day, not a weekly off, zone not in an area event) flags a possible hospitalization and triggers a proactive check-in (K2).
- It avoids the complexity of family KYC and multiple benefit limits.

**Standard product analogy:** hospital daily cash is a standard insurance product (A16). It pays a fixed amount per 24 h in hospital, regardless of the bill. Chhatri's variant ties it to income: it replaces lost income during the hospitalization.

## Decision

**Personal claim scope (K2):**

1. **Trigger (BUILT):** the merchant is silent: no sales in business hours on a completed day, and still none by 11:00 the next morning.
2. **Proactive check-in (BUILT as text):** at 11:20 Chhatri sends the catalogue message CHECKIN_SILENT: "Your shop has been closed since yesterday. Is everything okay?" (Hindi and English). A voice version through Sarvam TTS is PLANNED (N4).
3. **Merchant reply (BUILT):** "I'm in hospital with a fever" (detected by the word-list intent classifier).
4. **Slip submission (BUILT):** the merchant sends one photo of the hospital slip.
5. **Extraction (BUILT with Sarvam, live only with `SARVAM_API_KEY`, else the simulated reader):** the reader returns patient name, admission date, discharge date, hospital name and document type. Gemini vision comes first with the pre-check (N3, BUILT).
6. **Pre-check (BUILT, flag `n3_slip_precheck`, N3, H5, H15):** the extracted fields are shown to the merchant, who confirms them before any check runs, with a readiness checklist:
   - Photo readable? (no blur, crop)
   - Name matches KYC? (token-set ratio of at least 85, with initials expanded)
   - Do the slip dates cover the silent days? (e.g., admitted 20 Aug, silent day 20 Aug)
7. **Decision (policy engine, K2, BUILT):**
   - HARD checks: cover in force, premium prepaid through the day, at least one verified silent day, not already paid for the day, annual limit.
   - SOFT checks: slip readable and medical (confidence ≥ 0.80), name matches KYC (score ≥ 85), slip dates cover the silent days, at most 3 silent days.
   - APPROVED: days × the smaller of 50% of the expected day and ₹1,500. The expected day is the one of the first silent day.
   - A SOFT FAIL or UNSURE check: REFERRED to a claims officer, who re-runs all checks. A SOFT check the officer approves is recorded WAIVED_BY_OFFICER.
   - HARD fail: DECLINED (for example cover not in force, premium not prepaid).
8. **Payout (BUILT):** if APPROVED, the simulated payout rail credits 4 minutes later. Chhatri then requests an EDI holiday (K3) at 5 minutes. The lender decides (ADR 0006); today the simulated lender always grants, and X4 (Wave 1) adds its rule.

**Claim form: minimal.**

The merchant submits only:
- One hospital slip (photo).

No requirement for:
- Multiple documents (bill, prescription, doctor note).
- Income proof (Chhatri already has sales data).
- Deductible or copay calculation.

**Product framing:**

The illustrative [policy wording, C3](../../02-product/policy-wording-and-cis.md) says, in short: if your shop has a silent day and you send a hospital slip that shows your name and covers the silent days, we pay half your expected day, up to ₹1,500 a day, for up to 3 days automatically. For more than 3 silent days a person reviews the whole claim.

**Not covered:** see C7 in the policy wording. In short: medical bills (hospital-cash pays lost income only), silent days with no cover in force, and days already paid. The prototype does not check the cause of the admission. Whether the insurer would exclude pre-existing conditions or self-inflicted harm is an open question below.

## Alternatives considered

1. **Family health-insurance assistant (rejected):** a separate product for merchant's dependents. Pro: broader coverage; attracts health-focused insurance partners. Con: requires family KYC, multiple slips per claim, higher complexity; dilutes income-cover message; does not fit a short demo; opens new regulatory questions (family health vs income).

2. **Merchant disability insurance (considered):** instead of hospitalization, cover temporary disability (merchant cannot sell due to injury). Pro: broader relevance. Con: hard to verify without documentation (no discharge slip); easier to fake; requires doctor's note; less standard.

3. **Hospital reimburser (rejected):** cover actual hospital bills instead of income. Pro: standard product. Con: requires bill submission, itemization, policy limits per condition, deductible; medical underwriting is complex; goes beyond Paytm's risk model.

## Consequences

**Positive:**

- **Track alignment:** the claim demonstrates the full health-insurance track example, demonstrating AI's role in claim resolution.
- **Simplicity:** one document (slip); minimal form; no family KYC.
- **Income focus:** consistent with Chhatri's core narrative (income cover for merchants).
- **Deterministic validation:** hospital discharge slip is a standard document; date ranges and name matching are checkable.
- **A familiar product:** hospital daily cash is a standard health-insurance product (A16), which should make it easier for a partner insurer to review. Whether an insurer would underwrite it is not known.

**Negative:**

- **Scope risk:** judges may expect "family health insurance" since the track mentions health. Mitigate: in the pitch, clearly say "hospital-cash **income** claim" and explain the link to income protection.
- **Coverage gaps:** the automatic limit is 3 silent days per claim. A merchant hospitalized for 5 days has the whole claim sent to a claims officer, not 3 days paid and 2 reviewed. If the officer approves, the amount covers all 5 days (each at most ₹1,500). This may feel slow. Mitigate: explain that the limit keeps automatic payouts predictable and that a person reviews longer stays.

**Risks:**

- **Fraud:** merchants could submit fake discharge slips. Mitigate: for now, the human review of doubtful slips (REFERRED) and the annual limit of ₹30,000 over a rolling 365 days. Signature verification or a hospital verification service is a later option.
- **Medical privacy:** hospital slips contain medical details. Mitigate (N6 and H23, BUILT behind `n6_consents`): a slip consent before a slip is read, a cleaned copy (no metadata) for the provider, and "forget my slip" to delete the photo and the slip text on request. Not built: deleting images automatically when a claim closes, and keeping the name out of the check text at write time (fs-02 task N3.14).

## How we will know it was right

**Signals:**

1. In the demo, the merchant submits a slip and the decision follows at once, with the formula shown. Reading and decision times are targets until measured; none is measured yet.
2. The claim tracker shows the steps (Detected → Checked → Decided → Paid → EDI holiday) with plain reasons (N1, H1, BUILT behind `n1_miniapp`).
3. A judge can verify the ₹1,500 payout from the expected day and the number of silent days: ½ × ₹4,300 = ₹2,150 a day, capped at ₹1,500 × 1 day (shown in the decision).
4. After a pilot: the partner insurer accepts the policy wording (C3) as within its underwriting guidelines.
5. Ask Chhatri (N2, BUILT behind `n2_ask_chhatri`) answers "Can I claim if I'm in hospital for 5 days?" with the rule: up to 3 silent days are paid automatically; for more, a person reviews the claim.

## Follow-ups

- **Task:** Build the slip pre-check UI (H5, H15) showing extracted fields and the readiness checklist (Omkar, N3, Wave 2).
- **Task:** Add Gemini vision for slips with the labelled fallback chain (Ujjwal, N3, Wave 2). Tesseract is a later link ([ADR 0003](0003-free-ai-provider-chain.md)).
- **Task:** Write tests for the personal-claim edge cases: name fuzzy match, low confidence, dates that do not cover the silent days, more than 3 silent days, and a stay that crosses a month end (the engine works per day).
- **Task:** Check that REFERRED personal claims reach the officer queue with the slip image, extracted name, KYC name, score and checks (BUILT; keep it covered by tests).

## Open questions

1. The 3-day limit applies per claim, and the annual limit is ₹30,000 over a rolling 365 days (HARD). Does the partner insurer want a different annual structure? Owner: Omkar Kadam.
2. A day that is already paid for a personal claim cannot be paid again (NOT_ALREADY_PAID). Should an area payout and a hospital-cash payout for the same day both be allowed? Owner: Ujjwal Pardeshi.
3. Are the slip confidence threshold (0.80) and the name-match threshold (85) right for real slips? They have not been tested on real slips. Owner: Ujjwal Pardeshi.
4. Should the insurer exclude pre-existing conditions or self-inflicted harm? The prototype does not check the cause of admission. Owner: Omkar Kadam.

## Changelog

- 2026-10-02 · status synced with the working tree at the end of the build: the PLANNED parts named here are BUILT behind their flags
- 2026-10-02 · v2.1 · aligned with the code: check-in is CHECKIN_SILENT text at 11:20 (voice is N4); name, dates, readability and the 3-day limit are SOFT, so a REFERRED claim is decided whole by an officer; officer waives SOFT checks; silent-day definition; Gemini, pre-check and tracker marked PLANNED; Tesseract is a later link; policy wording quoted in short, exclusions deferred to C7; invented 3-minute demo and latency targets removed.
- 2026-10-02 · v2 · consistency check against the code: no changes needed; ADR correctly frames hospital-cash as income claim with proper decision outcomes.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: verified ADR 0007 correctly frames hospital-cash as income claim and scopes extraction to Sarvam/Gemini/Tesseract with fallback order; no changes needed (compliant with canonical framing).
- 2026-10-02 · v1.1 · corrections: fixed HARD fail outcome from BLOCKED to DECLINED (claim outcomes are APPROVED/REFERRED/DECLINED only); reworded "verify" to note the formula is shown; removed overclaiming risk on the backtest.
- 2026-10-02 · v1 · first draft.
