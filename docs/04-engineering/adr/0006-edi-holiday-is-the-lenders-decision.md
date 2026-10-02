# 0006: EDI holiday is the lender's decision

| | |
|---|---|
| Status | Accepted |
| Owner | Omkar Kadam |
| Date | 2026-10-02 |
| Related | [SPEC §10, §13.4, §15](../../SPEC.md) · [fs-03 EDI holiday (K3, X4, X8)](../../02-product/feature-specs/fs-03-edi-holiday.md) · [fs-06 grievance](../../02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md) · [fs-07 consent](../../02-product/feature-specs/fs-07-cover-purchase-and-consent.md) · [fs-08 console (provider panel)](../../02-product/feature-specs/fs-08-claims-officer-console.md) · [PRD, K3 and X4](../../02-product/prd.md) · [Policy wording and CIS, C10](../../02-product/policy-wording-and-cis.md) · [Regulatory and compliance, section 5.2](../../05-business/regulatory-and-compliance.md) · [Facts and sources (A25, section B)](../../01-strategy/facts-and-sources.md) |

## TL;DR

EDI means equated daily instalment. After a payout is credited, Chhatri **asks** the merchant's lender to move the next instalment to the end of the loan. The lender answers from a rule it agreed in advance, and Chhatri tells the merchant what the lender decided.

The regulatory position (A25, to be confirmed with the partner insurer's compliance team and counsel): under the RBI (Digital Lending) Directions, 2025, any instalment deferral is the lender's decision under its board-approved policy. Chhatri can only request an EDI holiday, or have the insurer pay the instalment as part of the payout. Whether a pre-agreed holiday counts as a restructuring is for the lender's compliance team to decide.

- **BUILT today:** the `pause_instalment` step pauses the next instalment with no check and no lender answer, and the message reads as if Chhatri did it.
- **BUILT, wave 1 (X4, flag `x4_lender_request`):** the step becomes a request to a simulated lender that applies four conditions. A refusal creates no pause. The payout is never touched.

## Context

**What the code does today (BUILT).** `InstalmentService.pause_next` (`backend/chhatri/ledger/instalments.py`) pauses the instalment due on the event date plus one day, unless the merchant has no loan or that instalment is already paused. It writes an `InstalmentPause` and the audit entry `instalment.pause`, naming "Simulated lender (NBFC partner)". The `Loan` record holds an id, a lender name, a daily instalment and an outstanding amount. It has no status, no arrears and no holiday allowance, so the code cannot tell a loan that qualifies from one that does not. The merchant is told "Tomorrow's ₹600 instalment is paused." and nothing says who decided.

**Why that is not good enough.**

- The lender owns the loan contract. Chhatri is not the lender.
- Under the A25 position a deferral is the lender's decision. A message that says Chhatri paused the instalment states something Chhatri cannot do.
- A real lender would refuse some requests (a loan in arrears, an allowance used up). The merchant must hear that as the lender's answer, with the payout unaffected.

**Two ways to make the holiday real.** Both are described in the regulatory page.

1. **Lender-deferred (the default of this ADR).** The lender moves the instalment to the end of the tenure under a pre-agreed rule.
2. **Insurer-funded (alternative, not built).** The instalment is paid to the lender out of the payout, so the loan terms never change. That is a payout split, not a holiday.

The Insurance Act 1938, s.64VB (cash before cover) is unaffected: a holiday defers a loan instalment, it is not premium relief.

**Use case (monsoon replay).** Anil (S-0142) is paid ₹1,380 on decision D-000142. The credit is at 17:04. At 17:05 Chhatri sends his lender a request for the ₹600 instalment due the next day. The simulated lender finds the loan active, not in arrears and with allowance left, and grants. Anil reads (proposed wording) "Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty." C-2291 is the case id of Anil's later dispute, not a decision id.

## Decision

**Chhatri requests. The lender decides. Chhatri never changes a loan.**

1. **When.** After the payout is CREDITED, at the existing instalment step, 5 simulated minutes after the decision (17:05 for the storm), one minute after the credit. The step `pause_instalment` is renamed `request_holiday` in `backend/chhatri/workflows/definitions.py`, and the n8n files are regenerated with `scripts/n8n_workflows.py` (`make test-infra` fails on drift).
2. **Chhatri's own guards (G1 to G4), the X4 guard.** The decision is APPROVED. The payout is CREDITED. The merchant has a loan on record. No request exists yet for that loan and instalment date. If the payout is not credited, no request goes out and the skip is audited.
3. **The lender's rule (L1 to L4).** The simulated lender (new `Lender` port in `integrations/base.py`, adapter `integrations/lender.py`) grants only if all four hold. When several fail, it returns the first in this order.

   | Order | Condition | Reason code if not met |
   |---|---|---|
   | 1 | Programme flag on for the loan (L4) | `FLAG_OFF` |
   | 2 | Loan active (L1) | `NOT_ACTIVE` |
   | 3 | Not in arrears (L2) | `IN_ARREARS` |
   | 4 | Holiday allowance left (L3) | `NO_ALLOWANCE` |

   The rule belongs to the lender and is not in `rules.yaml`. The simulator's allowance (a count per rolling 365 days, illustrative value 3) is a setting of the simulator, not a Chhatri rule. With no fixture on by default, every loan holder in the storm is granted, so the KPI "instalments paused" stays at 123 and no golden number moves.
4. **The request carries only what the lender needs:** request id (`HR-` plus six digits, also the idempotency key), merchant, loan, decision id, payout id, credit time, instalment date, instalment amount, request time and the basis ("Pre-agreed rule: one instalment holiday after a credited Chhatri payout"). It carries no claim kind, no reason, no slip data and no payout amount, so a hospital-cash payout is not revealed to the lender. The exact JSON is in fs-03 section 7.3.
5. **One attempt, fail safe.** If the lender gives no answer within the time limit, Chhatri records `NO_RESPONSE` and does not pause. There is no retry, because a later grant could land after the merchant was told "not paused". Any error is treated as not granted. The time limit is a setting, with a proposed target of 10 seconds. In simulated time the wait is instant.
6. **The payout is independent.** It is credited at 17:04, before the request. A refusal or no answer changes nothing about it.
7. **No public HTTP route for the request.** It is an internal call through the `Lender` port, like the other integrations. `GET /api/merchants/{id}` gains `holiday_requests[]` (every outcome) beside the existing `pauses` (grants only).
8. **Merchant wording.** Every line names the lender as the one who decided. None says "Chhatri paused" and none promises a follow-up. A refusal says the payout is not affected and offers "Ask the lender about this", a grievance with respondent LENDER (fs-06). The five proposed keys `HOLIDAY_GRANTED`, `HOLIDAY_GRANTED_TODAY`, `HOLIDAY_GRANTED_ON`, `HOLIDAY_REFUSED` and `HOLIDAY_NO_RESPONSE` replace the three `INSTALMENT_PAUSED*` keys. Replacing them touches the catalogue, SPEC §13.4, DEMO.md and the tests that pin them, in one change (fs-03 section 8.4).
9. **Audit.** `instalment.holiday_request` and `instalment.holiday_decision` (proposed names) are new. `instalment.pause` is kept, written only on a grant, and gains the request id. The audit chain stays the record of who asked and who answered.
10. **Demo control.** The provider panel (X6, fs-08) can force the `lender` component to FALLBACK. In FALLBACK the simulated lender does not answer, so every request ends as `NO_RESPONSE` and the merchant sees the fail-safe message. A named refusal needs a loan fixture in arrears, which tests set.

## Alternatives considered

1. **Unilateral pause by Chhatri (BUILT today, rejected).** Update the loan state without asking. Pro: instant, no external call. Con: under the A25 position the deferral is the lender's decision, the lender's records and the merchant's view can drift apart, and Chhatri would be promising relief on a loan it cannot see (arrears, allowance).
2. **Standing permission at cover purchase (considered, deferred).** Get the lender's pre-signed permission to pause instalments when the merchant buys cover. Pro: faster at payout time. Con: it needs a legal agreement with each lender, adds a step to cover purchase, needs its own consent (fs-07), and the lender still decides under its own policy.
3. **Insurer-funded instalment (deferred beyond the hackathon).** Pay the next instalment to the lender out of the payout: `payout_to_merchant = payout − next instalment` and `payout_to_lender = next instalment`. The loan terms never change, and it is a payout split, not a restructuring. Con: the merchant receives less cash on the day the product is for, and the published payout arithmetic (half of the expected day times the drop) no longer matches the cash the merchant receives. The partner insurer and lender choose between the two models in a pilot.
4. **Automatic reduction of the next instalment (rejected).** Reduce the instalment by the payout amount instead of pausing it. Pro: no lender call. Con: it breaks the lender's amortisation schedule and the lender's system would have to accept partial payments.

## Consequences

**Positive**

- The merchant sees the lender's decision, in the lender's terms, not a promise from Chhatri.
- Every request and answer is in the audit chain with the decision id.
- The `Lender` port is the one place where a real lender's API would sit. The simulated lender stays a SIMULATED component and is labelled as one.
- The payout does not wait for, or depend on, the lender.

**Negative**

- Three outcomes (granted, refused, no response) mean more states in the tracker, the console and the tests.
- The demo grants every request by default. That keeps the golden numbers, and it also means the refusal path is seen on stage only when it is forced.
- The coordinated wording change touches several pinned files at once (fs-03 section 8.4).

**Risks**

- **Lender policy values are illustrative.** The programme flag, the allowance count and the arrears definition come from the partner lender, and a real lender may define "active" and "in arrears" differently.
- **Timing.** A real lender may deduct the instalment at a fixed time. The request goes out one minute after the credit in the simulation. Real deduction times are not known.
- **Several loans.** The data model holds one loan per merchant. A merchant with two loans is not modelled.
- **Consent.** Which consent purpose covers sharing the loan id, the instalment date and the payout proof with the lender is not settled (fs-07).

## How we will know it was right

1. A refusal creates no pause record and the payout stays CREDITED (`test_refusal_creates_no_pause` in `backend/tests/ledger/test_instalments.py`).
2. No merchant line says "Chhatri paused" or promises a follow-up (the honest-wording test X7 scans the `HOLIDAY_*` keys).
3. With the default lender the KPI "instalments paused" is still 123 and counts grants only (`test_kpi_counts_grants_only`).
4. A request built for a hospital-cash payout carries no claim kind, reason, slip field or amount (`test_request_carries_no_claim_reason_or_amount`).
5. On stage, forcing the lender to FALLBACK shows `HOLIDAY_NO_RESPONSE` and no pause.
6. In a pilot, a partner lender reviews the request format and the four conditions and confirms or changes them.

## Follow-ups

- Wave 1: `Lender` port and `SimulatedLender` (L1 to L4, ledger, fixtures, FALLBACK as no answer), `HolidayRequest` records with `HR-` ids, `request_holiday` with G1 to G4, the `HOLIDAY_*` messages and the coordinated change in fs-03 section 8.4 (Ujjwal, with Omkar for copy).
- Wave 1: regenerate `n8n/workflows/*.json` for the renamed step and keep `make test-infra` green.
- Wave 2: the `lender` switch in the provider panel (fs-08 section 9).
- Waves 1 and 3: tracker row, console feed line and the grievance link `EDI_HOLIDAY` (Omkar).
- After the hackathon: confirm the lender's own rule, the restructuring treatment and the time limit with a partner lender.

## Open questions

1. Does a pre-agreed holiday count as a restructuring for the lender? A compliance call by the lender. Owner: Omkar Kadam.
2. Which loan does a request name when a merchant has more than one? Owner: Ujjwal Pardeshi, with the lender.
3. Is a 10-second time limit right for a real lender API? Owner: Ujjwal Pardeshi.
4. Which consent purpose covers the sharing with the lender (a purpose in the consent centre, N6)? Owner: Omkar Kadam.
5. Should the insurer-funded alternative be a feature flag in a pilot, or stay deferred? Owner: Omkar Kadam.
6. On stage, is the X6 "no response" switch enough, or should one scenario carry an arrears fixture that shows a named refusal? It would need that scenario's golden file and DEMO.md updated. Owner: Omkar Kadam.

## Changelog

- 2026-10-02 · status synced with the working tree at the end of the build: the PLANNED parts named here are BUILT behind their flags
- 2026-10-02 · v3 · restated against the code and fs-03: today's pause is unconditional (BUILT), the lender request is PLANNED in wave 1; lender rule L1 to L4 with reason codes and a fixed order; request carries no claim data; one attempt and a fail-safe no response; the `POST /api/merchants/{id}/edi-holiday-request` route, which does not exist in the code, removed (no public route for the request); the "We will follow up" wording removed; C-2291 corrected to a case id (the decision is D-000142); the regulatory position uses the facts-page hedge, with the unsupported "illegal" claim and the invented ₹5,000 example removed; SPEC references corrected
- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly establishes EDI holiday as lender's decision with Chhatri as requester.
- 2026-10-02 · v1 · first draft.
