# Security

Chhatri is a hackathon prototype that moves only simulated money. It is still built so that no
component except the policy engine can approve a payout, and every step can be audited. This page
lists the controls that exist in the code and in the infra (SPEC §0.2, §11, §14, §19, §21), the known
limits, and the checklist to run before a demo.

## Controls

### Secrets (SPEC §21)

- Secrets come only from the environment: `.env` at the repo root, or the shell. `.env` is
  git-ignored. `.env.example` lists every setting but carries no secret values.
- `make env` (`scripts/init_env.py`) creates `.env` with a random `CHHATRI_INTERNAL_SECRET` and
  `N8N_ENCRYPTION_KEY` (32 random bytes each), with file mode `0600`. It never overwrites an existing
  `.env` and never prints a secret.
- Secret settings are pydantic `SecretStr`. `Settings.public_summary()` is the only view of the
  settings that leaves the process, and it holds booleans and modes only.
- `docker compose` refuses to start without `CHHATRI_INTERNAL_SECRET`. Optional credentials are passed
  to the backend only when they are set.
- The Paytm key never reaches the browser, and neither does any other key.

### Who can do what

| Surface | Protection |
|---|---|
| Officer actions (`POST /api/cases/{id}/approve`, `/decline`, `POST /api/premium/link`; with their flags: `POST /api/merchants/{id}/consents/{consent_id}/withdraw`, `POST /api/merchants/{id}/slips/{slip_id}/forget`, and `POST /api/integrations/{component}/fallback`, which also needs demo mode) | `Authorization: Bearer <CHHATRI_OFFICER_TOKEN>`, constant-time compare. When the token is unset, a random one is generated at start-up and logged once. In demo mode (`CHHATRI_DEMO_MODE=true`) `GET /api/session` hands it to the console. **Set `CHHATRI_DEMO_MODE=false` anywhere but the demo laptop.** |
| n8n callbacks (`POST /internal/workflows/{step}`) | `X-Chhatri-Secret` compared in constant time (`hmac.compare_digest`). An empty configured secret refuses everything. The body is validated against `WORKFLOWS`, and every `execute_payout` re-checks that the decision exists, is APPROVED and has not been executed. Idempotent per `(run_id, step)`. Not proxied by the console's nginx. |
| n8n webhooks (`/webhook/chhatri-*`) | The workflow compares `X-Chhatri-Secret` with `$env.CHHATRI_INTERNAL_SECRET` and requires the secret to be non-empty; otherwise 403 and no callbacks (proved by `make n8n-selftest`). |
| WhatsApp webhook (`/webhooks/whatsapp`) | GET needs `WHATSAPP_VERIFY_TOKEN`. POST verifies `X-Hub-Signature-256` (HMAC-SHA256 of the raw body with `WHATSAPP_APP_SECRET`) before parsing. Idempotent on message id. |
| Paytm callback (`/api/webhooks/paytm`) | In REST mode, `CHECKSUMHASH` is verified with `PaytmChecksum.verifySignature`. Only `TXN_SUCCESS`/`SUCCESS`/`PAID` count. |
| Uploads (`/api/merchants/{id}/photo`, `/voice`, `/slip-precheck`, `POST /api/voice/stt`) | Type is checked by magic bytes, not headers (JPEG, PNG and WebP images; the §19 audio formats). Images and audio are limited to 5 MB and audio to 30 s. nginx caps request bodies at 6 MB. |
| Rate limits | In-memory sliding window of 60 s per client: webhooks 60, uploads 20, phone messages and Ask 60, what-if 300. |
| Feature flags (`CHHATRI_FEATURES`) | Every flag is off by default. A route whose flag is off answers exactly like a path that does not exist (404 `not_found`, before the body is read), pinned by `backend/tests/api/test_feature_routes.py`. |
| CORS | Only `CHHATRI_CONSOLE_ORIGIN`, with no credentials. The docker console is same-origin through nginx. |

### Money path (SPEC §0.2, §9)

- `chhatri.policy.engine` is pure and is the only code that returns `APPROVED`. With `n2_ask_chhatri`
  off, LLM output can choose an intent from a fixed list and nothing else, and a model-chosen intent never
  runs a handler that writes. With it on, only the word lists choose intents. Model answers pass a
  two-layer guard (`grounded()` and `guard_strict.py`): no number that is not in the fact sheet, no
  promise of money, no links or phone numbers, valid clause ids only. The question is wrapped as untrusted
  data, and strong injection signals skip the model (H16).
- An officer's approval creates a new decision after re-running every HARD check, so an officer cannot
  pay an uncovered merchant, a merchant with an unpaid premium, or the same claim twice. SOFT checks
  are recorded as `WAIVED_BY_OFFICER`.
- n8n only orders steps. It never decides, and the backend sets the timing from simulated time (B1).
- Cover bought while an alert is active or forecast starts only after the 7-day waiting period (§9.5).

### Audit (SPEC §11)

The audit log is an append-only SQLite hash chain: SHA-256 over canonical JSON, with a genesis of
64 zeros. The wall-clock `recorded_at` is excluded from the hash. `GET /api/audit/verify` recomputes
the chain and reports the first bad `seq`. Every decision stores all of its checks. Actors are named:
`policy-engine`, `officer:<id>`, `workflow:<name>`, `merchant:<id>`, and so on. The chain is
tamper-evident, not durable: it lives in an in-memory database that is rebuilt on every scenario load
(the replay is deterministic, so a reload gives the same chain), and a restart empties it.

### Privacy (SPEC §14.2, §21)

- Phone numbers are masked in logs as `+91•••••12345`. The merchant view shows only the masked phone and
  masked KYC name. The officer's case view shows the KYC name, because the name check needs it.
- Live WhatsApp messages go only to `WHATSAPP_DEMO_RECIPIENT`, and only for demo merchants. Simulated
  merchants have fake `+9199000…` numbers and are never contacted.
- Error responses use the envelope and never echo secrets or stack traces.
- Only synthetic data may reach a free-tier AI service (ADR 0009). `CHHATRI_DATA_IS_SYNTHETIC` must be
  `true` for Gemini, Sarvam or Cognee to be called; unset, every such call is skipped.
- A slip photo is re-encoded without EXIF, XMP or text chunks before a provider or the store sees it.
  With `n6_consents` on, a slip is read only under a slip consent, and "forget my slip" erases the photo
  and the slip text in decisions and cases. Audit entries for Ask and voice hold hashes, ids and counts,
  never the question, the answer or a transcript.

### Containers and network

- Backend image: Python 3.12 slim, **non-root** (uid 10001). The code, data and artefacts under `/app`
  are root-owned and read-only to the app; `/app/var` (a volume) is the one place it may write, and
  nothing is written there yet, because the store and the audit log are in memory. There is no compiler,
  curl or wget in the image, and the healthcheck uses stdlib urllib.
- Console image: **unprivileged** nginx (uid 101), `server_tokens off`, `X-Content-Type-Options:
  nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: same-origin`. Only `/api/` and `/webhooks/`
  are proxied.
- All published ports bind to `127.0.0.1` by default (`CHHATRI_BIND_ADDR`). Expose the WhatsApp
  webhook through a tunnel that forwards only `/webhooks/whatsapp`.

## Known limits (accepted for the prototype)

| Limit | Why it is acceptable here | Mitigation |
|---|---|---|
| In MCP or simulated Paytm mode, the process has no merchant key, so the Paytm callback cannot be checksum-verified | Staging and simulated premiums only; no real cover is sold | Use REST mode (`PAYTM_MID` + `PAYTM_KEY_SECRET`) to verify, or keep `/api/webhooks/paytm` off the tunnel |
| The n8n webhook secret check is a plain string comparison in an n8n expression, not constant time | n8n listens on localhost or the compose network only | Keep port 5678 unexposed; the backend re-checks the secret on every callback in constant time |
| `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`: any workflow in this n8n can read its environment | This n8n runs only the three generated Chhatri workflows | Never import third-party workflows into it; its environment holds only the internal secret, the public URL and the encryption key |
| The n8n editor is reachable on `localhost:5678` until an owner account is created | Local only | Open it once and create the owner account, or leave the port closed |
| Rate limits are in memory, per process | Single-process demo | A shared store would be needed to scale out |
| Demo mode hands the officer token to any console user | Needed for one-tap approval on stage | `CHHATRI_DEMO_MODE=false` outside the demo |

## Pre-demo security checklist

- [ ] `.env` exists (`make env`), is mode 0600, is not committed (`git status` shows nothing), and has
      no empty `CHHATRI_OFFICER_TOKEN=` line.
- [ ] `WHATSAPP_DEMO_RECIPIENT` is the presenter's own number, if WhatsApp is live.
- [ ] Every Paytm variable that is set points at **staging** (`PAYTM_BASE_URL=https://securestage.paytmpayments.com`).
      With none set, the premium link is simulated and no request goes to Paytm.
- [ ] Ports are bound to `127.0.0.1`. If a tunnel is used, it forwards only `/webhooks/whatsapp`.
- [ ] `GET /api/audit/verify` returns `valid: true` after a full rehearsal.
- [ ] `make test`, `make test-infra` and `make n8n-selftest` pass on the demo machine.
- [ ] `.env` has `CHHATRI_DATA_IS_SYNTHETIC=true` only because every slip, voice note and question on
      stage is synthetic (`make env` warns when it is missing); `/api/preflight` shows the `free_tier_gate` row.
- [ ] `CHHATRI_FEATURES` and `VITE_FEATURES` list the same flags, and `GET /api/health` prints them.
