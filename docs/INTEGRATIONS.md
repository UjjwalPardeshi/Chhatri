# Chhatri Integrations (SPEC §14, §21)

Each integration is optional. Leave the environment variable unset to use the simulator (labelled "SIMULATED" in the UI).

---

## Sarvam AI (Speech, Chat, Vision)

Provides live STT (speech-to-text), TTS (text-to-speech), chat (intent classification), and vision (slip extraction).

### 1. Get API Key

- Visit https://sarvam.ai/ (sign up for free tier)
- Create a new API key in the dashboard
- Copy the key (format: `sk-...` or similar)

### 2. Set Environment Variable

```bash
# .env
SARVAM_API_KEY=sk-your-key-here
```

### 3. Verify

```bash
curl -X GET https://api.sarvam.ai/v1/health \
  -H "api-subscription-key: sk-your-key-here"
# Should return 200
```

### 4. What's Used in Demo

- **STT** (merchant voice → text): `saaras:v3` model, language auto-detect (Hindi/English)
- **TTS** (Chhatri replies → voice): `bulbul:v3` model, speaker `ritu`, output `opus` for WhatsApp
- **Chat** (intent classification): `sarvam-105b` model, JSON schema response
- **Vision** (slip extraction): `doc_ai` endpoint, fields: `patient_name`, `admission_date` (YYYY-MM-DD), `discharge_date`, `hospital_name`, `document_type` (enum)

### 5. Timeouts

- STT: 30s max audio
- TTS: 2,500 chars max
- Chat: 10s timeout
- Vision: 60s timeout (includes polling for async job)

---

## WhatsApp Cloud API (Live Messaging)

Sends messages to real merchants on WhatsApp (or simulator if env vars unset).

### 1. Prerequisites

- Paytm account (or META business account)
- WhatsApp Business Account (via Facebook/Meta)
- Test phone number (for development)
- Webhook URL (public, HTTPS — use ngrok for local dev)

### 2. Get Credentials

From Meta for Developers (https://developers.facebook.com/):

1. Create an App
2. Add "WhatsApp" product
3. Generate test credentials:
   - `WHATSAPP_ACCESS_TOKEN`: user access token (long-lived)
   - `WHATSAPP_PHONE_NUMBER_ID`: your test number's ID (1234567890...)
   - `WHATSAPP_APP_SECRET`: app secret (for webhook verification)
   - `WHATSAPP_VERIFY_TOKEN`: custom string (e.g., `my-secret-token`)

4. Add test numbers (Meta dashboard → Test contacts): your own number + judge's phone (E.164 format: `+919876543210`)

### 3. Set Environment Variables

```bash
# .env
WHATSAPP_ACCESS_TOKEN=EAA...
WHATSAPP_PHONE_NUMBER_ID=1234567890
WHATSAPP_APP_SECRET=abcdef123456
WHATSAPP_VERIFY_TOKEN=my-secret-token
WHATSAPP_DEMO_RECIPIENT=+919876543210  # Only this number receives live messages; others get simulator
```

### 4. Configure Webhook URL

In Meta dashboard:

1. Webhook URL: `https://your-domain.com/webhooks/whatsapp` (HTTPS required)
2. Verify token: `my-secret-token` (must match `WHATSAPP_VERIFY_TOKEN`)
3. Subscribe to: `messages`, `message_status`

### 5. Test Locally (Dev)

Use ngrok to expose local backend:

```bash
ngrok http 8000
# -> https://abc123.ngrok.io

# Add webhook: https://abc123.ngrok.io/webhooks/whatsapp
# (Meta will POST to verify the endpoint)
```

### 6. WhatsApp Templates (24-hour window)

Outside the 24-hour window after a merchant's last message, we use pre-approved UTILITY templates:

**Templates to submit to Meta** (category: UTILITY, language: hi):

1. **chhatri_area_payout** (params: name, drop, amount)
   ```
   {{1}} जी, भारी बारिश से आपके इलाके की बिक्री {{2}}% गिरी। {{3}} आपके सेटलमेंट के साथ जमा।
   ```

2. **chhatri_checkin** (params: name)
   ```
   {{1}} जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है?
   ```

Both require ~24 hours for Meta approval. Status check:

```bash
curl -X GET "https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/message_templates" \
  -H "Authorization: Bearer ${WHATSAPP_ACCESS_TOKEN}"
```

---

## Paytm Payment Links (Premium Payments)

Generates payment links for merchants to buy cover. Two options:

### Option 1: Paytm MCP Server (Recommended)

The Paytm payment MCP server exposes payment link creation via SSE.

#### Setup

1. Clone https://github.com/shivam3-garg/payment-mcp (public repository)
2. Build Docker image:
   ```bash
   cd payment-mcp
   docker build -t paytm-mcp .
   ```
3. Run:
   ```bash
   docker run -p 8080:8080 paytm-mcp
   # Or: docker compose --profile paytm-mcp up
   ```

#### Set Environment Variable

```bash
# .env
PAYTM_MCP_URL=http://localhost:8080/sse  # for local dev
# or
PAYTM_MCP_URL=http://paytm-mcp:8080/sse  # inside Docker Compose
```

### Option 2: Paytm Direct REST API (Staging)

Use Paytm's staging API directly (requires Merchant ID + Key Secret).

#### Get Credentials

From Paytm:
- `PAYTM_MID`: Merchant ID (staging environment)
- `PAYTM_KEY_SECRET`: API key secret (staging)

#### Set Environment Variables

```bash
# .env
PAYTM_MID=YOUR_MID
PAYTM_KEY_SECRET=YOUR_SECRET
PAYTM_BASE_URL=https://securestage.paytmpayments.com  # staging (default)
# For production, use https://secure.paytmpayments.com
```

### Option 3: Simulated (No Setup)

Leave both options unset. Payment links show as `https://paytm.me/sim-XXXXXX` (marked "SIMULATED").

### Test Payment Link

```bash
# In app, click "Buy cover" → link is generated
# In simulator: shown as https://paytm.me/sim-...
# With MCP: redirects to Paytm staging QR code
# With REST: redirects to Paytm staging QR code
```

---

## n8n Workflows (Orchestration)

n8n handles asynchronous workflow steps (payout → credit → notify → pause instalment).

### Option 1: In-Process (Recommended for Demo)

Leave `N8N_BASE_URL` unset. Backend runs workflows in-process (same logic, no external service).

### Option 2: Live n8n

1. Run n8n container:
   ```bash
   docker compose --profile n8n up
   # or: docker run -p 5678:5678 docker.n8n.io/n8nio/n8n:latest
   ```

2. Set environment variable:
   ```bash
   # .env
   N8N_BASE_URL=http://localhost:5678
   # Inside Docker: http://n8n:5678
   ```

3. Import workflows:
   ```bash
   # Via n8n UI (http://localhost:5678):
   # Settings → Import workflows → select n8n/workflows/*.json

   # Via CLI:
   n8n import:workflow --input n8n/workflows/chhatri-payout.json
   n8n import:workflow --input n8n/workflows/chhatri-human-review.json
   n8n import:workflow --input n8n/workflows/chhatri-follow-up.json
   ```

4. Activate workflows:
   ```bash
   # In n8n UI, activate each workflow (toggle in top-right)
   ```

5. Test:
   ```bash
   python scripts/n8n_selftest.py
   ```

### Workflow Details

See `n8n/workflows/` for definitions:

- **chhatri-payout**: execute_payout (0 min) → credit_payout (4 min) → notify_merchant (4 min) → pause_instalment (5 min)
- **chhatri-human-review**: open_case → notify_officer
- **chhatri-follow-up**: wait (configurable SLA) → check_case_sla

Each workflow:
- Accepts POST at `/webhook/chhatri-{name}`
- Verifies `X-Chhatri-Secret` header
- Returns 202 immediately
- POSTs to backend `/internal/workflows/{step}` with secret header + body

---

## Cognee Memory Graph (Optional)

Stores precedents of past cases for context.

### Option 1: In-Process (Default)

Uses networkx MultiDiGraph (no external service). Suitable for demos.

### Option 2: Live Cognee

1. Install cognee:
   ```bash
   pip install cognee  # or add to backend/pyproject.toml extras
   ```

2. Configure LLM (Sarvam or OpenAI):
   ```bash
   # .env
   COGNEE_ENABLED=true
   SARVAM_API_KEY=sk-...  # or OpenAI key
   ```

3. Restart backend:
   ```bash
   make dev
   ```

---

## Open-Meteo Weather (Live vs Fixtures)

Real rainfall data for backtest and live queries.

### Option 1: Fixtures (Default for Demo)

Real Open-Meteo data is cached in `backend/data/weather/` (committed to git). Demo/backtest read from fixtures; no API calls needed.

### Option 2: Live API

```bash
# .env
OPENMETEO_LIVE=true
```

Then `GET /api/weather/now` fetches live Mumbai rainfall. Backtest/replay still use fixtures (they need historical consistency).

---

## Environment Variables Checklist

### Minimal (Offline Demo)

```bash
# .env (all simulators)
CHHATRI_SEED=20251019
CHHATRI_DEMO_MODE=true
CHHATRI_LOG_LEVEL=INFO

# Everything else is simulated and labelled
```

### Full Demo (Live Everything)

```bash
# Core
CHHATRI_SEED=20251019
CHHATRI_PUBLIC_URL=http://localhost:8000
CHHATRI_CONSOLE_ORIGIN=http://localhost:5173
CHHATRI_DEMO_MODE=true

# Sarvam
SARVAM_API_KEY=sk-your-key

# WhatsApp
WHATSAPP_ACCESS_TOKEN=EAA...
WHATSAPP_PHONE_NUMBER_ID=1234567890
WHATSAPP_APP_SECRET=abcdef123456
WHATSAPP_VERIFY_TOKEN=my-secret-token
WHATSAPP_DEMO_RECIPIENT=+919876543210

# Paytm (option 1)
PAYTM_MCP_URL=http://localhost:8080/sse

# n8n (optional)
N8N_BASE_URL=http://localhost:5678

# Memory
COGNEE_ENABLED=false

# Weather
OPENMETEO_LIVE=false  # fixtures are sufficient
```

---

## Deployment Checklist

- [ ] Secrets in `.env` (never committed)
- [ ] `.env` has all required vars for the integrations you're using
- [ ] Backend started: `make dev` or `docker compose up backend`
- [ ] Frontend started: `make dev` or `docker compose up frontend`
- [ ] Integrations status: `curl http://localhost:8000/api/integrations`
- [ ] Expected output: each integration shows `LIVE` or `SIMULATED`
