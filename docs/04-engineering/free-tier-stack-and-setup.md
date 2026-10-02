# Free-tier stack and setup

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Ujjwal Pardeshi |
| Audience | Engineers building and operating Chhatri |
| Related | [System architecture](system-architecture.md) · [Data model and API](data-model-and-api.md) · [AI architecture and guardrails](ai-architecture-and-guardrails.md) · [Facts and sources](../01-strategy/facts-and-sources.md) · [Regulatory and compliance](../05-business/regulatory-and-compliance.md) |

## TL;DR

- Every component is LIVE when its API key is set, otherwise SIMULATED and labelled.
- Sarvam (free starter credits) is approved and live on 3 Oct; Gemini Flash free tier (PLANNED, N2/N3) will accept **only synthetic data** (demo merchants, sample slip images) when integrated.
- All other integrations are free or in-process (n8n, Cognee, Open-Meteo).
- Set `SARVAM_API_KEY` to activate all four Sarvam modules (STT, TTS, chat, vision). Proposed per-component toggles (X6) allow spending credits on hero moments only.
- Local setup via `make setup` and `make dev`. Static mock-mode deploy to GitHub Pages or Vercel Hobby for a public backup.
- Demo laptop must have browser speech recognition (en-IN) and microphone, run at 1280×720, and test offline fallback.

## 1. Free-tier component table

| Component | Need | Primary | Fallback 1 | Fallback 2 | Status | Cost |
|---|---|---|---|---|---|---|
| **Grounded answers (N2)** | Ask Chhatri text replies in Hindi and English | Gemini Flash free tier (PLANNED) | Sarvam chat (free credits) | deterministic templates | SIMULATED (Gemini PLANNED; Sarvam if LIVE) | ₹0 |
| **Slip reading (N3)** | Extract patient name, dates, hospital from slip photo | Gemini Vision (PLANNED) | Sarvam Vision (credits, LIVE if key set) | Tesseract OCR (offline, hin+eng, PLANNED) | SIMULATED (fallbacks if provider unavailable) | ₹0 |
| **Speech-to-text (N4)** | Hindi voice input in the mini-app and WhatsApp | Sarvam Saaras v3 or v4 (credits, existing) | browser Web Speech API (PLANNED) | tap-to-send chips | SIMULATED (canned demos) or LIVE (Sarvam with key) | ₹0 |
| **Text-to-speech (N4)** | Hindi and English voice output (proactive check-in, payout notice) | Sarvam Bulbul v3 (credits, existing) | browser speechSynthesis (PLANNED) | text only | SIMULATED or LIVE (Sarvam with key) | ₹0 |
| **Workflows (DEMO.md)**  | Orchestrate claim checks, EDI requests, payouts | in-process runner (stage) | n8n CE 2.41.3 (self-hosted in docker stack) | manual | LIVE on stage | ₹0 |
| **Memory graph (K5)** | Store facts about merchants and claims for Ask Chhatri | networkx (in-process, labelled) | Cognee (open source; uses Gemini or Ollama) | — | SIMULATED | ₹0 |
| **Weather data** | Real Open-Meteo rainfall for the monsoon replay scenario | cached fixtures (committed to repo) | live Open-Meteo API (test only, `OPENMETEO_LIVE=true`) | — | SIMULATED (real data) | ₹0 |
| **Hosting** | Static mock-mode console and fallback video | GitHub Pages (free) | Vercel Hobby (free plan) | local laptop | LIVE on 3 Oct | ₹0 |
| **Database** | Store scenarios, cases, decisions, audit log, consents | SQLite in-process | PostgreSQL (future) | — | LIVE | ₹0 |

## 2. Account setup

### Google AI Studio (Gemini Flash free tier) — PLANNED

**Status:** PLANNED (N2, N3 integration pending on 2–3 Oct; implementation not yet in the backend code).

**When implemented (2–3 Oct):**

1. Go to [ai.google.dev](https://ai.google.dev) and sign in with a personal Google account.
2. Click **Get API key** and create a new API key in a new project (or an existing project).
3. Copy the key to `.env`:
   ```env
   GOOGLE_API_KEY=<your key>
   ```

**Privacy rule (critical):** The Gemini free tier may use submitted content to improve Google products (A19). When live, never send real customer data (KYC names, real slip photos, real sales figures). Send only:
- Synthetic demo merchants (Anil, Ramesh, Priya, Rajesh, Amit from the personas).
- Sample slip images baked into the repo (`backend/data/slips/`).
- Demo policy wording and rules (from `backend/chhatri/policy/rules.yaml`).

**Provider order:** Once the integration is live, N2 (Ask Chhatri) and N3 (slip reading) will try Gemini free tier **first** (LIVE with key), then fall back to Sarvam (LIVE if `SARVAM_API_KEY` set, otherwise SIMULATED), or deterministic simulators (SIMULATED). Today, all AI provider calls are SIMULATED and labelled in the console.

### Sarvam AI (free starter credits)

1. Create a free account at [sarvam.ai](https://sarvam.ai) (or your region's Sarvam instance).
2. Go to the **API dashboard** and create a new API key or copy your existing one.
3. Copy the key to `.env`:
   ```env
   SARVAM_API_KEY=<your key>
   ```
4. Check the Sarvam **free credit balance** on the dashboard before and after each test.

**Current behaviour:** Setting `SARVAM_API_KEY` activates all four Sarvam modules (STT, TTS, chat, vision) as LIVE. The backend uses models:
- **STT:** `SARVAM_STT_MODEL` (default `saaras:v3`; `v4` is available).
- **TTS:** `SARVAM_TTS_MODEL` (default `bulbul:v3`), speaker `SARVAM_TTS_SPEAKER` (default `ritu`).
- **Chat:** `SARVAM_CHAT_MODEL` (default `sarvam-105b`).
- **Vision:** Sarvam Vision document intelligence.

**Proposed per-component toggles (X6):** To spend free credits only on hero moments, the next iteration proposes conditional env vars:

| Variable | Module | Behaviour if set | Behaviour if unset |
|---|---|---|---|
| `CHHATRI_ASSIST_PROVIDER=sarvam` (PROPOSED) | N2 Ask Chhatri text, N2 Ask Chhatri voice | Use Sarvam chat (Sarvam-105b) | Fall back to Gemini or templates |
| `CHHATRI_STT_PROVIDER=sarvam` (PROPOSED) | N4 STT in mini-app and WhatsApp | Use Sarvam Saaras | Fall back to browser Web Speech API |
| `CHHATRI_TTS_PROVIDER=sarvam` (PROPOSED) | N4 TTS for check-in and payout notices | Use Sarvam Bulbul | Fall back to browser speechSynthesis |
| `CHHATRI_SLIP_PROVIDER=sarvam` (PROPOSED) | N3 slip reading (vision) | Use Sarvam Vision | Fall back to Tesseract or REFERRED |

For now, the single `SARVAM_API_KEY` controls all four. Future commits will implement X6 (per-component toggles) and a provider-status panel (X6, H7) in the console so operators can see which is LIVE, FALLBACK or SIMULATED.

**Quotas:** Sarvam free accounts have rate limits. The free-tier credits are finite. To avoid overspending:
- Use Sarvam only for demo hero moments (Anil's check-in, the slip photo upload, payout voice notification).
- Use deterministic simulators for repetitive testing.
- Monitor the dashboard credit balance daily.
- Never set the key in public repos or shared machines.

## 3. Local development setup

### Prerequisites

- **Python 3.12** with `python3.12` or `python3` aliased.
- **Node 22+** (Vite needs ≥ 20.19); check `npm --version`.
- **GNU make**.
- **Git** and a clone of the repo at `<root>`.

### Steps

1. **Create the virtual environment and install dependencies:**
   ```bash
   cd <root> && make setup
   ```
   This creates `backend/.venv`, installs `backend[dev]` (FastAPI, pytest, etc.), and runs `npm ci` in `frontend/`.

2. **Generate `.env` with a random secret:**
   ```bash
   make env
   ```
   This creates `.env` from `.env.example` and generates a random `CHHATRI_INTERNAL_SECRET`. It never overwrites an existing `.env`.

3. **(Optional) Add API keys:**
   Edit `.env` and add:
   ```env
   GOOGLE_API_KEY=<your Google key>
   SARVAM_API_KEY=<your Sarvam key>
   ```
   Commit `.env` never; it stays local.

4. **(Optional) Build artefacts:**
   ```bash
   make data
   ```
   This runs the full pipeline (geo → city → history → model → calibration → backtest) and writes to `backend/artifacts/`. It is slow (~15–20 min) and the outputs are already committed. Skip this unless you change the simulation parameters in `backend/chhatri/pipeline/`.

5. **Start the dev servers:**
   ```bash
   make dev
   ```
   This runs:
   - **Backend** (FastAPI, uvicorn) on `http://localhost:8000` with auto-reload.
   - **Console** (Vite) on `http://localhost:5173` with hot module reload.

   Open `http://localhost:5173` in a browser. The backend starts paused in the `monsoon` scenario at 08:00.

6. **Check preflight:**
   ```bash
   curl http://localhost:8000/api/preflight | jq .
   ```
   This lists artefacts, integrations (LIVE/SIMULATED), the scenario and the clock. Verify `integrations` shows the expected statuses.

### Other targets

| Command | What it does |
|---|---|
| `make test` | Fast suite: backend (pytest, coverage ≥ 80%) + frontend (typecheck, lint, test). |
| `make test-slow` | Slow suite: golden numbers and full-artefact flows. Reads committed artefacts, never rebuilds. |
| `make demo-check` | Run every scenario through the HTTP API (70 checks). Used in CI and as a final pre-demo gate. |
| `make e2e` | Playwright tests (chromium) against a running console. |
| `make lint` | ruff check and format check (backend and scripts). |

## 4. Docker stack setup (optional)

To run the full stack (backend, console, n8n) in Docker:

```bash
make up      # = make env, then docker compose up -d --build --wait
make down    # stop the stack (volumes persist)
```

| Service | URL | Notes |
|---|---|---|
| Console | http://localhost:8080 | nginx serves the console and proxies `/api` and `/webhooks` to the backend. |
| Backend | http://localhost:8000 | FastAPI (non-root). The stack passes env vars from `.env`. |
| n8n | http://localhost:5678 | n8n 2.41.3. The three Chhatri workflows are imported and run live. |

**Demo mode:** The stack runs workflows on n8n by default. To use the in-process runner instead (faster for demo on a single machine), edit `.env`:
```env
CHHATRI_STACK_N8N_URL=
```
This makes the backend skip n8n and run workflows in-process. Both modes give the same timeline; n8n holds the monsoon replay at 17:00 for 30–60 s real time while 312 payouts go through.

**Ports:** Change `CHHATRI_BIND_ADDR`, `CHHATRI_BACKEND_PORT`, `CHHATRI_CONSOLE_PORT` and `CHHATRI_N8N_PORT` in `.env` if defaults are in use.

## 5. Static mock-mode deployment (N7)

For a public backup demo without a backend:

1. **Build the mock-mode console:**
   ```bash
   cd frontend && npm run build -- --mode mock
   ```
   This produces `frontend/dist/` with the in-browser mock backend baked in. Query strings like `?mock=1` are unnecessary in this build.

2. **Deploy to GitHub Pages or Vercel Hobby:**

   **GitHub Pages:**
   ```bash
   # Assuming the dist/ folder is pushed to docs/ or a gh-pages branch
   git subtree push --prefix frontend/dist origin gh-pages
   ```
   Visit `https://<username>.github.io/<repo-name>/`.

   **Vercel Hobby:**
   - Link the repo to Vercel at [vercel.com](https://vercel.com).
   - Set the build command to `npm run build -- --mode mock` in the frontend root.
   - Deploy.

3. **Add a permanent SIMULATED banner:** The mock-mode build should display a visible banner stating "SIMULATED demo" or "Mock mode" so judges and users know the data is not live. This is implemented in `frontend/src/components/SimulatedBanner.tsx` (or similar); confirm the banner is visible in the mock build before deploying.

**Fallback video:** Record a 7-minute narrated walk-through of the console using the mock-mode build or a replay video (as per [docs/DEMO.md](../DEMO.md)). Upload it to YouTube or store it on the demo laptop so it plays if the live demo has network issues.

## 6. Demo laptop checklist

Before the final demo on 3 Oct, verify:

### Browser and audio

- [ ] Browser supports Web Speech API for speech recognition. Test at `about:config` or [Google Codelabs](https://codelabs.developers.google.com/codelabs/web-speech-api/).
- [ ] Language is set to **Hindi (India)** (`hi-IN`) for STT fallback. Set in browser settings or test with `navigator.language`.
- [ ] Microphone is connected and has permission. Test in the console under N4 settings or in `https://test.webrtc.org/`.
- [ ] Speaker/headphone output works. Test with a notification sound or a Sarvam TTS fallback.

### Display

- [ ] Screen resolution is at least **1280×720** (1920×1080 recommended). Test with `screen.width × screen.height` in the browser console.
- [ ] Zoom is at **100%** (no zoom-in or zoom-out). Ctrl+0 (Windows/Linux) or Cmd+0 (Mac) to reset.
- [ ] The mini-app and maps render without overflow or truncation. Visually inspect each screen in the prototype console.

### Network and fallback

- [ ] Latency to Sarvam (if LIVE) and Gemini (if integrated) is acceptable (target: < 3 s per call). Test with `curl -w "@curl-format.txt"` or the browser DevTools Network tab.
- [ ] If live keys are set but unreachable (e.g., during the demo), the FALLBACK path works. Trigger it by killing the API or setting `OPENMETEO_LIVE=false` in the .env for the demo laptop.
- [ ] The offline fallback (Tesseract OCR, browser speechSynthesis, deterministic templates) works without internet. Test by disconnecting WiFi and retrying N2, N3, N4 flows.

### Sanity checks

- [ ] `make demo-check` passes all 70 checks (or 69+ if X1 fixes are pending).
- [ ] The demo scenarios (`monsoon`, `illness`, `buy_cover`, etc.) load correctly and play to the expected golden numbers.
- [ ] Console header shows the right LIVE/SIMULATED badges for each component (e.g., "Sarvam LIVE" if `SARVAM_API_KEY` is set, "Gemini SIMULATED" if not).

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'chhatri'` after `make setup` | venv not activated or installation failed | Run `source backend/.venv/bin/activate` and `make setup` again. Check `backend/.venv/bin/python -m pip list \| grep chhatri`. |
| `uvicorn: command not found` | backend not installed | Run `make setup` and retry `make dev`. |
| `frontend/node_modules` missing | `npm ci` skipped | Run `make setup` again. |
| Console on port 5173 is blank or errors on every click | Vite build failed or proxy misconfigured | Check `frontend/.env.local` has `VITE_API_URL=http://127.0.0.1:8000` (or your `BACKEND_PORT`). Restart `make dev`. |
| Backend returns 500 on `/api/integrations` | Artefact missing (e.g., `backend/artifacts/model/`) | Run `make data` (slow), or copy a known good `backend/artifacts/` from CI/another machine. Check with `curl http://localhost:8000/api/preflight \| jq .`. |
| `SARVAM_API_KEY` is set but STT/TTS show SIMULATED | Key is invalid or rate-limited | Check the key is correct in `.env`. Verify account balance on sarvam.ai dashboard. Look for 401 or 429 errors in the backend logs (`tail -f backend.log \| grep -i sarvam`). |
| Slip photo upload hangs and times out | Vision API (Sarvam or Gemini) is slow or unavailable | The vision component has a ~60 s timeout. If it exceeds that, the slip is REFERRED to a human. Try retaking the photo or using a pre-cached sample slip from `backend/data/slips/`. |
| "demo-check" fails on one scenario but not others | Deterministic bug or integration race condition | Run the scenario alone with `curl` to isolate. Check logs for async issues in workflows. This may indicate an X1–X8 fix is still needed. |
| Offline fallback (speechSynthesis, Tesseract) does not trigger | Network issue not caught, or feature flag not set | Manually disconnect WiFi and retry, or set the Sarvam/Gemini provider to `FALLBACK` in the provider panel (X6, H7) if implemented. |

## Open questions

1. **Per-component Sarvam toggles (X6):** Shall we implement `CHHATRI_ASSIST_PROVIDER`, `CHHATRI_STT_PROVIDER`, `CHHATRI_TTS_PROVIDER` and `CHHATRI_SLIP_PROVIDER` to gate credit spend, or is a single `SARVAM_API_KEY` on/off sufficient for a one-day demo? Owner: Ujjwal Pardeshi.
2. **Vercel vs GitHub Pages:** If N7 requires a backend mock for some endpoints (e.g. `/api/merchants/{id}/slip-precheck`), shall we use Vercel Hobby with minimal Node functions, or stay with static-only GitHub Pages and hard-code mock responses? Owner: Ujjwal Pardeshi.
3. **Demo laptop audio permissions:** On Linux and some Android emulators, requesting microphone access may require beforehand grant. Is there a setup script or a README reminder needed? Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v1.5 · second fact-check pass: corrected env var name GEMINI_API_KEY → GOOGLE_API_KEY to match section 2.1 and ADR 0004.
- 2026-10-02 · v1.4 · final consistency pass against the code: corrected status column for Speech-to-text and Text-to-speech rows to show SIMULATED (canned) or LIVE with key (not FALLBACK, which only exists with X6); marked browser Web Speech API as PLANNED.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: Gemini reframed as PLANNED (N2/N3 integration pending); TL;DR and status table updated to clarify Sarvam LIVE and Gemini PLANNED; privacy rule reframed for free-tier constraint; latency target labeled as assumption not verified.
- 2026-10-02 · v1.1 · fact-check pass: clarified that Gemini integration is PLANNED (N2/N3) and env var is not yet configured; removed reference to nonexistent GEMINI_API_KEY.
- 2026-10-02 · v1 · first draft: account setup, local dev, docker stack, static deploy, demo checklist, troubleshooting.
