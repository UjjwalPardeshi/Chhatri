# Stage script: the 3-minute demo

| | |
|---|---|
| Status | v1 · 3 Oct 2026 · walked end to end against the real backend by `frontend/tests/e2e/stage-demo.spec.ts` (`make stage-e2e`) |
| Owner | Omkar Kadam (voice) with Ujjwal Pardeshi (every click) |
| Audience | The team on stage, the backup operator |
| Related | [Demo runbook](demo-runbook.md) (the long cuts, the beat rules and the contingency ladder) · [DEMO.md](../DEMO.md) (the golden numbers) · [On-site checklist](on-site-checklist.md) · [Pitch and judge Q&A](pitch-and-judge-qa.md) |

## 1. The story in one line

A storm halves sales in three wards at 17:00 and 312 shops are paid by 17:04 with no claim filed. Anil sees it in Hindi, with every number traced to its source and the lender's holiday labelled simulated. Then Anil falls ill and a photo of one slip is enough. Every step is in a hash-chained log.

Five moments, nothing else: **1** the trigger and the 312 shops, **2** Anil's phone in Hindi (tracker, why this amount, sources, the lender's holiday), **3** the illness claim with the slip pre-check, **4** Ask Chhatri with its honest label, **5** the audit chain. The what-if on Zone 9 is a spare 15 seconds, not part of the 3 minutes.

## 2. The flag set and the start command

The eight flags below are the same in the backend (`CHHATRI_FEATURES`) and the console (`VITE_FEATURES`). `make demo-stage` sets both from one variable, `STAGE_FLAGS`, and adds `CHHATRI_DATA_IS_SYNTHETIC=true`.

```
n1_miniapp, n2_ask_chhatri, n3_slip_precheck, x4_lender_request, x6_provider_panel, h24_whatif, console_polish, telegram_channel
```

| Flag | Why it is on |
|---|---|
| `n1_miniapp` | Anil's app inside the phone frame: Hindi, claim tracker, "Why this amount?", source badges |
| `x4_lender_request` | The instalment step says the lender decided, labelled SIMULATED. Without it the screen says Chhatri paused it, which we do not claim |
| `n3_slip_precheck` | The slip pre-check: what the reader found, a three-line checklist, one tap to confirm |
| `n2_ask_chhatri` | Ask Chhatri with clause chips and a footer that names what answered |
| `x6_provider_panel` | The header chip and the Integrations panel: the one-click way to force a component to FALLBACK if a live AI call misbehaves |
| `h24_whatif` | The spare 15 seconds on Zone 9, and the pricing simulator on Backtest for questions |
| `console_polish` | The moment card on the map while the payout runs |
| `telegram_channel` | The chat-app switch on the console phone and in the app (WhatsApp or Telegram). With `TELEGRAM_BOT_TOKEN` in `.env` the presenting machine polls the real bot; every other machine runs `TELEGRAM_POLLING=false`. Without a token the messages stay on the console phone |

Left off on purpose: `n6_consents` (it adds a tick before the slip and a tick before a purchase, which costs seconds the 3 minutes do not have), `n4_voice` (needs a microphone and a quiet room), `n5_grievances`, `n8_marathi` (a draft that waits for a native speaker's review), `x8_distress_guard`, `h8_ops_strip`, `h25_evals`. `make demo-check` must still be run with its own flag set (`x4_lender_request` only); it is never run against this stack, and never with `n3_slip_precheck` or `n6_consents` on.

**Start command** (repo root, one terminal, never saved-file reload):

```bash
make demo-stage                 # backend :8000, console :5173; LIVE Gemini by default (STAGE_AI=live, keys read from .env)
make demo-stage STAGE_AI=sim    # same, with both AI keys blanked: every badge reads SIMULATED
```

`demo-stage` runs the backend without `--reload`, so saving a file cannot restart it. It sets `GEMINI_MODEL=gemini-3.5-flash-lite` (`STAGE_GEMINI_MODEL`) and `GEMINI_BACKUP_MODELS=gemini-flash-lite-latest` (`STAGE_GEMINI_BACKUPS`). The free tier allows about 20 requests a day per model: on 3 Oct 2026 `gemini-2.5-flash-lite` was spent by midday and `gemini-2.5-flash` answered HTTP 404, and a rejected live reader sends the slip to a person instead of reading it. `gemini-3.5-flash-lite` answers an Ask question in about 2 s; the larger 3.x models and Gemma miss the 3-second Ask budget. Do not loop rehearsals on the live models: check once on the demo day that the model answers, and change `STAGE_GEMINI_MODEL` if it does not.

**Which AI mode to stage.** Choose before the slot, never during the talk:

| Mode | Command | What the screen says | Say |
|---|---|---|---|
| All simulated (the fallback, walked 3 of 3 by `make stage-e2e`) | `make demo-stage STAGE_AI=sim` | Slip footer SIMULATED, Ask footer `LIVE · rules` for the first question | "No AI key on this machine, so the slip reader and the model are simulators, and the label says so." |
| Gemini live (the default; walked by `make stage-e2e STAGE_E2E_AI=live`) | `make demo-stage`, after the three checks below pass | Slip footer LIVE `gemini`; a free question shows `LIVE · gemini` with a clause chip | "This answer came from a live model; the footer says which. The amount was never its decision." |

Three checks before choosing Gemini live, at T-30 on the venue network: `make check-keys` (key SET and the model listed); one slip read through the app (READY inside 6 s; on 3 Oct a read took about 5 s); one free question ("What is the yearly limit?" returned `LIVE gemini` with clause C4.3). Any one fails: restart with `STAGE_AI=sim`. Free-tier services get synthetic data only: the sample slip, never a real document.

Pre-flight at T-30, after the stack is up:

1. `curl -s localhost:8000/api/health` lists exactly the eight flags above. `curl -s localhost:8000/api/preflight` has every item `"ok": true`.
2. Console at 1280×720, browser zoom 100%, full screen, Chrome. Click **Enable sound** once. Presenter mode stays off (the spec runs without it).
3. Copy `backend/data/slips/anil_admission_slip.png` to the Desktop so the file dialog finds it in one click.
4. Park: pick **Monsoon replay**, seek **16:40**, stay paused on **Live map**. The clock reads `Mumbai · monsoon replay · 16:40`. Slow near payout stays on.
5. Open **Merchant phone** once so the page is loaded, then come back to **Live map**.

## 3. The script

Omkar speaks and never clicks. Ujjwal clicks. Times are the plan for the speaker's clock; the spec walks the same clicks in about 35 s because it does not talk.

| Time | Ujjwal clicks | Omkar says | Screen must show (asserted by the spec) | If it fails |
|---|---|---|---|---|
| 0:00 to 0:20 | Nothing. Live map parked at 16:40 | "Before the demo, one honest line: the policy engine, the console and the audit chain are real; shop sales, WhatsApp and the Paytm link are simulated, and every screen labels which is which. Anil runs a tea stall in Parel. In heavy rain his sales fall by more than half, and his 600 rupee instalment is still cut. Getting paid for a day like that has typically taken 30 to 60 days. Watch what Chhatri does with no claim." | Map at 16:40, paused. Header chip `Simulated`. Footer: `Sales, alerts, KYC, payouts, lender and Soundbox are simulated` | Blank map: reload the page (the backend holds the clock). Still blank: `post /api/replay/load '{"scenario":"monsoon"}'` then seek 16:40 |
| 0:20 to 0:45 | **Play** (about 12 s later the clock reads 17:05) then **Pause** | "A red alert from 14:00 over three wards. Zone 7: sales at 37% of expected for three hours, all 46 shops. At 17:00 the rule fires. At 17:04, with the evening settlement, 312 shops are paid. Nobody filed anything." | Map labels `Z7 · 37% · 46 shops`, `Z3 · 38% · 141 shops`, `Z12 · 47% · 125 shops`. Moment card `₹1,380 credited · 17:04` with `Anil's Tea Stall · with the settlement`. Strip `123 instalments paused · ₹4,25,420 to 312 shops`. Tiles `3` zones, `312` shops paid, `4 min` to money. Zone 7 panel: Alert `Red alert from 14:00`, Sales `37% of expected for 3 hours`, Cover `46 of 46 prepaid`, Paid `17:04, with the settlement`, Total `₹58,900 · instalments paused` | Replay stalls: pause, then seek 17:05 and say "same replay, one step". Last resort: Overview "Watch the storm replay" |
| 0:45 to 0:55 | Nothing (Zone 7 and the Zone 9 line are already on screen) | "Zone 9 also dipped, to 61%, but it had no alert. A slow day is not a loss event, so it gets nothing." | `Z9 · 61% of expected`. Line `Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. That's a slow day, not a loss event, so Chhatri doesn't pay.` | Skip the line (first thing to drop) |
| 0:55 to 1:10 | **Merchant phone** | "Anil's phone, in Hindi. 1,380 rupees with today's settlement, and the Soundbox says it out loud. No claim needed." | Chat card `₹1,380`, badge `No claim needed`, Soundbox `“Paytm par ₹1,380 prapt hue — Chhatri se”`. The app header reads `डेमो: 19 अगस्त, 17:05` on one line, with the SIMULATED badge. The lender line `आपके लेंडर ने कल की ₹600 की किस्त रोक दी है।` | No sound: click **Enable sound**; the Soundbox text is on screen |
| 1:10 to 1:25 | In the app: tab **दावे**, tap the claim | "He follows the claim: detected, checked, decided, paid. And tomorrow's 600 rupee instalment: Chhatri asks his lender for a holiday, and the lender decides. Here the lender is simulated, and it says so." | Five steps, all done. `मंज़ूर ₹1,380`. Paid step and holiday step carry `SIMULATED`. Holiday step `किस्त की छुट्टी (EDI)` with the lender line, and `SIMULATED लेंडर` | The phone's "What happened" card at the right shows the same numbers |
| 1:25 to 1:50 | Tap **इतने पैसे क्यों?**. Scroll to the area-index row. Tap one source badge, read it, tap **Close** | "His usual Tuesday is 4,380. His area fell 63%. Chhatri pays half of the lost sales. Every number says where it came from. Tap one: it names the record, its time, and that it is simulated." | `₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380` and `½ × ₹4,380 × 63% = ₹1,380`. Rows ₹4,380, 37%, 63%, आधा, ₹2,500, ₹1,380, each with a source badge. Sheet shows `SIMULATED`. Line `इलाके की गिरावट एक प्रतिशत और होती, तो लगभग ₹22 और जुड़ते।` | Tap the chat chip "मुझे इतने ही पैसे क्यों मिले?": the reply gives the same formula |
| 1:50 to 2:05 | **Live map**, pick **Anil falls ill · Thu 21 Aug**, seek **11:20**, then **Merchant phone**, tap the chip **मैं अस्पताल में हूँ, बुखार है।** | "Thursday. Anil's shop was shut all Wednesday while his area was normal. Nobody filed a claim: Chhatri checks in before he asks. He is in hospital." | Chat: `Your shop has been closed since yesterday. Is everything okay?`, then `Get well soon. Please send one photo of the hospital slip.` | Backup: load illness, seek 11:20, then `post /api/merchants/S-0142/voice-demo '{"key":"ill"}'` |
| 2:05 to 2:30 | App: tab **मदद**, **अस्पताल की पर्ची भेजें**, **गैलरी से चुनें**, choose `anil_admission_slip.png`, tap **हाँ, सही है** | "One photo. The app shows what it read, and asks whether that is right. If it is not sure it asks for another photo instead of guessing." | Fields `Anil R. Jadhav`, `20 अगस्त`, `KEM Hospital, Parel`. Three ticks: photo readable, name on slip, admission date on slip. No percentage anywhere. Footer `SIMULATED` (or `LIVE` with the Gemini mode). After the tap: `₹1,500`, `मंज़ूर ₹1,500` and `₹4,300 का आधा = ₹2,150 प्रतिदिन; सीमा ₹1,500 × 1 दिन = ₹1,500` | Use **डेमो पर्ची इस्तेमाल करें** (the sample button, same slip). Slip reads NEEDS_TEAM: open the Integrations chip, force `gemini_vision` to FALLBACK, send again (section 6) |
| 2:30 to 2:38 | **Play**, wait for the paid step, **Pause** | "Half his usual Wednesday is 2,150, capped at 1,500 a day. 1,500, credited with the settlement." | Paid step done and `SIMULATED` | The clock is paused: Play, or +15 min |
| 2:38 to 2:52 | App: tab **मदद**, **छतरी से पूछें**, type `मुझे इतने पैसे क्यों मिले?`, Send | "He can ask in his own words. The answer cites the policy clause, and the footer says what answered. Here it says rules: the policy engine, not a language model. With a live key, free questions go to the model and the footer says live and names it." | Answer with a rupee figure, clause chip (`C4.1` and friends), source badges, footer `LIVE` and `rules` | Nothing by 8 s: skip. Do not type free questions in the all-simulated mode: the simulator replies with a generic help line, which is honest and weak |
| 2:52 to 3:00 | **Audit**, **Verify chain** | "Every step you just saw is in a hash-chained log. The chain reads valid. The AI builds the case; code decides the money. Sales, alerts, KYC, payouts, the lender, WhatsApp and the Paytm link are simulated and labelled on screen." | `Chain valid · N entries`. Footer disclosure line | Say it over the Policy page. Never skip the disclosure sentence |

**Time checks.** At 0:20 you press Play. At 0:55 you are on Anil's phone. At 1:50 you are loading illness. At 2:52 you are on Audit. More than 10 s late at a check: drop the next item from the order below.

**Drop order if late:** the Zone 9 line, the source-badge tap, the Ask beat, the ₹1,500 credit step (say it instead). Never the slip pre-check, never the disclosure.

**Spare 15 seconds (not in the 3 minutes).** On Live map after 17:00, click `Z9 · 61%`, **What if…**, drag the three hours to 49, tap **Rain**. The panel reads `Would fire: yes, 51% drop`, and "Read-only: nothing is saved". Say: "Give Zone 9 an alert and the same rule fires. Nothing is stored." The spec walks this in its own test, which loads monsoon, so do it before leaving monsoon or reload monsoon and seek 17:05 first.

**Spare 30 seconds, the slide 8 live tests (not in the 3 minutes; walked by the second test of `stage-demo.spec.ts`).** *HUMAN:* load **Illness mismatch**, seek 11:25, on **Merchant phone** tap the check-in reply, **Send a photo**, **Slip with a different name**, **Yes, this is right**. The phone says the team will check it within 24 hours and shows `case C-2291`. Open **Claims**: case C-2291 is `REFERRED` (`Name on the slip doesn't match KYC`); tap **Approve** once and the resolution reads `APPROVED` with the ₹1,500 credit. Say: "A name that does not match is never decided by the AI: a person sees it, and one tap releases the money." *BLOCKED:* load **Buy cover**, seek 18:10, on **Merchant phone** tap `Red alert tomorrow. Cover me today.` The reply says new cover starts after the waiting period, from 25 August, with a SIMULATED Paytm link. Say: "Cover bought after an alert is told the truth, never approved."

### 3.1 For the questions (not in the 3 minutes)

Each answer is one screen. Open it only when a judge asks.

| Question | Open | Say |
|---|---|---|
| "Who approved this money?" | Anil's app: **दावे**, the claim, **रसीद देखें** (see the receipt) | The receipt opens with who authorised the money: the policy engine under rules `pilot-0.1`, "AI authority: none", and **Verify this decision**, which checks the audit log. |
| "What happens to Anil after the payout?" | Anil's app: the paid claim | "What happens next": the credit, the lender's answer (SIMULATED), how to dispute and the reply time, the cover's paid-up date. Every line comes from the receipt and the cover. |
| "How do you know the AI is any good?" | `/evals` (flag `h25_evals`, not in the stage flag set: use `make dev` with every flag, or say it) | One stored run on synthetic questions we wrote: 50 live Ask answers with no forbidden statement, 30 of 31 citing the right clause, 2 of 50 with a rupee figure not traced to a fact; slip reading and voice not measured. Quote the page, with its n. |
| "How did you price it? What if the price is wrong?" | **Backtest**, scroll to **Price the cover** (flag `h24_whatif`, in the stage set) | Every zone priced from the backtest's own triggers. Z7 is ₹18.62 a day at the published rules; press 55% or drag the share and the premium, the loss ratio at today's price and the false payouts move with it. "Planning figures, not an actuarial price; the pilot sets the price." |
| "Is the build real?" | A terminal: `make judge` | One line per check, ending `CHHATRI JUDGE READY ✓`: artefacts against their hashes, 70 demo checks, the audit chain after the payout. |

## 4. The cut-downs

**30 seconds, no clicks** (Live map at 17:05, or slide 1):

> "Anil runs a tea stall in Parel. When heavy rain halves his sales, his 600 rupee instalment is still cut, and earlier merchant plans took 30 to 60 days to pay a claim. In our replay three wards triggered at 17:00 and 312 shops were paid at 17:04 with the evening settlement. Nobody filed anything. The AI builds the case; code decides the money. The sales are simulated and the rainfall is real. WhatsApp and the Paytm link are simulated. Next step: a pilot with an insurer and a lender. Chhatri: the claim starts itself."

**1 minute.** Park at **16:50** (seek 16:50 instead of 16:40; Play to 17:05 takes about 9 s). Rows 0:20 to 0:45 and 0:55 to 1:10 of the script, then the Why screen (row 1:25), then the disclosure sentence. Clicks: Play, Pause, Merchant phone, tab दावे, tap the claim, **इतने पैसे क्यों?**. Say the four numbers (1,380 paid, 312 shops, 4 minutes, 4,380 times 63% over two) and nothing else. Drop the tracker narration to one sentence.

**2 minutes.** The 1-minute cut plus the slip beat (rows 1:50 to 2:30), minus the Ask and the audit. Close on the disclosure sentence.

## 5. Reset between runs

1. Load the scenario again: pick **Monsoon replay** in the console, or `post /api/replay/load '{"scenario":"monsoon"}'`. The clock returns to 08:00, paused, and case ids restart at C-2291. Everything held in memory (claims, slip pre-checks, the audit log) restarts with it.
2. Seek **16:40** and stay paused on **Live map**.
3. Open the header chip. If a component shows `forced`, press **Clear all**.
4. In the phone, tap the **होम** tab so no screen from the last run stays open. Close any sheet.
5. If the backend was restarted, reload the console page once.
6. Never save a file under `backend/` while the stack is up. If the stack does die: `make demo-stage` again, reload the page, do steps 1 and 2.

## 6. Fallbacks that keep the story going

| Symptom | Do |
|---|---|
| The slip reads NEEDS_TEAM (`READ_FAILED`) with a key set | The live reader was rejected or is slow. Open the header chip, force `gemini_vision` to FALLBACK, send the slip again; the simulator reads the data embedded in the sample slip and the footer says FALLBACK with a `forced` chip. Say so in one sentence |
| An AI reply has no label | Do not use it. Skip the beat |
| A number differs from this page | Reload the scenario, seek 16:40. Still different: stop the live demo and run the recorded run ([runbook](demo-runbook.md#6-contingency-ladder)) |
| The console shows `Mock data` | The backend is not reachable. `curl -s localhost:8000/api/health`, restart `make demo-stage`, reload |

The honest labels stay as they are: sales, alerts, KYC, payouts, the lender, the Soundbox, WhatsApp and the Paytm link are SIMULATED; the slip reader and Ask are LIVE only when the screen says LIVE. Never say a component is live if its label says SIMULATED or FALLBACK.

## 7. Rehearsal and proof

- The automatic walk: `make stage-e2e` starts a fresh backend on :8301 and console on :5301 with this flag set and no AI keys, walks every row above with Playwright (`--workers=1`) and stops both. `STAGE_RUNS=3 make stage-e2e` repeats it; the pass rule is 3 green runs in a row.
- What the walk does not prove: the speaker's timing, the sound, the room, and any live AI call. Rehearse those by hand on the demo laptop with `make demo-stage`.
- Rehearsal log: use the log in [section 8 of the runbook](demo-runbook.md#8-rehearsals), and add "stage script 3 minutes: __:__".

## Changelog

- 2026-10-03 · v1.1 · §3.1 for the questions: the receipt's authority block, What happens next, /evals, the pricing simulator, `make judge`
- 2026-10-03 · v1 · first version: story, flag set, start command, script, cut-downs, reset, fallbacks
