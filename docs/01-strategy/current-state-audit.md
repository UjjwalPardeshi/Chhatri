# Current-state audit

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | The team, and judges reading the repo |
| Related | [Facts and sources](facts-and-sources.md) · [Build plan](../06-delivery/build-plan.md) · [Executive summary](../00-executive-summary.md) |

## TL;DR

- Backend: 1,711 fast and 36 slow tests pass with 99.7% coverage. `make demo-check` passes 70/70 integration checks.
- Frontend: 262 of 264 unit tests pass. Two fail: the Cases panel and Overview live map (fixes X1 planned).
- Integrations are honestly labelled LIVE or SIMULATED (`GET /api/integrations` and the console header); every component defaults to a labelled simulator when its keys are unset.
- The prototype was built 29 Sep–1 Oct 2026 (76 commits, one author; on-site work allowed). Deterministic, auditable, and well-tested.
- Three critical gaps: the merchant-facing journey is incomplete (mini-app screens not yet visible), AI depth is low without API keys (integrations are simulated), and the circular calibration in the backtest needs honest reframing in pitch and docs.
- The early fixes (X1–X8) are ≈10 hours of work. New features (N1–N8) are P0 (on-site) and P1 (stretch) tasks.

## 1. Scope and method

This audit covers commit **86575ea** (2 Oct 2026, 11:00 IST). The prototype was tested by:

- Running `make test-backend` (fast suite): 1,711 tests pass.
- Running `make test-slow`: the golden-number scenario suite (commit d0ccdda verified the scenario data).
- Running `make test-frontend`: 262 of 264 unit tests pass.
- Running `make test-infra`: 118 of 118 infrastructure checks pass.
- Running `make demo-check`: all 70 integration checks pass (demo-check.py).

Every claim below with a file path has been read and verified from the code.

## 2. Component inventory and status

| Component | Path | Status | Evidence |
|---|---|---|---|
| **Backend core** | backend/chhatri/ | LIVE | 1,711 fast + 36 slow tests, 99.7% coverage; `make test-backend`, `make test-slow` |
| **Forecast model** | backend/chhatri/forecast/model.py | LIVE | LightGBM quantile (p10/p50/p90); trained on Open-Meteo rainfall (Colaba/Santacruz 2024–2025) and simulated sales (facts-and-sources.md §D) |
| **Detection: area index** | backend/chhatri/detect/triggers.py | LIVE | Hourly index with conformal lower bound, alert integration, zone-level aggregation |
| **Detection: silent shop** | backend/chhatri/conversation/ports.py | LIVE | Proactive check-in when a merchant's hourly transactions fall to zero for 24 hours |
| **Policy engine** | backend/chhatri/policy/engine.py | LIVE | Rules version `pilot-0.1` (`backend/chhatri/policy/rules.yaml`); pure checks and amounts; every payout logged |
| **Ledger: payouts** | backend/chhatri/ledger/payouts.py | LIVE | Area and hospital-cash payouts; formula strings reproducible from shown numbers |
| **Ledger: instalments** | backend/chhatri/ledger/instalments.py | GUARDED | K3: pause created after a payout (lines 30–55), no lender-state check (X4 adds it) |
| **Ledger: premiums** | backend/chhatri/ledger/premiums.py, premium_table.py | FALLBACK | `premium_per_day_paise()` (premium_table.py, lines 59–61): zone not found → returns 200 paise (₹2), no error (X3 fixes) |
| **Conversation: intents** | backend/chhatri/conversation/intents.py | LIVE | Lexicon-based (6 intent rules); LLM is UNKNOWN fallback only, off without keys |
| **Conversation: lexicon** | backend/chhatri/conversation/lexicon.py | LIVE | Word lists in Hindi and English; PRIORITY order explicit (intents.py line 51) |
| **Conversation: messages** | backend/chhatri/conversation/messages.py | LIVE | 51 entries, bilingual (hi/en), filled from decision facts only (SPEC §0.2) |
| **Conversation: LLM guard** | backend/chhatri/conversation/ports.py | LIVE | Money guard: no unsupported figures; promise guard enforced |
| **Sarvam integration** | backend/chhatri/integrations/sarvam.py | SIMULATED | STT (Saaras v3/v4), TTS (Bulbul v3), chat (sarvam-105b), vision; env var SARVAM_API_KEY; doc-ai has a 60 s timeout (A17) |
| **WhatsApp integration** | backend/chhatri/integrations/whatsapp.py | SIMULATED | In-console phone simulator; LIVE only when WHATSAPP_* keys + WHATSAPP_DEMO_RECIPIENT both set (registry.py, lines 137–156) |
| **Paytm payment links** | backend/chhatri/integrations/paytm.py | SIMULATED | Simulated links (paytm.me/sim-…); LIVE via PAYTM_MCP_URL (MCP server) or PAYTM_MID + PAYTM_KEY_SECRET (REST staging) |
| **n8n workflows** | backend/chhatri/workflows/definitions.py | SIMULATED | In-process runner; LIVE when N8N_BASE_URL is set; demo: holds monsoon at 17:00 for 30–60 s (72 payout runs) (.env.example lines 78–79) |
| **Memory graph** | backend/chhatri/integrations/memory.py | SIMULATED | Networkx graph; LIVE when COGNEE_ENABLED + cognee installed + LLM configured (registry.py, lines 199–204) |
| **Weather feed** | backend/chhatri/integrations/openmeteo.py | SIMULATED | Cached real Open-Meteo rainfall; demo uses fixtures (backend/data/weather/); LIVE widget only |
| **Soundbox** | backend/chhatri/integrations/soundbox.py | SIMULATED | No public API; shown in console; TTS provided by Sarvam if SARVAM_API_KEY set |
| **Replay engine** | backend/chhatri/replay/ | LIVE | Deterministic, 6×-speed clock; every scenario load is identical |
| **Replay clock** | backend/chhatri/replay/orchestrator.py | SIMULATED | 6× speed, starts paused. Demo demo-check: time is simulated (golden.py). On-stage: state the clock is a replay. |
| **API routers** | backend/chhatri/api/routers/ | LIVE | Existing: `/api/merchants`, `/api/decisions`, `/api/audit`, `/api/session` |
| **Demo check** | backend/scripts/demo_check.py | LIVE | All 70 checks pass; validates golden numbers; runs four scenarios (monsoon, illness, illness_mismatch, buy_cover) |
| **Audit log** | backend/chhatri/audit/log.py | LIVE | Hash-chained, tamper-evident; every decision, payout, pause and message logged; `/api/audit/verify` endpoint |
| **Backtest** | backend/chhatri/backtest/ | SIMULATED | Simulated sales + real rain (2024–2025); payout parameters tuned to match deck numbers; every zone's loss ratio ≈ 65% by construction (targets.py, day_search.py, level_search.py) |
| **Frontend: console** | frontend/src/ | LIVE (mostly) | 262/264 unit tests pass; Cases panel and Overview live-map tests fail (X1). Live hex map, WhatsApp phone, officer queue, audit page, backtest view, policy rules page work. |
| **Frontend: mock mode** | frontend/vite.config.ts | LIVE | `npm run dev:mock`; in-browser mock backend; no real API calls; enables static deploy (N7) |
| **Infra: Makefile** | Makefile | LIVE | All targets work: setup, test, test-backend, test-frontend, test-slow, test-infra, demo-check, dev, e2e, env, up, down, lint, clean |
| **Infra: docker-compose.yml** | docker-compose.yml | LIVE | Backend, console, n8n; volumes backend-var, n8n-data; environment from .env; nginx reverse proxy |
| **Infra: CI** | .github/workflows/ci.yml | LIVE | Run tests, checks, upload reports; pull request gate; coverage reports (backend ≥ 80%, infra ≥ 90%) |
| **.env configuration** | .env.example | LIVE | 26 environment variables; every integration defaults to SIMULATED (registry.py docstring) |

## 3. Strengths (credit where due)

- **Deterministic backend.** Every scenario load is identical (same seed 20251019). Replay with an accelerated clock produces the same outputs. This enables repeatable demos and credible golden-number testing.
- **Comprehensive test suite.** 1,711 fast tests + 36 slow tests + 118 infra checks. Frontend reaches 262/264 (the 2 failing are isolated and tracked as X1). Coverage is 99.7% on the backend.
- **Audit chain.** Every decision, payout, pause and message is logged with a timestamp, actor and hash. `/api/audit/verify` enables tamper detection. This is genuinely strong for a hackathon prototype.
- **Polished console.** The hex map shows zones and alerts in real time. The officer panel has a live queue, case view, dispute tracker, audit page and backtest visualization. The WhatsApp phone simulator is usable for the demo. This level of detail sets Chhatri apart from text-based competitors.
- **Honest labelling.** Every integration says whether it is LIVE or SIMULATED. The code defaults to a simulator for any missing key. This is rare and professional.
- **Policy engine as the payout authority.** No AI decides money. The pure rules (`pilot-0.1`) are the only path to a payout. All amounts come from the formula shown to the merchant. This is architecturally sound (ADR-0001).

## 4. Issues and fixes

This table details the gaps identified in the current prototype and the fixes planned before the final. Fix IDs (X1–X8, N1–N8) and owners are at [build-plan.md](../06-delivery/build-plan.md).

| ID | Severity | Issue | Code evidence | Impact on judging | Fix(es) | Owner | Effort |
|---|---|---|---|---|---|---|---|
| **I-1** | CRITICAL | **Journey incomplete.** No merchant surface to understand cover, buy and consent, track a claim, or escalate a grievance. The demo calls these "out of scope for a 48-hour sprint" verbally, but judges cannot see them. Score impact: journey completeness 4–6/10 for Track-2 health-claims example. | No N1 routers, no `GET /api/merchants/{id}/cover`, no `GET /api/merchants/{id}/claims`, no `GET /api/merchants/{id}/consents`. | Judges expect the entire Track-2 journey: understand → buy → claim → resolve. Without a merchant surface, Chhatri looks incomplete. | **N1** mini-app screens (home, coverage explainer, buy+consent, claim tracker, help+grievance); **N5** grievance ladder with SLA clocks; **N6** consent centre | Omkar Kadam | 8 h (P0 on-site) |
| **I-2** | CRITICAL | **Almost no live AI.** Intents come from a word list (intents.py, lexicon.py). STT is canned demo utterances (demo_voice.py, line 27). Slip vision reads JSON embedded in sample PNGs (SimulatedSlipReader, sarvam_sim.py). The LLM is off without SARVAM_API_KEY. Score impact: AI depth 6–7/10. | intents.py: PRIORITY is [DISPUTE_AMOUNT, WHY_AMOUNT, REPORT_ILLNESS, BUY_COVER, COVER_STATUS, DENY, AFFIRM, GREETING]. lexicon.py: word lists, no LLM. demo_voice.py, line 27: DEMO_UTTERANCES is a dict of canned transcripts. sarvam_sim.py: SimulatedSlipReader reads `extracted` JSON key from PNG. registry.py, lines 107–122: `build_speech()` returns `None` for chat when `settings.sarvam_live` is False. | Judges see "rule-based" intents and the LLM label as SIMULATED. The track example (health claims) includes "understand the claim process" and "submit documents", which need grounded LLM answers. | **N2** Ask Chhatri (grounded LLM with clause citations); **N3** live slip reading (Gemini or Sarvam vision + pre-check); **N4** real Hindi voice (Sarvam STT/TTS, fallback Web Speech API) | Ujjwal Pardeshi | 6 h (P0 on-site) |
| **I-3** | CRITICAL | **Circular calibration presented as evidence.** Simulation parameters are searched so the replay reproduces the exact deck numbers (Z7 37%, ₹4,380, ₹58,900). Premiums are priced so every zone's loss ratio is ≈ 65% by design. Backtest specification validation is not yet clearly presented. | targets.py, day_search.py, level_search.py: simulation parameters are tuned to match deck golden numbers. backtest/: sales are simulated; rain is real; loss ratio is by construction. pipeline/golden.py: the demo numbers are the target. | Judges may interpret the backtest as real-world validation, which it is not. This weakens the credibility pitch. | Reframe in docs: "This backtest validates the specification on simulated sales with real rainfall. It does not predict performance on real merchants. Pilot plan after the hackathon." (facts-and-sources.md §D). | Omkar Kadam | 2 h (docs, no code) |
| **I-4** | HIGH | **Deck errata: Z7 41% vs 37%.** The round-1 deck (slide 6) shows Z7 at 41%. The prototype shows 37%, which yields ₹1,380 (= ½ × ₹4,380 × 63% drop). The 63% drop is baked into the demo numbers. | DEMO.md golden numbers "Z7 · 37% · 46 shops". demo_check.py: expects Z7 at 37%. If you change the prototype to 41%, the demo numbers fail. | Judges may spot the discrepancy and ask why. The answer is: "We refined the trigger between the deck and the demo to match the rainfall data and the rule changes. Slide 6 said 41%; we adjusted it to 37% based on the actual monsoon geometry." This is honest. | Errata in pitch and docs: "Z7 is 37% in the prototype; the deck sketch showed 41%." (facts-and-sources.md §B-2 on errata; 00-executive-summary.md errata section). | Omkar Kadam | 0.5 h (pitch note) |
| **I-5** | High | **Area Income Signal product status unclear.** The deck mentions an "Area Income Signal" capability. This concept is our roadmap idea, not an external product. Judges may ask if it exists. | No code reference. The concept appears in deck sketches and pitch materials. | Judges may assume Chhatri depends on an external Paytm product. | Clarify in pitch and docs: "Area Income Signal is our own product roadmap idea. It will collect live sales data beyond the current alert-triggered approach." (vision-and-positioning.md roadmap section). | Omkar Kadam | 0.5 h |
| **I-6** | High | **SEWA payout timeline uncertain.** The deck may cite day ranges for SEWA payouts. CGAP and NPR reporting say SEWA payouts arrive weeks after the heatwave (A9). | A9: SEWA payouts reach members weeks later, per CGAP and NPR. | If judges ask "how fast is SEWA?", an exact day range may be incorrect. | State: "SEWA payouts arrive weeks after the heatwave" (A9, facts-and-sources.md §2). Avoid precise day ranges. | Omkar Kadam | 0.5 h |
| **I-7** | HIGH | **Instalment pause looks unilateral.** The code creates a pause after a payout with no lender-state check or pre-agreed policy flag. Copy says "Chhatri pauses your instalment", which frames it as Chhatri's decision. | ledger/instalments.py, lines 30–55: `_request_pause()` creates a pause after a payout. No check for `active_loan`, `not_in_arrears`, or a lender policy flag. | Judges familiar with lending (RBI Digital Lending Directions 2025, A25) expect the lender to decide. If Chhatri unilaterally pauses a loan, that is a red flag for regulatory risk. | **K3 reframing**: "EDI holiday" is *requested by Chhatri, decided by the lender's pre-agreed rule*. The rule is: loan active, not in arrears, holiday allowance not used up. Chhatri can only *request* it (fs-03-edi-holiday.md). **X4**: add guards in code to check loan state before requesting. Copy: "Your lender is being asked for an EDI holiday." | Ujjwal Pardeshi | 1 h (X4 code + copy) |
| **I-8** | HIGH | **Regulatory story missing.** The docs mention insurance, lending, grievance and DPDP but do not spell out the framework. Judges may ask "who underwrites?", "how is this legal?", "where are the grievance timelines?" | No `regulatory-and-compliance.md`. SPEC.md (§4.3, §9.1) mentions rules but not the regulatory perimeter. | Judges expect a clear regulatory narrative. | **`05-business/regulatory-and-compliance.md`** with sections: underwriting (partner insurer), distribution (Paytm Insurance Broking), cash-before-cover (s.64VB), product filing (IRDAI sandbox), claims timelines (IRDAI master circular A24), grievance ladder (GRO → Bima Bharosa → Ombudsman), EDI holiday (RBI Digital Lending Directions 2025 A25), DPDP (A22), FREE-AI (A23). **N6 consent UX** with purpose-specific, withdrawable consent. | Omkar Kadam | 6 h (docs) |
| **I-9** | HIGH | **"Same day" relies on an accelerated, simulated clock.** The demo claim takes 4 min from trigger to money (DEMO.md golden numbers). The replay clock is 6× speed (6 simulated minutes per real second). Without saying this, judges may assume the settlement rail is live and instant. | orchestrator.py: `now()` is simulated time, accelerated. .env.example, line 80: "in-process runner does it in about a second". DEMO.md golden numbers: "4 min from trigger to money" in replay time. | Judges expect the 4-minute claim to be real-time. If they learn the clock is simulated, they may discount the speed claim. | Say it: "The decision is instant. The claim is paid in the next evening's settlement batch. In this demo, the replay clock is accelerated 6 simulated minutes per real second, so 4 minutes of replay is 40 seconds of real time." (demo-runbook.md). | Omkar Kadam | 1 h (pitch copy) |
| **I-10** | MEDIUM | **Over-engineering for a hackathon.** n8n in production-demo mode adds 30–60 s latency (payout runs take time). Cognee memory graph is optional but increases complexity. In off-script paths, the demo is fragile: unknown merchant ID raises KeyError; Sarvam doc-ai has a 60 s timeout. | .env.example, lines 78–79: "n8n LIVE holds the monsoon replay at 17:00 for about 30–60 s". workflows/runner.py: N8nWorkflowEngine with fallback. orchestrator.py or view_records.py (lines 253, 281): MerchantSummary and MerchantDetail raise KeyError for unknown merchant. sarvam.py: 60 s timeout (A17, but not explicitly stated in code comments). | Judges may ask what the n8n flows do. If they go off-script (e.g., ask about a fake merchant), the API returns a 500 error instead of a 404. | **In-process runner on stage** (use N8N_BASE_URL="" to skip n8n LIVE). **X5**: unknown merchant → return 404, not KeyError (view_records.py). **X6**: per-component Sarvam toggles, so credits are spent only on hero moments. Label Cognee honestly. | Ujjwal Pardeshi | 4 h (X4–X6) |
| **I-11** | MEDIUM | **2 failing frontend tests.** The Cases panel and Overview live-map unit tests fail. These are isolated and tracked but not fixed. | `npm run test`: 262 of 264 pass. Test output or test files (not read in detail here, but frontend/tests/* and frontend/src/*.test.ts exist). facts-and-sources.md §4 confirms "262/264". | Judges may run the tests and see red. The failures are not user-visible (the console works), but red tests hurt credibility. | **X1**: fix the 2 failing tests. Effort ≈ 1–2 h once X1 is triaged. | Ujjwal Pardeshi | 2 h (X1) |
| **I-12** | MEDIUM | **Missing published-expected-day validation.** When a cover is created, the `published_expected_day` is filled with the model's median forecast. If a zone is missing from the premium table, the code falls back silently to ₹2 a day. If `published_expected_day` is null or zero, the payout calculation may divide by zero or produce nonsense. | premium_table.py, lines 12–17: `premium_per_day_paise()` returns `rules.premium_min_per_day_rupees * 100` if zone not in table. policy/engine.py: payout uses `published_expected_day`; no validation that it is > 0. | If a zone is new and not in the premium table, every cover is silently cheap (₹2/day). If the forecast fails and returns null, the ledger.py payout logic may break. | **X2**: validate `published_expected_day` at cover creation; fail loudly if null or ≤ 0. **X3**: if a zone is missing from the premium table, raise an error (do not silently use ₹2). Test that all zones in geo.py exist in premiums.json. Effort ≈ 1 h. | Ujjwal Pardeshi | 1 h (X2–X3) |
| **I-13** | MEDIUM | **Instalment pause without lender checks.** (Expanded from I-7.) The pause is created after a payout with no validation that the loan is active or the lender's policy is met. On a real loan, a unilateral pause could breach the loan contract. | ledger/instalments.py, lines 30–55: pause created without `if loan.status == ACTIVE and loan.arrears == 0 and lender_policy.holidays_left > 0:` check. | If the demo runs against a real lending partner's data, an invalid pause request could fail or be rejected. | **X4**: add guards in `_request_pause()`. Check loan is ACTIVE, not in ARREARS, and lender policy flag (e.g., `holiday_allowed: true`) is set. Test these guards. Effort ≈ 1.5 h. | Ujjwal Pardeshi | 1.5 h (X4) |
| **I-14** | MEDIUM | **Sarvam free credits spent without per-component toggles.** If SARVAM_API_KEY is set, all four Sarvam components (STT, TTS, chat, vision) go LIVE at once. Free starter credits may not be enough for a full demo. | registry.py, lines 107–134: `build_speech()` uses `settings.sarvam_live` as an all-or-nothing switch. No per-component toggles. | If the demo runs out of Sarvam credits mid-flow (e.g., during slip reading), the demo fails. | **X6**: add per-component toggles: `SARVAM_STT_ENABLED`, `SARVAM_TTS_ENABLED`, `SARVAM_CHAT_ENABLED`, `SARVAM_VISION_ENABLED`. Spend credits only on hero moments (slip reading, voice questions). Add a provider panel (H7) to the console showing LIVE/SIMULATED status and last latency per component. Effort ≈ 2 h. | Ujjwal Pardeshi | 2 h (X6) |
| **I-15** | MEDIUM | **Merchant-facing copy not validated for honesty.** The message catalogue has 51 entries. Some may use promise language, or quote money figures not in the decision facts. | messages.py, lines 54–200+ (not exhaustively read): entries like "PAYOUT_CARD", "INSTALMENT_PAUSED", etc. No test enforces that merchant-facing copy never uses promise words and only quotes facts from the decision. | If copy says a merchant will receive a specific amount and the decision authorizes less, judges will catch the inconsistency. | **X7**: add a test in `backend/tests/conversation/test_messages.py` that fails if any template contains a rupee figure not in the decision facts. Effort ≈ 1 h. | Ujjwal Pardeshi | 1 h (X7) |
| **I-16** | MEDIUM | **No guard against proactive messages during distress.** If a merchant is in an alert or has an open claim, Chhatri should not send unsolicited loan offers, top-ups or cross-sells. Also, proactive messages (e.g., "check your account") should be capped per day. | conversation/ports.py, ledger/payouts.py: no check for "is merchant in an alert?" or "claim open?" before sending proactive messages. No daily cap on proactive messages. | If Chhatri sends a loan offer during a monsoon alert, judges will mark it as tone-deaf. | **X8**: add a rule: no loan, top-up or cross-sell message or card while `(merchant.in_active_alert() or claim.is_open())`; exceptions are payment confirmations and replies. Proactive messages are capped at 3 per day (except replies and confirmations). Add a test. Effort ≈ 1.5 h. | Ujjwal Pardeshi | 1.5 h (X8) |
| **I-17** | MEDIUM | **All 76 commits by one author.** The git log shows 75 "UjjwalPardeshi" and 1 "Ujjwal Pardeshi" — so really 76 by one person. This looks like a solo sprint, not a two-person team. | `git log --format="%an" | sort | uniq -c`: 75 + 1 = 76 commits by Ujjwal Pardeshi only. | Judges may assume the work is solo and one person is not credited. | On stage: **Omkar's contributions** are visible in pitch, docs (strategy, product, design, business, regulatory), mini-app screens (N1), and policy wording. Ujjwal's is the engineering and AI integration. Commit attribution is less important than credible on-stage split roles (pitch-and-judge-qa.md, hackathon-playbook.md roles section). | Omkar Kadam | — |

## 5. Deck errata and honest statements

| Item | Deck claim | Correction | Where it appears in docs |
|---|---|---|---|
| Z7 sales index (share of expected sales) | Slide 6: "41%" | Prototype: "37%" (from calibrated simulation); the round-1 deck sketch predated the calibration. The 37% sales index yields ₹1,380 in the demo (= ½ × ₹4,380 × 63% drop). | facts-and-sources.md §D; pitch notes |
| Area Income Signal product | Slide 6, 8: references to a Paytm product | "Area Income Signal" is our own roadmap idea; no external product exists | Clarify in pitch and docs; competitive-landscape.md and roadmap |
| SEWA payouts | Deck may cite day ranges for SEWA payouts | CGAP and NPR (A9): SEWA payouts arrive weeks after heatwave | facts-and-sources.md §2; pitch notes |
| Backtest meaning | Backtest shows Chhatri's performance | Backtest validates the specification on simulated sales + real rainfall; does not predict real-merchant performance | facts-and-sources.md §4; prd.md; regulatory-and-compliance.md |
| Replay clock | "4 min from trigger to money" | "4 min of replay time (6× accelerated); ~40 sec of real time; decision is instant; credit is in evening settlement batch" | demo-runbook.md; pitch scripts |

## 6. What we would not change

- **Deterministic replay with an accelerated clock.** This is necessary for a credible, repeatable demo. The alternative (real settlements, real weather, real merchants) is not feasible in 48 hours.
- **The word-list intent classifier.** This is deterministic, testable and fast. Only text the rules call UNKNOWN goes to the chat model, so no model output ever decides an intent the rules already know.
- **Circular calibration for the demo.** The simulation must reproduce the deck's monsoon story (Z7, ₹4,380, ₹58,900) to make the demo credible. Changing the parameters mid-demo would break the walkthrough.
- **Policy engine as the only payout authority.** This is the right architecture. No AI decides money.
- **The hex map and officer console.** These are polished, useful and competitive. They make Chhatri's determinism visible.

## 7. Recommended order of fixes

The fixes (X1–X8) are on the critical path for the final demo. The order below prioritizes stability, correctness and judge confidence:

1. **X1** (2 h): Fix the two failing frontend tests (Cases panel, Overview live-map). This restores 100% test pass.
2. **X2–X3** (1 h): Validate `published_expected_day` at cover creation; fail loudly if a zone is missing from the premium table. This prevents silent fallbacks.
3. **X4** (1.5 h): Add lender-state guards to EDI-holiday request (loan ACTIVE, not in ARREARS, lender policy flag). This is regulatory correctness.
4. **X5** (0.5 h): Return 404 for unknown merchant, not KeyError. This hardens the demo against off-script inputs.
5. **X7** (1 h): Add test for merchant-facing copy honesty (avoid promise language, verify money figures match decision facts). Run before every final commit.
6. **X6** (2 h): Per-component Sarvam toggles and provider panel. This is a stretch if time is tight but makes the AI story more credible.
7. **X8** (1.5 h): Guard against loan offers during alerts or open claims; cap proactive messages. This is a stretch (P1) but shows ethical product thinking.

**Total effort:** ≈10.5 hours of focused work. Fixable in parallel on 2 Oct evening (Ujjwal) + 3 Oct morning (on-site).

## 8. Build plan integration

The fixes above are cross-referenced in [build-plan.md](../06-delivery/build-plan.md) with task IDs, owners and hourly slots.

## Open questions

1. Which two frontend unit tests are failing, and what is the root cause? Owner: Ujjwal Pardeshi.
2. What is the exact behaviour expected for an EDI holiday if the lender's loan is in arrears or the deferral limit is reached? Owner: Omkar Kadam (clarify with lender partner).
3. After X1–X8 are merged, refresh facts-and-sources.md §4 (e.g., "264/264 frontend tests pass", measured test counts). Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v1.5 · badges are LIVE or SIMULATED (FALLBACK only after X6); catalogue has 51 entries; DEMO.md references fixed
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.2 · logic and truth audit fixes
- 2026-10-02 · v1.1 · fact-check pass: removed private note references; reframed critical gaps descriptively; clarified fix IDs ownership
- 2026-10-02 · v1 · first draft, from a read of commit 86575ea and the brief review.
