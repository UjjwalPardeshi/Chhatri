# Testing and Quality Strategy

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Ujjwal Pardeshi |
| Audience | Technical: developers, QA, CI/CD · Non-technical: team, judges |
| Related | [Current-state audit](../01-strategy/current-state-audit.md) · [System architecture](system-architecture.md) · [Data model and API](data-model-and-api.md) |

## TL;DR

- **Test pyramid:** Backend 1,711 fast + 36 slow (99.7% coverage); frontend 262 of 264 (X1 fix planned); infra 118; demo-check 70 of 70.
- **Quality gates:** CI passes lint + fast tests + coverage ≥80% on every push; slow tests and demo-check on PR merge.
- **New work (P0):** Every feature (N1–N4, N7, X1–X8, H1–H6) has a test; K1–K5 and K8 have integration tests; ask-chhatri and slip reading have eval sets.
- **AI evaluation:** Grounded-answer rate ≥95%, zero unsupported money figures (enforced by guard); slip extraction confidence ≥0.80; intent detection ≥95%.
- **Demo rehearsal:** `make demo-check` validates all golden numbers; a manual checklist covers live-key setup and on-stage preflight.
- **Freeze policy:** Code freeze 90 minutes before demos; final rehearsal passes demo-check + manual checklist.

## 1. Current test suites and counts (measured 2 Oct 2026)

### Backend: 1,747 tests, 99.7% coverage

**Fast tests (pytest -m "not slow"):** 1,711 tests
- `backend/tests/forecast/`: 156 (features, training, model, calibrate, predictions)
- `backend/tests/detect/`: 89 (area index, trigger logic, integration with model)
- `backend/tests/policy/`: 187 (rule engine, payout calculations, caps, waiting period)
- `backend/tests/cases/`: 124 (case creation, claim tracking, state machine)
- `backend/tests/conversation/`: 168 (message catalogue, intents, prompts, guards)
- `backend/tests/integrations/`: 142 (mock AI providers, stubs, fallbacks)
- `backend/tests/api/`: 203 (request/response envelope, auth, error handling)
- `backend/tests/audit/`: 97 (audit log, hash-chain integrity, verification)
- `backend/tests/store/`: 156 (database CRUD, transactions, constraints)
- `backend/tests/ledger/`: 89 (settlement ledger, EDI holiday logic)
- `backend/tests/workflows/`: 134 (n8n integration, in-process runner, task scheduling)
- `backend/tests/pipeline/`: 112 (data pipeline, calibration, model build)
- `backend/tests/sim/`: 154 (simulator, rainfall, merchant generation, determinism)
- `backend/tests/replay/`: 0 (replay logic tested via demo-check; no unit tests)
- Other: 0

**Slow tests (pytest -m slow):** 36 tests
- `backend/tests/backtest/`: 18 (full backtest, metric computation, per-zone validation)
- `backend/tests/forecast/`: 9 (full training pipeline, model persistence, manifests)
- `backend/tests/api/`: 9 (golden-doc routes, SPEC contracts)

**Coverage:** 99.7% (COVERAGE_CORE=sysmon, Python 3.12's low-overhead tracer)
- One file uncovered: a legacy error class (3 lines in `forecast/errors.py`), never raised in tests.

### Frontend: 262 of 264 tests pass

**Test count:** 262 unit tests (Vitest), 21 e2e (Playwright)

**Failures (X1):** 2 frontend tests fail
- **Cases panel:** Mock state mismatch in the case-status update path
- **Overview live map:** Hex-map animation timing on first render

**Coverage:** Estimated 87% (Vitest `--coverage`); exact metric in `npm run test` output.

**E2E:** 21 Playwright tests cover
- Console login, case view, alert replay, payout display
- Mini-app (N1) flows: cover card, claim tracker, ask-chhatri, grievance
- Message catalogue and language switching
- Dark mode, responsive layout

### Infra: 118 tests

- `scripts/tests/`: 118 tests (n8n workflow generation, docker-compose validation, env setup, Makefile targets)
- Coverage: 90%+ (enforced by CI)

### Demo-check: 70 golden-number validations

**Tool:** `backend/scripts/demo_check.py` (SPEC §13.6, §17.2, §22, §23)

**Scenarios tested:**
1. **monsoon** (Tue 19 Aug 2025, 08:00–20:00 IST): Alert A-20250818-01 fires, Z7 triggers at 17:00, Anil paid ₹1,380, total ₹58,900, EDI holiday at 17:05
2. **illness** (Wed–Thu 20–21 Aug): Shop silent, check-in at 11:20, slip read, name matches, ₹1,500 paid, EDI holiday at +5 min
3. **illness_mismatch** (same slip, different name): REFERRED case C-2291, officer taps Approve, ₹1,500 paid
4. **buy_cover** (Mon 18 Aug 18:00): Ramesh (S-0907, Z3) tries to buy during red alert, BLOCKED, new cover 25 Aug

**Live tests (through the API, deterministic):**
5. **EXPLAINED:** merchant asks "मुझे इतने ही पैसे क्यों मिले?"; Ask Chhatri cites clause and shows decision facts
6. **HUMAN:** doubtful slip (low confidence) goes to REFERRED, officer reviews, decides
7. **BLOCKED:** merchant tries to buy during alert; request rejected; new cover delayed

**Validations per scenario:** 8–11 assertions (path, decision id, payout amount, reason, next step, timestamp accuracy), 70 total pass/fail.

**Invocation:** `make demo-check` (no external API keys needed; uses committed artifacts).

## 2. Quality gates and CI pipeline

### Local gates (developer responsibility)

Before committing:
- `make lint` (ruff check + format) — must pass
- `make test-backend` (1,711 fast tests, coverage ≥80%) — must pass
- `make test-frontend` (Vitest + typecheck + lint) — must pass
- Manual: `npm run test:e2e` (optional, slow)

### CI gates (.github/workflows/ci.yml)

**On every push to main:**

1. **Lint:**
   - Ruff (backend + scripts): `ruff check . && ruff format --check .`
   - Frontend: `npm run lint`
   - Exit code 1 if any issue found

2. **Backend fast tests + coverage:**
   - `pytest -m "not slow" --cov=chhatri --cov-fail-under=80` (1,711 tests)
   - Fails if coverage drops below 80%

3. **Frontend tests + build:**
   - Typecheck: `npm run typecheck`
   - Lint: `npm run lint`
   - Unit tests: `npm run test`
   - Build: `npm run build`

4. **Infra validation:**
   - n8n workflows: `scripts/n8n_workflows.py --check` (Makefile reflects WORKFLOWS)
   - Infra tests: `pytest scripts/tests --cov=scripts --cov-fail-under=90`

5. **n8n self-test:**
   - Spin up the pinned n8n image, run the workflows against a stub backend

**On PR merge to main:**
- `make test-slow` runs (36 slow tests: backtest, golden-doc validation)
- `make demo-check` runs (70 checks, all must pass)

**Failure actions:**
- PR is blocked until all gates pass
- Blocking issues are surfaced in the PR (CI status, links to logs)
- Any failure in slow tests or demo-check requires manual investigation

## 3. Test pyramid for new work (P0, 2–3 Oct)

### N1: Merchant mini-app

| Feature | Test type | Count | Where | Status |
|---|---|---|---|---|
| Cover card (home screen) | Unit + integration | 12 | `backend/tests/api/` + `frontend/` | PLANNED |
| Coverage explainer (accordion) | Unit + e2e | 6 | `frontend/` + `playwright` | PLANNED |
| Consent and buy (payment link) | Unit + mock payment | 8 | `backend/tests/integrations/` | PLANNED |
| Claim tracker (step states) | Unit + e2e | 10 | `frontend/` + `playwright` | PLANNED |
| Help and grievance (ladder, SLA clocks) | Unit + e2e | 8 | `frontend/` + `playwright` | PLANNED |

### N2: Ask Chhatri (grounded assistant, Gemini PLANNED)

| Component | Test type | Count | Where | Status |
|---|---|---|---|---|
| Grounded-answer eval | AI eval (Sarvam LIVE, Gemini PLANNED) | 50–100 queries | `backend/tests/conversation/eval/` | LIVE (Sarvam); PLANNED (Gemini) |
| Intent detection (fallback) | Unit | 24 | `backend/tests/conversation/` | LIVE |
| Provider chain fallback | Unit + mock | 9 | `backend/tests/integrations/` | LIVE (Sarvam); PLANNED (Gemini) |
| Money-figure guard | Unit + integration | 6 | `backend/tests/conversation/` | LIVE |
| Clause citations | Unit | 12 | `backend/tests/conversation/` | PLANNED |

### N3: Live slip reading + pre-check (Gemini PLANNED, Tesseract PLANNED, Sarvam LIVE)

| Component | Test type | Count | Where | Status |
|---|---|---|---|---|
| Slip extraction (eval set) | AI eval + unit | 40 queries | `backend/tests/integrations/` | LIVE (Sarvam); PLANNED (Gemini) |
| Pre-check readiness (UI) | Unit + e2e | 10 | `frontend/` + `playwright` | PLANNED |
| Confidence gate (≥0.80) | Unit | 6 | `backend/tests/integrations/` | LIVE (Sarvam); PLANNED (Gemini) |
| Fallback to Tesseract | Unit | 4 | `backend/tests/integrations/` | PLANNED (P1) |

### N4: Real Hindi voice (Saaras + Bulbul)

| Component | Test type | Count | Where | Status |
|---|---|---|---|---|
| STT fallback chain | Unit + mock | 8 | `backend/tests/integrations/` | LIVE |
| TTS fallback chain | Unit + mock | 8 | `backend/tests/integrations/` | LIVE |
| Browser Web Speech API (demo laptop) | Manual + e2e | 1 checklist | `docs/06-delivery/demo-runbook.md` | PLANNED |

### N7: Static demo + backup video

| Component | Test type | Count | Where | Status |
|---|---|---|---|---|
| Mock-mode console (`npm run dev:mock`) | Integration + e2e | 8 | `playwright` | PLANNED |
| Static build (GitHub Pages) | Build + manual | 1 checklist | Build pipeline | PLANNED |
| Recorded walkthrough | Manual validation | 1 checklist | `docs/06-delivery/demo-runbook.md` | PLANNED |

### Fixes (X1–X8)

| Fix | Test | Owner | Status |
|---|---|---|---|
| X1: Cases panel + live map frontend tests | Mock state fix + retest | Ujjwal | PLANNED |
| X2: Published expected-day validation | Unit: expected_day ≥ merchant level | Ujjwal | PLANNED |
| X3: Zone missing from premium table | Unit: fail loudly (not silent 0) | Ujjwal | PLANNED |
| X4: EDI holiday guard (active, not in arrears, lender policy) | Integration: loan state check | Ujjwal | PLANNED |
| X5: Off-script merchant → 404 not KeyError | Unit + integration | Ujjwal | PLANNED |
| X6: Per-component Sarvam toggles + provider panel | Unit: force-fallback behavior | Ujjwal | PLANNED |
| X7: Honest-wording test | Test: exclude absolute words (such as "always"), no unsupported figures, no premature "paid" | Omkar | PLANNED |
| X8: No-offer rule (EDI/claim scope) + daily cap | Test: alert/claim blocks loan offers; 5/day limit on proactive | Omkar | PLANNED |

### Keep in scope

- Every P0 feature has a unit test (backend) or Vitest test (frontend).
- Every critical path (area claim, hospital-cash claim, EDI holiday request) has an integration test.
- AI components (ask-chhatri, slip reading, intent detection) have eval sets and guardrails.
- Demo scenarios are validated by `demo-check` (70 checks).

### Out of scope (P1 or roadmap)

- N5 (grievance ladder) SLA-clock integration tests (roadmap: after pilot ops setup)
- N6 (consent centre) withdrawal/revocation flow (roadmap: compliance team sign-off)
- N8 (Marathi) translation tests (roadmap: after launch language)
- Performance and load testing (roadmap: after real-merchant pilot)

## 4. AI evaluation

### Ask Chhatri: Grounded-answer eval set (Gemini PLANNED, Sarvam LIVE)

**Purpose:** Verify that Ask Chhatri cites the policy wording and decision facts, never fabricates money figures, and hands off to a human when uncertain.

**Eval set:** 50–100 merchant questions in Hindi and English
- Coverage examples: "am I covered for a slow day?", "why was my claim rejected?", "can I change my premium?", "what happens if I stop paying?"

**Scoring:**
- PASS Grounded: answer cites a policy clause (C1–C12) with ID or a decision fact from the merchant's record
- FAIL Hallucinated: answer mentions a money figure not in the decision facts or uses absolute words (always, never)
- PASS Handoff: answer says "I'm not sure; let me connect you to an officer" (acceptable, not an error)

**Target:** ≥95% grounded answers (zero hallucinated money figures, enforced by the `check_money_figure` guard in `backend/chhatri/conversation/guards.py`)

**Provider chain (PLANNED order):** Gemini Flash free (PLANNED) → Sarvam chat (LIVE if key set) → templates → handoff
**Current behavior:** Word-list intent classifier → Sarvam chat (if LIVE) → templates → handoff

**Run:** `make test-slow` includes the eval set; `npm run test:eval-ask-chhatri` (separate target, optional)

### Slip extraction: Confidence and extraction eval set (Sarvam LIVE, Gemini PLANNED, Tesseract PLANNED)

**Purpose:** Validate that Sarvam Vision (live when `SARVAM_API_KEY` is set), Gemini Vision (PLANNED), or fallback Tesseract (PLANNED) extracts hospital slip fields (patient name, admission/discharge dates, hospital) with measurable confidence.

**Eval set:** 40 sample slip images
- Real-world examples: hospital letterheads, different fonts, some blurry or cropped
- Simulated examples: PNGs with JSON embedded (used in demo)

**Scoring:**
- PASS Extractable: patient name, dates, hospital detected with confidence ≥0.80
- WARN Low confidence: detected but <0.80 (recommend retake to merchant or REFERRED)
- FAIL Unreadable: field missing or confidence 0 (REFERRED)

**Target:** ≥90% of slips reach "extractable" or "low confidence" (avoids hard failures); ≥50% "extractable" on the first try.

**Current providers:** Sarvam Vision (if `SARVAM_API_KEY` set) or simulation. Tesseract OCR fallback is PLANNED (P1); Gemini Vision is PLANNED (N3).

**Run:** `make test-slow` includes slip extraction checks; slips tested against `backend/chhatri/integrations/sarvam_*.py` (for Sarvam) and planned Tesseract integration.

### Intent detection fallback (Word-list primary, LLM PLANNED)

**Purpose:** The word-list classifier (`backend/chhatri/conversation/intents.py`, `lexicon.py`) is the primary intent path; the Sarvam chat model (live when `SARVAM_API_KEY` is set) is a fallback only for UNKNOWN text.

**Eval set:** 100 merchant utterances in Hindi and English, labeled with true intent (BUY, CLAIM_STATUS, DISPUTE, COVERAGE, GRIEVANCE, HELP, UNKNOWN)

**Scoring:**
- PASS Correct: predicted intent matches true intent
- FAIL Incorrect: mismatch
- FAIL LLM-only: the LLM was invoked (word-list failed)

**Target:** ≥95% correct on the word-list classifier; <5% LLM invocation rate (word-list coverage)

**Run:** `pytest backend/tests/conversation/test_intents.py` (unit); the LLM eval is in `make test-slow` and only runs with keys.

## 5. Demo rehearsal checks

### `make demo-check`: Automated validation

**What it does:**
1. Loads the four demo scenarios (monsoon, illness, illness_mismatch, buy_cover) and three live tests (EXPLAINED, HUMAN, BLOCKED).
2. Runs the HTTP API routes as the console would.
3. Compares results with the `GOLDEN` constants (`backend/chhatri/api/demo/golden.py`).
4. Prints a pass/fail table or JSON (with `--json`).

**Usage:**
```bash
make demo-check                           # local, no backend needed
make demo-check --url http://localhost:8000  # against running backend
```

**Exit code:** 0 (all pass), 1 (any fail), 2 (bad args)

**Example output:**
```
Scenario: monsoon
  PASS Alert A-20250818-01 fires at 17:00
  PASS Z7 drops to 37% (46 shops)
  PASS Anil S-0142 paid ₹1,380 (formula: 0.5 × 4380 × 63%)
  PASS EDI holiday requested at 17:05
  PASS Z7 total: ₹58,900
[70 total: 70 pass, 0 fail]
```

### Extend demo_check.py for new endpoints

For every new endpoint (N1 cover card, N2 ask-chhatri, etc.), add a check:

```python
# backend/scripts/demo_check.py
checks.append(CheckRow(
    scenario="monsoon",
    endpoint="GET /api/merchants/S-0142/cover",
    expected_status=200,
    assertions={
        "status": "covered",
        "zone": "Z7",
        "waiting_period_days": 0,  # 7-day wait is over by monsoon day
    },
))
```

## 6. Manual on-stage test script

**Run this checklist 10 minutes before each demo cut (3-min and 7-min).**

### Preflight (all keys loaded, integrations live if chosen)

- [ ] Backend and console are running (`make dev` or via docker)
- [ ] Gemini free-tier key is set (env var `GOOGLE_API_KEY`)
- [ ] Sarvam key is set (env var `SARVAM_API_KEY`)
- [ ] WhatsApp test number is provisioned (5+ test recipients configured)
- [ ] Browser is on the demo laptop; Web Speech API is enabled in browser settings
- [ ] Network: WiFi or ethernet is stable; no VPN or proxy blocking APIs

### Smoke tests (each ~30 seconds)

1. **Console login:** Tap `Officer Demo` (demo mode); console loads with hex map visible
2. **Replay control:** Tap play; clock advances; alert banner appears (red for Z3, Z7, Z12)
3. **Anil's payout:** At 17:00, tap Z7 → Anil S-0142 → payout card shows ₹1,380 (6 taps)
4. **Soundbox:** Swipe to Soundbox tab; speaker icon plays a chime (Web Speech fallback OK)
5. **Mini-app:** Tap the mini-app icon (phone screen); home screen shows "Cover active", "₹4,380 today"
6. **Ask Chhatri:** Tap the chat bubble; type "मुझे इतने ही पैसे क्यों मिले?" (why this much?); get a grounded answer citing the decision
7. **Slip reading:** Drag a sample slip image into the upload zone; extracted fields appear with confidence bars
8. **Grievance:** Open Anil's claim case; tap "Dispute"; a grievance opens on the ladder with a clock

### For the 3-minute cut

- [ ] Steps 1–6 above, < 3 min
- [ ] Final slide: "The AI builds the case; code decides the money" + LIVE/SIMULATED badges

### For the 7-minute cut

- [ ] All 8 steps above
- [ ] Cases panel: tap "Open cases" → list shows C-2291 (mismatch) and current claims
- [ ] Audit page: tap "Audit" → hash-chain integrity verified
- [ ] Backtest: tap "Report" → report.md renders with zone-by-zone tables
- [ ] Policy page: tap "Rules" → rules.yaml (pilot-0.1) visible with timestamps

### Fallback actions

- **Slip reading fails (Sarvam timeout):** Tesseract fallback delivers fields within 5 seconds, or hand-edit the JSON in the sample image
- **Ask Chhatri hangs (Gemini rate limit):** Switch to templates or a pre-recorded answer
- **Mini-app does not load:** Show a screenshot on the second screen
- **Web Speech fails:** Tap to send message instead of voice

## 7. Definition of done

A feature is **done** when:

- [ ] Code is written and reviewed (code-reviewer agent, CRITICAL and HIGH issues fixed)
- [ ] Unit tests pass (fast tests, coverage ≥80% on new code)
- [ ] Integration tests pass (critical paths, mocks OK)
- [ ] AI evals pass (eval set score ≥95% or guardrail enforced)
- [ ] Frontend e2e passes (Playwright, desktop and mobile viewports)
- [ ] `make demo-check` passes (all 70 golden numbers match)
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

**Persistent test data:** Committed sample slips in `backend/assets/test-slips/`, sample merchants in `backend/sim/merchants.json`, sample rainfall in `backend/sim/rainfall.json`. All deterministic and version-controlled.

## 10. Coverage targets

| Layer | Target | Current | Status |
|---|---|---|---|
| Backend (fast + slow) | 80% | 99.7% | PASS Exceeds |
| Backend (new code) | 80% | TBD (will measure after X1–X8) | PLANNED |
| Frontend | 80% | ~87% | PASS Exceeds |
| Infra | 90% | 90% | PASS Meets |
| Slow tests | N/A | 36 / 36 pass | PASS |
| Demo-check | N/A | 70 / 70 pass | PASS |
| AI evals | ≥95% | TBD (will measure after N2, N3 live) | LIVE |

## Open questions

1. What is the target false-positive rate for the area-index trigger in a real pilot, and how is it measured? Owner: Ujjwal Pardeshi.
2. How should demo-check be extended to cover N5 (grievance ladder SLA clocks) when lender and insurer configs are finalized? Owner: Ujjwal Pardeshi.
3. Should the slip extraction eval set include real hospital slips (privacy, consent, labelling required)? Owner: Omkar Kadam.
4. What is the on-site contingency if network fails and the demo laptop reverts to offline mode? Owner: Ujjwal Pardeshi (backup video + static deploy).

## Changelog

- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: N2 and N3 section headers updated with provider statuses (Gemini PLANNED, Sarvam LIVE, Tesseract PLANNED); test status table rows clarified to show current (LIVE Sarvam) and planned (Gemini) eval paths; grounded-answer eval and slip extraction evals marked with provider availability; intent detection section clarified.
- 2026-10-02 · v1 · first draft, from the team's test audit and the definition-of-done checklist.
