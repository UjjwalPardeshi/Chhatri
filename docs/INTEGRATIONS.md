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
`payout_rail`, `lender`, `kyc`. With the flag `x6_provider_panel` on it also lists `gemini_chat` and
`gemini_vision` (17 rows; with `telegram_channel` on, an 18th row `telegram`), with `mode` LIVE, SIMULATED or FALLBACK, the provider, the model, the reason and
a demo switch (data-model 5.6). `/api/preflight` always lists all 17.

**Free-tier data gate (ADR 0009).** Gemini, Sarvam and Cognee's LLM run on free tiers, so they are called
only when `CHHATRI_DATA_IS_SYNTHETIC=true` (set in `.env.example`; unset means false). With the gate closed
they make zero calls even with a key: the chains label the answer SIMULATED with `FREE_TIER_BLOCKED`, the
direct Sarvam paths get the simulators, Cognee stays off, and `/api/preflight` (row `free_tier_gate`), the
start-up log and the panel say so.

---

## Sarvam: speech, voice, chat, vision (SPEC §14.1)

**Live when** `SARVAM_API_KEY` is set and the data gate is open. Models are configurable: `SARVAM_STT_MODEL` (`saaras:v3`),
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

## Telegram bot (flag `telegram_channel`; data-model 5.13)

Telegram is a second chat app next to WhatsApp, never a replacement: WhatsApp stays the default, and a
merchant (or the officer, for the demo) can move Chhatri's messages to Telegram and back. It only changes
where messages go; cover, decisions and payouts are the same.

**Live when** the flag is on, `TELEGRAM_BOT_TOKEN` is set and `CHHATRI_DATA_IS_SYNTHETIC=true` (ADR 0009:
Telegram is a free third-party service). Otherwise the channel records every message on the console phone
and `/api/integrations` labels the `telegram` row SIMULATED (reason `NO_KEY` or `FREE_TIER_BLOCKED`).

- **Set-up**: create a bot with @BotFather, put its token in `.env` as `TELEGRAM_BOT_TOKEN` (never commit
  it), and run `make check-keys`: it prints SET or NOT SET and the bot's `@username` with the demo deep link,
  never the token.
- **No public URL**: the backend reads updates by long polling (`getUpdates`) while `TELEGRAM_POLLING=true`
  (the default). There is no webhook. Only one process may poll a token, so `make stage-e2e` starts its
  backend without the token.
- **Binding a chat**: open `https://t.me/<bot username>?start=S-0142` on a phone and press Start; the chat is
  bound to that demo merchant. `/stop` unbinds it. Only demo merchants are ever bound or sent to.
- **Choosing the channel**: the console's merchant phone has a "Chat app" switch (WhatsApp | Telegram), and
  the mini-app's Settings screen has "Messages from Chhatri". Both call `POST /api/merchants/{id}/channel`
  (officer token; audit `channel.preference_set`). A replay load starts again on WhatsApp.
- **What the bot sends**: the same bilingual texts as WhatsApp, voice notes as OGG/Opus, and the payout card
  with its quick-reply buttons ("why", "my loss was bigger"). A reply to an inbound message goes back on the
  channel it came from. The console phone wears Telegram's colours while the merchant is on Telegram.

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
  `200 {"ok": true, "data": {"step", "status": "done"|"skipped"}}`. A callback that fails (an error, a
  4xx or 5xx answer, or no answer within 10 s; n8n follows redirects) is tried 3 times, with a 1 s wait
  between tries; then the run stops, later steps are not called, and the webhook answers 500. Three
  timed-out tries take about 32 s, longer than the backend's 30 s wait, so that case ends as a timeout
  (see Fallback).
- **Fallback**: a connection that fails outright (refused, unknown host: `httpx.ConnectError`), a 4xx or
  5xx webhook answer, or an answer without the completion body hands the run to the in-process runner,
  which schedules only the steps Chhatri has not already accepted from n8n, that is, not yet put on its
  simulated scheduler (`Scheduler.was_scheduled`). A step report that Chhatri refused (for example 404
  or 409) was never scheduled, so the runner schedules that step; no step runs twice. A timeout
  (connecting included) or another transport error, such as a dropped connection, is not handed over (if
  the request reached n8n, n8n may still be running the workflow); it is audited as
  `workflow.start_failed`.
- **Throughput**: about 5–10 runs per second on an otherwise idle dev machine (n8n 2.41.3, SQLite, every
  execution saved). The monsoon burst of 312 payout runs then holds the simulated clock at 17:00 for
  roughly 30–60 s. On a heavily loaded machine (load average about 20) it took about 3 minutes, longer
  than `backend/scripts/demo_check.py`'s default 120 s request timeout: keep the stage machine free of
  other heavy work, and give `demo_check.py` `--timeout 300` when n8n is live. See docs/DEMO.md for the
  stage set-up.
- **Steps**:

  | Workflow | Steps |
  |---|---|
  | `payout` | `execute_payout` → `credit_payout` → `notify_merchant` → `request_holiday` |
  | `human-review` | `open_case` → `notify_officer` |
  | `follow-up` | `check_case_sla` → `notify_officer` |

  There are no Wait nodes. The backend schedules each effect at the run's start (the decision for
  payout, the case opening for human-review and follow-up) + the step's simulated offset (+0/+4/+4/+5
  min for payout, +0 for human-review, +24 h for follow-up), so the timeline is identical to the
  in-process runner.
- **Files**: `n8n/workflows/chhatri-{payout,human-review,follow-up}.json` are generated from
  `chhatri.workflows.definitions.WORKFLOWS` by `make n8n-workflows`. Never edit them by hand; CI fails on
  drift. In each workflow, the `Secret OK?` node checks `x-chhatri-secret` against
  `$env.CHHATRI_INTERNAL_SECRET` and requires the secret to be non-empty (its node id still comes from
  its earlier name, `Verify X-Chhatri-Secret`). Reading `$env` needs `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`,
  which compose sets.
- **Canvas**: the words are in `scripts/n8n_canvas_text.py` and the layout in `scripts/n8n_canvas.py`.
  Each workflow has a plain-words name and numbered plain-words step nodes, on one row from left to
  right:

  | Workflow (name in n8n) | Step nodes |
  |---|---|
  | `payout` (Chhatri · Payout (approved claim)) | 1 · Prepare the payout → 2 · Credit ₹ to merchant → 3 · Tell merchant: WhatsApp + Soundbox → 4 · Ask lender to pause next instalment |
  | `human-review` (Chhatri · Human review (referred claim or dispute)) | 1 · Queue for an officer → 2 · Notify the officer |
  | `follow-up` (Chhatri · Follow-up (case deadline)) | 1 · Check the deadline → 2 · Remind officer if open |

  The secret check is called `Secret OK?`, short enough to fit under its node. `Reject (403)` sits
  below it, one node width to the right, so n8n draws the `false` edge as a curve down past the check's
  name instead of a loop back to the left. Each step node's notes give the step key and its simulated
  offset, the callback `POST /internal/workflows/{step}`, the retry policy and when Chhatri runs the
  step. n8n shows the notes as one line under the node, cut off with "…" at the node's width: the first
  line (step key and offset) always fits, and the full text is under the node's Settings, Notes. Four
  sticky notes explain the workflow: a title note (blue) with what starts it and that n8n never decides;
  the security check (red) around the webhook, the secret check and the reject branch; the checklist
  (green) around the steps, with each step's simulated time and, for payout, the monsoon example and
  what is simulated (the settlement rail, the lender and the Soundbox); and what happens when a step
  fails (gold). The times are computed from the step offsets.

  The layout uses n8n 2.41.3's own geometry: 96 px nodes on its 16 px grid (so nothing is moved when
  n8n snaps positions), names in a 192 px box under each node, and its edge rule (a loop only when the
  target handle is more than 20 px left of the source handle). Nothing overlaps, every node and name sits inside
  its note below the note's text, and no note's text is clipped. The "+" that n8n shows after
  `Completed (200)` (an output with no connection) sits just outside the green note on payout. Zoom to
  fit in a 1280 × 720 window shows all three canvases at zoom 0.67, so the note text is about 9 px:
  titles, headings and node names read at a glance; zoom in to read the notes. Each time a published
  workflow opens, n8n shows its own "Production Checklist" pop-up over the top left of the canvas; close
  it with its × (the workflow does not change) before showing the canvas.

  The canvas changes how the workflow looks, not what it does. Ids, file names, webhook paths, the
  secret check, every callback and its retry settings are unchanged: node ids still come from the step
  key (and, for the check, its earlier name), and a test pins the executable part of each file by hash.
  A backend step without a plain-words text makes `make n8n-workflows` fail.
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

## Gemini: chat and vision (N2, N3; ADR 0003)

**Live when** `GOOGLE_API_KEY` and `GEMINI_MODEL` are set and the data gate is open. `GEMINI_VISION_MODEL`
optionally names a model that accepts images for the slip reader (default: `GEMINI_MODEL`). The model is
chosen on the day from the AI Studio free tier; `make check-keys` lists the models the key can use and never
prints the key. A key without a model id leaves Gemini out of the chains (reason `MODEL_NOT_SET`).

One call is `POST {base}/models/{model}:generateContent` over httpx (`integrations/gemini_client.py`), with
the key only in the `x-goog-api-key` header. The request asks for JSON shaped by the caller's schema with as
little thinking as the model allows: `thinkingBudget: 0` for 2.x models, and `thinkingLevel` for 3.x models,
which ignore the budget (`minimal` for flash-lite, `low` otherwise). Without it a 3.x model thinks past the
3 s link budget. If the API answers 400 to those fields, the call is sent once more with the schema in the
prompt and the adapter keeps that shape. Interactive paths make one attempt per link. Every reply is checked
against the full schema, then by the guard (Ask) or the field validator (slips). Run against the real API on
3 Oct 2026 (the stage checks and the stored eval run, [AI evaluation plan §1.2.1](04-engineering/ai-evaluation-plan.md)).

**Free-tier quota and backups.** On the AI Studio free tier each model allows about 20 requests a day per
project (seen on 3 Oct 2026); a spent model answers 429 until the daily reset. A 429 is `RATE_LIMITED` and
the chain moves on at once. `GEMINI_BACKUP_MODELS` (comma-separated, optional) adds more Gemini links right
after the main one, each with one attempt, so a spent model hands over to a sibling model before Sarvam or the
template. Backups share the main link's component name, so the provider switch turns them off together, and
the status reads "Gemini <model> (+N backup)". The stage runs `gemini-3.5-flash-lite` with
`gemini-flash-lite-latest` as the backup (`make demo-stage`); rehearsals spend the same quota as the show.

| Use | Adapter | Chain |
|---|---|---|
| Ask answer (flag `n2_ask_chhatri`) | `gemini_chat.py` | Gemini → Sarvam chat → catalogue template |
| Slip read (flag `n3_slip_precheck`) | `gemini_vision.py`, on a cleaned copy with no metadata | Gemini vision → Sarvam Vision → REFERRED; the simulated reader only when nothing live applies |

**Simulated**: templates answer Ask, and the simulated reader reads the sample slips.

## Memory (SPEC §14.6, §16)

**Live when** `COGNEE_ENABLED=true`, the data gate is open, and the optional extra is installed (`pip install -e
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

These are always simulated and always labelled (SPEC §0.1). With the flag `x4_lender_request` on, the
simulated lender decides each EDI holiday request by its own rule (active loan, not in arrears, allowance
left, in the scheme) and can be forced to give no answer from the provider panel (X6); with the flag off it
grants every pause as before. The Soundbox emits a `soundbox` SSE event
with the text `Paytm par ₹1,380 prapt hue — Chhatri se`, plus TTS audio when Sarvam is live.
