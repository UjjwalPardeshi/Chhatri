# Chhatri architecture

This document explains how the parts fit together. The contract is [SPEC.md](SPEC.md); section numbers
below refer to it. Wherever this document and the SPEC differ, the SPEC wins.

## 1. Principle: the AI builds the case, code decides the money (SPEC §0.2)

```
SIGNALS                  REASONING + MEMORY               CONTROL                    ACTION
hourly sales per shop -> expected-sales model (LightGBM -> policy engine          -> payout + instalment pause
weather/civic alerts      quantiles per area + shop type)   (pure functions,        (simulated rails)
merchant voice replies -> Sarvam chat + vision (slip)      the ONLY layer that   -> WhatsApp + Soundbox
hospital-slip photos   -> memory graph (precedents)        can APPROVE money)    -> n8n workflows
loan instalments                                                  |               -> audit log (hash chain)
                                                                  v
                                                      claims officer for REFERRED
```

- `chhatri.policy.engine` is pure: facts in, a `Decision` out, no I/O. Only it can produce `APPROVED`.
  An officer's approval re-runs every HARD check (§9.4).
- LLM output (Sarvam chat) can pick an intent from a fixed list and nothing else. It never sets an
  amount. Money messages are rendered from templates filled with decision facts (§13.3, §13.4).
- Every money number shown to a merchant can be recomputed from the numbers shown next to it (§4.3):
  `½ × ₹4,380 × 63% = ₹1,380`.
- Deterministic: the same seed and scenario give the same numbers, ids, messages and audit hashes (§0.2).
  The id factory, store, audit log and scheduler are recreated on every scenario load, so the first
  case is always `C-2291` (§3).

## 2. Packages (SPEC §1, §24)

| Package | Role |
|---|---|
| `config`, `clock`, `money`, `ids`, `events`, `features`, `domain/` | scaffold: settings, IST clock, paise + `format_inr`, deterministic ids, event bus, the 14 feature flags (all off by default), frozen pydantic models |
| `sim/` | 24 real BMC wards as zones (§5), 1,820 simulated pilot shops at seed 20251019 (`backend/data/zones.json`) plus the uncovered demo merchant S-0907 (1,821 merchants), hourly sales with rain/slow-day/bandh/closure shocks, scripted scenarios (§6, §17.2), sample slips |
| `forecast/` | LightGBM quantile models (P10/P50/P90) over shop-hours with `zone_id` and `shop_type` features ("LightGBM per area and shop type", §7.1); per-zone conformal lower bound (§7.4) |
| `detect/` | trailing 3-hour zone index, trigger rule, silent-shop finder (§8) |
| `policy/` | `rules.yaml` (`pilot-0.1`), checks, amounts, explanation strings, cover purchase and derived cover status (§9); sources on every check and number (`provenance.py`, H13), counterfactuals the engine verifies (`counterfactual.py`, H14), the receipt |
| `store/`, `audit/`, `ledger/`, `cases/` | in-memory store, SQLite hash-chained audit log (§11), payouts, instalment pauses, EDI holiday requests (X4) and premiums (§10), officer cases starting at C-2291 (§12), the grievance ladder and respondent router (`cases/ladder.py`, `grievances.py`, N5) |
| `integrations/` | live and simulated Sarvam, Gemini, WhatsApp, Paytm, Open-Meteo, n8n, memory, Soundbox and the simulated lender, built by `registry.py` from `Settings` (§14); the Ask and slip chains, the free-tier data gate (`free_tier.py`, ADR 0009) and the X6 fallback switch and panel |
| `workflows/` | `WORKFLOWS` step lists with simulated-time offsets; in-process runner; n8n callback validation (§15) |
| `conversation/` | intents, explain-first routing, message catalogue, two-layer guard, the X8 message guard, flows for WhatsApp and the phone simulator (§13) |
| `ai/` | the provider chain runner and the H26 labels (mode, provider, model, fallback reason, attempts) |
| `ask/` | Ask Chhatri (N2): fact sheet, clauses, model path, injection and scam checks, next action, voice and chips (N4) |
| `precheck/` | the slip pre-check (N3): metadata stripping, field validation, status table, confirm or send to the team |
| `consent/` | the consent centre, activity log and "forget my slip" (N6, H23) |
| `evals/` | the offline evaluation harness and the S4 slip generator (H25) |
| `replay/` | `ReplayEngine` (clock, play/pause/step/seek), `Orchestrator` (the integration core), `views` (the only place domain objects become JSON) (§17, §24.6) |
| `backtest/` | two past monsoons, Chhatri vs a weather-only trigger, per-zone premiums (§18) |
| `api/` | thin FastAPI routers over `AppState`/`Runtime` (57 route handlers, 18 of them from the feature waves, each flagged route 404 while its flag is off); SSE; security (§19, §21) |

## 3. Area claim: the monsoon replay (SPEC §8, §9, §17.2)

The replay day is **Tue 19 Aug 2025**, 08:00 to 20:00 simulated IST. Red rain alert `A-20250818-01`
for Z3, Z7 and Z12 was issued Mon 18 Aug at 17:30 and is valid on Tue from 14:00 to 20:00.

1. **Every simulated minute** the `ReplayEngine` advances the `ManualClock` and runs due jobs on the
   `SimScheduler`. The default speed is 6 simulated minutes per real second, adjustable from 1 to 120.
2. **Every hour boundary** `t`, `Orchestrator.on_hour` calls `detect.triggers.evaluate_hour`. For each
   zone the index is Σ actual / Σ P50 over its covered, open shops for the window `[t−3h, t)`. A zone
   triggers when all of these hold (§8.2):
   - an alert covers the whole window;
   - each of the 3 hours is below 50 %;
   - the window index is below the zone's model lower bound;
   - at least 20 shops are in the index;
   - the zone has not triggered already that day.
   All comparisons are strict.
3. **17:00**: Z7 at 37 % (drop 63 %), Z3 at 38 % and Z12 at 47 % trigger. Z9 is at 61 % with no alert,
   which is a slow day, so there is no payout. One `AreaTrigger` per zone becomes one area `Claim` per
   covered shop. `evaluate_area_claim` returns a `Decision` for each, all decided at 17:00.
4. Each `APPROVED` decision starts the **payout workflow** (§5 below). Credits land at 17:04, with the
   WhatsApp message and Soundbox announcement. Next-day instalments are paused at 17:05.
5. KPIs: 3 zones triggered, 312 shops paid (46 + 141 + 125), 4 min from trigger to money. Z7's total is
   ₹58,900.

Anil (`S-0142`, Z7): his usual Tuesday is ₹4,380, published rounded to ₹10. His payout is
`½ × ₹4,380 × 63% = ₹1,379.70`, rounded half up to ₹1,380 and capped at ₹2,500 a day. His ₹600
instalment for Wed 20 Aug is paused.

Map values (decision B3): `index_pct` is the trailing 3 completed hours. `live_index_pct` is a sliding
3-hour window that pro-rates the current partial hour. A hex takes the live index of its own covered
open shops when at least 3 contribute; otherwise it takes its zone's value. Sales for hours at or after
the current simulated hour are never visible through any view (B4).

## 4. Personal claim: illness on WhatsApp (SPEC §8.3, §9.2, §13.5)

- Anil's shop has zero transactions all of **Wed 20 Aug**, his P10 day range is above zero, and his
  zone had no area event, so he is *silent*. On **Thu 21 Aug** the shop is still silent by 11:00, and
  at 11:20 Chhatri sends `CHECKIN_SILENT`. Live WhatsApp needs a template for this, because the message
  is business-initiated.
- His voice reply goes through STT and the `REPORT_ILLNESS` intent, and Chhatri answers with `ASK_SLIP`.
  The slip photo is read into a `SlipExtraction` by Sarvam vision, or by the simulator reading the PNG's
  embedded JSON. That extraction becomes a personal `Claim` with verified silent dates, which goes to
  `evaluate_personal_claim`:
  - HARD checks: cover in force, premium prepaid, silence verified, not already paid, annual limit.
  - SOFT checks: slip readable (confidence ≥ 0.80), name matches KYC (score ≥ 85), dates match, at
    most 3 days.
- If every check passes, the claim is `APPROVED`: `½ × expected day, capped at ₹1,500 × 1 day = ₹1,500`,
  paid through the payout workflow, and Thursday's instalment is paused.
- If any SOFT check fails or is UNSURE, the claim is `REFERRED`. A `PERSONAL_CLAIM_REVIEW` case is
  opened (`C-2291`), the human-review workflow runs, and the merchant gets `SLIP_TO_HUMAN`. The officer
  approves or declines in one tap in `/claims`. Approval produces a new decision,
  `decided_by="officer:<id>"`, and pays ₹1,500.
- A dispute ("मेरा नुकसान ज़्यादा हुआ।") opens a `DISPUTE` case and a follow-up workflow. Its SLA check
  runs 24 simulated hours later.

## 5. Workflows: n8n or in-process, same timeline (SPEC §14.5, §15; decision B1)

`chhatri.workflows.definitions.WORKFLOWS` holds the step lists. Offsets are simulated minutes from the
decision time:

| Workflow | Steps (offset) | Payload |
|---|---|---|
| `payout` | `execute_payout` +0, `credit_payout` +4, `notify_merchant` +4, `request_holiday` +5 | `{decision_id, merchant_id}` |
| `human-review` | `open_case` +0, `notify_officer` +0 | `{case_id, merchant_id}` |
| `follow-up` | `check_case_sla` +1440, `notify_officer` +1440 | `{case_id}` |

- **In-process** (`InProcessWorkflowEngine`): each step is scheduled on the `SimScheduler` at
  start + offset.
- **n8n** (`N8nWorkflowEngine`, used when `N8N_BASE_URL` is set):
  ```
  backend --POST /webhook/chhatri-{workflow} {run_id, workflow, payload} + X-Chhatri-Secret--> n8n
  n8n: verify secret (403 otherwise) -> for each step in WORKFLOWS order:
       POST {CHHATRI_PUBLIC_URL}/internal/workflows/{step} {run_id, workflow, step, payload} + secret
         backend: Orchestrator.handle_callback re-validates and schedules the step effect at
                  decision time + offset on the SimScheduler (idempotent per (run_id, step)) -> 200
     -> answer the webhook 200 {"ok": true, "data": {"run_id", "status": "completed", "steps"}}
  ```
  The backend's start call waits for that final answer, so by the time it returns every step of the
  run is on the simulated scheduler, and the simulated clock cannot pass a step's due minute before n8n
  reported it. The n8n workflows contain no Wait nodes. n8n only orders the steps; it never decides and
  never sets the timing. So the replay timeline is identical in both modes (verified: `demo_check.py
  --url` against the compose stack gives credits at 17:04 and pauses at 17:05 in n8n mode).
- **Cost of n8n mode**: each run costs n8n about 0.1–0.2 s of real time, and the monsoon burst starts
  312 payout runs one after another at 17:00. With n8n on, the simulated clock therefore holds at
  17:00 for roughly 30–60 s of real time while the runs complete (measured on the 8-CPU dev machine),
  then continues exactly on schedule. The in-process runner does the same minute in about a second.
- **Failures**: a callback answered non-2xx stops the n8n run after 3 tries and n8n answers the webhook
  500; if n8n cannot be reached, answers non-2xx, or answers without the completion body, the backend
  hands the run to the in-process runner, which schedules only the steps n8n had not already reported
  (so nothing runs twice), and logs it at ERROR. A start that times out (30 s) is not handed over, since
  n8n may still be running it; it is audited as `workflow.start_failed`.
- The JSON files in `n8n/workflows/` are **generated** from `WORKFLOWS` by `scripts/n8n_workflows.py`.
  `make test-infra` and CI fail if they drift. `make n8n-selftest` proves the behaviour against a real
  n8n container.
- Step effects (B2):
  - `execute_payout`: `PayoutService.execute` creates a PENDING payout after re-checking that the
    decision exists, is APPROVED and has not been executed.
  - `credit_payout`: the payout becomes CREDITED.
  - `notify_merchant`: the WhatsApp intro, payout card and Soundbox announcement.
  - `request_holiday` (was `pause_instalment`): with the flag `x4_lender_request` on (the stage set-up), Chhatri asks the
    lender once (`InstalmentService.request_holiday`), the lender answers by its own rules L1 to L4
    (`integrations/lender.py`), only a grant pauses `event_date + 1 day`, and the merchant is told what the lender
    answered. With the flag off it is the unconditional `pause_next` and the pause message, as at commit 86575ea.

## 6. Audit log (SPEC §11)

The audit log is an append-only SQLite table:
`hash = sha256(canonical_json({seq, at, actor, action, subject_type, subject_id, data, prev_hash}))`,
with a genesis `prev_hash` of 64 zeros. Wall-clock `recorded_at` is stored but excluded from the hash,
so a replay reproduces the same chain. `GET /api/audit/verify` recomputes the chain and returns
`{valid, entries, head_hash, first_bad_seq}`. Every decision stores all of its checks. The actors are
`system`, `model`, `policy-engine`, `ai-agent`, `officer:<id>`, `merchant:<id>` and `workflow:<name>`.

## 7. API, SSE and console (SPEC §19, §20)

- The ASGI factory is `chhatri.api.app:create_app`. Its lifespan loads static context (city, model,
  geo, backtest) once, then loads `monsoon` paused at 08:00.
- Envelope: `{"ok": true, "data": …, "meta"?}` or `{"ok": false, "error": {code, message, fields?}}`.
  Every money field has a preformatted `*_label` (`format_inr`, Indian grouping), so the UI never
  re-derives money.
- `GET /api/stream` is SSE (sse-starlette, ping every 15 s). Event types include `scenario`, `tick`,
  `zone`, `hexes`, `alert`, `trigger`, `decision`, `payout`, `instalment`, `message`, `soundbox`, `case`,
  `audit` and `kpis`. The client resumes with `Last-Event-ID`.
- Console routes (SPEC §20): `/` overview homepage, `/live` live map, `/claims` officer queue,
  `/merchant/:id` phone, `/audit`, `/backtest` and `/policy`, plus `/evals` with flag `h25_evals`. The merchant mini-app
  (flag `n1_miniapp`, ADR 0005) is a third column beside the phone simulator on `/merchant/:id` and a standalone page at `/merchant/:id/app`. Fonts are
  self-hosted, so it works offline.

## 8. Deployment topology (SPEC §23)

```
make dev:     browser -> vite :5173 --/api proxy--> uvicorn :8000 (reload)       n8n: optional (N8N_BASE_URL)

make up:      browser -> frontend (nginx :8080) --/api, /webhooks--> backend :8000 <--/internal/workflows-- n8n :5678
                                     SPA fallback, SSE unbuffered        ^--/webhook/chhatri-{wf}---------'
```

- The **backend image** (`backend/Dockerfile`) is Python 3.12 slim and runs as non-root uid 10001.
  `/app/data` and `/app/artifacts` are baked in, `/app/var` is a volume reserved for run state (nothing
  is written there yet: the store and the audit log are in memory and are rebuilt on every scenario
  load), and the healthcheck uses only the stdlib (urllib).
- The **frontend image** (`frontend/Dockerfile`) runs `npm run build`, then unprivileged
  nginx 1.30. `frontend/nginx.conf` is a template (`${CHHATRI_BACKEND_UPSTREAM}`). `/api` is proxied
  over HTTP/1.1 with buffering off and a 1 h read timeout, and there is no gzip on
  `text/event-stream`. Uploads up to 6 MB are accepted; `/internal/` is not exposed.
- **n8n**: `docker.n8n.io/n8nio/n8n:2.41.3`. `n8n/entrypoint.sh` imports the workflows with fixed ids,
  publishes them, then starts n8n. Its callbacks go to `http://backend:8000` inside the compose network.
- **Artefacts** (B6) live in `backend/artifacts/`. `model/`, `calibration.json` and `MANIFEST.json` are
  written only by the data pipeline; `backtest/` and `premiums.json` only by `chhatri.backtest`, which
  `build_data.py` calls. Images, tests and the demo only read them.

## 9. Testing (SPEC §22)

- `make test` runs the fast backend suite (`-m "not slow"`, coverage ≥ 80 %) and the frontend
  typecheck, lint and vitest. It never needs artefacts.
- `make test-slow` runs golden numbers and full-artefact flows.
- `make demo-check` runs every scenario through the HTTP API.
- `make e2e` runs Playwright against running servers.
- `make test-infra` and `make n8n-selftest` cover the infrastructure: generated workflows, compose,
  Makefile, env, nginx, entrypoint, and a real n8n run.
- CI (`.github/workflows/ci.yml`) runs lint, the fast backend suite with coverage, the frontend typecheck, lint, test and
  build, the infra checks and the n8n self-test. It does not run `make test-slow`, `make demo-check` or `make e2e`.
