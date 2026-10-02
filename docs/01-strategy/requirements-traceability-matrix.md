# Requirements traceability matrix

| | |
|---|---|
| Status | Draft v2 · 3 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Judges, mentors and the team. For each line of the track statement it shows which feature answers it, what is built, where it shows on stage and which tests check it |
| Related | [Problem statement analysis](problem-statement-analysis.md) · [PRD §3](../02-product/prd.md) · [Build plan](../06-delivery/build-plan.md) · [Demo script](../DEMO.md) · [Demo runbook](../06-delivery/demo-runbook.md) · [Competitive landscape §4](competitive-landscape.md#4-feature-harvest-what-we-learned-and-adopted) |

## TL;DR

- The track statement breaks into 14 atomic requirements, PS-1 to PS-14. We add 7 more that nobody wrote down and we hold ourselves to, IR-1 to IR-7: honest labels, consent, accessibility, languages, auditability, safe AI, and a person for doubtful cases.
- Each row names the features (K, N, X, H) that answer it, whether they are BUILT, the demo moment and the tests.
- Every feature in the table is BUILT. The stages that decide and pay (detect, decide, pay, explain, dispute, audit) have run on every build since 1 Oct. The stages a merchant meets in an app (coverage explainer, claim tracker, free questions, escalation, consent) were built on 2 Oct, each behind a feature flag that is off until the build turns it on.
- BUILT means the code and its tests exist. It does not mean a live provider was tried: the Gemini and Sarvam paths are tested against fakes only, and no key has been run. Sales, alerts, KYC, payouts, the lender, Soundbox, WhatsApp and the Paytm link are SIMULATED.
- Still not done, and only a person can do them: deploying the static demo, recording the backup video, the rehearsals, and a native speaker's review of the Marathi text.
- A test shows what we check. It does not show that Chhatri is ready for a pilot.

## 1. How to read this page

| Word | Meaning |
|---|---|
| BUILT | In the code of this repository and covered by the tests in the row. A feature marked "behind `flag`" is off until `CHHATRI_FEATURES` (backend) and `VITE_FEATURES` (console build) name it. Sales, alerts, KYC, payouts, the lender, Soundbox, WhatsApp and the Paytm link are always SIMULATED and labelled. BUILT means the logic exists, not that a partner is connected |
| Not done | Needs a person (deploy, video, rehearsal, a native reviewer) or a real key. Listed in section 5 |
| Demo moment | A scene in the [demo script](../DEMO.md): **Storm** (the live map), **EXPLAINED**, **Personal claim**, **HUMAN**, **BLOCKED**, **Trust**, **Close**. Where a flagged feature shows is in [runbook §4](../06-delivery/demo-runbook.md) |
| Tests | Files and test functions that exist in the repository. Paths are under `backend/tests/` unless they start with `frontend/`. A frontend file name without a folder is under `frontend/src/miniapp/screens/` |

## 2. The track statement as 14 requirements

The verbatim statement is in [problem statement analysis §1](problem-statement-analysis.md#1-the-track-problem-statement-verbatim). We split it by its own words.

| Words in the statement | Requirements |
|---|---|
| "Make Insurance, Lending and Fintech simpler, faster and more human." | PS-1 insurance, PS-2 lending, PS-3 fintech, PS-7 simpler, PS-8 faster, PS-10 more human |
| "Reimagine customer-facing journeys across Insurance, Lending and Fintech using AI." | PS-4 customer-facing, PS-5 using AI |
| "removing friction, reducing complexity, and helping customers complete critical financial journeys faster and with greater confidence" | PS-6 less friction, PS-7 less complexity, PS-8 faster, PS-9 more confidence |
| "from understanding policy coverage and submitting documents to tracking claims and resolving customer queries" | PS-11 understand coverage, PS-12 submit documents, PS-13 track claims, PS-14 resolve queries |

### 2.1 The whole statement (PS-1 to PS-10)

| ID | Requirement | Features and status | Demo moment | Tests, core | Tests, flagged features |
|---|---|---|---|---|---|
| PS-1 | Insurance: simplify an insurance journey | K1 area auto-claim, K2 hospital-cash claim, K6 cover quote and purchase. All BUILT | Storm · Personal claim · BLOCKED | `detect/test_triggers.py`: `test_seventeen_hundred`, `test_quorum`<br>`policy/test_engine.py`: `test_area_approved_anil_1380`, `test_personal_approved_anil_1500`<br>`policy/test_cover.py`: `test_ramesh_blocked_by_red_alert` | `api/test_cover_route.py`<br>`replay/test_view_cover.py`<br>`Buy.test.tsx` |
| PS-2 | Lending: a lending journey | K3 EDI holiday: BUILT as an unconditional pause through the simulated lender. X4 BUILT behind `x4_lender_request`: it is a request, the simulated lender decides, and a guard stops it for a merchant with no loan, in arrears or with no holiday left. X8 BUILT behind `x8_distress_guard`: no loan offers while a merchant is in distress | Storm (17:05) · Personal claim (the pause after the credit) | `ledger/test_instalments.py`: `test_pauses_tomorrows_instalment`<br>`cases/test_demo_flows.py`: `test_monsoon_anil_paid_1380_at_1704_and_instalment_paused_at_1705` | `integrations/test_lender.py`<br>`conversation/test_message_guard.py`<br>`frontend/src/mock/lender.test.ts`<br>`frontend/tests/e2e/human-miniapp-lender.spec.ts` |
| PS-3 | Fintech: a payments-linked journey | A payout that rides the evening settlement, with a Soundbox line (K1, K2), and a Paytm payment link for cover (K6). BUILT on simulated rails. The link is `paytm.me/sim-…` unless Paytm staging keys are set, and the team has none | Storm (17:04) · BLOCKED (the link) | `ledger/test_payouts.py`: `test_credit_due_at_is_rail_delay`<br>`integrations/test_soundbox.py`<br>`integrations/test_paytm.py` | `api/test_cover_route.py` |
| PS-4 | Customer-facing journeys, not an ops tool only | BUILT: a WhatsApp-style phone simulator at `/merchant/:id`, with a "What happened" strip, in Hindi and English. BUILT behind `n1_miniapp`: the merchant mini-app (nine screens, three tabs) as a third column and at `/merchant/:id/app`; its consent and grievance screens sit behind `n6_consents` and `n5_grievances`, Marathi behind `n8_marathi`. N7: the static build and its deep-link fallback are BUILT; deploying it is not done | Storm, then Anil's phone · [runbook §4](../06-delivery/demo-runbook.md) for N1 | `frontend/src/pages/Merchant.test.tsx`<br>`frontend/src/components/phone/whatHappened.test.tsx`<br>`frontend/tests/e2e/demo.spec.ts` | `Home.test.tsx`, `Help.test.tsx`, `MiniappRoot.test.tsx`<br>`frontend/tests/e2e/static-build.spec.ts`<br>`frontend/tests/e2e/human-miniapp-screens.spec.ts`<br>[fs-04 §19](../02-product/feature-specs/fs-04-merchant-mini-app.md) |
| PS-5 | Using AI | BUILT: a LightGBM quantile forecast of each shop's expected day, with a conformal zone bound (K1). Sarvam adapters for speech, chat and slip reading, live only with `SARVAM_API_KEY`. A guard for free-text replies. BUILT behind flags: N2 Ask Chhatri, N3 slip pre-check and N4 voice run a provider chain (Gemini, then Sarvam, then fixed templates) with the H26 label (mode, provider, reason) on every reply. The chain is tested against fakes only: no key has been run. H25 offline evaluation harness and `/evals` page behind `h25_evals`, with no stored run | Storm (the zone bound) · Personal claim (the slip reader) | `forecast/test_model.py`<br>`forecast/test_calibrate.py`<br>`integrations/test_sarvam_docai.py`<br>`conversation/test_guard.py`: `test_ungrounded_numbers_fail` | `ai/test_chain.py`, `ai/test_labels.py`<br>`integrations/test_chat_chain.py`, `integrations/test_slip_chain.py`<br>`ask/test_ask_service.py`<br>`evals/test_suites.py`<br>`frontend/src/mock/ask.test.ts` |
| PS-6 | Less friction | BUILT: K1 needs no action from the merchant, K2 needs one photo. BUILT behind flags: H21 next-best-action bar on every mini-app screen (`n1_miniapp`), and the N3 pre-check, which hands a bad photo back while the merchant still holds the paper (`n3_slip_precheck`) | Storm ("No claim needed") · Personal claim | `conversation/test_live_tests.py`: `test_illness_story_one_photo_paid_same_day_and_todays_instalment_paused`<br>`replay/test_area_flow.py`: `test_payouts_are_executed_at_17_00_and_credited_at_17_04` | `frontend/src/miniapp/hooks/nextBestAction.test.ts`<br>`SlipPrecheck.test.tsx`<br>`replay/test_slip_precheck.py`<br>`api/test_slip_precheck_api.py` |
| PS-7 | Less complexity | BUILT: K5 "why this amount" with the formula and the numbers. BUILT behind flags: the N1 coverage explainer with the H20 jargon lens (`n1_miniapp`), and N2 clause chips C1 to C12 (`n2_ask_chhatri`) | EXPLAINED | `policy/test_explain.py`: `test_formulas_equal_spec_literals_character_for_character`<br>`conversation/test_live_tests.py`: `test_explained_why_then_dispute_opens_c2291` | `Coverage.test.tsx`, `Why.test.tsx`<br>`frontend/src/miniapp/components/JargonSheet.test.tsx`<br>`ask/test_clauses.py` |
| PS-8 | Faster | BUILT: K1 and K2 credit 4 simulated minutes after the decision. The clock is the replay's simulated clock, so this shows the design, not a measured settlement time | Storm (the "4 min trigger to money" tile) · Personal claim | `ledger/test_payouts.py`: `test_credit_due_at_is_rail_delay`<br>`replay/test_golden.py`: `test_decisions_17_00_credits_17_04_pauses_17_05_and_the_kpis` | - |
| PS-9 | More confidence | BUILT: K4 deterministic engine, K7 hash-chained audit, K5 numbers that can be reproduced, X7 honest-wording test. BUILT in Wave 1: H13 verified-by badges, H14 counterfactuals and the H3 receipt (`GET /api/decisions/{decision_id}/receipt`). H25 evaluation harness behind `h25_evals`, with no run stored yet | Trust | `policy/test_engine.py`: `test_engine_is_deterministic`<br>`audit/test_log.py`: `test_tamper_data_detected_via_direct_sqlite_edit` | `api/test_receipt.py`, `replay/test_view_receipt.py`<br>`policy/test_counterfactual.py`, `policy/test_provenance.py`<br>`conversation/test_honest_wording.py`<br>`Receipt.test.tsx` |
| PS-10 | More human | BUILT: Hindi and English templates (H11), a check-in after a silent day before any claim, and a claims officer for every REFERRED claim (K8). BUILT behind flags: N4 Hindi voice (`n4_voice`), the N5 grievance ladder (`n5_grievances`) and N8 Marathi, a draft (`n8_marathi`) | Personal claim (the check-in) · HUMAN | `conversation/test_messages.py`: `test_catalogue_matches_spec_character_for_character`<br>`policy/test_engine.py`: `test_personal_name_mismatch_referred_with_amount_and_explanation`<br>`conversation/test_live_tests.py`: `test_human_slip_with_a_different_name_is_referred_and_paid_only_after_the_officer` | `ask/test_voice_service.py`, `api/test_voice.py`<br>`api/test_grievances.py`, `cases/test_ladder.py`<br>`frontend/src/miniapp/copy/mr.test.ts`, `Language.test.tsx` |

### 2.2 The track's health-claims example (PS-11 to PS-14)

Chhatri walks this example on its hospital-cash claim. The stage-by-stage story is in [problem statement analysis §3](problem-statement-analysis.md#3-the-health-claims-example-on-chhatris-hospital-cash-journey).

| ID | Stage | Features and status | Demo moment | Tests, core | Tests, flagged features |
|---|---|---|---|---|---|
| PS-11 | Understand policy coverage | BUILT: the `/policy` page, and a cover answer of OK or BLOCKED with the reason (K6). BUILT behind flags: the N1 coverage explainer with H20 (`n1_miniapp`), and N2 Ask Chhatri with H17 clause chips and the H19 scam warning (`n2_ask_chhatri`) | BLOCKED · [runbook §4](../06-delivery/demo-runbook.md) (N1, N2) | `policy/test_cover.py`: `test_ramesh_blocked_by_red_alert`<br>`frontend/src/components/policy/ruleFormat.test.ts` | `Coverage.test.tsx`, `Ask.test.tsx`<br>`ask/test_scam.py`, `ask/test_clauses.py` |
| PS-12 | Submit documents | BUILT: one slip photo, read by the Sarvam reader (live with a key, simulated otherwise). The engine checks that the slip is readable, the name matches KYC and the dates cover the silent days. Doubt goes to a person. BUILT behind `n3_slip_precheck`: the pre-check with H5 (the merchant confirms what was read), H15 (document class, slots, confidence gate) and H16 (injection defence). The reader chain is tested against fakes only | Personal claim · HUMAN | `conversation/test_slip_flow.py`: `test_referred_variants_with_case_chip`<br>`policy/test_names.py`: `test_spec_pairs`<br>`policy/test_engine.py`: `test_personal_unsure_referred` | `SlipPrecheck.test.tsx`<br>`replay/test_slip_precheck.py`<br>`precheck/test_untrusted_slip_text.py`<br>`conversation/test_slip_injection.py` |
| PS-13 | Track claims | BUILT: messages at decision, credit and pause, a "What happened" strip beside the phone, and the officer queue at `/claims` with a case chip. BUILT behind `n1_miniapp`: the claim tracker with the REFERRED and DISPUTE paths (H1) and the trust receipt (H3) | Storm, then Anil's phone · HUMAN | `frontend/src/components/phone/whatHappened.test.tsx`<br>`frontend/src/pages/Claims.test.tsx`<br>`cases/test_service.py`: `test_first_case_is_c2291_with_sla` | `replay/test_view_claims.py`<br>`ClaimDetail.test.tsx`, `Claims.test.tsx` (mini-app)<br>`frontend/src/miniapp/hooks/trackerModel.test.ts` |
| PS-14 | Resolve customer queries | BUILT: the "why" answer. A dispute opens a case with a 24 h clock, and the officer confirms the payout or rejects the dispute, so the amount never changes. BUILT behind flags: N2 free questions (`n2_ask_chhatri`) and the N5 grievance ladder with response clocks and a respondent router, H22 (`n5_grievances`) | EXPLAINED · HUMAN | `replay/test_dispute_cover.py`: `test_explained_numbers_then_a_dispute_case_c_2291`<br>`cases/test_service.py`: `test_resolve`<br>`conversation/test_notifications.py`: `test_closed_area_dispute_is_answered_with_the_area_numbers`<br>`conversation/test_replies.py`: `test_why_after_a_personal_payout_shows_the_formula` | `ask/test_ask_service.py`, `conversation/test_explain_first.py`<br>`api/test_grievances.py`, `cases/test_ladder.py`<br>`Grievances.test.tsx`, `Ask.test.tsx` |

## 3. Requirements nobody wrote down (IR-1 to IR-7)

A merchant, a judge or a regulator would expect these even though the track statement does not list them.

| ID | Requirement | Features and status | Demo moment | Tests, core | Tests, flagged features |
|---|---|---|---|---|---|
| IR-1 | Honest labels: what is live, what is simulated, what is only planned | BUILT: LIVE and SIMULATED badges on every integration, and a demo script that names only what shows LIVE. BUILT: X7 honest-wording test. BUILT behind `x6_provider_panel`: the provider panel with the FALLBACK status and a demo fallback switch, and the H26 label on every AI reply. H25 numbers are shown only from a stored run, and none is stored. H12 measured test counts are not published in the README | Close ("what runs live") | `integrations/test_registry.py`: `test_offline_build_is_fully_simulated`<br>`api/test_meta_live.py`: `test_integrations_lists_every_component`<br>`frontend/src/components/common/status.test.tsx` | `conversation/test_honest_wording.py`<br>`integrations/test_fallback_switch.py`, `api/test_fallback_route.py`<br>`ai/test_labels.py`<br>`frontend/src/miniapp/copy/honestWording.test.ts`<br>`frontend/src/components/layout/providerPanel.test.tsx` |
| IR-2 | Consent and data rights | BUILT behind `n6_consents`: the consent centre with three purposes, withdrawal that takes effect at once, H23 activity log and "forget my slip", and a consent gate on the cover purchase. The slip read is audited without the patient name | Not on the main path | `conversation/test_slip_flow.py`: `test_slip_read_is_audited_without_the_patient_name` | `api/test_consents.py`, `api/test_consent_gates.py`<br>`consent/test_notice_and_activity.py`<br>`Consents.test.tsx`<br>`frontend/tests/e2e/human-miniapp-consents.spec.ts` |
| IR-3 | Accessibility | BUILT: reduced-motion rules in the console CSS, the jsx-a11y lint rules in `npm run lint`, a computed contrast check of the console tokens, and 44 px targets in the mini-app. A keyboard walk of the tabs is an e2e test. There is no automated axe-style screen scan, and no assistive-technology review | Mini-app | `npm run lint` (jsx-a11y)<br>`frontend/src/contrast.test.ts` | `frontend/tests/e2e/human-miniapp-help-lang.spec.ts` (keyboard test)<br>[fs-04 §16.3](../02-product/feature-specs/fs-04-merchant-mini-app.md) |
| IR-4 | Hindi, English and Marathi | BUILT: a Hindi and English message catalogue, filled from decision facts, and Hindi speech through Sarvam when keyed. BUILT behind flags: N4 Hindi voice (`n4_voice`) and N8 Marathi for the mini-app, a draft behind `n8_marathi` until a native speaker reviews it | Personal claim (the Hindi check-in) | `conversation/test_messages.py`: `test_every_key_renders_in_every_language_it_has`<br>`frontend/src/components/phone/messages.test.ts` | `frontend/src/miniapp/copy/mr.test.ts`<br>`Language.test.tsx`<br>`ask/test_voice_service.py` |
| IR-5 | Auditability: every decision can be replayed and checked | BUILT: a hash-chained audit log with a verify call, every check stored with each decision, and H13 sources plus H14 counterfactuals on `GET /api/decisions/{decision_id}/receipt` | Trust | `audit/test_log.py`: `test_chain_links_and_same_inputs_same_hashes`, `test_deleted_row_detected`, `test_decision_data_contains_every_check`<br>`api/test_cases_records.py`: `test_audit_paging_and_verify` | `api/test_receipt.py`<br>`policy/test_counterfactual.py` |
| IR-6 | Safe AI: code decides money, models only read and explain | BUILT: K4 decides every amount. A free-text reply passes only if every number is a decision fact and it promises no money or approval. Only synthetic data goes to free-tier AI ([ADR 0009](../04-engineering/adr/0009-synthetic-data-only-to-free-tier-ai.md)). BUILT: H16 injection defence and H17 grounded answers. The H25 red-team suites exist and run offline, and no run is stored | Trust · Close | `conversation/test_guard.py`: `test_ungrounded_numbers_fail`, `test_money_or_approval_promises_fail`<br>`policy/test_engine.py`: `test_engine_is_deterministic` | `ask/test_injection.py`, `ask/test_fact_sheet.py`<br>`ai/test_untrusted.py`<br>`evals/test_suites.py`<br>`integrations/test_free_tier_gate.py` |
| IR-7 | A person decides doubtful cases, and a merchant in trouble is not sold to | BUILT: a SOFT fail or an unsure read sends the claim to an officer, and an officer cannot override a HARD check. BUILT behind `x8_distress_guard`: no loan, top-up or cross-sell message while an alert covers the zone or a claim or dispute is open, and a daily message cap | HUMAN | `policy/test_engine.py`: `test_officer_cannot_override_hard_checks`, `test_personal_hard_beats_soft` | `conversation/test_message_guard.py` |

## 4. Reverse index: each feature points to a requirement

Every K, N, X and H item serves at least one requirement. Credits for the H items are in the [competitive landscape §4](competitive-landscape.md#4-feature-harvest-what-we-learned-and-adopted).

### 4.1 Kept features and new features

| ID | Feature | Status | Serves | Spec |
|---|---|---|---|---|
| K1 | Area auto-claim | BUILT | PS-1, PS-3, PS-5, PS-6, PS-8 | [fs-01](../02-product/feature-specs/fs-01-area-auto-claim.md) |
| K2 | Hospital-cash claim | BUILT | PS-1, PS-6, PS-10, PS-12 | [fs-02](../02-product/feature-specs/fs-02-hospital-cash-claim.md) |
| K3 | EDI holiday request | BUILT; with `x4_lender_request` the simulated lender decides (X4) | PS-2 | [fs-03](../02-product/feature-specs/fs-03-edi-holiday.md) |
| K4 | Policy engine and payout authority | BUILT | PS-9, IR-6, IR-7 | [fs-09](../02-product/feature-specs/fs-09-policy-engine-and-audit.md) |
| K5 | Explanations and disputes | BUILT | PS-7, PS-14 | [fs-06](../02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md) |
| K6 | Cover purchase with the waiting period | BUILT | PS-1, PS-3, PS-11 | [fs-07](../02-product/feature-specs/fs-07-cover-purchase-and-consent.md) |
| K7 | Hash-chained audit log | BUILT | PS-9, IR-5 | [fs-09](../02-product/feature-specs/fs-09-policy-engine-and-audit.md) |
| K8 | Claims-officer console | BUILT | PS-10, PS-13, PS-14, IR-1 | [fs-08](../02-product/feature-specs/fs-08-claims-officer-console.md) |
| N1 | Merchant mini-app | BUILT · behind `n1_miniapp` (consent and grievance screens behind `n6_consents` and `n5_grievances`, Marathi behind `n8_marathi`) | PS-4, PS-7, PS-11, PS-13 | [fs-04](../02-product/feature-specs/fs-04-merchant-mini-app.md) |
| N2 | Ask Chhatri | BUILT · behind `n2_ask_chhatri` (Gemini and Sarvam tested against fakes only) | PS-5, PS-11, PS-14 | [fs-05](../02-product/feature-specs/fs-05-ask-chhatri.md) |
| N3 | Slip reading with a pre-check | BUILT · behind `n3_slip_precheck` | PS-5, PS-6, PS-12 | [fs-02](../02-product/feature-specs/fs-02-hospital-cash-claim.md) |
| N4 | Real voice | BUILT · behind `n4_voice` | PS-5, PS-10 | [fs-05](../02-product/feature-specs/fs-05-ask-chhatri.md) |
| N5 | Grievance ladder | BUILT · behind `n5_grievances` | PS-14, IR-7 | [fs-06](../02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md) |
| N6 | Consent centre | BUILT · behind `n6_consents` | IR-2 | [fs-07](../02-product/feature-specs/fs-07-cover-purchase-and-consent.md) |
| N7 | Public static demo and backup video | Static build BUILT; deploying it (the repo owner) and the backup video are not done | PS-4, IR-1 | [fs-08 §9.7](../02-product/feature-specs/fs-08-claims-officer-console.md), [build plan](../06-delivery/build-plan.md) |
| N8 | Marathi | BUILT as a draft · behind `n8_marathi`, until a native speaker reviews it | PS-10, IR-4 | [fs-04](../02-product/feature-specs/fs-04-merchant-mini-app.md), [fs-05](../02-product/feature-specs/fs-05-ask-chhatri.md) |

### 4.2 Fixes

| ID | Fix | Status | Serves | Spec |
|---|---|---|---|---|
| X1 | Fix the 2 failing frontend tests | BUILT · Wave 0 | IR-1 | [build plan](../06-delivery/build-plan.md) |
| X2 | Validate the expected day at claim creation | BUILT · Wave 1 | PS-9 | [fs-01](../02-product/feature-specs/fs-01-area-auto-claim.md) |
| X3 | Fail loudly on a zone missing from the price table | BUILT · Wave 1 | PS-9 | [fs-07](../02-product/feature-specs/fs-07-cover-purchase-and-consent.md) |
| X4 | EDI guard and lender-decides wording | BUILT · behind `x4_lender_request` | PS-2 | [fs-03](../02-product/feature-specs/fs-03-edi-holiday.md) |
| X5 | A clean 404 for an unknown merchant | BUILT · Wave 1 | PS-9 | [fs-06](../02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md) |
| X6 | Provider panel with LIVE, SIMULATED and FALLBACK, and a demo fallback switch | BUILT · behind `x6_provider_panel` | IR-1, PS-5 | [fs-08](../02-product/feature-specs/fs-08-claims-officer-console.md) |
| X7 | Honest-wording test | BUILT · Wave 1 | IR-1, IR-6 | [fs-09](../02-product/feature-specs/fs-09-policy-engine-and-audit.md) |
| X8 | No loan offers during distress, and a message cap | BUILT · behind `x8_distress_guard` | IR-7, PS-2 | [fs-03](../02-product/feature-specs/fs-03-edi-holiday.md) |

### 4.3 Ideas from other teams

| ID | Idea | Status | Serves |
|---|---|---|---|
| H1 | Step-by-step tracker with "you are here" | BUILT · behind `n1_miniapp` | PS-13 |
| H2 | "Why this amount" with source badges | BUILT (K5 card; N1 view behind `n1_miniapp`) | PS-7, PS-9 |
| H3 | Payout receipt | BUILT · Wave 1 | PS-9, IR-5 |
| H4 | Honest-wording test (X7) | BUILT · Wave 1 | IR-1 |
| H5 | The merchant confirms what was read | BUILT · behind `n3_slip_precheck` | PS-12 |
| H6 | Zero-login public demo (N7) | Static build and deep-link fallback BUILT; not deployed | PS-4 |
| H7 | Provider panel with a fallback switch (X6) | BUILT · behind `x6_provider_panel` | IR-1 |
| H8 | Real operational counts | BUILT · behind `h8_ops_strip` | IR-1, PS-9 |
| H9 | No loan offers in distress (X8) | BUILT · behind `x8_distress_guard` | IR-7 |
| H10 | Deterministic core, no model authority over money | BUILT | PS-9, IR-6 |
| H11 | Bilingual templates, not model translation | Hindi and English BUILT; Marathi a draft behind `n8_marathi` | PS-10, IR-4 |
| H12 | Visible, measured test counts | BUILT: the README states the counts measured on 3 Oct 2026 (backend 3,221 fast and 63 slow, infra 164, frontend 1,340, demo-check 70 of 70) and links the [testing strategy](../04-engineering/testing-and-quality-strategy.md); rerun the commands at the freeze and update both | IR-1 |
| H13 | Verified-by badges | BUILT · Wave 1 (console chips Wave 4) | PS-9, IR-5 |
| H14 | Counterfactual in every explanation | BUILT · Wave 1 (console Wave 4) | PS-7, PS-9, PS-14 |
| H15 | Slip pre-check: class, slots, confidence gate | BUILT · behind `n3_slip_precheck` | PS-6, PS-12 |
| H16 | Prompt-injection defence | BUILT · Wave 2 | IR-6 |
| H17 | Clause citations in answers | BUILT · behind `n2_ask_chhatri` | PS-11, IR-6 |
| H18 | Voice confirmation chips | BUILT · behind `n4_voice` | PS-10 |
| H19 | Scam-message warning | BUILT · behind `n2_ask_chhatri` | PS-9 |
| H20 | Jargon lens | BUILT · behind `n1_miniapp` | PS-7, PS-11 |
| H21 | Next-best-action bar | BUILT · behind `n1_miniapp` (chat replies behind `n2_ask_chhatri`) | PS-6, PS-13 |
| H22 | Grievance ladder with response clocks | BUILT · behind `n5_grievances` | PS-14, IR-7 |
| H23 | Consent activity log and "forget my slip" | BUILT · behind `n6_consents` | IR-2 |
| H24 | What-if panel for judges | BUILT · behind `h24_whatif` | PS-9, IR-1 |
| H25 | Published AI evaluation | Offline harness and `/evals` page BUILT behind `h25_evals`; no run stored, live suites need keys | IR-1, IR-6 |
| H26 | Mode, provider and reason on every AI reply | BUILT · Wave 2 | IR-1, PS-5 |

## 5. Gaps we can see today

| Gap | Requirement | What closes it |
|---|---|---|
| Every flagged feature is off until the build turns it on. A demo build with the flags off shows only the console and the phone simulator | PS-4 | Set `CHHATRI_FEATURES` and `VITE_FEATURES` to the demo list ([runbook §4](../06-delivery/demo-runbook.md)) |
| Gemini and Sarvam are tested against fakes only. No key has been tried, so no live AI answer, slip read or voice has been seen | PS-5, IR-6 | A person sets the keys, runs `make check-keys` and the live smoke test |
| H25: the evaluation harness runs offline and no run is stored, so the `/evals` page shows no numbers | IR-1, IR-6 | Run `make evals` once and store the result; until then the page says so |
| No automated axe-style accessibility scan, and no review with assistive technology | IR-3 | Optional; a person does a keyboard and screen-reader pass |
| Marathi is a draft | IR-4 | A native speaker's review, then drop "draft" from the copy deck |
| No public demo link. The static build exists; the repo owner has to deploy it, and the backup video is not recorded | PS-4 | N7: deploy, record, rehearse (human-only) |
| Sales, alerts, KYC, payouts, the lender, Soundbox, WhatsApp and the Paytm link are simulated, and a decision time of 4 simulated minutes is a design, not a measurement | PS-8, IR-1 | Labels stay on every screen. A pilot with a partner insurer and lender would replace the simulators |
| Hospital cash has no price yet. The premium covers area claims only | PS-1 | Open: priced with a partner insurer after the hackathon |
| The README publishes its test counts as of 3 Oct 2026 | IR-1 | H12 done; rerun and update at the freeze if tests change |

## Open questions

1. A row is BUILT when its code and tests exist, with the flag on in the demo build. A feature that passes its tests but stays hidden by a flag is BUILT here, and the flags section of each spec says so. Owner: Omkar Kadam and Ujjwal Pardeshi.
2. Should the optional automated accessibility scan (IR-3) be added before the final? Owner: Omkar Kadam.

## Changelog

- 2026-10-03 · v2 · every row re-checked against the code: the planned rows are BUILT behind their flags with real test files; the gaps list is rewritten (keys untried, no stored evaluation run, no axe scan, Marathi draft, static demo not deployed)
- 2026-10-02 · v1 · first version: the track statement as 14 requirements and 7 implicit ones, each traced to features, BUILT or PLANNED status with the build wave, demo moment and tests; a reverse index of every K, N, X and H item; the gaps we can see today
