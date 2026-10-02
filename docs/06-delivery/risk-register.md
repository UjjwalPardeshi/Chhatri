# Risk register

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam and Ujjwal Pardeshi |
| Audience | The team, mentors, judges, post-hackathon stakeholders |
| Related | [Build plan](build-plan.md) · [Demo runbook](demo-runbook.md) · [Current-state audit](../01-strategy/current-state-audit.md) |

## TL;DR

- 16 risks tracked across five themes: demo delivery (7), on-site build (3), AI and data quality (3), credibility and disclosure (2), team capacity (1).
- Three high-impact risks: venue Wi-Fi failure (demo cannot run), Gemini or Sarvam quota exceeded (demo stalls), and a circular-calibration question at final Q&A that needs a clear, honest answer.
- Contingencies: force-fallback UI switch to show degraded paths gracefully; static mock demo (N7) with a backup video; rehearsal twice on 3 Oct and a 30-minute pre-demo technical check.
- Likelihood and impact scores: 1 high-impact/medium-likelihood (Wi-Fi), 2 high-impact/low-likelihood (API quota, build time), 3 medium-impact/medium-likelihood (clock hold, off-script KeyError, calibration question).
- Top five risks with owners and next actions (below).

## 1. Risks by category

| ID | Category | Risk | Likelihood | Impact | Owner | Mitigation | Early signal or trigger | Contingency |
|---|---|---|---|---|---|---|---|---|
| R1 | Demo infrastructure | Venue Wi-Fi fails or is congested | Medium | High | Ujjwal | Pre-check Wi-Fi signal on 2 Oct (18:00) at the Paytm office. Verify `curl -s localhost:8000/api/preflight` works over Wi-Fi. Carry a mobile hotspot as backup. | No connectivity during the 30 min pre-demo check (17:30 on 3 Oct). Test at least 5 Mbps down and 2 Mbps up. | Switch to the static mock-mode demo URL (N7) and play the backup video. Judges see the full user journey labelled SIMULATED. Total prep time approximately 2 min to switch links. |
| R2 | Demo infrastructure | Google Gemini API quota exhausted or service down | Low | High | Ujjwal | Monitor quota daily on 2–3 Oct using Google AI Studio dashboard. Set an alert at 80% of daily quota. On 2 Oct, if the quota shows heavy use, test Sarvam fallback end-to-end. | "Error: resource exhausted" or "429 Too Many Requests" for `GET /api/merchants/{id}/ask`. Response time spikes above 5 s. Ask Chhatri returns "No provider available". | N2 (Ask Chhatri) falls back to Sarvam chat on the first error. If both fail, show deterministic template answers (offline). The demo still works; the merchant sees a helpful response. "Ask Chhatri is using a template while we reset the connection." |
| R3 | Demo infrastructure | Sarvam free starter credits run out | Low | High | Ujjwal | Measure Sarvam spend each evening (2 Oct and morning 3 Oct). Track voice (Saaras, Bulbul) and vision (doc-ai) separately. Spend only on hero moments: the hospital-cash voice check-in (N4) and the slip reading (N3). Don't spend on every query. Test offline Tesseract fallback for vision on 2 Oct. | The slip-reading API returns an error or empty extraction. Voice check-in plays browser speechSynthesis (English-only). The provider panel shows FALLBACK. | Force-fallback switch in the provider panel shows the Tesseract path. The slip text is shown as "extracted by Tesseract" with a note that confidence is lower. Slip decision can still be REFERRED (the normal path for borderline cases). |
| R4 | Demo delivery | Replay clock holds at 17:00 for 30–60 s (n8n LIVE) | Medium | Medium | Ujjwal | Run the demo with `make dev` (in-process runner) so the badge honestly reads SIMULATED. The in-process runner gives the same timeline without a clock hold. If you choose `make up` with n8n, rehearse the clock hold on 2 Oct evening and talk over it smoothly. | The clock does not advance past 17:00 for more than 10 s. The feed is filling with decisions (312 payout rows). | Pause at 16:59, step once with the backup `curl` command (about 2 min per 10 min simulated), or have a talking point ready ("This is the backend processing 312 payments in sequence; it's about 30 seconds of real time"). The clock does resume and payouts land at 17:04. |
| R5 | Demo delivery | Off-script merchant request raises a KeyError or 404 | Medium | Medium | Ujjwal | X5 guard: test that any unknown merchant id returns a clean HTTP 404 with a helpful JSON error, not a Python traceback. Add a test case `test_unknown_merchant_404`. Rehearse a recovery script: "Let me go back to Anil (the merchant in the demo)." | A judge or a question triggers a merchant lookup with an id not in the demo scenario. | The API returns `{"error":"Merchant not found"}` with HTTP 404. The console shows "Merchant not found" in a message. Omkar pivots back to Anil's case without delay (< 5 s). The judge sees that edge cases are handled. |
| R6 | Demo delivery | Browser microphone unavailable or recognition fails (voice input) | Low | Medium | Ujjwal | Test the Sarvam Saaras STT on the demo laptop's microphone on 2 Oct. If it does not work, enable the browser's Web Speech API as fallback. If both fail, use tap-to-send chips and read the text manually for the judge. Prepare a script: "The voice input is coming from a canned demo transcript for reliability; here is what the merchant said." | STT returns an empty or nonsensical transcription (not "मुझे इतने ही पैसे क्यों मिले?"). | Show the tap-to-send chips and tap manually. The voice fallback is already labelled as SIMULATED (the demo uses canned transcripts for the monsoon scenario). |
| R7 | Demo delivery | Speaker or audio playback fails (Soundbox and voice) | Low | Medium | Omkar | Test the speaker on the demo laptop and the venue audio system on 2 Oct (18:00). Check browser autoplay permissions and the "Enable sound" button in the header. | No sound from the speaker during the 30 min pre-demo check. The Soundbox line or voice note does not play. | Mute the speaker and read the text aloud instead. The console shows the Soundbox text and voice transcriptions on screen, so judges see what would have played. Point to the screen: "The merchant would hear this on their Soundbox." |
| R8 | Demo delivery | Browser screen resolution or viewport size causes layout issues | Low | Low | Omkar | Set the demo-laptop browser to 1280×720 at 100% zoom (fixed in `docs/DEMO.md` §T−30 min). Test on the demo laptop on 2 Oct. Verify that the mini-app (N1) and the console fit. | The mini-app or console elements are cut off, buttons are not clickable, or text wraps unexpectedly at the venue. | The backup is a pre-recorded 7-minute video (N7 fallback video) showing the full journey at the correct resolution. Switch to the video, which plays fullscreen. Judges see the same steps as the live demo but in a recorded format. |
| R9 | Demo delivery | Time overrun: the demo takes longer than 7 minutes | Low | Medium | Omkar | Rehearse the 3-minute cut and the 7-minute cut at full speed on 2 Oct. Use a timer and mark the cutoff times. Omkar presents; Ujjwal watches the clock. If a question slows the story, jump to the next demo step without waiting for the question to finish. | The presenter is at the 6-minute mark but still showing the first scenario (monsoon). The 7-minute cut is incomplete. | Skip the illness scenario (personal claim) or move it to Q&A. Show the one-slide explanation on the policy slide instead of running it live. The monsoon + explanation + audit is the tightest path (about 5 min), leaving 2 min for a question or closing. |
| R10 | Build on 2 and 3 Oct | Ujjwal's on-site time is insufficient for X1–X6 + N2 + N3 backend | Medium | High | Ujjwal | Start the list on 2 Oct evening and prioritize: X4 (EDI guard) and X5 (404 error) are P0. X1 (frontend tests) is P1. N2 and N3 backend are in the demo, so they go P0 too. Build in 2-hour sprints with 10-minute checkpoints. Identify blockers early: if the LightGBM slip extractor fails, mark it SIMULATED and move on. | By 09:00 on 3 Oct, X1 is not done and X4 is not committed. The backend does not start, or `make demo-check` fails more than 3 items. | Drop X1 (frontend test fixes) and focus on X4, X5, X6 (fixes that are in the demo), N2 (Ask Chhatri backend), and N3 (slip pre-check). Mark the new items honestly: N2 is LIVE Gemini/Sarvam, N3 is LIVE Sarvam vision or FALLBACK Tesseract. If slip reading is not ready, use the sample slip (canned extraction) for the demo and say so. |
| R11 | Build on 2 and 3 Oct | Integration breaks an existing golden test | Low | Medium | Ujjwal | Every commit runs `make test` and `make demo-check` before merge. Before 3 Oct 12:00 (3 hours before final), freeze the code and run `make test-slow` in full. If a test fails, it is a blocker. Fix it before the freeze. Use feature flags to hide half-done code from the golden tests. | `make demo-check` returns fewer than 70 passed. A test in `test_slow` fails. The console does not load. | Revert the last commit and bring the tests back to 70 passed. If you cannot fix it in 30 min, move on. Run the demo on the last-known good commit and explain any missing features as "built for the on-site day but not quite ready". |
| R12 | Build on 2 and 3 Oct | A copy change breaks the docs tests | Low | Medium | Omkar | Do not edit copy (merchant-facing messages) without updating `backend/tests/conversation/test_messages.py` in the same commit. Check docs/DEMO.md: if any of the 3-minute or 7-minute strings change, update `docs/DEMO.md` and the test file together. Run `make test-backend` after every copy edit. | A test in `test_messages.py` fails because a message changed but the test did not. The docs and the code show different copy. | Revert the copy change, update the test file, and recommit. Both the DEMO.md and the code must match. If you are in a hurry, mark the copy as PENDING in the docs: "The merchant-facing message is being finalised; it will say something like: …" |
| R13 | AI and data quality | Ask Chhatri hallucinates a money figure or makes an unsupported claim | Medium | High | Ujjwal | The `ask_chhatri` guard in the backend (code) rejects any answer that contains a money figure not in the decision facts, or any word like "covered" or "covered always" that is not grounded in the policy. Run the eval set on Gemini and Sarvam on 2 Oct and check for violations. The test suite includes `test_ask_grounding` and `test_unsupported_figures`. | The answer shows "₹2,000" when the decision was for ₹1,500. The answer says "You'll always get this in the future." The guard did not catch it, or the guard is disabled. | The fallback is a deterministic template from the policy clause library, with no figures except those in the decision. "I can see your decision was for ₹1,500. You can ask a member of our team if you'd like a different outcome." The LLM is turned off and the template is sent instead. |
| R14 | AI and data quality | Slip reader misses a field or reads it incorrectly, leading to wrong REFERRED or DECLINED decision | Medium | Medium | Ujjwal | N3 shows the extracted fields to the merchant on screen before any checks run. The merchant can retake the photo if the extraction is wrong. The policy engine runs after the merchant confirms. Test the vision model (Gemini and Sarvam) on 10 sample slips (real and synthetic) on 2 Oct. Run the extraction at the required 80% confidence threshold. | The slip shows the patient name as "Animol J. Jadhav" (missing the middle initial "R."). The extracted dates are off by a day. The merchant does not see this and taps "looks good". | The pre-check is mandatory. If the merchant retakes, a second extraction happens. If the extraction is consistently wrong, the decision is REFERRED to a human for review (a SOFT check fails) or DECLINED (a HARD check fails), preventing automatic payment. The honest label is "N3 Sarvam Vision: LIVE or FALLBACK Tesseract" and the backup is Tesseract OCR (offline). |
| R15 | Credibility and disclosure | At Q&A, a judge asks "Isn't your backtest circular?" | Low | High | Omkar | Prepare a 2-sentence answer: "Yes, the backtest is designed circularly: we searched for simulation parameters that reproduce the demo numbers (Z7 37%, ₹58,900), so it validates the rules for the replay, not for real merchants. Our pilot plan uses real data to test on live merchants." Have it memorised and delivered calmly. Omkar answers, not Ujjwal. Link the answer to the build plan (N7 static demo and backup video) and the pilot-plan promise. | A judge asks about circular calibration, basis risk, or whether the numbers are real. | Deliver the honest answer without hedging. "We built the backtest to validate the policy rules on a replay scenario, and we know the calibration is baked in. The pilot will use real merchants and real rainfall." Never say "The backtest will work in production." |
| R16 | Credibility and disclosure | Judges or press question whether the pre-built work is fair | Low | Medium | Omkar | State plainly in the pitch and the Q&A: "We built the prototype from 29 Sep to 1 Oct (before the on-site day), and the hackathon organisers confirmed pre-built work is allowed. On 3 Oct, we built the mini-app (N1), the Ask Chhatri backend (N2), and the slip pre-check (N3) on-site, and we fixed X4, X5 and X6." Show the GitHub commit dates and the diff. | A judge says "This was all pre-built." or "You didn't build anything on-site." | Omkar answers: "29 of the 76 commits were from 2–3 Oct on-site. Here's what we built on-site: [point to N1 screens, N2 backend, N3 slip flow]." Link to the commit list on the repo (visible in the live GitHub page). Be concrete: show a file diff that was committed on 3 Oct. |
| R17 | Team and fatigue | Ujjwal or Omkar falls ill on 3 Oct, or a personal crisis prevents them from presenting | Low | Medium | Both | Stay well on 2 Oct: sleep, hydrate, light meals. No caffeine after 16:00. Omkar is the primary presenter and is fully rehearsed. Ujjwal is the demo operator and is fully rehearsed. If Omkar is unavailable, Ujjwal can present the demo + a short slide narration (30 seconds per slide). If Ujjwal is unavailable, the static mock demo (N7) runs with Omkar narrating and Ujjwal remote (phone or Slack screen-share if Wi-Fi allows). | Omkar or Ujjwal is absent or unable to perform at 15:00 on 3 Oct. | Plan B: Run the static demo (N7) + backup video. Omkar presents the slides (max 7 min). Judges see the demo and ask questions on Q&A. It is not ideal, but judges see the full journey. If both are unable, play the backup video and stay in communication with the organisers. |

## 2. Heat-map summary

```
           Low        Medium     High
High       —          R2, R10    R1, R13
Medium     —          R3, R4, R5, R6, R9, R14, R16  —
Low        R8, R17    R7, R11, R12, R15  —
```

**High-impact/medium-likelihood (monitor daily):**
- **R1 (Wi-Fi):** Test at venue on 2 Oct. Carry a mobile hotspot. Fallback: static demo URL.
- **R10 (on-site build time):** Prioritise X4, X5, X6 and N2, N3. Start on 2 Oct. Checkpoint at 09:00 on 3 Oct.

**High-impact/low-likelihood (have fallbacks ready):**
- **R2 (Gemini quota):** Monitor daily. Sarvam and template fallbacks are live. Pre-demo check confirms they work.
- **R13 (Ask Chhatri hallucination):** The guard is in the code. Run the eval set on 2 Oct. If a hallucination slips through, the fallback is a deterministic template and the LLM is turned off.

**Medium-impact/medium-likelihood (rehearse to avoid):**
- **R4 (clock hold):** Use `make dev` (in-process). Rehearse talking over the 30 s hold on 2 Oct if you use n8n.
- **R5 (off-script KeyError):** Add X5 guard test. Rehearse recovery ("Let me go back to Anil").
- **R6 (microphone):** Test on demo laptop on 2 Oct. Fallback: tap-to-send chips.
- **R9 (time overrun):** Rehearse at full speed on 2 Oct. Identify what to cut if you run late (illness scenario).
- **R14 (slip extraction wrong):** N3 shows fields to the merchant before checks. Retake is built in.

## 3. Top five risks and next actions

| Rank | Risk | Owner | Likelihood | Impact | Status | Next action (due date) |
|---|---|---|---|---|---|---|
| 1 | **R1: Venue Wi-Fi fails** | Ujjwal | Medium | High | Active | Pre-check Wi-Fi signal at Paytm office on 2 Oct 18:00. Test `curl` to preflight. Carry a mobile hotspot. (2 Oct 18:00) |
| 2 | **R10: Build time is insufficient** | Ujjwal | Medium | High | Active | Start on 2 Oct evening. Prioritise X4, X5, X6, N2, N3. Checkpoint at 09:00 on 3 Oct (daily until 3 Oct 09:00). |
| 3 | **R2: Gemini quota exhausted** | Ujjwal | Low | High | Monitoring | Check Google AI Studio quota daily. Set alert at 80%. Test Sarvam fallback end-to-end on 2 Oct. (Daily 2–3 Oct) |
| 4 | **R13: Ask Chhatri hallucinates** | Ujjwal | Medium | High | Testing | Run eval set on 2 Oct. Verify the guard rejects unsupported figures and unpromised claims. Run `test_ask_grounding` in full. (2 Oct evening) |
| 5 | **R15: Circular-calibration question at Q&A** | Omkar | Low | High | Rehearsed | Memorise the 2-sentence honest answer. Practise delivery. Include in pitch and Q&A prep. (2 Oct 18:00) |

## 4. De-risking plan by date

**2 Oct (all day):**
- Ujjwal: Check Gemini quota, test Sarvam fallbacks, test Wi-Fi and hotspot, test microphone and speaker on demo laptop.
- Omkar: Write this file, build-plan, and pitch/Q&A docs, rehearse the 3 min and 7 min pitch.

**2 Oct (evening 18:00–22:00):**
- Both: Attend pre-demo check (Wi-Fi, audio, browser zoom, header badges).
- Ujjwal: Start X4, X5, X6 build. Run eval set on Ask Chhatri. Test slip extraction on sample slips.
- Omkar: Rehearse at full speed. Identify cuts for R9 (time overrun). Practise Q&A answers.

**3 Oct (morning 08:00–09:00):**
- Ujjwal: Checkpoint on X4, X5, X6. If not done, decide what to drop.
- Both: One final rehearsal (3-minute cut only).

**3 Oct (12:00, code freeze):**
- Ujjwal: Run `make test-slow` in full. If a test fails, it is a blocker. Fix or revert.

**3 Oct (14:30–15:00, final pre-demo check):**
- Both: 30-minute technical check (Wi-Fi, preflight, browser, zoom, sound, scenario load). Mark the start time.
- Omkar: Load the deck PDF and the demo URLs.
- Ujjwal: Start the backend, load the monsoon scenario, pause at 08:00.

## Open questions

1. Will the venue have a fast, stable Wi-Fi connection on 3 Oct, or should we assume mobile hotspot as the primary? Owner: Omkar Kadam (confirm with Paytm on 2 Oct by 17:00).
2. Are Gemini and Sarvam free-tier quota limits likely to hold through the 7-minute demo? Owner: Ujjwal Pardeshi (monitor daily 2–3 Oct; plan a hotspot-based offline path if usage is heavy).
3. If the pre-demo check on 3 Oct finds a new blocker (e.g. a backend service fails), do we have 90 minutes to fix it, or should we pivot to the static demo immediately? Owner: Omkar Kadam (plan B at 14:30).

## Changelog

- 2026-10-02 · v2 · final consistency pass against the code: no changes needed; all risk descriptions are accurate.
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.1 · fact-check pass: fixed R14 description to use correct claim decision outcome names (REFERRED/DECLINED, not BLOCKED which is for cover purchase).
- 2026-10-02 · v1 · first draft. 16 risks across demo delivery, build, AI, credibility and team themes. Heat-map and top five identified.
