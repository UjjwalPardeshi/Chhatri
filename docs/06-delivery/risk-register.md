# Risk register

| | |
|---|---|
| Status | v3 · 2 Oct 2026 · re-baselined for the six-wave plan, with every item P0 |
| Owner | Omkar Kadam and Ujjwal Pardeshi |
| Audience | The team, mentors, judges, post-hackathon stakeholders |
| Related | [Build plan](build-plan.md) · [Demo runbook](demo-runbook.md) · [On-site checklist](on-site-checklist.md) · [Current-state audit](../01-strategy/current-state-audit.md) · [Rival teardown appendix](../01-strategy/rival-teardown-appendix.md) · [AI evaluation plan](../04-engineering/ai-evaluation-plan.md) · [Pitch and judge Q&A](pitch-and-judge-qa.md) |

## TL;DR

- **24 risks in five themes:** plan and build (5), AI and data (5), demo delivery (9), credibility and disclosure (4), team (1).
- **The biggest is scope.** Every item is P0, so some work will not be finished (R10). The answer is the plan, not hope: six waves, checkpoints with pass criteria, flags that start off, and a hide order. Unfinished work is hidden and never shown half-working.
- **The next group is the AI chain and the golden path:** a golden test that breaks (R11), an Ask answer with an unsupported figure (R13), Gemini free-tier limits (R2), Sarvam credits (R3), a slip misread (R14), and real data reaching a free tier (R24). Each has a fallback that is the golden path.
- **New in v3:** all-P0 scope (R10, rewritten), the Tailwind and shadcn setup on Vite 8 (R18), Gemini limits (R2, rewritten), Sarvam credits (R3, rewritten), unreviewed Marathi and Hindi (R19), a strong rival with the same problem (R20), flag lists that differ (R21), a backend restart that resets the state (R22), a missing static copy or video (R23) and free-tier data (R24).
- **Scores are judgements,** Low, Medium or High, not measurements. They change at each checkpoint, so update them in the checkpoint log.
- **Triggers are things we can see:** a command result, a label on screen, a failed checkpoint. There are no clock times. The freeze is 90 minutes before our slot, and the slot time is not announced.

## 1. Risks by theme

### 1.1 Plan and build

| ID | Risk | Likelihood | Impact | Owner | Mitigation | Trigger | Contingency |
|---|---|---|---|---|---|---|---|
| R10 | **All-P0 scope.** N1–N8, X1–X8 and H1–H26 are all must-ship, and some work will not be finished | High | Medium | Both | Six waves and two tracks. A checkpoint with pass criteria closes each wave. Flags start off, and the hide order and the veto rule keep half-done work off the screen ([build plan](build-plan.md#7-hide-order-if-time-runs-out)). Wave 5 starts no later than the freeze minus its estimate | A checkpoint fails or runs late. The Wave 5 start time arrives with a wave still open. CP1 has not passed when sleep is due | Hide by the order (Marathi at the top, the mini-app at the bottom). No new feature after CP4. Return to the last tagged checkpoint |
| R11 | **A change breaks a golden test** or `make demo-check` | Medium | High | Ujjwal | The suites run at every checkpoint, and the other person runs them. Flags keep half-done code out of the golden runs. Each passed checkpoint gets a local tag | `make demo-check` shows fewer than 70 passed. `make test-slow` fails. The console does not load | Revert the last commit or return to the tag. If it is not fixed quickly, run the last good tag and hide what is missing |
| R12 | **A copy change breaks the docs tests.** The X4 wording replaces strings that several files pin | Medium | Medium | Omkar | Change a pinned string in one coordinated commit across `messages.py`, `golden.py`, the mock, DEMO.md and `scripts/tests/test_docs.py` ([fs-03](../02-product/feature-specs/fs-03-edi-holiday.md) section 8.4). Run `make test-backend` after every copy edit | `scripts/tests/test_docs.py` or `backend/tests/conversation/test_messages.py` fails. DEMO.md and the console show different text | Revert the copy change, update every pinned place, commit again |
| R18 | **Tailwind and shadcn on Vite 8** leak into the console or break the build | Low | High | Omkar | Tailwind v4 through `@tailwindcss/vite`. The 2 Oct registry check shows it lists Vite 8 as a peer, and `@tailwindcss/postcss` is the fallback. No Preflight, class detection limited to the mini-app folder, theme variables under `.miniapp`. The isolation criteria AC-05 and AC-06 are checked at CP0 | Console tests change after the setup. The built CSS holds a rule outside `.miniapp`. The console looks different with every flag off. The plugin fails on Vite 8 | Switch to `@tailwindcss/postcss`. Fix the scoping before Wave 1 goes on. Hide `n1_miniapp` |
| R21 | **The flag lists differ,** or a flag changes during the talk | Medium | Medium | Ujjwal | One list, written on the demo card, in `CHHATRI_FEATURES` and `VITE_FEATURES`. Read the backend's start-up line against the card. Build the static copy with the same list. Never change a flag during the talk | A button whose call answers 404. A screen the card lists is missing. The start-up line differs from the card | Restart with the right list before the slot. On stage, use the fallback of the beat ([runbook](demo-runbook.md#4-the-new-beats-flags-pass-rule-and-fallbacks)) |

### 1.2 AI and data

| ID | Risk | Likelihood | Impact | Owner | Mitigation | Trigger | Contingency |
|---|---|---|---|---|---|---|---|
| R2 | **Gemini free-tier limits.** A rate limit or the quota is reached, a model name changes, or the service is down | Medium | Medium | Ujjwal | Read the limits in Google AI Studio on the day. They change, so no figure is written in the docs. Write the quota in the checkpoint log at CP0 and CP2. The chain is Gemini, then Sarvam, then a template (Ask) or a person (slip). Rehearse the forced-fallback path. Spend calls on rehearsed beats | An HTTP 429 or a "resource exhausted" error on a call. An Ask answer later than its 5 s target. `make check-keys` lists no model that accepts images. The quota page shows heavy use at a checkpoint | The next link answers and the label says FALLBACK. Force `gemini_chat` and `gemini_vision` (proposed names) in the provider panel. If both links fail, hide `n2_ask_chhatri` or `n3_slip_precheck` by the hide order |
| R3 | **Sarvam free credits run out** | Low | Medium | Ujjwal | Note the credit balance before and after each rehearsal. Run `live_smoke.py` before the slot. Spend on the beats that need it | `live_smoke.py` fails. The dashboard balance is low. A badge turns FALLBACK or SIMULATED | The chain falls to browser speech and to the simulated reader, and the labels say so. The BUILT voice chips and sample slips still work. If the key is out, remove it and restart so every badge reads SIMULATED |
| R13 | **Ask Chhatri states an unsupported figure or a promise** | Medium | High | Ujjwal | Guard layer B blocks figures that are not engine facts and blocks promise words. Injection and scam defences. The evaluation harness (H25) and its red-team set run when Wave 2 closes. Every reply carries its label | The guard test fails. A reply shows a figure the decision did not give. A reply has no label | The template answer replaces the model (force the chat component to FALLBACK). Hide `n2_ask_chhatri` |
| R14 | **The slip reader misses or misreads a field** | Medium | Medium | Ujjwal | The merchant confirms what was read before any check runs. A confidence gate of 0.80 sends a doubtful read to a retake or a person. The chain is Gemini, then Sarvam Vision, then a person decides. Test the three sample slips and the red-team fixtures | A name or date read wrong on the sheet. READY shown on a slip that should be RETAKE | The engine decides: a SOFT fail gives REFERRED and a HARD fail gives DECLINED, so a doubt never pays on its own. Force the simulated reader for the demo. Hide `n3_slip_precheck` |
| R24 | **Real personal data reaches a free-tier AI service** | Low | High | Omkar | Synthetic data, and nothing else, goes to Gemini or Sarvam ([ADR 0009](../04-engineering/adr/0009-synthetic-data-only-to-free-tier-ai.md)). The notice on the initial recording says so. Nobody photographs a real document or speaks personal details in the demo or in Q&A | A judge or visitor tries a real document or speaks personal details | Stop the call, say the data rule and go back to the sample slip. Do not hand the microphone or camera to a visitor |

### 1.3 Demo delivery

| ID | Risk | Likelihood | Impact | Owner | Mitigation | Trigger | Contingency |
|---|---|---|---|---|---|---|---|
| R1 | **Venue network fails or is congested** | Medium | Medium | Ujjwal | Test on arrival on 3 Oct. Carry a phone hotspot. The console, the backend and the replay run on the laptop. The AI calls, the map tiles and browser speech recognition are what need the network | No connection at the T−60 check ([on-site checklist](on-site-checklist.md)). Gemini or Sarvam calls time out. Map tiles missing | Carry on offline. The AI parts show FALLBACK or SIMULATED, questions are typed or tapped, and the BUILT voice chips work. The map shows ward outlines. Then the static copy, then the video |
| R4 | **The replay clock holds at 17:00** for 30–60 s (n8n LIVE) | Low | Medium | Ujjwal | Run with `make dev` (in-process runner), so the n8n badge honestly reads SIMULATED | The clock stays at 17:00 for more than 10 s while the feed fills with 312 rows | Keep talking, because the clock resumes and credits land at 17:04. Or pause at 16:59 and step once |
| R5 | **An off-script request** names an id that does not exist | Low | Medium | Ujjwal | An unknown id on an existing route already returns a clean 404 `not_found`. X5 gives every new route the same answer and adds the tests. Practise the pivot "Let me go back to Anil" | A judge types an id, or opens a bad address, on a new route | The 404 envelope shows. Pivot back to Anil in one sentence |
| R6 | **The microphone is unavailable or recognition fails** | Medium | Medium | Ujjwal | The chain is Sarvam, then browser recognition (Chrome, needs the network, test hi-IN), then the text box and chips. Allow the microphone for the console address at the pre-flight. Rehearse the sentence in the room | An empty or wrong transcript. A permission prompt on stage. Browser recognition errors | Type the question, or tap the BUILT voice chips. They fall back to the canned transcript when speech-to-text fails |
| R7 | **Speaker or audio playback fails** | Low | Medium | Omkar | Click **Enable sound**. Test the speaker and the room audio at the pre-flight | No Soundbox or voice output at the pre-flight | Read the text aloud. The Soundbox line is on screen in Hindi and English |
| R8 | **The projector or viewport breaks the layout** | Low | Low | Omkar | 1280×720 at 100% zoom, the console minimum in the [design system](../03-design/design-system.md). The overflow check at CP4. Look at the venue display on arrival | Elements cut off or sideways scroll on the venue display | Change zoom, or use presenter mode. Else the backup video |
| R9 | **A cut runs over time** | Medium | Medium | Omkar | Rehearse both cuts. Use the time checks and the drop order in the [runbook](demo-runbook.md#3-the-7-minute-cut). Aim to land 10 to 15 seconds early | The presenter is more than 10 seconds behind a time check | Drop the inserts in the runbook's order. Never drop the disclosure or the honest limits |
| R22 | **A backend restart resets the state.** `make dev` reloads on a saved file, and the replay and the in-memory records are lost | Low | High | Ujjwal | Nobody saves a backend file once the stack is up. Keep a second terminal. Know the reset steps ([runbook](demo-runbook.md#7-reset-between-runs)) | The clock jumps to 08:00. Cases, consents, grievances or the audit log are gone | Reload the scenario, seek, and resume at the nearest beat. Say "let me restart this part" |
| R23 | **No static copy or backup video** can be shown | Medium | Medium | Ujjwal | Build the static copy with the demo flags in Wave 5. Record the video from the release candidate. Keep both on the laptop and the video on a phone. No doc claims a public address until the repo owner has deployed one | No static build at CP5. The video does not play with the network off | Use whichever exists. If neither does, run from the laptop and say what is simulated |

### 1.4 Credibility and disclosure

| ID | Risk | Likelihood | Impact | Owner | Mitigation | Trigger | Contingency |
|---|---|---|---|---|---|---|---|
| R15 | **"Isn't your backtest circular?"** | Medium | High | Omkar | Say it before anyone asks, on the honest-limits slide. Use the answer in [pitch and judge Q&A](pitch-and-judge-qa.md). Never say the backtest proves anything about real merchants | A judge asks about circular calibration, basis risk or whether the numbers are real | Omkar answers calmly and in plain words: it validates the rules, not the market, and the pilot is how that is tested |
| R16 | **Judges question the pre-built work** | Medium | Medium | Omkar | State plainly: the prototype was built 29 Sep to 1 Oct, the organisers confirmed pre-built work is allowed, and everything added on 2 and 3 Oct is in the git log with its date. Each of us commits under our own name ([build plan](build-plan.md#9-commit-hygiene)) | A judge says it was all pre-built, or asks who built what | Answer from the Q&A and show the git log |
| R19 | **Marathi, or a new Hindi line, ships without a native reader** | Medium | Medium | Omkar | `n8_marathi` stays off until a named reader signs off, and it heads the hide order. Each new key gets a Hindi review in its wave ([copy deck](../03-design/copy-deck.md)) | No recorded sign-off by CP4. A reader finds an error | Hide `n8_marathi` and say Marathi is planned. Show Hindi. Fix a wrong Hindi line, or show the English line |
| R20 | **A strong rival with the same problem is compared with us.** Praman is the closest overlap in the understand, submit and resolve stages ([rival teardown appendix](../01-strategy/rival-teardown-appendix.md)) | Medium | Medium | Omkar | Know the appendix. Credit projects by name, never individuals. Show the whole path on screen: the check-in, one photo, the decision, the payout and the lender request, each with its source. Do not criticise a team | A judge names a rival or compares demos | Answer from the Q&A: we share the rule that money decisions stay in code, and our path starts from the merchant's own sales. Offer to show it |

### 1.5 Team

| ID | Risk | Likelihood | Impact | Owner | Mitigation | Trigger | Contingency |
|---|---|---|---|---|---|---|---|
| R17 | **Illness or a personal crisis** on the day | Low | Medium | Both | Sleep ([build plan](build-plan.md#83-sleep)). Both of us can run both cuts. The static copy and the video exist | Someone is absent at the pre-flight | The other runs both cuts. If both are out, play the video and stay in touch with the organisers |

## 2. Heat map

Each cell lists the risk ids. Likelihood runs across, impact runs down.

| Impact \ Likelihood | Low | Medium | High |
|---|---|---|---|
| **High** | R18, R22, R24 | R11, R13, R15 | none |
| **Medium** | R3, R4, R5, R7, R17 | R1, R2, R6, R9, R12, R14, R16, R19, R20, R21, R23 | R10 |
| **Low** | R8 | none | none |

## 3. Top five and next actions

| Rank | Risk | Owner | Likelihood | Impact | Next action (checkpoint) |
|---|---|---|---|---|---|
| 1 | **R10: all-P0 scope** | Both | High | Medium | Run CP0 and review the Wave 0 files that are in the working tree. Keep the checkpoint log. Work out the Wave 5 start time when the slot is known (CP0, then each checkpoint) |
| 2 | **R11: a golden test breaks** | Ujjwal | Medium | High | Tag each passed checkpoint. Run `make demo-check` before every commit that touches pinned text (every checkpoint) |
| 3 | **R13: Ask states an unsupported figure** | Ujjwal | Medium | High | Build the guard test and the red-team set in Wave 2. Run the evaluation harness when Wave 2 closes (CP2, CP3) |
| 4 | **R2: Gemini free-tier limits** | Ujjwal | Medium | Medium | Read the quota in Google AI Studio and write it in the log. Rehearse the forced-fallback path (CP0, CP2) |
| 5 | **R15: the circular-calibration question** | Omkar | Medium | High | Put the limit on the slide. Rehearse the Q&A answer twice (REHEARSE-2) |

## 4. De-risking plan by checkpoint

| When | Risks to close or check | Action |
|---|---|---|
| CP0 (Wave 0) | R18, R21, R2, R3, R10 | Check the isolation criteria AC-05 and AC-06. Confirm that the two flag lists are identical. Run `make check-keys` and `live_smoke.py`. Write the quota and credit balance in the log. Review and commit the Wave 0 files |
| CP1 (Wave 1) | R11, R12, R5 | Make the X4 wording change in one commit. Check 404 on every new route. Run all suites with the demo flag set and with every flag off |
| CP2 (Wave 2) | R13, R14, R6, R2, R3, R24 | Run the Ask and slip drills, the forced-fallback drill and the voice drill with the real keys. Check that the free-tier data gate blocks real data. Write the latencies seen |
| CP3 (Wave 3) | R10, R19 | Run the harness. Decide the flags for grievances and consent. Ask for the native reader |
| CP4 (Wave 4) | R8, R19, R9 | Run the overflow check at 1280×720. Get the recorded sign-off for Marathi or keep it off. Run a full 7-minute rehearsal |
| CP5 (Wave 5) | R23, R16, R15, R22 | Build the static copy and record the video. Rehearse the Q&A answers. Write the demo card. Freeze, and tag |
| On arrival, 3 Oct | R1, R8, R7 | Test the network and the hotspot. Look at the venue display. Test the sound ([on-site checklist](on-site-checklist.md)) |
| T−60 and T−30 | R21, R22, R6, R2, R3 | Start the stack and read the flag line against the card. Run `demo_check.py --url`. Test the microphone, one Ask, one slip read |

## Open questions

1. Will the venue network be usable, or is the phone hotspot the main path? Owner: Omkar Kadam (ask the organisers on arrival).
2. What are the Gemini free-tier limits on the day, and does the model we pick accept images? Owner: Ujjwal Pardeshi (read Google AI Studio and write the answer in the checkpoint log).
3. Is a second laptop available as the backup machine? Owner: Ujjwal Pardeshi.
4. Who is the native reader for Hindi in each wave and for Marathi in Wave 4? Owner: Omkar Kadam.
5. If a rival shows a public demo link and we have none, how do we answer? The static copy needs the repo owner to deploy it. Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v3 · rewritten for the six-wave plan with every item P0: 24 risks in five themes with owners, observable triggers and no clock times. New or rewritten: all-P0 scope (R10), Tailwind and shadcn on Vite 8 (R18), Gemini free-tier limits (R2), Sarvam credits (R3), unreviewed Marathi and Hindi (R19), a strong same-problem rival (R20), flag lists that differ (R21), a backend restart that resets the state (R22), a missing static copy or video (R23), free-tier data (R24). Corrected the old text: unknown ids already return a 404 (not a KeyError), the Tesseract fallback is not in the chain, the "29 of 76 commits" claim was wrong and is gone, the invented 80% quota alert and the venue visit on 2 Oct are gone, the Ask route is a POST, and the header count matches the list
- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; all risk descriptions are accurate.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.1 · fact-check pass: fixed R14 description to use correct claim decision outcome names (REFERRED/DECLINED, not BLOCKED which is for cover purchase).
- 2026-10-02 · v1 · initial draft. 16 risks across demo delivery, build, AI, credibility and team themes. Heat-map and top five identified.
