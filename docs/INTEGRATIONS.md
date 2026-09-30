# Integrations: verified API facts and set-up

Every integration is optional. With its variables unset, a deterministic simulator runs and
`GET /api/integrations` labels the component `SIMULATED`. The facts below come from SPEC §14. The SDK
calls were checked against the installed packages: sarvamai 0.1.34, mcp 1.30.0, paytmchecksum 1.7.0.

All live clients use a 10 s timeout (60 s for Sarvam doc-ai). They retry only on 429 or 5xx, with
backoff and at most 3 attempts. They never log secrets, and they raise `IntegrationError` with a safe
message. The one exception is the n8n start call: it waits up to 30 s for the whole run and is not
retried, because n8n already retries each callback (see "n8n workflows").

`/api/integrations` reports these components: `sarvam_stt`, `sarvam_tts`, `sarvam_chat`,
`sarvam_vision`, `whatsapp`, `paytm`, `n8n`, `memory`, `weather`, `soundbox`, `sales_data`, `alerts`,
`payout_rail`, `lender`, `kyc`.

---

## Sarvam: speech, voice, chat, vision (SPEC §14.1)

**Live when** `SARVAM_API_KEY` is set. Models are configurable: `SARVAM_STT_MODEL` (`saaras:v3`),
`SARVAM_TTS_MODEL` (`bulbul:v3`), `SARVAM_TTS_SPEAKER` (`ritu`), `SARVAM_CHAT_MODEL` (`sarvam-105b`).
The base URL is `https://api.sarvam.ai` with header `api-subscription-key`. An auth failure is
HTTP 403. The SDK is synchronous, so calls run in `asyncio.to_thread`.

| Use | SDK call | Notes |
|---|---|---|
| STT (merchant voice) | `client.speech_to_text.transcribe(file=(name, bytes, mime), model="saaras:v3", mode="transcribe", language_code="unknown"\|"hi-IN", input_audio_codec=…)` | returns `.transcript`, `.language_code`, `.language_probability`; REST limit 30 s of audio; accepts OGG/Opus (WhatsApp) and WebM (browser) |
| TTS (voice notes, Soundbox) | `client.text_to_speech.convert(text=…, language_code="hi-IN", model="bulbul:v3", speaker="ritu", pace=1.0, output_audio_codec="mp3"\|"opus")` | returns `.audios[0]` (base64); at most 2,500 characters; lowercase speaker names; Opus sent as `audio/ogg` for WhatsApp, mp3 for the browser |
| Chat (intent fallback) | `client.chat.completions(model="sarvam-105b", messages=[…], temperature=0.1, response_format={"type":"json_schema","json_schema":{…}}, max_tokens=…)` | used only to choose one of the fixed intents; anything else means the rules decide (§13.2) |
| Vision (hospital slip) | `client.doc_ai.extract(file=[(name, bytes, mime)], schema=json.dumps(schema), language="en-IN", output_format="json")`, then `get_status(job_id)` until `completed`/`partially_completed`/`failed`/`rejected`, then `get_results(job_id)` | schema fields `patient_name`, `admission_date` (YYYY-MM-DD), `discharge_date`, `hospital_name`, `document_type` (admission_slip, discharge_summary, prescription, bill, other); confidence = min(confidence of `patient_name`, `admission_date`), with a missing value counting as 0 |

**Simulated**:
- STT uses the canned transcripts of the voice-demo keys: `why` → `मुझे इतने ही पैसे क्यों मिले?`,
  `dispute` → `मेरा नुकसान ज़्यादा हुआ।`, `ill` → `मैं अस्पताल में हूँ, बुखार है।`, `cover` →
  "Red alert tomorrow. Cover me today."
- TTS falls back to the browser's `speechSynthesis` in hi-IN, labelled.
- Vision reads the JSON embedded in the sample slip PNG (`tEXt` chunk `chhatri:slip`).

The LLM never sets an amount, approves, or overrides a check (§0.2). Free-text replies pass the guard
(§13.3), which rejects any digit not found in the decision facts.

## WhatsApp Cloud API (SPEC §14.2, §13.7)

**Live when** `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET` and
`WHATSAPP_VERIFY_TOKEN` are all set. The Graph API base is
`https://graph.facebook.com/{WHATSAPP_GRAPH_VERSION}`, with default `v25.0`.

- **Recipient safety**: live messages go only to demo merchants (`is_demo=True`) and only to
  `WHATSAPP_DEMO_RECIPIENT` (E.164). Every other merchant's messages are recorded on the simulator
  channel and never sent; their numbers are fake. Inbound messages from the demo recipient are routed
  to the loaded scenario's demo merchant (B5: `S-0142` Anil for monsoon, illness and illness_mismatch;
  `S-0907` Ramesh for buy_cover). Any other number gets at most one "this is a demo" reply a day.
- **Webhook**: set the callback URL to `https://<public host>/webhooks/whatsapp` and the verify token
  to `WHATSAPP_VERIFY_TOKEN`. For a laptop, run a tunnel to the backend port or to the console port;
  nginx proxies `/webhooks/`.
  - `GET` answers `hub.challenge` as `text/plain` 200 when `hub.mode=subscribe` and the token matches,
    else 403.
  - `POST` verifies `X-Hub-Signature-256 == "sha256=" + HMAC-SHA256(WHATSAPP_APP_SECRET, raw body)`
    with a constant-time comparison before parsing, and answers 403 on a mismatch. It is idempotent on
    the message id and always answers 200 quickly.
  - Messages are read from `entry[].changes[].value.messages[]`: text, audio (`voice`), image and
    `interactive.button_reply`.
- **Media**: `GET /{media-id}` with Bearer returns `{url, mime_type}` (the URL is valid for about
  5 minutes); then `GET url` with Bearer.
- **Send**: `POST /{phone-number-id}/messages` with `messaging_product:"whatsapp"`. A voice note is
  OGG/Opus uploaded with `POST /{phone-number-id}/media` (multipart `messaging_product=whatsapp`,
  `type=audio/ogg`, `file`) and then sent as `{"type":"audio","audio":{"id":…}}`. Reply buttons: at
  most 3, titles at most 20 characters.
- **24-hour window**: free-form messages only within 24 h of the merchant's last inbound message.
  Outside it, business-initiated messages (the 17:04 payout and the 11:20 check-in) must use an
  approved template.

### Templates to register (category UTILITY, language `hi`)

Register both in WhatsApp Manager with exactly these bodies. The parameters are positional, in the
order `chhatri.conversation.notifications` sends them. The texts are SPEC §13.4 `AREA_PAYOUT_INTRO` +
`PAYOUT_CARD` and `CHECKIN_SILENT`, with a leading `नमस्ते` because WhatsApp Manager rejects a body
that starts with a variable.

**`chhatri_area_payout`**: parameters `{{1}}` name (Hindi given name), `{{2}}` drop (integer %), `{{3}}` amount label.

```
नमस्ते {{1}} जी, आज भारी बारिश से आपके इलाके की बिक्री {{2}}% गिरी। {{3}} आज के सेटलमेंट के साथ जमा।
```

Sample values for review: `अनिल`, `63`, `₹1,380`.

**`chhatri_checkin`**: parameter `{{1}}` name.

```
नमस्ते {{1}} जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है?
```

Sample value: `अनिल`.

The send payload is
`{"type":"template","template":{"name":…,"language":{"code":"hi"},"components":[{"type":"body","parameters":[{"type":"text","text":…},…]}]}}`,
built by `chhatri.integrations.whatsapp_payloads.template_payload`.

## Paytm payment link (SPEC §14.3)

**Live when** `PAYTM_MCP_URL` is set (preferred), or when `PAYTM_MID` + `PAYTM_KEY_SECRET` are set
(direct REST).

- **MCP server** (Paytm's payment MCP server, SSE transport, path `/sse`). Client, with mcp 1.x:
  `async with sse_client(url) as (r, w): async with ClientSession(r, w) as s: await s.initialize();
  res = await s.call_tool("create_payment_link", {...})`. The tool is
  `create_payment_link(recipient_name, purpose, customer_email, customer_mobile, amount) -> str`. It
  returns `"url =<shortUrl>\nlinkId=<id>"`, which is parsed with a strict regex; anything else is an
  error. Run the server on the host and point the backend at it:
  - `make dev`: `PAYTM_MCP_URL=http://localhost:<port>/sse`
  - `make up`: `PAYTM_MCP_URL=http://host.docker.internal:<port>/sse` (the backend service maps
    `host.docker.internal` to the host)
- **Direct REST**: `POST {PAYTM_BASE_URL}/link/create` with
  `{"body": {mid, linkType:"FIXED", linkDescription, linkName, sendSms, sendEmail, maxPaymentsAllowed:1,
  amount, customerContact:{…}}, "head": {"tokenType":"AES", "signature": PaytmChecksum.generateSignature(json.dumps(body), PAYTM_KEY_SECRET)}}`.
  It succeeds when `body.resultInfo.resultStatus == "SUCCESS"`; the link is `body.shortUrl` and the id
  `body.linkId`. The staging base is `https://securestage.paytmpayments.com` (default); production is
  `https://secure.paytmpayments.com`.
- **Callback**: `POST /api/webhooks/paytm` accepts form or JSON. In REST mode, `CHECKSUMHASH` is
  verified with `PaytmChecksum.verifySignature`. Only `TXN_SUCCESS` (or `SUCCESS`/`PAID`) marks the
  premium paid and extends `prepaid_through`.
- The key never reaches the browser. Simulated links look like `https://paytm.me/sim-XXXXXX` and are
  labelled SIMULATED.

## n8n workflows (SPEC §14.5, §15; decision B1)

**Live when** `N8N_BASE_URL` is set. `make up` sets it to `http://n8n:5678`; set
`CHHATRI_STACK_N8N_URL=` (empty) to turn it off. The image is pinned to
`docker.n8n.io/n8nio/n8n:2.41.3`; the tag was checked on docker.n8n.io on 30 Sep 2026.

- **Start**: `POST {N8N_BASE_URL}/webhook/chhatri-{workflow}` with header `X-Chhatri-Secret` and body
  `{"run_id", "workflow", "payload"}`. `run_id` is `{workflow}:{decision_id|case_id}`, which makes the
  run idempotent. n8n answers only after the last step's callback:
  `200 {"ok": true, "data": {"run_id", "status": "completed", "steps": [...]}}`, or `403` for a wrong
  or missing secret, or `500` when a callback failed. The backend waits for this answer (timeout 30 s),
  so every step is scheduled before the simulated clock moves on; an answer without the completion body
  counts as a failed start.
- **Callbacks**: n8n calls `POST {CHHATRI_PUBLIC_URL}/internal/workflows/{step}` for each step, in
  `WORKFLOWS` order. Each call has the same header and the body `{"run_id", "workflow", "step",
  "payload"}`, with the payload passed through unchanged. The backend answers
  `200 {"ok": true, "data": {"step", "status": "done"|"skipped"}}`. Any non-2xx answer, after 3 tries,
  stops the n8n run, and the webhook answers 500.
- **Fallback**: connect failure, a non-2xx webhook answer or a missing completion body hands the run
  to the in-process runner, which schedules only the steps n8n had not reported yet. A timeout is not
  handed over (n8n may still be running it); it is audited as `workflow.start_failed`.
- **Throughput**: about 5–10 runs per second on the dev machine (n8n 2.41.3, SQLite, every execution
  saved). The monsoon burst of 312 payout runs holds the simulated clock at 17:00 for roughly 30–60 s;
  see docs/DEMO.md for the stage set-up.
- **Steps**:

  | Workflow | Steps |
  |---|---|
  | `payout` | `execute_payout` → `credit_payout` → `notify_merchant` → `pause_instalment` |
  | `human-review` | `open_case` → `notify_officer` |
  | `follow-up` | `check_case_sla` → `notify_officer` |

  There are no Wait nodes. The backend schedules each effect at decision time + the step's simulated
  offset (+0/+4/+4/+5 min for payout, +24 h for follow-up), so the timeline is identical to the
  in-process runner.
- **Files**: `n8n/workflows/chhatri-{payout,human-review,follow-up}.json` are generated from
  `chhatri.workflows.definitions.WORKFLOWS` by `make n8n-workflows`. Never edit them by hand; CI fails on
  drift. In each workflow, the webhook node verifies `x-chhatri-secret` against
  `$env.CHHATRI_INTERNAL_SECRET` and requires the secret to be non-empty. Reading `$env` needs
  `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`, which compose sets.
- **Start-up**: `n8n/entrypoint.sh` fails fast without `CHHATRI_INTERNAL_SECRET` or
  `CHHATRI_PUBLIC_URL`. It then runs `n8n import:workflow --separate` (fixed ids, so a restart
  re-imports in place), `n8n publish:workflow --id=…` for each workflow, and finally starts n8n.
- **Self-test**: `make n8n-selftest` starts the pinned image with these files and a stub
  `/internal/workflows/{step}` server. It proves:
  - the step order for all three workflows;
  - the secret header on every callback and payload pass-through (nested Unicode);
  - 403 and no callbacks for a wrong or missing secret;
  - the webhook answers 200 with the completion body only after the last callback;
  - a 500 on `credit_payout` stops the payout run before `notify_merchant`, and the webhook answers 500.

## Memory (SPEC §14.6, §16)

**Live when** `COGNEE_ENABLED=true` and the optional extra is installed (`pip install -e
"backend[memory]"`) with an LLM configured for cognee. Otherwise an in-process networkx
`MultiDiGraph` is used, with nodes for shops, zones, events, payouts, disputes, cases and decisions.
`precedents()` ranks facts: same merchant 1.0, same zone 0.7, other 0.4. The officer console shows
them as "Similar past cases"; with none, it shows "No similar past cases yet".

## Open-Meteo (SPEC §14.4)

The archive is `https://archive-api.open-meteo.com/v1/archive` and the forecast
`https://api.open-meteo.com/v1/forecast`. Parameters are `latitude, longitude, hourly=precipitation,
timezone=Asia/Kolkata, start_date, end_date`. The replay and backtest never call the network: they read
`backend/data/weather/openmeteo_{santacruz,colaba}_{2024,2025}.json`. The live client serves only
`GET /api/weather/now`, when `OPENMETEO_LIVE=true`. Attribution: "Weather data by Open-Meteo.com"
(CC BY 4.0).

## Soundbox, sales, alerts, KYC, payout rail, lender

These are always simulated and always labelled (SPEC §0.1). The Soundbox emits a `soundbox` SSE event
with the text `Paytm par ₹1,380 prapt hue — Chhatri se`, plus TTS audio when Sarvam is live.
