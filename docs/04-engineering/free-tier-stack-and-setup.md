# Free-tier stack and setup

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Ujjwal Pardeshi |
| Audience | Engineers building and operating Chhatri |
| Related | [System architecture](system-architecture.md) · [Data model and API](data-model-and-api.md) · [AI architecture and guardrails](ai-architecture-and-guardrails.md) · [Facts and sources](../01-strategy/facts-and-sources.md) · [Regulatory and compliance](../05-business/regulatory-and-compliance.md) |

## TL;DR

- Setup for the mini-app's Tailwind CSS v4 + shadcn/ui (scoped to `frontend/src/miniapp/`), the feature flags and the Gemini and Sarvam key checks is in [implementation guide §2](implementation-guide.md) (Wave 0).

- Every component is LIVE when its API key is set, otherwise SIMULATED and labelled.
- Sarvam (free starter credits) and the Gemini free tier are both BUILT as adapters; each is LIVE only when its key (and, for Gemini, a model id) is set in the environment. No key is in the repository. Both take **only synthetic data** (demo merchants, sample slip images), and a code gate (`CHHATRI_DATA_IS_SYNTHETIC`, ADR 0009) closes every free-tier link unless the deployment declares its data synthetic.
- All other integrations are free or in-process (n8n, Cognee, Open-Meteo).
- Set `SARVAM_API_KEY` to activate all four Sarvam modules (STT, TTS, chat, vision). The X6 demo switch (flag `x6_provider_panel`) lets the presenter force a component into its fallback path, so credits are spent on hero moments only.
- Local setup via `make setup` and `make dev`. Static mock-mode deploy to GitHub Pages or Vercel Hobby for a public backup.
- Demo laptop must have browser speech recognition (en-IN) and microphone, run at 1280×720, and test offline fallback.

## 1. Free-tier component table

| Component | Need | Primary | Fallback 1 | Fallback 2 | Status | Cost |
|---|---|---|---|---|---|---|
| **Grounded answers (N2)** | Ask Chhatri text replies in Hindi and English | Gemini Flash free tier (`GOOGLE_API_KEY` and `GEMINI_MODEL`) | Sarvam chat (free credits) | deterministic templates | LIVE with a key, FALLBACK when a link fails or is forced, otherwise SIMULATED | ₹0 |
| **Slip reading (N3)** | Extract patient name, dates, hospital from slip photo | Gemini Vision (`GOOGLE_API_KEY` and a model id) | Sarvam Vision (credits, LIVE if key set) | the simulated reader, then REFERRED to a person (Tesseract OCR is NOT BUILT) | LIVE with a key, FALLBACK when a link fails or is forced, otherwise SIMULATED | ₹0 |
| **Speech-to-text (N4)** | Hindi voice input in the mini-app and WhatsApp | Sarvam Saaras v3 or v4 (credits, existing) | browser Web Speech API (BUILT in the mini-app, depends on the browser) | tap-to-send chips | SIMULATED (canned demos) or LIVE (Sarvam with key) | ₹0 |
| **Text-to-speech (N4)** | Hindi and English voice output (proactive check-in, payout notice) | Sarvam Bulbul v3 (credits, existing) | browser speechSynthesis (BUILT) | text only | SIMULATED or LIVE (Sarvam with key) | ₹0 |
| **Workflows (DEMO.md)**  | Orchestrate claim checks, EDI requests, payouts | in-process runner (default for `make dev`) | n8n 2.41.3 (self-hosted in the docker stack, where it is the default) | manual | LIVE when `N8N_BASE_URL` is set, otherwise SIMULATED | ₹0 |
| **Memory graph (K5)** | Store facts about merchants and claims for Ask Chhatri | networkx (in-process, labelled) | Cognee (open source; uses Gemini or Ollama) | — | SIMULATED | ₹0 |
| **Weather data** | Real Open-Meteo rainfall for the monsoon replay scenario | cached fixtures (committed to repo) | live Open-Meteo API (test only, `OPENMETEO_LIVE=true`) | — | SIMULATED (real data) | ₹0 |
| **Hosting** | Static mock-mode console and fallback video | GitHub Pages (free) | Vercel Hobby (free plan) | local laptop | Build BUILT (`dist/` with `404.html`); not deployed unless the repo owner does it | ₹0 |
| **Database** | Store scenarios, cases, decisions, audit log, consents | in-memory store per scenario load, audit log in a private in-memory SQLite database | PostgreSQL (future) | — | in-process | ₹0 |

## 2. Account setup

### Google AI Studio (Gemini Flash free tier)

**Status:** BUILT (`backend/chhatri/integrations/gemini_chat.py`, `gemini_vision.py`, `gemini_client.py`), tested against fakes only. It is LIVE only when you set a key and a model id. No Gemini model name is written in these documents, because the free-tier ids change.

1. Go to [ai.google.dev](https://ai.google.dev) and sign in with a personal Google account.
2. Click **Get API key** and create a new API key in a new project (or an existing project).
3. Copy the key to `.env` and name a model:
   ```env
   GOOGLE_API_KEY=<your key>
   GEMINI_MODEL=<a text model id from the current free tier>
   GEMINI_VISION_MODEL=<optional, a model that accepts images; the text model reads slips if this is empty>
   ```
4. Run `make check-keys`. It prints SET or NOT SET for each key (never the value) and, with a Google key, lists the Gemini models the key can use.

A key without a model id leaves Gemini out of the chain, and the provider panel says "key set, model not set".

**Privacy rule (critical):** The Gemini free tier may use submitted content to improve Google products (A19). When live, never send real customer data (KYC names, real slip photos, real sales figures). Send only:
- Synthetic demo merchants (Anil, Ramesh, Priya, Rajesh, Amit from the personas).
- Sample slip images baked into the repo (`backend/data/slips/`).
- Demo policy wording and rules (from `backend/chhatri/policy/rules.yaml`).

**Provider order:** N2 (Ask Chhatri) and N3 (slip reading) try Gemini first when it is configured, then Sarvam (LIVE if `SARVAM_API_KEY` is set), then a template or the simulated reader (SIMULATED). With no keys, every AI call is SIMULATED and labelled in the console. The data gate (`CHHATRI_DATA_IS_SYNTHETIC`, true in `.env.example`) must be true, or the free-tier links are skipped with the reason `FREE_TIER_BLOCKED`.

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

**Per-component switch (X6, BUILT, flag `x6_provider_panel`):** one `SARVAM_API_KEY` activates the four Sarvam modules, and the presenter can force any one component into its fallback path without a restart. `POST /api/integrations/{component}/fallback` with `{"force": true}` (officer token) forces it, `{"force": false}` releases it, and the console's provider panel has the same switches. The forceable components are `sarvam_chat`, `gemini_chat`, `sarvam_vision`, `gemini_vision`, `sarvam_stt`, `sarvam_tts`, `lender`, `n8n`, `whatsapp` and `paytm` (`FORCEABLE` in `backend/chhatri/integrations/switch.py`). Each row reports `LIVE`, `FALLBACK` or `SIMULATED` with a reason. The separate `CHHATRI_*_PROVIDER` environment variables once proposed for this were not built and are not needed.

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
   This runs the full pipeline (geo → city → history → model → calibration → backtest) and writes to `backend/artifacts/`. It is slow (many minutes) and the outputs are already committed. Skip this unless you change the simulation parameters in `backend/chhatri/pipeline/`.

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
| `make demo-check` | Run every scenario through the HTTP API (offline, committed artefacts). In process it runs with `CHHATRI_FEATURES=x4_lender_request` (plus any flag you name), because the scripted flow stops by design at the `n3_slip_precheck` and `n6_consents` steps. Against a running backend (`--url`) that backend must have the same flags. A pre-demo gate; CI does not run it. |
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
   cd frontend && VITE_FEATURES=n1_miniapp npm run build -- --mode mock
   ```
   This produces `frontend/dist/` with the in-browser mock backend baked in, and a `404.html` so deep links work on a static host. Query strings like `?mock=1` are unnecessary in this build. `VITE_FEATURES` names the flags the build shows; leave it out for the console alone. `STATIC_DIR=dist npx playwright test --project=mock static-build` checks the build.

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

3. **Check the labels:** the mock build shows an amber "Mock data" badge in the console footer (`frontend/src/components/layout/Footer.tsx`) and a static-demo banner in the mini-app (`frontend/src/miniapp/shell/StaticBanner.tsx`), so judges and users know the data is not live. Confirm both are visible in the mock build before deploying.

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
- [ ] The offline fallback (the simulated slip reader, browser speechSynthesis, deterministic templates) works without internet. Test by disconnecting WiFi and retrying N2, N3, N4 flows.

### Sanity checks

- [ ] `make demo-check` passes every check (the count is in the [testing strategy](testing-and-quality-strategy.md), section 1).
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
| "demo-check" fails on one scenario but not others | Deterministic bug or integration race condition | Run the scenario alone with `curl` to isolate. Check logs for async issues in workflows. Compare the failing row with `backend/chhatri/api/demo/golden.py`. |
| Offline fallback (speechSynthesis, simulated reader, templates) does not trigger | Network issue not caught, or feature flag not set | Manually disconnect WiFi and retry, or force the Sarvam or Gemini component into its fallback in the provider panel (flag `x6_provider_panel`). |

## Open questions

1. **Per-component Sarvam toggles (X6):** Settled for the demo: one `SARVAM_API_KEY` plus the forced-fallback switch per component (section 2). Should a pilot add separate environment variables per component to gate credit spend? Owner: Ujjwal Pardeshi.
2. **Vercel vs GitHub Pages:** If N7 requires a backend mock for some endpoints (e.g. `/api/merchants/{id}/slip-precheck`), shall we use Vercel Hobby with minimal Node functions, or stay with static-only GitHub Pages and hard-code mock responses? Owner: Ujjwal Pardeshi.
3. **Demo laptop audio permissions:** On Linux and some Android emulators, requesting microphone access may require beforehand grant. Is there a setup script or a README reminder needed? Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-03 · v1.7 · synced with the code: Gemini and the per-component switch are BUILT, browser speech and the static build are BUILT, Tesseract is not built, the demo-check note names its flag set
- 2026-10-02 · v1.6 · linked the Wave 0 setup (Tailwind and shadcn, flags, key checks) in the implementation guide
- 2026-10-02 · v1.5 · corrections: corrected env var name GEMINI_API_KEY → GOOGLE_API_KEY to match section 2.1 and ADR 0004.
- 2026-10-02 · v1.4 · consistency check against the code: corrected status column for Speech-to-text and Text-to-speech rows to show SIMULATED (canned) or LIVE with key (not FALLBACK, which only exists with X6); marked browser Web Speech API as PLANNED.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned: Gemini reframed as PLANNED (N2/N3 integration pending); TL;DR and status table updated to clarify Sarvam LIVE and Gemini PLANNED; privacy rule reframed for free-tier constraint; latency target labeled as assumption not verified.
- 2026-10-02 · v1.1 · corrections: clarified that Gemini integration is PLANNED (N2/N3) and env var is not yet configured; removed reference to nonexistent GEMINI_API_KEY.
- 2026-10-02 · v1 · first draft: account setup, local dev, docker stack, static deploy, demo checklist, troubleshooting.
