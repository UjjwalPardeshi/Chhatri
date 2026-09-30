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
those badges. Nothing simulated is ever presented as live.

| Component | Live when | Otherwise |
|---|---|---|
| Sarvam STT, TTS, chat, vision | `SARVAM_API_KEY` set | deterministic simulator |
| WhatsApp Cloud API | `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` all set | in-console phone simulator |
| Paytm payment link | `PAYTM_MCP_URL` (MCP over SSE), or `PAYTM_MID` + `PAYTM_KEY_SECRET` (REST, staging) | simulated `https://paytm.me/sim-…` link |
| n8n workflows | `N8N_BASE_URL` set (the docker stack sets it) | in-process workflow runner, with the same steps and timeline |
| Cognee memory | `COGNEE_ENABLED=true`, cognee installed and an LLM configured | in-process networkx graph |
| Open-Meteo | live only for `GET /api/weather/now` when `OPENMETEO_LIVE=true` | replay and backtest always read cached real data in `backend/data/weather/` |
| Sales data, alerts feed, KYC, payout rail, lender, Soundbox | never | always simulated, always labelled |

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
| `make test-slow` | `pytest -m slow`: golden numbers and full-artefact flows; reads committed artefacts, never rebuilds them |
| `make test-infra` | checks that the n8n workflow JSON matches `WORKFLOWS`; runs the compose, Makefile, env, nginx and script tests |
| `make dev` | uvicorn with reload on :8000 plus vite on :5173 (`BACKEND_PORT=`, `CONSOLE_PORT=` to change) |
| `make demo-check` | `python backend/scripts/demo_check.py`: every scenario through the HTTP API |
| `make e2e` | Playwright (chromium) against running servers at `CONSOLE_URL` (default http://localhost:5173) |
| `make up` / `make down` | docker compose stack: backend, frontend, n8n |
| `make lint` | ruff check + format check (backend, scripts) |
| `make n8n-workflows` | regenerate `n8n/workflows/*.json` from `chhatri.workflows.definitions.WORKFLOWS` |
| `make n8n-selftest` | run the pinned n8n image with the workflows against a stub backend: step order, payload pass-through, secret check, stop on error |

## Repository layout

```
backend/            Python 3.12 package `chhatri` (FastAPI app factory chhatri.api.app:create_app)
  chhatri/          config, domain, policy, store, audit, ledger, cases, sim, forecast, detect,
                    integrations, workflows, conversation, replay, backtest, api
  data/             committed inputs: BMC ward polygons, Open-Meteo fixtures, sample slips, zones
  artifacts/        generated by `make data` only (committed): model/, calibration.json, backtest/, premiums.json
  scripts/          build_data.py, calibrate.py, demo_check.py, make_slips.py, ...
  tests/            pytest, one module per source module
frontend/           Vite + React 19 + TypeScript + react-leaflet console (Dockerfile, nginx.conf)
n8n/                entrypoint.sh and workflows/ (generated; see scripts/n8n_workflows.py)
scripts/            infra tooling: init_env.py, n8n_workflows.py, n8n_selftest.py (+ tests/)
docs/               SPEC.md (contract), ARCHITECTURE.md, DEMO.md, INTEGRATIONS.md, SECURITY.md
docker-compose.yml  Makefile  .env.example  .github/workflows/ci.yml
```

## Documentation

- [docs/DEMO.md](docs/DEMO.md): the minute-by-minute presenter script with every golden number and string.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how a claim flows from signal to money, and how the parts fit.
- [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md): verified API facts, set-up, WhatsApp templates, the n8n contract.
- [docs/SECURITY.md](docs/SECURITY.md): controls, threat model and the pre-demo checklist.

## Credits and data

Ward boundaries: DataMeet Mumbai BMC wards (CC BY-SA 2.5 India). Weather data by Open-Meteo.com
(CC BY 4.0). Map tiles, when enabled: © OpenStreetMap contributors, © CARTO. CARTO now needs an API key,
so by default the console draws its own no-tile map from the ward outlines; set `VITE_TILE_URL` (a keyed
tile URL) to show tiles. Sales, alerts, KYC, payouts and the
lender are simulated and labelled as such. Built with Sarvam AI (Saaras, Bulbul, chat, vision),
Paytm payment MCP server, WhatsApp Cloud API, n8n, LightGBM and Cognee.
