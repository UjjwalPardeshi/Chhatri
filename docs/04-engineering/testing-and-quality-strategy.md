# Testing and Quality Strategy

| | |
|---|---|
| Status | v2 · 3 Oct 2026 · counts measured on 3 Oct 2026 (section 1); every feature is BUILT and has tests |
| Owner | Ujjwal Pardeshi |
| Audience | Technical: developers, QA, CI/CD · Non-technical: team, judges |
| Related | [Current-state audit](../01-strategy/current-state-audit.md) · [System architecture](system-architecture.md) · [Data model and API](data-model-and-api.md) · [Implementation guide](implementation-guide.md) · [AI evaluation plan](ai-evaluation-plan.md) |

## TL;DR

- **Measured on 3 Oct 2026:** backend 3,221 fast tests (98.85 % line coverage of `chhatri/`) and 63 slow tests; infra 164 tests (99.44 % coverage of `scripts/`); frontend 1,340 unit tests in 135 files; `make demo-check` 70 of 70; 134 Playwright tests listed in 26 spec files (counted, not run for this page).
- **Quality gates:** CI runs lint, the fast backend suite with coverage of at least 80 %, the frontend typecheck, lint, tests and build, the infra checks and the n8n self-test on every push to main and every pull request. `make test-slow`, `make demo-check` and `make e2e` are local gates that CI does not run.
- **Every feature has tests:** N1 to N8, X1 to X8 and H-items are mapped to their test files in section 3. Failing-first test lists per card are in the [implementation guide](implementation-guide.md).
- **AI quality is not measured.** The offline evaluation harness (H25) is BUILT and `make evals` runs it, but no run is committed, so the `/evals` page reads NOT MEASURED. The live suites need keys and graders and are not built ([AI evaluation plan](ai-evaluation-plan.md)).
- **Demo rehearsal:** `make demo-check` validates the golden numbers offline. It runs with `CHHATRI_FEATURES=x4_lender_request`, the one flag the scripted flow expects; with `n3_slip_precheck` or `n6_consents` also on, the scripted photo and purchase steps stop by design (section 5).
- **Freeze policy:** code freeze 90 minutes before the demo; the final rehearsal passes demo-check and the manual checklist.

## 1. Test suites and counts (measured 3 Oct 2026)

Counts come from one run of each command on 3 Oct 2026 (`make test-backend`, `make test-slow`, `make test-infra`, `npx vitest run --maxWorkers=2`), plus `make demo-check` and `playwright test --list`.

| Suite | Command | Result on 3 Oct 2026 |
|---|---|---|
| Backend, fast | `make test-backend` (`pytest -m "not slow"`, coverage gate 80 %) | 3,221 passed, 63 deselected; line coverage 98.85 % |
| Backend, slow | `make test-slow` (`pytest -m slow`) | 63 passed |
| Infra | `make test-infra` (workflow JSON check, then `pytest scripts/tests`, coverage gate 90 %) | 164 passed; coverage 99.44 % |
| Frontend unit | `npm run test` (Vitest) | 1,340 passed in 135 files; coverage not measured (`npm run test:coverage` exists and was not run) |
| Demo rehearsal | `make demo-check` | 70 of 70 checks pass |
| Playwright e2e | `make e2e` (live project) or `npm run test:e2e:mock` | 134 tests in 26 spec files, counted with `playwright test --list --project=mock`; not run for this page |

### Backend fast tests by folder (3,221)

`api` 718 · `conversation` 514 · `integrations` 378 · `replay` 294 · `policy` 188 · `ask` 162 · `pipeline` 133 · `forecast` 115 · `sim` 103 · `detect` 88 · `ai` 84 · `backtest` 78 · `ledger` 61 · `precheck` 53 · `evals` 48 · `consent` 43 · `workflows` 37 · `cases` 37 · `audit` 29 · files directly under `tests/` 27 · `store` 23 · `domain` 8.

### Backend slow tests by folder (63)

`api` 22 · files directly under `tests/` 18 (golden numbers, demo flows) · `replay` 17 · `forecast` 2 · `backtest` 2 · `sim` 1 · `pipeline` 1. They read the committed artefacts and never rebuild them.

### Infra (164)

`scripts/tests/`: workflow generation and the self-test harness, compose and Dockerfile checks, env setup, the nginx proxy, the Makefile, the flag lockstep between `features.py` and `features.ts`, and the key checker.

### Demo-check (70)

`backend/scripts/demo_check.py` (SPEC §13.6, §17.2, §22, §23) runs the four scenarios (`monsoon`, `illness`, `illness_mismatch`, `buy_cover`) and the three live tests (EXPLAINED, HUMAN, BLOCKED) through the HTTP API and compares what the console would show with the constants in `backend/chhatri/api/demo/golden.py`. It needs no keys; it uses the committed artefacts with every live integration switched off.

## 2. Quality gates and CI pipeline

### Local gates (developer responsibility)

Before committing:
- `make lint` (ruff check and format check for the backend and `scripts/`) must pass.
- `make test-backend` (fast tests, coverage at least 80 %) must pass.
- `make test-frontend` (typecheck, lint, Vitest) must pass.
- `make test-infra` when anything under `scripts/`, `n8n/`, the Makefile, compose or nginx changed.
- Before a demo: `make test-slow` and `make demo-check`.

### CI gates (`.github/workflows/ci.yml`, on every push to main and every pull request)

1. **Backend:** `ruff check .`, `ruff format --check .`, then `pytest -m "not slow" --cov=chhatri --cov-fail-under=80`.
2. **Frontend:** `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`.
3. **Infra:** ruff on `scripts/`, `scripts/n8n_workflows.py --check` (the generated JSON matches `WORKFLOWS`), `pytest scripts/tests --cov=scripts --cov-fail-under=90`, then `scripts/n8n_selftest.py --start-container` against the pinned n8n image.

CI never builds artefacts and does not run `make test-slow`, `make demo-check` or `make e2e`. A failing job blocks the merge.

## 3. Where each feature is tested

Backend paths are under `backend/tests/`, frontend paths under `frontend/`.

| Feature | Backend | Frontend and end to end |
|---|---|---|
| N1 mini-app: cover card, claim tracker, receipt, buy | `api/test_cover_route.py`, `api/test_claims_route.py`, `api/test_receipt.py`, `policy/test_cover_status.py`, `replay/test_view_cover.py`, `replay/test_view_claims.py`, `replay/test_view_receipt.py` | `src/miniapp/screens/*.test.tsx`, `src/mock/endpoints/*.test.ts`; e2e `miniapp-*.spec.ts`, `human-miniapp-cover.spec.ts`, `human-miniapp-screens.spec.ts` |
| N2 Ask Chhatri | `ask/`, `api/test_ask.py`, `api/test_ask_real.py`, `conversation/test_guard.py`, `conversation/test_guard_strict.py`, `conversation/test_ask_chat.py`, `conversation/test_explain_first.py`, `integrations/test_gemini_chat.py`, `integrations/test_chat_chain.py`, `integrations/test_free_tier_gate.py` | `src/miniapp/screens/Ask.test.tsx`, `src/mock/ask.test.ts`; e2e `human-miniapp-ask.spec.ts` |
| N3 slip pre-check | `precheck/`, `replay/test_slip_precheck.py`, `api/test_slip_precheck_api.py`, `conversation/test_slip_flow.py`, `conversation/test_slip_injection.py`, `integrations/test_gemini_vision.py`, `integrations/test_slip_chain.py` | `src/miniapp/screens/SlipPrecheck.test.tsx`, `src/components/phone/PrecheckActions.test.ts`, `src/mock/precheck.test.ts`; e2e `human-miniapp-slip.spec.ts` |
| N4 voice | `api/test_voice.py`, `ask/test_voice_service.py`, `ask/test_mentions.py`, `integrations/test_sarvam.py`, `integrations/test_sarvam_sim.py` | `src/miniapp/components/voiceMentions.test.ts`; e2e `human-miniapp-voice.spec.ts` |
| N5 grievance ladder | `cases/test_ladder.py`, `api/test_grievances.py` | `src/miniapp/screens/Grievances.test.tsx`, `grievanceModel.test.ts`; e2e `human-miniapp-grievance.spec.ts`, `miniapp-dispute.spec.ts` |
| N6 consent centre, activity, forget my slip | `api/test_consents.py`, `api/test_consent_gates.py`, `consent/test_notice_and_activity.py` | `src/miniapp/screens/Consents.test.tsx`; e2e `human-miniapp-consents.spec.ts` |
| N7 static demo | none | `src/mock/*.test.ts`; e2e `static-build.spec.ts` (runs when `STATIC_DIR` names a mock build) |
| N8 Marathi | none | `src/miniapp/copy/mr.test.ts`, `src/miniapp/screens/Language.test.tsx`; the text still needs a native speaker's review |
| X1 frontend tests | none | the whole Vitest suite |
| X2 to X3 published expected day, zone price | `domain/test_claim_model.py`, `policy/test_amounts.py`, `ledger/test_premium_table.py` | none |
| X4 lender decides the EDI holiday | `integrations/test_lender.py`, `ledger/test_instalments.py`, `replay/test_area_flow.py` | `src/mock/lender.test.ts`; e2e `human-miniapp-lender.spec.ts` |
| X5 unknown merchant | `api/test_unknown_merchant.py` | none |
| X6 provider panel and fallback switch | `api/test_fallback_route.py`, `integrations/test_fallback_switch.py`, `integrations/test_registry_gemini.py` | `src/components/layout/providerPanel.test.tsx` |
| X7 honest wording | `conversation/test_honest_wording.py` | `src/miniapp/copy/honestWording.test.ts` |
| X8 no offers in distress, daily cap | `conversation/test_message_guard.py`, `conversation/test_outbox.py` | none |
| H8 ops strip, H24 what-if | `api/test_ops_summary.py`, `api/test_whatif_route.py`, `replay/test_whatif.py`, `replay/test_whatif_vectors.py` | `src/components/layout/OpsStrip.test.tsx`, `src/mock/endpoints/whatif.test.ts` |
| H25 offline evaluation harness | `evals/`, `api/test_evals.py` | `src/pages/Evals.test.tsx` |
| Feature flags | `test_features.py`, `api/test_feature_flags.py`, `api/test_feature_routes.py` | `src/features.test.ts`; `scripts/tests/test_feature_flags.py` keeps the two flag lists identical |
| Core: detection, policy engine, audit, ledger, workflows, replay, golden numbers | `detect/`, `policy/`, `audit/`, `ledger/`, `workflows/`, `replay/`, `test_golden_numbers.py`, `test_demo_flows.py` | e2e `demo.spec.ts`, `smoke.spec.ts`, `screens.spec.ts` |

### Not built

- Tesseract OCR as a slip fallback, and the live evaluation suites (S2 part B, S3, S4, S5; see the [AI evaluation plan](ai-evaluation-plan.md)).
- Performance and load testing (a roadmap item for after a real-merchant pilot).

## 4. AI evaluation

The offline harness (H25) is BUILT: `make evals` runs the intent, guard and chain suites with fakes and no network, and writes `backend/artifacts/evals/summary.json`. No run is committed, so the `/evals` page shows NOT MEASURED, and no accuracy figure for any model exists. The sets that need keys or human grading (`ask.jsonl`, `voice.jsonl`, the staged slip photographs) are not built. The targets below are targets, not results.

### Ask Chhatri: grounded-answer set (not built)

**Purpose:** verify that answers cite the policy wording and decision facts, never invent a money figure, and hand off to a person when unsure.

**Target:** at least 95 % grounded answers, with zero unsupported money figures. The guard (`backend/chhatri/conversation/guard.py` and `guard_strict.py`) enforces the figures rule on every reply whatever the evaluation says, and `backend/tests/conversation/test_guard_strict.py` pins it.

**Provider chain:** Gemini, then Sarvam chat, then a template, then a hand-off (BUILT; tested against fakes only).

### Slip extraction (not built as a measured set)

**Purpose:** show that the readers (Gemini vision, Sarvam document reading) fill the five fields with a measurable confidence gate of 0.80.

**What exists:** the gate and the chain are unit-tested against fakes (`integrations/test_gemini_vision.py`, `integrations/test_slip_chain.py`, `integrations/test_sarvam_docai.py`). The simulated reader reads the answer key embedded in the sample image, so any accuracy figure from it would be meaningless.

### Intent detection

The word-list classifier (`backend/chhatri/conversation/intents.py`, `lexicon.py`) is the intent path; with `n2_ask_chhatri` on no model chooses an intent. `backend/tests/conversation/test_intents.py` (48 cases) is regression testing: the word lists were written beside the cases, so they pass by construction. `chhatri.evals` holds a labelled `intents.jsonl` split into development and held-out items.

## 5. Demo rehearsal checks

### `make demo-check`: Automated validation

**What it does:**
1. Loads the four demo scenarios (monsoon, illness, illness_mismatch, buy_cover) and three live tests (EXPLAINED, HUMAN, BLOCKED).
2. Runs the HTTP API routes as the console would.
3. Compares results with the `GOLDEN` constants (`backend/chhatri/api/demo/golden.py`).
4. Prints a pass/fail table or JSON (with `--json`).

**Usage:**
```bash
make demo-check                                                                 # in process, no backend needed
backend/.venv/bin/python backend/scripts/demo_check.py --url http://localhost:8000   # against a running backend
```

**Flags.** In process, `make demo-check` runs with `CHHATRI_FEATURES=x4_lender_request` (`DEMO_FEATURES` in `backend/chhatri/api/demo/local.py`), on top of any flag you name in the environment. The golden strings pin the lender-decides wording of X4. The scripted flow stops by design when `n3_slip_precheck` is on (the photo then needs the pre-check confirm) or `n6_consents` is on (a purchase needs the consent ticks, and a photo needs a slip consent), so the check does not turn those on. Against a running backend (`--url`), that backend must run with the same flags: `GET /api/health` must list `"features": ["x4_lender_request"]`.

**Exit code:** 0 (all pass), 1 (any fail), 2 (bad args)

**Example output (a few rows):**
```
PASS    buy_cover         audit chain valid           True
PASS: 70 passed, 0 failed, 0 skipped
```

### Adding a check for a new endpoint

Checks are built in `backend/chhatri/api/demo/` (`flows.py` observes, `golden.py` holds the expected values, `compare` pairs them into `CheckRow`s). Add the observed value in `flows.py`, the expected value in `golden.py`, and keep the figures asserted by `backend/tests/api/test_demo_report.py` and `backend/tests/test_demo_flows.py` in step.

## 6. Manual on-stage test script

**Run this checklist 10 minutes before each demo cut (3-min and 7-min).**

### Preflight (all keys loaded, integrations live if chosen)

- [ ] Backend and console are running (`make dev` or via docker)
- [ ] Gemini key and model id are set (`GOOGLE_API_KEY`, `GEMINI_MODEL`; `make check-keys` lists the models), or Gemini is meant to be SIMULATED
- [ ] Sarvam key is set (env var `SARVAM_API_KEY`)
- [ ] WhatsApp test number is provisioned (5+ test recipients configured)
- [ ] Browser is on the demo laptop; browser speech recognition works in this browser (optional: the voice chips work without it)
- [ ] Network: WiFi or ethernet is stable; no VPN or proxy blocking APIs

### Smoke tests (each about 30 seconds; the steps and exact strings are in [DEMO.md](../DEMO.md))

1. **Console:** open `/live` at 1280×720; the header badges read what you configured (everything SIMULATED unless a key is set) and the map shows the wards.
2. **Replay control:** pick `monsoon`, seek 13:30, press Play; the clock advances and the red alert `A-20250818-01` is in the feed.
3. **Anil's payout:** at 17:04 the KPI tiles read 3 zones, 312 shops, 4 min; Z7's panel reads `₹58,900`; Anil's pin reads `₹1,380 paid · 17:04`.
4. **Soundbox and phone:** on `/merchant/S-0142` the phone shows the payout card and the Soundbox line (browser speech is fine).
5. **Mini-app (flag `n1_miniapp`):** the frame beside the phone shows the cover card and the claim tracker with the five steps.
6. **Ask Chhatri (flag `n2_ask_chhatri`):** ask "मुझे इतने ही पैसे क्यों मिले?"; the answer cites a clause and shows Anil's own numbers.
7. **Slip pre-check (flag `n3_slip_precheck`):** upload the sample slip; the read fields appear and you confirm or retake.
8. **Grievance (flag `n5_grievances`):** on Anil's claim open a dispute; a ladder with its clock appears.

### For the 3-minute cut

- [ ] Steps 1 to 6 above, in under 3 minutes
- [ ] Closing line: "The AI builds the case; code decides the money", with the LIVE and SIMULATED badges in view

### For the 7-minute cut

- [ ] All 8 steps above
- [ ] `/claims`: case `C-2291` (the `illness_mismatch` run) is listed
- [ ] `/audit`: Verify chain reads valid
- [ ] `/backtest`: the report tables render
- [ ] `/policy`: the rules (`pilot-0.1`) and the authority table render

### Fallback actions

- **Slip reading fails (provider timeout):** the chain falls to the next link, then to the simulated reader or a hand-off to the team (REFERRED); or force the component to its fallback in the provider panel
- **Ask Chhatri hangs (Gemini rate limit):** the chain falls to Sarvam and then a template; or force the component to its fallback in the provider panel
- **Mini-app does not load:** Show a screenshot on the second screen
- **Browser speech fails:** use the voice chips or type the message

## 7. Definition of done

A feature is **done** when:

- [ ] Code is written and reviewed (code-reviewer agent, CRITICAL and HIGH issues fixed)
- [ ] Unit tests pass (fast tests, coverage ≥80% on new code)
- [ ] Integration tests pass (critical paths, mocks OK)
- [ ] AI evals pass (eval set score ≥95% or guardrail enforced)
- [ ] Frontend e2e passes (Playwright, desktop and mobile viewports)
- [ ] `make demo-check` passes (all 70 checks match)
- [ ] Manual on-stage test script passes (preflight + smoke tests)
- [ ] Docs are updated (API docs, message catalogue changelog, SPEC / DEMO.md if copy changed)
- [ ] Commit message follows conventional format (feat, fix, refactor, etc.)
- [ ] No hardcoded secrets, no hype language, no unverified claims

## 8. Code freeze policy

**90 minutes before the first demo start time, the main branch is frozen:**
- No new commits
- No rebases or force-pushes
- Only hotfixes for blocker issues (crashes, data loss) are cherry-picked via emergency PR
- Final rehearsal: `make demo-check` + manual checklist (all must pass)

**During freeze:**
- Ujjwal runs the demo against the lab backend and the demo laptop
- Omkar reviews the audit log and dispute resolution
- Both walk through the 3-min and 7-min cuts once each

## 9. Test data policy

**Real data:** Never. The prototype runs on simulated merchants and rainfall.

**Demo data:** Synthetic slip images (hospital letterhead templates with embedded JSON), synthetic merchant names and dates, synthetic settlement records. All marked SIMULATED in the UI.

**Free-tier AI constraint:** Free-tier Gemini content may be used by Google to improve products. Send only demo data, never real customer slips or merchant records.

**Persistent test data:** Committed sample slips in `backend/data/slips/`, the pilot shops in `backend/data/zones.json` (generated at seed 20251019), and cached Open-Meteo rainfall in `backend/data/weather/`. All deterministic and version-controlled.

## 10. Coverage targets

| Layer | Target | Measured 3 Oct 2026 | Status |
|---|---|---|---|
| Backend (fast suite, `chhatri/`) | 80 % | 98.85 % | Gate passes |
| Infra (`scripts/`) | 90 % | 99.44 % | Gate passes |
| Frontend | no gate | not measured (`npm run test:coverage` was not run) | not measured |
| Slow tests | all pass | 63 of 63 | Pass |
| Demo-check | all pass | 70 of 70 | Pass |
| AI evals | at least 95 % grounded (targets in the evaluation plan) | not measured | NOT MEASURED |

## Open questions

1. What is the target false-positive rate for the area-index trigger in a real pilot, and how is it measured? Owner: Ujjwal Pardeshi.
2. How should demo-check be extended to cover N5 (grievance ladder SLA clocks) when lender and insurer configs are finalized? Owner: Ujjwal Pardeshi.
3. Should the slip extraction eval set include real hospital slips (privacy, consent, labelling required)? Owner: Omkar Kadam.
4. What is the on-site contingency if network fails and the demo laptop reverts to offline mode? Owner: Ujjwal Pardeshi (backup video + static deploy).

## Changelog

- 2026-10-03 · v2 · rewritten from measured counts (backend 3,221 fast and 63 slow, infra 164, frontend 1,340, demo-check 70) with the feature-to-test map in section 3, the CI description matched to `ci.yml`, PLANNED rows removed, and the demo-check flag set explained
- 2026-10-02 · v1.4 · linked per-feature test lists (implementation guide) and the AI evaluation plan
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: N2 and N3 section headers updated with provider statuses (Gemini PLANNED, Sarvam LIVE, Tesseract PLANNED); test status table rows clarified to show current (LIVE Sarvam) and planned (Gemini) eval paths; grounded-answer eval and slip extraction evals marked with provider availability; intent detection section clarified.
- 2026-10-02 · v1 · first draft, from the test results and the definition-of-done checklist.
