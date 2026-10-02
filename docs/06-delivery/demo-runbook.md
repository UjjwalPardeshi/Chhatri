# Demo runbook

| | |
|---|---|
| Status | Draft v1.5 · 2 Oct 2026 |
| Owner | Omkar Kadam (script) with Ujjwal Pardeshi (operator) |
| Audience | The team, on-site demo logistics, backup operator |
| Related | [docs/DEMO.md](../DEMO.md) (the golden script) · [Pitch and judge Q&A](pitch-and-judge-qa.md) · [Risk register](risk-register.md) · [Build plan](build-plan.md) · [Feature specs](../02-product/feature-specs) |

## TL;DR

- **The demo runs live on the demo laptop:** console at http://localhost:5173 (`make dev`) or http://localhost:8080 (`make up`), API at http://localhost:8000.
- **Presenter:** Omkar Kadam narrates and makes no clicks. **Operator:** Ujjwal Pardeshi makes every click and speaks only if the demo stalls.
- **The slot time and length are not announced.** Two cuts are ready: 3 minutes and 7 minutes. Freeze the code 90 minutes before our slot.
- **The golden path is [DEMO.md](../DEMO.md):** voice chips and sample slips, with every number asserted by tests. The new features (N1–N4) are planned for 2 Oct. Use one live only if it passed the morning rehearsal on the demo laptop; otherwise stay on the golden path.
- **Badges:** today the header shows LIVE or SIMULATED per component. With our keys, at most the Sarvam components can be LIVE (and Gemini, once N2/N3 land). WhatsApp, the Paytm link, sales, alerts, KYC, payouts and the lender are SIMULATED. Never call anything live that the screen shows as SIMULATED.
- **If something breaks:** the backup controls in DEMO.md, then the static demo (N7), then the backup video.

## 1. Pre-demo setup (T−30 minutes)

### 1.1 Code and backend

1. **Freeze the code 90 minutes before our slot.** From the repo root, run `make test-slow` (golden numbers). If anything fails, revert the last commit and run it again.
2. **Start the stack with the in-process workflow runner** (recommended; the n8n badge then honestly reads SIMULATED):
   ```bash
   make dev   # backend :8000, console :5173, in-process workflows
   ```
   `make up` with `CHHATRI_STACK_N8N_URL=` (empty) in `.env` gives the same set-up in Docker on port 8080. With n8n LIVE, the clock holds at 17:00 for about 30–60 s while 312 payout runs go through n8n; avoid that on stage.
3. **Rehearse every scenario against the running backend before opening the console:**
   ```bash
   backend/.venv/bin/python backend/scripts/demo_check.py --url http://localhost:8000
   ```
   It must print `PASS: 70 passed, 0 failed, 0 skipped`. It reloads scenarios, so never run it during the talk.
4. **Preflight:** `curl -s localhost:8000/api/preflight`. Every item must have `"ok": true`.

### 1.2 Console and browser

1. Open the console at 1280×720, browser zoom 100%, full-screen window.
2. Click **Enable sound** in the header once. It is the one user gesture the browser needs; Soundbox lines and voice notes then auto-play.
3. Check the header badges against `.env`. Write down which components are LIVE; the disclosure at the end must match them.
4. Pick the **monsoon** scenario. The clock must read `Mumbai · monsoon replay · 08:00 · simulated`, paused.
5. **Seek to 13:30 and stay paused** (`post /api/replay/seek '{"to":"13:30"}'` from the DEMO.md backup controls if the UI misbehaves). Open `/live`.

### 1.3 Hand signals

Agree these before the slot:

| Signal | Meaning |
|---|---|
| Open hand, palm down | Press Play |
| Raised index finger | Pause |
| Circling hand | Step 5 simulated minutes |
| Pointing at the screen | Keep this view up; Omkar is talking about it |
| Thumbs up | Working, move on |
| Flat hand across the throat | Something is wrong; go to the contingency ladder (section 6) |

## 2. The 3-minute cut

**Goal:** the hook, the trigger firing on the live map, Anil's money and his "why", the payout-authority rule, the close.

| Time | Omkar says | Ujjwal does | Screen |
|---|---|---|---|
| 0:00–0:30 | **Hook (slide 3):** "Anil runs a tea stall in Parel. On a day of heavy rain his sales fall by more than half, and his ₹600 loan instalment is still cut from his settlement. Today, getting paid for that day takes 30 to 60 days of forms and documents. Paytm already sees his sales fall, as it happens. With Chhatri, the claim starts itself, and he is paid the same evening." | Nothing. Monsoon is loaded, paused at 13:30, on `/live`. | The live map, paused. |
| 0:30–1:15 | **The trigger (slide 6):** "This is Mumbai, ward by ward, in our monsoon replay: real rainfall, simulated shop sales. A red rain alert covers three wards from 14:00. Watch their sales." … "The drop held for three hours across all 46 shops in Zone 7, below 50% and below the bottom of the model's range, during the alert. No one filed anything." … "312 shops, paid four minutes after the trigger, with the evening settlement." … "Zone 9 also dipped, but it had no alert. A slow day is not a loss event." | At 0:30 press **Play** (speed 6). The trigger fires at 17:00 (about 0:33 later), money at 17:04. Pause at about 17:06. Click **Z7**. | KPI tiles: 3 zones, 312 shops, 4 min. Z7 panel: 37% for 3 hours, 46 of 46 prepaid, paid 17:04, ₹58,900. |
| 1:15–2:15 | **The money (slide 7):** "Anil's phone: ₹1,380, credited with today's settlement, and the Soundbox says it out loud. No claim needed. He asks: 'Why did I get only this much?'" … "His usual Tuesday is ₹4,380, his area fell 63%, and Chhatri pays half the lost sales. Half of ₹4,380 times 63% is ₹1,380. Every number can be checked. The AI builds the case; code decides the money." | Open `/merchant/S-0142` (or the N1 mini-app if it passed rehearsal). Tap the voice chip **why**. | The Hindi payout message, the ₹1,380 card, the Soundbox line, then the "why" reply with the formula. |
| 2:15–2:45 | **Trust (slide 8):** "Who decides the money? An area drop: Chhatri pays, and a person looks only if the merchant disputes. A personal claim: the AI reads the hospital slip, and if anything is unclear, a person decides. Cover bought once a storm is forecast never covers that storm. The AI never has authority over money. Code decides." | Open `/policy`. | The payout-authority table. |
| 2:45–3:00 | **Close (slide 13):** "Paytm already has the live sales, the settlement rail and the lending partners. Our next step is a pilot with a partner insurer and lender. The claim starts itself." | No clicks. | `/policy` or Anil's phone. |

**If the 3-minute cut runs late:** skip the Z7 panel click; skip `/policy` and say the trust line over Anil's phone.

## 3. The 7-minute cut

**Goal:** the 3-minute story in more depth, then the personal claim, the three live tests (EXPLAINED, HUMAN, BLOCKED), the trust layer and the honest limits. The order follows DEMO.md, so each scenario is loaded once.

| Time | Omkar says | Ujjwal does | Screen |
|---|---|---|---|
| 0:00–0:30 | Hook, as in the 3-minute cut. | Nothing. | The live map, paused at 13:30. |
| 0:30–1:30 | The trigger, as in the 3-minute cut, plus the Z7 panel row by row and the Zone 9 line: "Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. That's a slow day, not a loss event." | Play at 0:30; pause at about 17:06; click **Z7**; point at the "Why Zone 9 got nothing" panel. | KPI tiles, Z7 panel, Z9 `61% · 64 shops · slow day`. |
| 1:30–2:15 | The money and the "why", as in the 3-minute cut. At 17:05: "Tomorrow's ₹600 instalment is paused." | `/merchant/S-0142`. Tap **why**. | Anil's phone. |
| 2:15–2:40 | **Test 1, EXPLAINED:** "Anil says his loss was bigger. Chhatri doesn't argue and doesn't change the amount. It sends the case to a claims officer, who answers within 24 hours." | Tap **dispute**. Optional: open `/claims`, case **C-2291** (DISPUTE). | The reply, then the chip **Sent to a claims officer · case C-2291**. |
| 2:40–3:40 | **Personal claim:** "Thursday. Anil's shop had no sales all of Wednesday while his area was normal. Nobody filed a claim: Chhatri checks in first." … "He's in hospital. One photo of the slip." … "The slip reader takes the name and dates; the policy engine checks them against KYC and the silent day. Half his usual Wednesday is ₹2,150, capped at ₹1,500 a day. ₹1,500, credited with today's settlement." | Load **illness**. Seek 11:15, Play; pause at the 11:20 check-in. Tap **ill**. Send the sample slip. Then Play (or step 5 minutes) for the credit at +4 minutes and the paused instalment at +5. | Check-in message, the "ill" exchange, decision **APPROVED ₹1,500** with its formula, the credit and Soundbox line. |
| 3:40–4:25 | **Test 2, HUMAN:** "Same story, but the slip says Sunil Pawar. The name doesn't match Anil's KYC, so no money moves. A claims officer sees the slip, the extracted name, the KYC name and the checks, and approves. The engine re-runs every hard check before it pays." | Load **illness_mismatch**. Seek 11:15, Play to 11:20, pause, tap **ill**, send the slip. Open `/claims` → **C-2291**, tap **Approve**. Step 5 minutes, back to the phone. | Decision **REFERRED** (`NAME_MATCHES_KYC`), the case evidence, then ₹1,500 credited after approval. |
| 4:25–4:55 | **Test 3, BLOCKED:** "Monday evening. A red alert for tomorrow has just been issued. Ramesh asks for cover. New cover starts after the 7-day waiting period, from 25 August, so it won't apply to tomorrow's alert. He can still buy cover for later. Nobody can buy cover once a storm is forecast." | Load **buy_cover**. Open `/merchant/S-0907`. Tap **cover**. | The waiting-period reply and the link: ₹424.80 for 30 days (₹14.16 a day). |
| 4:55–5:40 | **Trust:** "Every step, from trigger to decision, payout, pause and message, is hash-chained. Here is the chain check: valid. And here is who may decide money." | `/audit` → **Verify chain**. Then `/policy`. | Chain valid; the payout-authority table. |
| 5:40–6:10 | **Honest limits:** "We ran the rules over the 2024 and 2025 monsoons with real rainfall and simulated sales. Chhatri caught 89 of 148 real drops, against 49 for a weather-only trigger, and far fewer payouts without a real drop. The calibration is circular by design, and the price gives a 65% loss ratio by construction. This validates the rules, not the market. A pilot with real merchants is the next step." | `/backtest`. | "simulated sales · real Open-Meteo rainfall" and the report numbers. |
| 6:10–6:35 | **What is real:** say the disclosure line below. | Point at the header badges. | Header badges. |
| 6:35–7:00 | **Close:** "Chhatri is income cover where the claim starts itself: paid the same evening, explained in Hindi, with the loan instalment paused. Our next step is a pilot with a partner insurer and lender. Questions?" | No clicks. | `/backtest` or `/policy`. |

**The disclosure line.** [DEMO.md](../DEMO.md)'s close line lists WhatsApp and the Paytm link on staging as live. That is only true with keys we do not have. Until DEMO.md is updated, say this instead, naming only what the badges show as LIVE:

> "What runs live here: the policy engine, the forecast model, the audit chain and the console. [Sarvam speech and slip reading are live; check the badges.] Simulated and labelled: shop sales, the alert feed, WhatsApp, the Paytm link, KYC, payouts and the lender. Code decides the money, and every step is logged."

**If the 7-minute cut runs late:** drop the optional `/claims` view in test 1, then shorten the trust section to the chain check only. Never drop the honest-limits line.

## 4. Where the planned features appear (only if they pass rehearsal)

| Feature | Spec | Where in the demo | What judges see | If it is not ready |
|---|---|---|---|---|
| N1 Merchant mini-app | [fs-04](../02-product/feature-specs/fs-04-merchant-mini-app.md) | Anil's phone (1:15 / 1:30); tracker during the personal claim | Cover card, claim tracker (Detected → Checked → Decided → Paid → EDI holiday), "why this amount" card | Use `/merchant/S-0142` as today; the numbers are identical |
| N2 Ask Chhatri | [fs-05](../02-product/feature-specs/fs-05-ask-chhatri.md) | Optional 15 s after "why" in the 7-minute cut, taken from the trust section | One free question, answered with the decision's own numbers and a clause reference | Skip it |
| N3 Slip pre-check | [fs-02](../02-product/feature-specs/fs-02-hospital-cash-claim.md) | Personal claim (2:40) | Extracted name and dates, a three-item checklist (readable, name matches KYC, dates match), then the decision | Send the sample slip as today |
| N4 Live voice | [fs-05](../02-product/feature-specs/fs-05-ask-chhatri.md) | Instead of tapping **why** | Omkar speaks the question; the transcript and the spoken reply appear | Tap the chip |

## 5. LIVE badge rules

1. **Today** `GET /api/integrations` reports each component as LIVE or SIMULATED, and the header shows the same.
   - Sarvam speech-to-text, text-to-speech, chat and vision are LIVE only when `SARVAM_API_KEY` is set; otherwise labelled simulators run (canned transcripts; the slip simulator reads data embedded in the sample slips).
   - WhatsApp needs four WhatsApp Cloud API variables, and the Paytm link needs `PAYTM_MCP_URL` or `PAYTM_MID` + `PAYTM_KEY_SECRET`. We have neither, so both are SIMULATED and the link is `https://paytm.me/sim-…`.
   - Sales, the alert feed, KYC, the payout rail, the lender and the Soundbox are always simulated.
2. **After N2 and N3 land:** the Gemini free tier is the first provider for Ask Chhatri and slip reading, then Sarvam, then templates (N2) or a person (N3). A component is LIVE only if its key is set and the rehearsal call succeeded on the demo laptop.
3. **After X6 lands:** a FALLBACK state and a provider panel show when a secondary provider stepped in. Until then there is no FALLBACK badge.
4. **Browser speech** (planned for N4) needs no key, but Chrome's recognition needs a network connection. Test it on the venue Wi-Fi.
5. **The rule that matters:** never call a component live in the pitch or Q&A if the screen showed it as SIMULATED.

## 6. Contingency ladder

Stop at the first step that keeps the judges' eyes on the product.

1. **A UI control misbehaves:** use the backup `curl` controls in [DEMO.md](../DEMO.md) (load, seek, play, pause, step, voice-demo, photo). Cost: about 10 s.
2. **A planned feature (N1–N4) fails:** fall back to the golden path for that step (the chip, the sample slip, `/merchant/S-0142`). Say: "Let me show the same step on the tested path."
3. **Numbers differ from DEMO.md:** reload the scenario; loads are deterministic. If they still differ, stop the live demo.
4. **The phone shows nothing after the slip or the approval:** the clock is paused; money arrives 4 simulated minutes later. Play, or step 5 minutes.
5. **The live demo cannot continue:** open the static mock-mode demo (N7). URL: *to be filled in after the N7 deploy*.
6. **No laptop, no network:** play the backup video (N7). File: *to be filled in after recording*.

Omkar's role during a fallback: say what is happening in one calm sentence and keep the story going. Ujjwal's role: signal, then switch.

## 7. Reset between runs

1. Reload: `post /api/replay/load '{"scenario":"monsoon"}'` (from the DEMO.md backup controls). The clock returns to 08:00, paused, and case ids restart at C-2291.
2. Seek to 13:30 and stay paused.
3. Check the console clock reads 13:30 and the KPI tiles are empty before the next run.

## 8. Rehearsals

| Rehearsal | When (see the build plan) | What | Pass when |
|---|---|---|---|
| REHEARSE-1 | Evening of 2 Oct | Both cuts on the dev machine, timed | Each cut within its limit; every number matches DEMO.md |
| REHEARSE-2 | Morning of 3 Oct, before the freeze | Both cuts on the demo laptop, then 10 minutes of judge Q&A role-play | Within limits; badges written down; each planned feature either passed or is dropped to the golden path |

**Timing targets.** 3-minute cut: hook 30 s, trigger 45 s, money 60 s, trust 30 s, close 15 s. 7-minute cut: as in the table in section 3.

**Rehearsal log (copy for each run):**

```
Rehearsal [#], [date] [time]. Presenter: Omkar. Operator: Ujjwal.
Timing:   3-min __:__ (limit 3:00)   7-min __:__ (limit 7:00)
Scenarios loaded cleanly: monsoon [ ] illness [ ] illness_mismatch [ ] buy_cover [ ]
Numbers match DEMO.md: 312 shops [ ] ₹1,380 [ ] ₹1,500 [ ] C-2291 [ ] ₹424.80 [ ]
Badges written down (LIVE list): ______________________
Planned features: N1 pass/drop  N2 pass/drop  N3 pass/drop  N4 pass/drop
Audio: Soundbox audible [ ]  voice reply audible [ ]
Notes:
```

## 9. Q&A set-up

Keep these tabs open, in this order: `/` (overview), `/live` (map), `/merchant/S-0142` (Anil's phone), `/claims` (cases), `/audit`, `/policy`, `/backtest`. Ujjwal stays on the keyboard; Omkar answers and points when a judge asks to see something. Answers to likely questions are in [pitch and judge Q&A](pitch-and-judge-qa.md).

## Open questions

1. Will the demo laptop use a trackpad or an external mouse? Practise with the one we will use. Owner: Ujjwal Pardeshi.
2. How long does a `make dev` restart take on the demo laptop? Time it in REHEARSE-2 and keep a second terminal open. Owner: Ujjwal Pardeshi.
3. When the slot is announced, which cut do we run? Owner: Omkar Kadam.

## Changelog

- 2026-10-02 · v1.5 · rewritten against DEMO.md: no invented slot time, 7-minute order follows the golden script, dispute never changes the amount, BLOCKED wording, live/simulated disclosure matches our keys
- 2026-10-02 · v1.4 · provider status wording for N2 and N3
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.2 · logic and truth audit fixes
- 2026-10-02 · v1.1 · fact-check pass: verified all numbers match docs/DEMO.md and docs/SPEC.md; outcomes (EXPLAINED, HUMAN, BLOCKED) used correctly.
- 2026-10-02 · v1 · first draft. Covers pre-demo setup, timing for 3-min and 7-min cuts, new features (N1–N4) placement, LIVE badge rules, fallback ladder, rehearsal log.
