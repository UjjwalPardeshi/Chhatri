# 0001: Policy engine is the only payout authority

| | |
|---|---|
| Status | Accepted |
| Owner | Ujjwal Pardeshi |
| Date | 2026-10-02 |
| Related | [SPEC §0.2](../../SPEC.md) · [SPEC §9](../../SPEC.md) · [Data model and API](../data-model-and-api.md) |

## TL;DR

Only the policy engine (`backend/chhatri/policy/engine.py`) can produce an APPROVED decision. AI services (Sarvam today, Gemini PLANNED) help build the case: they read a slip and route a message. They never set an amount or an outcome. Code, reading `rules.yaml` (version pilot-0.1), decides the money. This gives reproducible, auditable payouts and one place for an insurer or regulator to look (SPEC §0.2, §9).

## Context

An AI hackathon in fintech naturally invites LLM-based claim approval: a grounded assistant reads the slip, computes the payout and approves it. This approach has risks:

- **Non-reproducibility:** two LLM calls on the same input may give different outputs; a merchant cannot verify how much they were paid.
- **Audit failure:** regulators and judges cannot trace an approval through an LLM's reasoning.
- **Regulatory exposure:** an insurer has to explain, document and file the rules it underwrites (to be confirmed with the partner insurer). A payout that depends on a model's answer is hard to defend.

The team's SPEC §0.2 principle, "The AI builds the case; code decides the money," inverts this: the AI assists in data gathering and reasoning, but only code produces APPROVED decisions.

## Decision

The policy engine is the **single enforcement point** for payouts. It reads the merchant's data (sales, alert state, KYC name, slip fields) and `rules.yaml` and produces a decision object with:

- Outcome: APPROVED, REFERRED or DECLINED. (BLOCKED is a cover quote outcome, never a claim outcome.)
- Amount (if APPROVED).
- Checks run and their results. HARD checks: cover in force, premium prepaid, the area-trigger checks, verified silence, not already paid, annual limit. SOFT checks: slip readable, name matches KYC, dates match, within the 3-day limit.
- Formula and source facts (for "why this amount" explanations).
- A hash-chained audit entry.

Any HARD fail gives DECLINED. A SOFT FAIL or an UNSURE check gives REFERRED. Area claims have HARD checks only, so they are never REFERRED.

Code path: `backend/chhatri/policy/engine.py`, `evaluate_area_claim()`, `evaluate_personal_claim()`. A claims officer decides only REFERRED personal claims, through `apply_officer_decision()`. It re-runs every check, and a SOFT check the officer approves is recorded as WAIVED_BY_OFFICER. A HARD fail still declines.

The AI's role:

- **Extract:** Sarvam Vision reads the hospital slip and extracts patient name, dates, hospital (live only with `SARVAM_API_KEY`, else the simulated reader). Gemini Vision is PLANNED (N3, Wave 2).
- **Route:** An intent classifier (the word list first; the chat model only for UNKNOWN text) routes the merchant's message (K5).
- **Suggest:** Ask Chhatri (PLANNED, N2) will cite policy clauses. It never suggests an amount or an approval.
- **Guard:** A guard function (PLANNED, N2, H17) will reject any answer containing a money figure that is not in the decision facts.

No money moves without the engine. The payout step (`backend/chhatri/ledger/payouts.py`) refuses any decision that is not a stored APPROVED decision, and only the engine creates APPROVED outcomes. The payout-authority table has tests in `backend/tests/policy/test_engine.py`.

## Alternatives considered

1. **LLM as final arbiter (rejected):** Give the grounded LLM authority to set the amount and status. Pro: faster to code; demo-friendly. Con: non-reproducible; unauditable; regulatory risk; merchants cannot verify fairness.

2. **Hybrid with human-in-the-loop (rejected):** Let the AI approve, and a human audits every decision. Pro: catches some errors. Con: the AI's non-reproducibility is still there; scalability fails; human review overhead is unbounded.

## Consequences

**Positive:**

- Reproducibility: `decision_id` and the decision's facts (merchant, alert, slip fields, rules version) are enough to re-run and verify the payout.
- Auditability: every step (extract, check, decision) is logged with the decision id.
- Testability: tests can run the policy engine deterministically; mock AI outputs; verify rule logic.
- Regulatory alignment: rules are documented, versioned, and can be submitted for compliance review.

**Negative:**

- More code: the policy engine and rules file are larger than a monolithic LLM call.
- Slower iteration: changes to payout logic require code and rule edits, not just a prompt change.

**Risks:**

- Rules become stale: policy-engine code must be kept in sync with actual requirements. Mitigate with tests and versioning.
- False confidence: code is deterministic but can still be wrong (a bug in `evaluate_area_claim`, e.g., a wrong threshold). Mitigate with the backtest and pre-release audits.

## How we will know it was right

**Signals:**

1. Backend tests pass at 99.7% coverage, measured on 2 Oct (see [Facts and sources](../../01-strategy/facts-and-sources.md), section D), and every rule edge case is tested.
2. No payout exists without a stored APPROVED decision (a test over the payout step).
3. The audit log is hash-chained and verifiable; `GET /api/audit/verify` returns `valid: true` (K7).
4. A merchant can reproduce the payout amount from the decision explanation's formula and facts.
5. After a pilot: no regulatory objection on the basis of non-determinism or missing logic.
6. A partner insurer or lender can read and change `rules.yaml` without touching code.

## Follow-ups

- **Task:** Implement the honest-wording test (X7, H4 in the [PRD](../../02-product/prd.md), Wave 1) to catch any message that claims a payout or a promise.
- **Task:** Document rules.yaml change process and review checklist before the partnership phase.
- **After the hackathon:** Consult with a partner insurer on regulatory filing requirements for the policy rules.

## Open questions

1. Does the partner insurer require rules to be submitted as a formal underwriting schedule, or can they remain in a YAML file? Owner: Omkar Kadam.
2. If a rule change is needed mid-policy, how does the insurer version and audit it? Owner: Omkar Kadam.

## Changelog

- 2026-10-02 · v2.1 · fixed against the code: claim outcomes are APPROVED, REFERRED, DECLINED (BLOCKED is a cover quote outcome); name match is a SOFT check; officer path and WAIVED_BY_OFFICER added; Gemini, Ask Chhatri and the money-figure guard marked PLANNED; the AI no longer "suggests amounts"; signals made checkable.
- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; ADR correctly establishes policy engine as sole APPROVED authority.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: verified ADR 0001 correctly establishes policy engine as sole APPROVED authority; no changes needed (compliant with canonical framing).
- 2026-10-02 · v1 · first draft.
