# Demo script: 3 October 2026 (about 7 minutes)

This is the presenter's script for the live demo. It follows the round-1 deck (slides 3, 6, 7 and 8;
the final deck has its own outline in `docs/06-delivery/final-deck-and-video-script.md`). Every
number and string below comes from the SPEC (§4.3, §9.6, §13.4, §13.6, §17.2) and is asserted by
`make test-slow` (golden numbers) and `make demo-check`. **If the console shows anything different
from this page, stop and run `make demo-check` before going on.**

Replay speed is 6 simulated minutes per real second by default, so 1 simulated hour takes 10 seconds.
Every scenario load is deterministic: same ids, same amounts, and the first case is always `C-2291`.

> The deck's concept screen (slide 6) shows "Z7 · 41%". The prototype shows **37 %**. That is the
> number that produces the 63 % drop and the ₹1,380 payout. Say "37 %".

---

## T−30 min: machine check

1. Start the stack with one of these (decide before the talk, see "Workflows: in-process or n8n" below):
   - `make dev`: console at http://localhost:5173, API at http://localhost:8000, in-process workflows.
   - `make up`: console at http://localhost:8080, API at http://localhost:8000, n8n at http://localhost:5678.
     `make up` returns only when every container is healthy. It runs the workflows on n8n unless `.env`
     has `CHHATRI_STACK_N8N_URL=` (empty value), which selects the in-process runner.
2. Rehearse every scenario against the running backend:
   `backend/.venv/bin/python backend/scripts/demo_check.py --url http://localhost:8000`. The backend must run
   with the demo flag set, `CHHATRI_FEATURES=x4_lender_request` in `.env` (the lender decides the instalment
   holiday); `curl -s localhost:8000/api/health` must list `"features": ["x4_lender_request"]`. With the flag
   off the 17:05 line is the old unconditional pause and the check fails on purpose. It must print
   `PASS: 70 passed, 0 failed, 0 skipped` (about 10 s in-process, about 50 s with n8n). It reloads
   scenarios, so run it before you open the console, never during the talk. `make demo-check` runs the
   same checks in a separate in-process app on the committed artefacts, with the demo flag set switched on
   by itself.
3. Run `curl -s localhost:8000/api/preflight`. Every item must have `"ok": true`.
4. Open the console at 1280×720 with browser zoom at 100 %, in a full-screen window.
5. Click **Enable sound** in the header once. This is the one user gesture the browser needs;
   afterwards Soundbox and voice notes auto-play.
6. Check the header badges. Everything is SIMULATED except what you configured, for example Sarvam,
   WhatsApp, Paytm staging or n8n. Nothing simulated may be called live.
7. Pick the **monsoon** scenario. The clock must read `Mumbai · monsoon replay · 08:00 · simulated`
   and the replay must be paused.

**Workflows: in-process or n8n.** Both give the same simulated timeline (decisions 17:00, credits
17:04, the lender asked and the instalments paused 17:05; checked by `demo_check.py --url` in both modes). With n8n LIVE the 17:00 minute
starts 312 payout runs on n8n one after another, so the simulated clock **holds at 17:00 for about
30–60 s of real time** before it moves on (the feed fills with decisions meanwhile). The deck (slide 13)
does not claim n8n as live, so the recommended stage set-up is the in-process runner (`make dev`, or
`make up` with `CHHATRI_STACK_N8N_URL=`); the n8n badge then honestly reads SIMULATED. If you present
with n8n LIVE, talk over the hold at step 4 of the storm, or pause at 16:59 and step once.

Backup controls, if a UI control misbehaves. `API` is `http://localhost:8000` with `make dev`, or
`http://localhost:8080` (through nginx) with `make up`:

```bash
API=http://localhost:8000
post() { curl -s -X POST "$API$1" -H 'Content-Type: application/json' -d "$2"; echo; }
post /api/replay/load  '{"scenario":"monsoon"}'      # reset to 08:00, paused; ids restart (C-2291)
post /api/replay/seek  '{"to":"13:30"}'
post /api/replay/play  '{"speed":6}'
post /api/replay/pause '{}'
post /api/merchants/S-0142/voice-demo '{"key":"why"}'   # why | dispute | ill | cover
post /api/merchants/S-0142/photo '{}'                   # the loaded scenario's sample slip
```

---

## 0:00–0:30 · The problem (deck slide 3)

> "Anil runs a tea stall in Parel. On a day of heavy rain his sales fall by more than half, and his ₹600
> loan instalment is still cut from his settlement. Getting paid for a day like that has typically
> taken 30 to 60 days of forms and documents. Paytm already sees his sales fall, as it happens. With
> Chhatri, the claim starts itself, and he is paid the same evening."

## 0:30–2:30 · Storm replay on the live map (deck slides 3 and 6)

Console `/live` (the live map; `/` is the overview homepage), scenario **monsoon**: Tue 19 Aug 2025,
paused at 08:00.

1. **Seek to 13:30 and press Play (speed 6).**
   > "This is Mumbai, ward by ward. Every hexagon is the shops' sales against what our model expected
   > for this hour. Green is normal."
2. **About 13:30–14:00**: the red alert `A-20250818-01` for Z3, Z7 and Z12 is already in the feed. It
   was issued yesterday, Mon 18 Aug at 17:30, and is valid from 14:00 to 20:00. From 14:00 the rain band
   appears over Z3, Z7 and Z12.
   > "A red rain alert from 14:00 for three wards. Watch their sales."
3. **14:00–17:00 (about 30 s at speed 6)**: Z3, Z7 and Z12 turn amber, then red. Zone status goes from `watch` to
   `triggered`. Z9 (Chembur, by the harbour) also dips, but it has no alert.
4. **17:00: the trigger fires** for Z3, Z7 and Z12. Pause if you want to talk over it.
   - Zone labels: `Z7 · 37% · 46 shops`, `Z3 · 38% · 141 shops`, `Z12 · 47% · 125 shops`; Z9 reads
     `Z9 · 61% · 64 shops` with status slow day.
   > "The drop held for three hours across all 46 shops in Zone 7, below 50 % and below the bottom of
   > the model's range, during the alert. The policy engine checks every shop's cover. No one filed
   > anything."
5. **17:04: money.** The KPI tiles read **3** zones triggered, **312** shops paid, **4 min** trigger to
   money. Anil's pin reads **₹1,380 paid · 17:04**. Click **Z7**. The panel must read exactly:

   | Row | Value |
   |---|---|
   | Alert | Red alert from 14:00 |
   | Sales | 37% of expected for 3 hours |
   | Cover | 46 of 46 prepaid |
   | Paid | 17:04, with the settlement |
   | Total | ₹58,900 · instalments paused |

   > "312 shops, paid four minutes after the trigger, with the evening settlement."
6. **Why Zone 9 got nothing** (right panel), verbatim: *"Why Zone 9 got nothing: its sales fell to 61%
   on a day with no weather alert. That's a slow day, not a loss event, so Chhatri doesn't pay."*
   > "A slow day is not a loss event. The trigger needs an alert and a drop the model can't explain."
7. **17:05**: Chhatri asks each merchant's lender to pause tomorrow's instalment, and the simulated lender
   grants it. **Pause the replay** at about 17:06.
   > "Chhatri does not pause a loan. It asks the lender, under a rule they agreed in advance, and the lender
   > decides. Here the answer is yes."

## 2:30–3:30 · What Anil sees, and "why this amount?" (deck slides 1, 7 and 8, test 1: EXPLAINED)

Open `/merchant/S-0142` (Anil's phone: "Paytm · Chhatri", "Merchant protection · Hindi, English").

At **17:04**:
- `अनिल जी, आज भारी बारिश से आपके इलाके की बिक्री 63% गिरी।` / *Anil ji, heavy rain cut your area's
  sales by 63% today.*
- Payout card **₹1,380**, `आज के सेटलमेंट के साथ जमा` / *Credited with today's settlement*, badge
  **No claim needed**.
- Soundbox: **"Paytm par ₹1,380 prapt hue — Chhatri se"** / *₹1,380 received on Paytm, from Chhatri*.

At **17:05**: `आपके लेंडर ने कल की ₹600 की किस्त रोक दी है। वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं।` /
*Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty.* The
line names the lender as the one who decided.

**Live test 1: EXPLAINED.**
1. Tap the voice chip **why**. Anil says `मुझे इतने ही पैसे क्यों मिले?` (*Why did I get only this
   much?*). The reply:
   `आपका आम मंगलवार: ₹4,380। आज आपके इलाके की बिक्री 63% गिरी। छतरी खोई हुई बिक्री का आधा देती है।` /
   *Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales.*
   > "Every number can be checked: half of ₹4,380 times 63 % is ₹1,379.70, which rounds to ₹1,380."
   > (Formula shown on the decision: `½ × ₹4,380 × 63% = ₹1,380`;
   > Hindi `₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380`.)
2. Tap **dispute**. Anil says `मेरा नुकसान ज़्यादा हुआ।` (*My loss was bigger.*). The reply:
   `ठीक है, मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा।` / *Okay, I'm sending this to our
   team. You'll hear back within 24 hours.* Then the chip **Sent to a claims officer · case C-2291**.
   > "Chhatri explains with his own numbers and offers a human. It never argues or changes the amount."
3. Optional: open `/claims` to show case **C-2291** (DISPUTE), with the expected-vs-actual hours.

## 3:30–4:45 · Personal claim: ill, one photo (deck slide 7, panel 2)

Pick scenario **illness**: Thu 21 Aug 2025, 10:30. Anil's shop had zero sales all of Wed 20 Aug and his
zone was normal.

1. **Seek to 11:15, then Play.** At **11:20** Chhatri checks in:
   `अनिल जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है?` / *Your shop has been closed since yesterday.
   Is everything okay?*
   > "Nobody filed a claim. Paytm saw a full day with no payments, and Chhatri reached out first."
2. Pause. Tap the voice chip **ill**: `मैं अस्पताल में हूँ, बुखार है।` (*I'm in hospital with a
   fever.*). Reply: `जल्दी ठीक हो जाइए। अस्पताल की पर्ची की एक फ़ोटो भेज दीजिए।` / *Get well soon. Please
   send one photo of the hospital slip.*
3. Send the **sample slip** (`anil_admission_slip.png`: patient "Anil R. Jadhav", admitted
   2025-08-20, "Viral fever", KEM Hospital, Parel).
   > "The slip reader takes the name and dates. The policy engine checks them against KYC
   > (ANIL RAMESH JADHAV) and against the silent day."

   Say "vision model" only if the Sarvam vision badge reads LIVE; with a simulator it is "the slip reader".

   Decision **APPROVED ₹1,500**, decided at the minute you send the slip (11:20 if you paused there):
   - Formula: `½ × ₹4,300 = ₹2,150 a day, capped at ₹1,500 × 1 day = ₹1,500` (Hindi
     `₹4,300 का आधा = ₹2,150 प्रतिदिन; सीमा ₹1,500 × 1 दिन = ₹1,500`). ₹4,300 is Anil's usual
     Wednesday, the silent day; the console's "expected today" for Thursday reads ₹4,560.
   - Credit time is 4 simulated minutes after the decision, so **press Play** (or
     `post /api/replay/step '{"minutes":5}'`): at +4 min the message
     `अनिल जी, आपका दावा मंज़ूर है। ₹1,500 आज के सेटलमेंट के साथ जमा।` / *Anil ji, your claim is approved.
     ₹1,500 credited with today's settlement.*, the ₹1,500 payout card and the Soundbox line
     **"Paytm par ₹1,500 prapt hue — Chhatri se"**.
   - At +5 min: `आपके लेंडर ने आज की ₹600 की किस्त रोक दी है। वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं।` /
     *Your lender has paused today's ₹600 instalment. It moves to the end of your loan with no penalty.*
     (Thursday 21 Aug, the day after the silent day).

## 4:45–5:45 · Live tests 2 and 3 (deck slide 8)

**HUMAN: a slip with a different name.** Pick scenario **illness_mismatch**. Seek to 11:15, play to
11:20, pause, tap **ill**, then send the sample slip (`mismatch_admission_slip.png`, patient "Sunil
Pawar").
- The decision is **REFERRED**: `NAME_MATCHES_KYC` fails and no money moves. Chat:
  `धन्यवाद। पर्ची पर नाम आपके KYC से मेल नहीं खा रहा, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।` /
  *Thank you. The name on the slip doesn't match your KYC, so our team will check it. You'll hear back
  within 24 hours.* Then **Sent to a claims officer · case C-2291**.
- Open `/claims` → **C-2291**. The evidence shows the slip image, the extracted name, the KYC name, the
  match score, the silent days and the checks. Tap **Approve**. The officer decision re-runs every HARD
  check and pays **₹1,500**. Anil gets `अनिल जी, हमारी टीम ने आपका दावा मंज़ूर किया। ₹1,500 जमा।` /
  *Anil ji, our team approved your claim. ₹1,500 credited.* That message comes at credit time, 4
  simulated minutes after the approval: press Play (or step 5 minutes) before switching to the phone.
  > "Doubtful claims always go to a person. The AI never pays on a doubt."

**BLOCKED: "Red alert tomorrow. Cover me today."** Pick scenario **buy_cover**: Mon 18 Aug 2025,
18:00. The alert `A-20250818-01` (issued 17:30) is in the feed. Open `/merchant/S-0907` (Ramesh Vada
Pav, Z3, not covered) and tap the voice chip **cover**.
- Reply: `नया कवर वेटिंग पीरियड के बाद शुरू होता है — 25 अगस्त से। कल के अलर्ट पर यह लागू नहीं होगा।` /
  *New cover starts after the waiting period — from 25 August. It won't apply to tomorrow's alert.*
- Then the link message for 30 days of Z3's premium: *To buy cover for later, pay ₹424.80
  (₹14.16/day) here: …* (Hindi `आगे के लिए कवर लेना हो तो ₹424.80 (₹14.16/दिन) यहाँ भरें: …`). The price
  comes from the backtest (`backend/artifacts/premiums.json`); the deck's "a few rupees a day" is a
  pricing decision still open, so do not quote a price beyond what the screen shows. The link comes
  from Paytm staging when `PAYTM_MCP_URL` or `PAYTM_MID` + `PAYTM_KEY_SECRET` is set; otherwise it is
  `https://paytm.me/sim-…`, labelled SIMULATED.
  > "Nobody can buy cover once a storm is forecast. The waiting period is seven days."

## 5:45–6:30 · Trust: audit, policy, backtest (deck slides 5, 8 and 11)

- `/audit` → **Verify chain** → valid. Every step, from trigger to decision, payout, holiday request, lender answer, pause and message,
  is hash-chained.
- `/policy`: the payout-authority table, exactly as on slide 8 (area drop: Chhatri pays, a human only
  on dispute; personal claim: pays up to the daily cap; slip unclear: never alone; cover after an
  alert: never, waiting period).
- `/backtest`: Chhatri vs a weather-only trigger over the 2024 and 2025 monsoons, labelled
  "simulated sales · real Open-Meteo rainfall". Read the numbers off the screen; they come from
  `backend/artifacts/backtest/report.json`.

## 6:30–7:00 · Close (deck slide 13)

WhatsApp and the Paytm premium link are **SIMULATED** on stage: the team has no WhatsApp Cloud API keys
and no Paytm staging keys, so the phone is the console's simulator and the link is `https://paytm.me/sim-…`.
Sarvam (speech, chat, slip reading) is live only when `SARVAM_API_KEY` is set. Name only what the header
badges show as LIVE.

> "What runs live here: the policy engine, the forecast model, the audit chain and the claims console.
> [Say that Sarvam speech and slip reading are live only if their badges read LIVE.] Simulated and
> labelled: shop sales, the alert feed, WhatsApp, the Paytm payment link, KYC, payouts, the lender and
> the Soundbox. Code decides the money, and every step is logged."

---

## If something goes wrong

| Symptom | Do this |
|---|---|
| Numbers differ from this page | Reload the scenario (picker, or `post /api/replay/load '{"scenario":"monsoon"}'`). It is deterministic. If they still differ, run `make demo-check` and use the backup machine. |
| Map tiles missing (no internet) | Nothing. The console falls back to ward outlines on a plain background. |
| "reconnecting" pill | Wait. SSE resumes with `Last-Event-ID`. Reload the page if it lasts more than 10 s; state is server-side. |
| No sound | Click **Enable sound** again. Every voice bubble also has a play button. |
| n8n container down | Nothing. A workflow n8n cannot start runs in-process instead, with the same steps and timeline; the backend logs it at ERROR. |
| Clock holds at 17:00 (n8n LIVE) | Expected: 312 payout runs are going through n8n (about 30–60 s). Keep talking; the clock resumes and credits land at 17:04. To avoid it, restart with `CHHATRI_STACK_N8N_URL=` in `.env` and `make up`. |
| Phone shows nothing after the slip or the officer's approval | The clock is paused; money arrives 4 simulated minutes later. Press Play, or `post /api/replay/step '{"minutes":5}'`. |
| Console does not load with `make up` | `docker compose ps` (all healthy?), `docker compose logs backend`. Fall back to `make dev` on the same machine: console http://localhost:5173. |
| Paytm staging slow or down | Say so; nothing else depends on it. For an offline demo, start without the Paytm variables: the link is then `https://paytm.me/sim-…`, labelled SIMULATED. |
| Replay stuck | `post /api/replay/pause '{}'`, then `post /api/replay/step '{"minutes":5}'`, or seek to the moment you need. |

## Golden numbers (all asserted by tests)

| Fact | Value |
|---|---|
| Replay day | Tue 19 Aug 2025, 08:00–20:00 IST (simulated) |
| Alert | `A-20250818-01`, RED rain, Z3 · Z7 · Z12, issued Mon 18 Aug 17:30, valid 14:00–20:00 |
| Indices at 17:00 | Z7 37 % (drop 63 %) · Z3 38 % · Z12 47 % · Z9 61 % (slow day, no alert) |
| Timeline | decisions 17:00 · credits + WhatsApp + Soundbox 17:04 · lender asked, instalment pauses 17:05 |
| KPIs | 3 zones triggered · 312 shops paid · 4 min trigger to money |
| Z7 | 46 shops, 46 of 46 prepaid, total ₹58,900 |
| Anil (S-0142) | usual Tuesday ₹4,380 · area payout ₹1,380 · instalment ₹600 paused by his lender (asked 17:05) |
| Personal claim | usual Wednesday ₹4,300 · ½ = ₹2,150 capped at ₹1,500, 1 day · credit +4 min · Thursday's ₹600 instalment paused by the lender +5 min |
| Z9 | `Z9 · 61% · 64 shops`, slow day, no payout |
| Cover link (Ramesh, S-0907, Z3) | ₹424.80 for 30 days (₹14.16/day, from the backtest; pricing decision pending) |
| First case after a fresh load | C-2291 |
| Cover bought Mon 18 Aug | BLOCKED, starts 25 August (7-day waiting period) |
