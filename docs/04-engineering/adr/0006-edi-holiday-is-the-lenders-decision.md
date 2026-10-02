# 0006: EDI holiday is the lender's decision

| | |
|---|---|
| Status | Accepted |
| Owner | Omkar Kadam |
| Date | 2026-10-02 |
| Related | [SPEC §9.5, §17.1](../../SPEC.md) · [PRD, K3](../../02-product/prd.md) · [Facts and sources (B, regulatory section)](../../01-strategy/facts-and-sources.md) · [RBI (Digital Lending) Directions 2025 (A25)](../../01-strategy/facts-and-sources.md) |

## TL;DR

When a merchant receives an approved payout, Chhatri can **request** that the lender pause the next instalment (EDI holiday), citing the decision id. The lender's own board-approved policy decides: the loan must be active, not in arrears, and the holiday allowance must not be used up. This is reframed from the early prototype's "Chhatri pauses the instalment," which was unilateral and legally risky. RBI (Digital Lending) Directions, 2025 (A25) make the lender the decision-maker. Chhatri is a **requester**, not an authority over the loan.

## Context

**Early prototype issue:** the code showed a comment "instalment paused" without checking the loan's state or the lender's policy. This is problematic because:

- The lender (NBFC or bank) owns the loan contract. Paytm acts as a settlement agent, not a lender.
- RBI Digital Lending Directions 2025 (A25) require any deferral or restructuring to be the lender's decision under its written policy, not Paytm's unilateral action.
- If a deferral is mislabeled as not being a restructuring (or vice versa), the lender's compliance team can face action.

**Regulatory clarification:** s.64VB of the Insurance Act 1938 does not require the insurer to pay the loan; it only requires cover to start after premium is received. The EDI holiday can be:

1. **Insurer-funded:** the payout amount is reduced by the instalment, so the loan terms never change (alternative lender setting, K3 open question).
2. **Lender's decision:** the lender pauses the instalment under a pre-agreed rule, and it is either a deferral (rescheduled later) or a waiver (forgiven). The rules must be documented.

**Use case:** Anil is paid ₹1,380 on day D. His ₹600 instalment is due on day D+1. Chhatri sends a message to the lender: "Merchant S-0142 received payout decision C-2291. Holiday allowed?" The lender checks: loan is active, balance is not past due, and Anil has one holiday left this quarter. Lender responds: "Holiday granted; instalment moved to [date]." Anil sees: "Your ₹600 instalment is paused until [date]."

## Decision

**Chhatri's role:**

1. After an APPROVED payout, check if a follow-up EDI holiday request should be sent to the lender (currently always yes, but this is parameterizable).
2. Call `POST /api/merchants/{id}/edi-holiday-request` with:
   - `payout_decision_id`: the id of the approved payout decision (decision ids start with D; C-2291 is a case id, not a decision id).
   - `payout_amount_rupees`: the amount paid.
   - `merchant_loan_id`: if Paytm has it.
3. The lender (simulated in the demo) responds with:
   - `granted: true/false`.
   - `holiday_end_date`: when the instalment is rescheduled (if granted).
   - `reason`: why granted or denied (e.g., "loan in arrears" → not granted).
4. Chhatri logs the response in the audit trail (K7) and shows the merchant the decision: "Your ₹600 instalment is paused until [date]" or "The lender could not grant a holiday because [reason]. We will follow up."

**Code enforcement (X4 guard):**

- Never call the EDI request without a successful payout decision.
- Never skip the lender's approval check; do not assume it is granted.
- Log the lender's response and show it to the merchant.
- A test enforces: "if payout is APPROVED, an EDI request is sent; if lender denies, no instalment is marked paused in the merchant's view."

**Wording change:**

- Old: "Your instalment is paused."
- New: "We've requested a ₹600 instalment pause with your lender. Here's their decision: [paused until X / not granted, reason]."

**Alternative lender setting (K3 open question):**

Some lenders may prefer the insurer to pay the instalment, so the lender's records never show a deferral. The rule then becomes:

- `payout_to_merchant = payout_amount − next_instalment`.
- `payout_to_lender = next_instalment`.

This is a payout-split, not a restructuring. It is deferred to the pilot phase.

## Alternatives considered

1. **Unilateral EDI pause by Chhatri (rejected):** update the loan state directly without asking the lender. Pro: instant; no external call. Con: illegal (violates RBI Directions); regulatory risk; the lender's compliance system becomes out of sync with the merchant's view.

2. **Lender pre-approval at cover purchase (considered):** when a merchant buys cover, get pre-signed permission to pause instalments (e.g., "up to ₹5,000 per quarter"). Pro: faster at payout time. Con: requires legal agreement with the lender; not scalable across many lenders; adds friction to the cover purchase.

3. **Automatic instalment reduction (rejected):** instead of a pause, reduce the next instalment by the payout amount (e.g., ₹600 → ₹0, leaving balance for later). Pro: no lender communication needed. Con: the loan's amortization schedule is broken; the lender's system must handle partial payments; not standard.

## Consequences

**Positive:**

- **Regulatory compliance:** Chhatri respects RBI Directions 2025; the lender is the decision-maker.
- **Transparency:** the merchant sees the lender's decision, not a promise from Chhatri.
- **Auditability:** every EDI request and response is logged with timestamps and decision ids.
- **Pilot-ready:** the design scales to multiple lenders, each with their own policy and holiday limits.

**Negative:**

- **Latency:** an EDI request adds 1–2 s to the payout workflow (lender API call). In the demo, the lender response is simulated and instant.
- **Failure mode:** if the lender denies, the merchant sees "instalment not paused." This may be unexpected. Mitigate: clear messaging and a follow-up option to contact the lender's support.

**Risks:**

- **Lender policy ambiguity:** different lenders may interpret "active" or "arrears" differently. Mitigate: the pilot design includes a lender-policy matrix (holidays per quarter, arrears threshold) confirmed with the partner.
- **Timing:** if the EDI request is sent late (e.g., after the instalment is already deducted), it is too late. Mitigate: send the request within 1 minute of the payout being credited (orchestration timing, X8).
- **Coverage:** if a merchant has multiple loans, which one's instalment is paused? Mitigate: Chhatri sends the request for the loan linked to the Paytm device (usually one per merchant).

## How we will know it was right

**Signals:**

1. Every payout decision (APPROVED) has a matching EDI request in the audit log.
2. The merchant's tracker shows the lender's decision ("paused until X" or "not granted, reason").
3. The UI wording never says "Chhatri paused" but always "We requested ... the lender decided."
4. A test enforces: if a lender denies the EDI request, the merchant does not see "paused" (X4 guard).
5. A partner lender can review the EDI request format and policy matrix and confirm alignment.

## Follow-ups

- **Task:** Implement the EDI request endpoint and mock lender responses (Ujjwal).
- **Task:** Add the EDI decision to the merchant's claim tracker (Omkar, N1 screen 4).
- **Task:** Write a test for the EDI request and lender response flow (both).
- **After the hackathon:** Consult with a lender partner on their policy (e.g., max holidays per quarter, arrears thresholds, restructuring vs deferral treatment).

## Open questions

1. Should the insurer-funded alternative (payout split) be included as a feature flag for the pilot, or deferred? Owner: Omkar Kadam.
2. If a lender denies the EDI holiday, should Chhatri offer to reduce the next instalment from the payout? Owner: Omkar Kadam.
3. How long does a typical lender take to respond to an EDI request (SLA)? Should Chhatri time out after 10 s and assume denial? Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly establishes EDI holiday as lender's decision with Chhatri as requester.
- 2026-10-02 · v1 · first draft.
