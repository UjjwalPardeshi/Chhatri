# Metrics and impact

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Judges, team, pilot partners |
| Related | [Facts and sources](../01-strategy/facts-and-sources.md) · [Current-state audit](../01-strategy/current-state-audit.md) · [Personas](personas-and-jtbd.md) · [Pilot plan](../05-business/go-to-market-and-pilot-plan.md) |

## TL;DR

- **North star:** Time from loss to money. Today: 30–60 days. Chhatri target: same day.
- **Guardrails:** Loss ratio on target, zero unsupported payout figures in explanations, human review of all unclear cases.
- **AI quality:** Ask Chhatri grounded-answer rate ≥95% on the eval set; slip-field extraction ≥90% accuracy on a labelled sample.
- **Backtest:** Specification validation on simulated sales and real rainfall; Chhatri paid 60% of real drops vs 33% for weather-only, but also 29% of payouts lacked a real drop vs 85% for weather-only.
- **Pilot success:** Dispute rate <5%, first-contact resolution >70%, merchant adoption >30%, lender EDI-holiday acceptance 100%.

## 1. North star: time from loss to money

### What it is

The number of hours from the merchant's loss event to credit in their Paytm account.

### Today

- **30–60 days** (A3) for area claims (e.g. weather, weather events hitting the shop). Multiple documents. Manual underwriting. Paytm's merchant protection plan exemplifies this.
- **Weeks** (A9) for parametric claims (e.g. SEWA heat insurance), because the insurer must aggregate claims and verify the trigger before settling.

### Chhatri target

- **Same day.** The decision happens at 17:00 when the trigger fires. The credit rides on that evening's settlement (typically 19:00–21:00). A merchant opens the app at 17:05 and sees the money.
- **Note on settlement:** The payout rail delay is 4 minutes in the rules (K3, SPEC §4.2). Evening settlement to the lender is Paytm's existing rail, typically 2–4 hours after the decision.

### Measurement

Measured from `audit_log.triggered_at` (the moment the alert fires and the sales-drop trigger is checked) to `audit_log.credited_at` (when the settlement rail confirms the credit). Captured in the audit log for every case.

### H0 demo

- Area claim: 4 minutes (simulated replay clock, 1 simulated minute ≈ 0.1 s).
- Hospital-cash claim: 5 minutes (after the slip is received and checked).

---

## 2. Input metrics

These are measurements of what Chhatri consumes and decides on.

| Metric | Definition | Measurement point | Proposed pilot target |
|---|---|---|---|
| **Loss rate (area)** | Percentage drop in hourly sales vs the 10th-percentile model baseline | Chhatri forecast module | Area trigger fires when drop >50% for 3 consecutive hours (SPEC §5.2) |
| **Alert accuracy** | Fraction of IMD colour-coded alerts (A11) that correspond to actual rainfall in at least one zone | Open-Meteo weather data | 100% (IMD alerts are the source of truth) |
| **Hospital-cash detection** | Fraction of silent days (0 sales) that precede a slip upload within 24 hours | Audit log, merchant `silent_days` field | >80% detected within 4 hours of silence |
| **Slip quality** | Fraction of uploaded photos that are readable by vision extraction (Sarvam Vision today; Gemini Vision PLANNED) | Slip-precheck module (N3) | >95% acceptable on first upload; <5% retakes |

---

## 3. Guardrails

These are upper or lower bounds that protect the insurer, the merchant, and trust.

| Guardrail | Definition | Enforcement | Proposed pilot target |
|---|---|---|---|
| **Loss ratio** | Payouts ÷ premiums collected | Rules engine; insurer actuary confirms | Within the partner insurer's target (typically 60–70%) |
| **False-payout share** | Fraction of payouts where a real loss did not occur (the merchant's sales did not actually drop) | Pilot analytics; audit log vs ground truth | <10% (to be refined after live data) |
| **Unsupported money figures** | Fraction of merchant-facing payout explanations that cite a number not in the decision facts | Guard in message renderer (SPEC §4.3) | 0% (enforced by code) |
| **Dispute rate** | Share of payouts that the merchant disputes within 30 days | Cases opened with grievances | <5% proposed; compare to health insurance 8% repudiation (A10) |
| **First-contact resolution** | Fraction of disputes resolved in the insurer's first response | Case outcome log | >70% proposed |
| **Human-review SLA** | Percentage of referred cases decided within 24 hours (K5) | Audit log, `decided_at` timestamp | 100% |
| **Zero authority-creep** | Fraction of decisions that came from the policy engine, not overridden by an LLM or human | Audit log decision path | 100% (only `chhatri.policy.engine` approves; humans review REFERRED; no LLM override) |

---

## 4. AI quality metrics

These measure how well the AI components perform in their specific tasks.

### Ask Chhatri (N2)

| Metric | Definition | Measurement | Proposed target |
|---|---|---|---|
| **Grounded-answer rate** | Fraction of questions that receive an answer citing at least one policy clause (C1–C12) or a fact from the merchant's records | Manual eval on 100+ merchant Q&A pairs | ≥95% |
| **Unsupported money figures** | Fraction of AI answers that mention a rupee amount not in the decision facts or policy | Automated guard (message renderer) | 0% (enforced by code guard) |
| **No-source handling** | Fraction of questions where the AI cannot ground an answer and hands off to a human | Eval set, marked `needs_human=true` | 100% (no guessing) |
| **Language accuracy** | Fraction of Hindi and English answers that are grammatically correct and use merchant-appropriate vocabulary | Native speaker review | >95% |

### Slip reading and pre-check (N3)

| Metric | Definition | Measurement | Proposed target |
|---|---|---|---|
| **Field extraction accuracy** | Fraction of labelled slip samples where Sarvam Vision (LIVE) or Gemini Vision (PLANNED) correctly extracts patient name, admission date, discharge date, hospital, and document type | Labelled sample set (150+ slips) | ≥90% on all fields |
| **Confidence calibration** | Fraction of extractions where the reported confidence (0–1 scale) matches the actual accuracy | Confusion matrix on the eval set | >85% agreement |
| **Readiness checklist accuracy** | Fraction of slips where the pre-check correctly flags missing or unreadable fields | Eval set with `is_readable` ground truth | >90% |

### Intent detection (N2 fallback)

| Metric | Definition | Measurement | Proposed target |
|---|---|---|---|
| **Intent accuracy** | Fraction of merchant questions classified into the correct intent (e.g. coverage_question, claim_status, dispute, other) | Eval set of 200+ questions | ≥85% |
| **Unknown fallback** | Fraction of questions marked UNKNOWN (not in the training lexicon) that are handed to the LLM or a human | Eval log, `intent=UNKNOWN` | <5% proposed |

---

## 5. Demo-day metrics

| Metric | Definition | Target |
|---|---|---|
| **demo-check score** | Automated validation of demo scenarios (SPEC §4.2) | 70 of 70 passed (status LIVE, commit 86575ea) |
| **3-minute cut** | Pitch flow: monsoon → area claim → payout → explanation → EDI holiday | All steps complete, under 3 minutes |
| **7-minute cut** | Pitch flow: everything in 3-minute cut, plus hospital-cash claim with slip reading, three live tests, tracker, grievance, audit | All steps complete, under 7 minutes |
| **Preflight checklist** | 15-item checklist: keys set, integrations labelled, console responsive, fallbacks work, backups tested | 15 of 15 OK |
| **Rollback readiness** | 5 fallback paths (Gemini → Sarvam → offline; n8n → in-process; live keys → demo data) | Each rehearsed on the demo laptop before the final (planned) |

---

## 6. Pilot success criteria

These hypotheses are tested in H2 (live pilot, Q4 2026 / Q1 2027) with real merchants, real rainfall, real claims.

| Hypothesis | Proposed threshold | Rationale |
|---|---|---|
| **Merchant adoption:** Share of merchants who buy Chhatri within 30 days of onboarding (at zone-specific premium, e.g. ₹18.62/day for monsoon zones) | >30% | Baseline: Paytm protection plan covers 2 lakh+ merchants, but adoption took months. Chhatri's same-day claim should accelerate. |
| **Accurate trigger:** Share of loss events where the 50%-drop threshold matches the merchant's lived experience | >75% | The area index must be credible. Merchants should feel the payout is fair. |
| **Dispute rate:** Share of payouts disputed within 30 days of credit | <5% | Chhatri uses deterministic triggers (not subjective underwriting judgment). Phase 1 shadow mode targets 80% merchant agreement on amounts (20% disagreement). Phase 2 targets <5% formal disputes because: (1) larger pilot cohort reduces selection bias; (2) Ask Chhatri reduces confusion on trigger reasoning; (3) merchants who already agreed in Phase 1 now complete live transactions. This assumes dispute resolution (Ask Chhatri, human review) in Phase 2 turns disagreement into acceptance for 75% of Phase 1 dissenters. Target will be refined post-pilot. |
| **First-contact resolution:** Fraction of disputes resolved by the insurer in the first response | >70% | A merchant should not wait for a second appeal. Ask Chhatri reduces confusion. |
| **EDI holiday acceptance:** Fraction of lender partners who grant the requested EDI holiday | 100% | Pre-agreed rules are the key. The lender must have confidence in the trigger. |
| **Lender confidence:** Fraction of lenders who renew or expand Chhatri to new merchants | >50% | The lender must see value in reduced distress and on-time repayments on shock days. |
| **Claim SLA:** Fraction of area and hospital-cash claims decided within 4 hours | >95% | Same-day is the promise. Four hours is a realistic upper bound (including slip upload and human review time). |

---

## 7. Impact model

**Objective:** Show how Chhatri reduces merchant distress and lender risk.

**Formula:**

```
Merchant Net Benefit = (Expected Loss × Payout Share × Trigger Accuracy) + (EDI Holiday Value) − Premium
```

Where:
- **Expected Loss** (assumption) = daily sales × loss probability during monsoon = ₹4,380 × 30% = ₹1,314 per monsoon day
- **Payout Share** (code) = 50% (SPEC §9.1)
- **Trigger Accuracy** (to measure) = fraction of payouts where a real loss occurred = target >90%
- **EDI Holiday Value** (assumption) = one-day merchant loan deferral = ₹600 (gives cash to restock)
- **Premium** (product) = depends on zone and risk profile; zone-specific rates apply (see scenarios below)

**Scenario 1: Hypothetical at Paytm baseline pricing (₹2/day)**
```
Benefit per event = (₹1,314 × 0.50 × 0.90) + ₹600 = ₹591 + ₹600 = ₹1,191
Cost over 365 days = ₹2 × 365 = ₹730
Net annual = (₹1,191 × ~4 monsoon events) − ₹730 = ₹4,764 − ₹730 = ₹4,034 (benefit)
```

**Scenario 2: Realistic for monsoon-exposed zone Z7 (₹18.62/day)**
```
Benefit per event = (₹1,314 × 0.50 × 0.90) + ₹600 = ₹591 + ₹600 = ₹1,191
Cost over 365 days = ₹18.62 × 365 = ₹6,796
Net annual = (₹1,191 × ~4 monsoon events) − ₹6,796 = ₹4,764 − ₹6,796 = −₹2,032 (loss)
```

**Key insight:** Real value depends on pricing power and merchant willingness to pay at zone-specific premiums. The pilot will test actual adoption and willingness in Scenario 2 zones.

**Assumptions:**
- Anil experiences 3–4 monsoon loss days per year (evidence-informed from rainfall data A13).
- EDI holiday value = deferral of one day's instalment = ₹600 (from demo numbers).
- Scenario 1 premium (₹2/day) is Paytm's existing plan baseline (A3); used to show model mechanics.
- Scenario 2 premium (₹18.62/day, ₹6,796/year) is the actual zone-specific rate for monsoon-exposed Z7.
- Lender accepts the EDI holiday (risk: open question).
- Real trigger accuracy >90% (to be measured in pilot).

**Lender Net Benefit:**
```
Lender Benefit = (Reduced Default Rate × Average Loan Value) − Cost of EDI Holiday
```

Where:
- **Reduced Default Rate** (assumption) = on shock days, Chhatri EDI holiday prevents forced EMI payment, reducing distress defaults by 20%.
- **Average Loan Value** (assumption) = ₹20,000 per merchant (typical micro-loan on Paytm, unverified).
- **Cost of EDI Holiday** (product decision) = ₹600 per event, pre-agreed and sanctioned.

**Example:**
```
Benefit = (20% × 4 events × ₹20,000 × 2% default probability reduction) − (₹600 × 4) = ₹320 − ₹2,400 (loss)
```

This is a **hypothesis to test in the pilot.** If lender default rates on Chhatri-covered merchants drop, the EDI holiday is justified.

---

## 8. Backtest findings

**Framing:** Specification validation on simulated sales and real rainfall.

The backtest runs the policy engine (`rules.yaml` pilot-0.1) over simulated merchant sales (driven by real Open-Meteo rainfall, Jun–Sep 2024 and 2025) and measures how often the trigger fires and how often a real loss occurred.

### Key numbers

| Metric | Chhatri | Weather-only trigger |
|---|---|---|
| **Real drops captured** | 89 of 148 (60%) | 49 of 148 (33%) |
| **Payouts lacking a real drop** | 36 of 125 (29%) | 287 of 336 (85%) |

Where "real drop" = simulator-defined loss of ≥40% of expected sales.

### What the backtest shows

1. **Chhatri captures more real drops than weather-only.** The 60% vs 33% difference shows the merchant's own sales data improves trigger timing.
2. **Basis risk exists.** 29% of Chhatri payouts lack a simulated real drop. This is basis risk: the zone's sales fell, but Anil's shop did not. (Counter: Anil's shop is one of 46 in the zone; the zone's loss is real. Anil benefits from pooling.)
3. **The trigger is calibrated to match the demo.** Simulation parameters are searched so Z7 shows 37% drop, producing the ₹1,380 payout (see current-state-audit.md errata).

### What the backtest does not show

- **Real-world performance.** Merchants' sales patterns may differ from the simulation. Real merchants may have backup channels (online sales, delivery) not modelled.
- **Merchant satisfaction.** A 60% detection rate may not feel fair if a merchant loses income but is not paid (the 40% miss rate).
- **Lender confidence.** The lender may see 29% false-positive payouts (paid when the merchant's specific shop did not lose) as a risk.

### Where to measure

- Backtest report: `backend/chhatri/backtest/report.py`, run via `make backtest`.
- Demo numbers (Z7 37%, ₹4,380, ₹1,380): SPEC §13.4, DEMO.md.
- Calibration code: `backend/chhatri/pipeline/day_search.py`, `level_search.py`.

---

## 9. Metric computation: where the data lives

| Metric | Audit log field | Code path | Query |
|---|---|---|---|
| **Decision time** | `triggered_at`, `decided_at`, `credited_at` | `/api/audit/verify` | SELECT avg(credited_at - triggered_at) |
| **Loss ratio** | `amount_paid_rupees`, `premium_collected` | `backend/chhatri/ledger/payouts.py` | Sum by month, divide |
| **Dispute rate** | `case_id`, `case_state` | `/api/merchants/{id}/claims`, cases table | SELECT count(*) WHERE dispute_opened=true |
| **Slip accuracy** | `slip_confidence`, `slip_fields` | `slip_precheck` response (N3) | Manual audit of extracted vs ground truth |
| **Area trigger fires** | `alert_id`, `area_index_pct`, `trigger_reason` | Trigger log in audit | SELECT count(*) WHERE trigger_reason='AREA_INDEX_BELOW_50PCT' |

---

## 10. What we will NOT claim

1. **That the backtest shows real-world performance.** It runs on simulated sales. The calibration targets the demo numbers.
2. **That every merchant will get paid when they lose income.** Basis risk exists. The zone's sales may drop, but the individual merchant's shop may have had a good day (e.g. hosted a birthday party). This is the trade-off of pooled parametric insurance.
3. **That the EDI holiday prevents all distress defaults.** Some merchants will still struggle. The holiday buys time, not solves poverty.
4. **That Chhatri replaces health insurance.** The hospital-cash claim covers lost income, not medical bills. A merchant still needs family health insurance (out of scope).
5. **That we have a partner insurer or lender confirmed.** We will approach partners after the hackathon (see go-to-market-and-pilot-plan.md).

---

## Open questions

1. **Trigger calibration:** Is the 50%-drop threshold the right one? Should it be 40% or 60%? Owner: Ujjwal Pardeshi.
2. **Basis risk tolerance:** What is the lender's acceptable false-positive rate (payouts when Anil's shop had a good day)? Owner: Omkar Kadam.
3. **Seasonal variation:** Do monsoon-season loss rates differ from non-monsoon? Should the trigger threshold adjust? Owner: Ujjwal Pardeshi.
4. **Grounding eval:** Can we build a 200-slip eval set with ground truth for slip extraction accuracy? Owner: Ujjwal Pardeshi.
5. **Pilot cohort:** What is the minimum merchant cohort (e.g. 50, 100, 500) needed to test the hypotheses in section 6 with statistical power? Owner: Omkar Kadam.

## Changelog

- 2026-10-02 · v1.4 · final consistency pass against the code
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: Slip quality and field extraction metrics clarified as Sarvam Vision LIVE, Gemini Vision PLANNED
- 2026-10-02 · v1.2 · logic and truth audit fixes
- 2026-10-02 · v1.1 · fact-check pass. Replaced internal references with public doc references.
- 2026-10-02 · v1 · first draft.
