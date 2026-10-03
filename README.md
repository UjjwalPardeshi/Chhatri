# Chhatri (छतरी, "umbrella")

**Merchant income cover on Paytm where the claim starts itself.** When a storm drops a ward's sales
during a weather alert, Chhatri pays every insured shop there automatically, the same evening. When one
shop goes silent because its owner is ill, Chhatri checks in on WhatsApp in Hindi and settles with one
photo of a hospital slip. The AI builds the case and a deterministic policy engine decides the money.
Every step goes into a tamper-evident audit log.

Build for India AI Hackathon, Track 2 (AI-powered financial journeys). Team **Da Goats**: Omkar Kadam,
Ujjwal Pardeshi. The live demo is on 3 October 2026. The contract is [`docs/SPEC.md`](docs/SPEC.md).

## Live vs simulated (SPEC §0.1)

`GET /api/integrations` reports each component as `LIVE` or `SIMULATED`, and the console header shows
those badges. With the flag `x6_provider_panel` on, a live component that failed or was forced off reads
`FALLBACK`, and the list adds the two Gemini rows. Nothing simulated is ever presented as live.

| Component | Live when | Otherwise |
|---|---|---|
| Sarvam STT, TTS, chat, vision | `SARVAM_API_KEY` set | deterministic simulator |
| Gemini chat and slip reading | `GOOGLE_API_KEY` and `GEMINI_MODEL` set (`GEMINI_VISION_MODEL` optional) | templates and the simulated slip reader |
| WhatsApp Cloud API | `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` all set | in-console phone simulator |
| Paytm payment link | `PAYTM_MCP_URL` (MCP over SSE), or `PAYTM_MID` + `PAYTM_KEY_SECRET` (REST, staging) | simulated `https://paytm.me/sim-…` link |
| n8n workflows | `N8N_BASE_URL` set (the docker stack sets it) | in-process workflow runner, with the same steps and timeline |
| Cognee memory | `COGNEE_ENABLED=true`, cognee installed and an LLM configured | in-process networkx graph |
| Open-Meteo | live only for `GET /api/weather/now` when `OPENMETEO_LIVE=true` | replay and backtest always read cached real data in `backend/data/weather/` |
| Sales data, alerts feed, KYC, payout rail, lender, Soundbox | never | always simulated, always labelled |

Sarvam, Gemini and Cognee run on free tiers, so they are called only when `CHHATRI_DATA_IS_SYNTHETIC=true`
(set in `.env.example`: every merchant, slip and sales figure here is synthetic). No key is committed.

## Feature flags

Every feature added for the final (the merchant mini-app, Ask Chhatri, the slip pre-check, voice, the grievance
ladder, the consent centre, Marathi, the lender request, the provider panel, the distress guard, the ops strip,
the what-if drawer, the evaluation page and the console polish) ships behind one of 14 flags that are **off by
default**. Set `CHHATRI_FEATURES` (backend) and `VITE_FEATURES` (console) to the same comma-separated list, for
example `n1_miniapp,n2_ask_chhatri`. A route whose flag is off answers the ordinary 404. The names are in
`backend/chhatri/features.py` and `frontend/src/features.ts`, and `GET /api/health` lists the flags that are on.

## Quickstart

Prerequisites: Python 3.12, Node 22 (Vite needs Node ≥ 20.19), GNU make. Docker with Compose v2 is
needed only for `make up`.

```bash
git clone <repo> chhatri && cd chhatri
make setup     # backend/.venv with backend[dev], and npm ci in frontend/
make env       # .env from .env.example with a generated CHHATRI_INTERNAL_SECRET (never overwrites)
make data      # only if an artefact is missing (see below); slow: geo -> city -> history -> model -> calibration -> backtest
make dev       # backend on http://localhost:8000, console on http://localhost:5173 (Ctrl+C stops both)
```

Open http://localhost:5173. The backend loads the `monsoon` scenario at start-up, paused at 08:00.
`GET http://localhost:8000/api/preflight` lists what is ready: artefacts, scenario, integrations and
clock.

`make data` is the only command that writes artefacts to `backend/artifacts/`: `model/`,
`calibration.json`, `backtest/report.json` + `report.md`, `premiums.json` and `MANIFEST.json`.
`/api/preflight` reports any that are missing. It is slow, and its output is committed so the demo
machine never trains. No other target runs it.

### Docker stack

```bash
make up        # = make env, then docker compose up -d --build --wait
make down
```

| Service | URL (default) | Notes |
|---|---|---|
| frontend | http://localhost:8080 | nginx serves the console and proxies `/api` and `/webhooks` to the backend (SSE-safe) |
| backend | http://localhost:8000 | FastAPI, non-root, artefacts baked into the image |
| n8n | http://localhost:5678 | n8n 2.41.3; the three Chhatri workflows are imported and published at start |

Ports bind to `127.0.0.1` by default. Change them with `CHHATRI_BIND_ADDR`, `CHHATRI_BACKEND_PORT`,
`CHHATRI_CONSOLE_PORT` and `CHHATRI_N8N_PORT` in `.env`. The stack runs workflows on n8n. To use the
in-process runner instead, set `CHHATRI_STACK_N8N_URL=` (an empty value). If the backend cannot reach
n8n, it falls back to the in-process runner and logs an error. Both modes give the same simulated
timeline, but with n8n the monsoon replay holds at 17:00 for about 30–60 s of real time while its 312
payout runs go through n8n (see [docs/DEMO.md](docs/DEMO.md) for the stage set-up).

Check a running stack with `backend/.venv/bin/python backend/scripts/demo_check.py --url
http://localhost:8000` (it reloads scenarios on that backend).

## Commands (SPEC §23)

| Command | What it does |
|---|---|
| `make setup` | venv + `pip install -e "backend[dev]"` + `npm ci` |
| `make data` | `python backend/scripts/build_data.py`, the only artefact writer |
| `make test` | backend `pytest -m "not slow"` with coverage ≥ 80 %, plus frontend `typecheck`, `lint`, `test`; never needs `make data` |
| `make test-backend` | backend `pytest -m "not slow"` with coverage ≥ 80 % |
| `make test-frontend` | frontend `typecheck`, `lint` and Vitest |
| `make test-slow` | `pytest -m slow`: golden numbers and full-artefact flows; reads committed artefacts, never rebuilds them |
| `make test-infra` | checks that the n8n workflow JSON matches `WORKFLOWS`; runs the compose, Makefile, env, nginx and script tests |
| `make evals` | the offline evaluation suites (no network, no key); writes `backend/artifacts/evals/summary.json` |
| `make env` / `make check-keys` | create `.env` with generated secrets / print which keys are SET (never the value) and list the Gemini models a key can use |
| `make dev` | uvicorn with reload on :8000 plus vite on :5173 (`BACKEND_PORT=`, `CONSOLE_PORT=` to change) |
| `make demo-check` | `python backend/scripts/demo_check.py`: every scenario through the HTTP API, in process with `CHHATRI_FEATURES=x4_lender_request` (the scripted flow stops by design when `n3_slip_precheck` or `n6_consents` is on) |
| `make e2e` | Playwright (chromium) against running servers at `CONSOLE_URL` (default http://localhost:5173) |
| `make demo-stage` | The 3-minute stage demo: backend and console with the stage flag set and `CHHATRI_DATA_IS_SYNTHETIC=true`, no reload; `STAGE_AI=sim` blanks both AI keys ([stage script](docs/06-delivery/stage-script.md)) |
| `make stage-e2e` | Walks the stage script with Playwright against a fresh backend (:8301) and console (:5301) with no AI keys, then stops both; `STAGE_RUNS=3` repeats it |
| `make up` / `make down` | docker compose stack: backend, frontend, n8n |
| `make lint` | ruff check + format check (backend, scripts) |
| `make n8n-workflows` | regenerate `n8n/workflows/*.json` from `chhatri.workflows.definitions.WORKFLOWS` |
| `make n8n-selftest` | run the pinned n8n image with the workflows against a stub backend: step order, payload pass-through, secret check, stop on error |

## Tests

Measured on 3 Oct 2026, one run of each command (details and how to read them in the
[testing strategy](docs/04-engineering/testing-and-quality-strategy.md)):

| Suite | Result |
|---|---|
| `make test-backend` | 3,221 passed, 63 slow deselected; coverage of `chhatri/` 98.85 % (gate 80 %) |
| `make test-slow` | 63 passed |
| `make test-infra` | 164 passed; coverage of `scripts/` 99.44 % (gate 90 %) |
| Frontend unit tests (`npx vitest run`) | 1,340 passed in 135 files |
| `make demo-check` | 70 of 70 checks |
| Playwright e2e (`make e2e`, `npm run test:e2e:mock`) | 136 tests in 27 spec files (counted, not run for this table) |

The suites run against simulated data. No test measures the accuracy of a live AI model: the evaluation
harness is offline, and its page reads NOT MEASURED until a run is stored.

## Repository layout

```
backend/            Python 3.12 package `chhatri` (FastAPI app factory chhatri.api.app:create_app)
  chhatri/          config, features, domain, policy, store, audit, ledger, cases, sim, forecast, detect,
                    integrations, workflows, conversation, ask, ai, precheck, consent, evals, replay,
                    backtest, pipeline, api
  data/             committed inputs: BMC ward polygons, Open-Meteo fixtures, sample slips, zones
  artifacts/        generated by `make data` only (committed): model/, calibration.json, backtest/, premiums.json
  scripts/          build_data.py, calibrate.py, demo_check.py, make_slips.py, ...
  tests/            pytest, one module per source module
frontend/           Vite + React 19 + TypeScript + react-leaflet console, with the merchant mini-app in src/miniapp/
                    (Tailwind v4 and shadcn, scoped to the mini-app) and an in-browser mock backend in src/mock/
n8n/                entrypoint.sh and workflows/ (generated; see scripts/n8n_workflows.py)
scripts/            infra tooling: init_env.py, n8n_workflows.py, n8n_selftest.py (+ tests/)
docs/               SPEC.md (contract), ARCHITECTURE.md, DEMO.md, INTEGRATIONS.md, SECURITY.md, and the
                    product docs indexed in docs/README.md
docker-compose.yml  Makefile  .env.example  .github/workflows/ci.yml
```

## Documentation

- [docs/user-manual.pdf](docs/user-manual.pdf): the user manual for a first-time reader (what Chhatri is, how to run it, a guided tour of every screen); source in [docs/user-manual/](docs/user-manual/user-manual.html).
- [docs/README.md](docs/README.md): the index of the full documentation set (strategy, product, design,
  engineering, business and delivery), with reading paths for judges, the team and engineers.
- [docs/DEMO.md](docs/DEMO.md): the minute-by-minute presenter script with every golden number and string.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how a claim flows from signal to money, and how the parts fit.
- [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md): verified API facts, set-up, WhatsApp templates, the n8n contract.
- [docs/SECURITY.md](docs/SECURITY.md): controls, threat model and the pre-demo checklist.

## Credits and data

Ward boundaries: DataMeet Mumbai BMC wards (CC BY-SA 2.5 India). Weather data by Open-Meteo.com
(CC BY 4.0). Map tiles and the Mumbai Metropolitan Region outline: © OpenStreetMap contributors (ODbL),
standard tiles from tile.openstreetmap.org. Without a network the console draws its own map from the ward
outlines; `VITE_TILE_URL` swaps in another tile source. Sales, alerts, KYC, payouts and the
lender are simulated and labelled as such. Built with Sarvam AI (Saaras, Bulbul, chat, vision),
Google Gemini (free tier), Paytm payment MCP server, WhatsApp Cloud API, n8n, LightGBM and Cognee.
