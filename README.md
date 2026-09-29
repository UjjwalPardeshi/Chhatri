# Chhatri — Merchant Income Cover on Paytm

**Chhatri** (छतरी · umbrella) is a claims engine for merchant income cover on Paytm where the claim starts itself. When rain or a heatwave hits an area, we pay every insured shop automatically. When one shop goes quiet because its owner is ill, we reach out on WhatsApp, settle with one photo of a hospital slip, and pay the same day.

- **Demo**: 3 October 2026 (Build for India AI Hackathon · Track 2: AI-powered financial journeys)
- **Team**: Da Goats (Omkar Kadam, Ujjwal Pardeshi)
- **Repo**: https://github.com/palkia/Chhatri

## What's Live vs Simulated

| Component | Live when | Otherwise |
|---|---|---|
| Sarvam STT/TTS/chat/vision | `SARVAM_API_KEY` set | deterministic simulator |
| WhatsApp Cloud API | `WHATSAPP_*` vars set | in-console phone simulator |
| Paytm payment link | `PAYTM_MCP_URL` or `PAYTM_MID`+`PAYTM_KEY_SECRET` | simulated link (marked `SIMULATED`) |
| n8n workflows | `N8N_BASE_URL` set | in-process workflow runner |
| Cognee memory | `COGNEE_ENABLED=true` and installed | in-process networkx graph |
| Sales data, alerts, KYC, payouts, lender, Soundbox | — | always simulated (labelled) |

See `GET /api/integrations` for status of each component.

## Quick Start

### Prerequisites
- Python 3.12
- Node 22
- Docker & Docker Compose (for containerized deployment)

### Local Development (5 minutes)

```bash
# Install dependencies and build artifacts
make setup
make data

# Start backend (FastAPI) + frontend (Vite) concurrently
make dev
```

Then open:
- **Frontend**: http://localhost:5173
- **Backend API docs**: http://localhost:8000/docs

### Docker Deployment

```bash
# Build and start all services
make up

# Visit http://localhost
```

## Demo Scenarios

The replay engine runs on simulated time (configurable speed: 6 sim minutes per real second by default).

### 1. **Monsoon** (Stock demo)
- **Date**: Tuesday, 19 Aug 2025, 08:00–20:00 IST
- **Trigger**: Red rain alert at 14:00
- **KPIs**: 3 zones triggered, 312 shops paid, 4 min trigger→money
- **What to see**:
  - Live heat map: red zones Z7, Z3, Z12 at 17:00
  - Anil's tea stall (S-0142) paid ₹1,380
  - Next instalment paused
  - Soundbox announcement

### 2. **Personal claim on WhatsApp** (Illness scenario)
- **Date**: Thursday, 21 Aug 2025
- **Flow**: Silent check-in → voice reply → slip photo → AI reads slip → policy engine → auto-payout
- **What to see**:
  - Chhatri checks in at 11:20: *"Your shop has been closed since yesterday. Is everything okay?"*
  - Merchant replies in Hindi with voice
  - Sends photo of admission slip
  - Slip name matches KYC → APPROVED ₹1,500

### 3. **Live tests** (Automated)
- **EXPLAINED**: Merchant asks "मुझे इतने पैसे क्यों मिले?" → system shows the breakdown (₹4,380 expected, 63% drop, half share = ₹1,380)
- **HUMAN**: Slip for different person → case opened, officer approves manually
- **BLOCKED**: Ramesh tries to buy cover during an alert → system blocks, offers link for after waiting period

## Architecture

Signals → Reasoning → Control → Action:

```
Signals: hourly sales, weather alerts, voice, photos
   ↓
Reasoning: LightGBM model, area index, Sarvam AI, Cognee memory
   ↓
Control: Policy engine (code decides the money, not AI)
   ↓
Action: Payout, instalment pause, WhatsApp, Soundbox, audit log
```

## Repo Layout

```
backend/
  chhatri/
    config.py, clock.py, money.py                       [shared scaffold]
    domain/{enums,models}.py                            [shared scaffold]
    policy/{engine,rules,checks,explain}.py             [policy: the core]
    integrations/{sarvam,whatsapp,paytm,n8n,memory}.py  [live + simulated]
    sim/{geo,city,sales,weather,scenarios}.py           [simulator]
    forecast/{model,features}.py                        [LightGBM + calibration]
    detect/{area_index,triggers,silent}.py              [detection]
    conversation/{intents,nlu,messages,service}.py      [conversational AI]
    workflows/{definitions,runner}.py                   [n8n or in-process]
    replay/{engine,orchestrator}.py                     [replay engine]
    api/{app,deps,routers/}.py                          [FastAPI]
  tests/                                                [pytest, 80%+ coverage]
  data/, artifacts/                                     [committed fixtures & models]

frontend/
  src/{pages,components,api,hooks}                      [React + TS]
  public/fonts/                                         [self-hosted: Ubuntu, Noto Sans]

n8n/workflows/                                          [importable .json definitions]
docker-compose.yml, Makefile                            [orchestration]
.env.example                                            [all config vars]
.github/workflows/ci.yml                               [GitHub Actions]
```

## Testing

```bash
make test              # backend pytest + frontend vitest
make test-backend     # pytest only, 80%+ coverage
make e2e              # Playwright: monsoon replay + officer approve
```

## Code Quality

```bash
make lint             # ruff check
make setup && make data && make dev    # local development
```

## Deployment

### Quick start (Docker)
```bash
make up               # backend, frontend, n8n all up
# Visit http://localhost
```

### Configure (optional)
Copy `.env.example` → `.env` and set:
- `SARVAM_API_KEY` for live voice/chat/vision
- `WHATSAPP_*` for live WhatsApp
- `PAYTM_MCP_URL` for live Paytm payment links
- `N8N_BASE_URL` for live n8n workflows

## Credits

**Merchants**: 1.57 crore on Paytm · **Data**: DataMeet (BMC wards, CC BY-SA 2.5 IN) · Open-Meteo (rainfall, CC BY 4.0) · OpenStreetMap / CARTO · **Tech**: Sarvam AI (voice/vision), Paytm (payments), n8n (workflows), LightGBM (ML), Cognee (memory)