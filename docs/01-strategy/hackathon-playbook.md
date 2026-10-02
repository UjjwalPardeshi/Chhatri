# Hackathon playbook

| | |
|---|---|
| Status | Draft v1.6 · 3 Oct 2026 · the features it names are BUILT behind flags and not yet rehearsed |
| Owner | Omkar Kadam |
| Audience | The team |
| Related | [Build plan](../06-delivery/build-plan.md) · [Risk register](../06-delivery/risk-register.md) · [Demo runbook](../06-delivery/demo-runbook.md) · [Pitch and judge Q&A](../06-delivery/pitch-and-judge-qa.md) |

## TL;DR

- **Format:** on-site build (reportedly 8 hours) followed by a demo slot (length not announced; we prepare 3-min and 7-min cuts).
- **Partners:** Paytm (distribution, settlement, Soundbox); partner insurer and lender (to be signed after the hackathon).
- **Three wow moments:** (1) the trigger fires at 17:00 on a live hex map; (2) Anil asks "मुझे इतने ही पैसे क्यों मिले?" and Ask Chhatri gives a grounded answer; (3) one hospital-slip photo, pre-checked, auto-approved and credited same day.
- **Roles:** Omkar (presenter, product lead, mini-app builder, disclosure spokesperson); Ujjwal (tech lead, demo operator, live troubleshooting).
- **Fallback ladder:** live mode → force fallback for N2/N3/N4 → static demo (N7) → backup video.

## 1. What we know and do not know

| What we know | Source |
|---|---|
| Mumbai edition, Track 2, on-site at Paytm office. Final is 3 Oct 2026. | User confirmation |
| On-site build (reportedly about 8 hours), then demo. | Fellow finalist README |
| Slot length not published. We prepare 3-min and 7-min cuts. | Pitch rehearsal |
| Pre-built prototype is allowed by the organisers. | User confirmed |
| Judges will see a live hex map, a claims flow, voice, slip reading and policy audit. | Track requirement |
| Paytm, the insurer and the lender are partners. Details TBD. | Problem statement; A4, A5 |

| What we do not know | How we handle it |
|---|---|
| Exact demo slot length | Two cuts: 3 min (essentials) and 7 min (the full story). |
| Judging criteria or weights | Show generic criteria: innovation, user journey completeness, AI depth, live demo, regulatory fit, business model. Give evidence for each. |
| How many judges, their backgrounds, or what they prioritize | Assume they read the code and the docs. Show honesty (simulated sales, circular calibration, the clock is accelerated). This builds credibility. |
| Whether we can connect to Paytm's staging or a lender's live API | Plan for fully simulated mode; label every integration. |
| If an insurer has committed to partner after the hackathon | Do not claim a partnership commitment; say "pilot partner to be approached after the hackathon". |

## 2. How we will be judged

**Generic criteria our evidence will address:**

1. **Innovation & novelty.** Evidence: the trigger (merchant's own sales, area-level check, settlement-linked payout) vs. Riskwolf/SEWA basis risk. Credit H1–H12 ideas we adopted. Show that automatic claims from live data is unique among Track-2 projects.
2. **Customer journey completeness.** Evidence: N1 mini-app (cover explainer, consent, claim tracker, grievance ladder, help) spans the whole journey. Three test cases (EXPLAINED, HUMAN, BLOCKED) show guardrails.
3. **AI depth & quality.** Evidence: N2 (grounded LLM, no unsupported money figures, policy citations); N3 (slip reading with pre-check, confidence gates, fallbacks); N4 (voice in Hindi and English; Marathi is text only). Not just a word list or canned intents.
4. **Live demo & system maturity.** Evidence: `make demo-check` (70 of 70 at 86575ea; run it again at the freeze); the backend and frontend suites (the measured counts are written after the final run); live hex map, WhatsApp phone, slip photos, officer console, audit and backtest pages. Deterministic replay.
5. **Regulatory fit & governance.** Evidence: deterministic policy engine only source of payout authority; audit chain with hash verification; consent design for DPDP rollout; EDI holiday is lender's decision (K3), not ours; grievance ladder with SLAs.
6. **Business model & scalability.** Evidence: Paytm's 1.57 crore merchants (A1), ₹814 cr financial-services revenue (A2), existing merchant plan demonstrates market demand. Claim cost is ½ × expected day, capped. Partner insurer and lender underwrite risk.

## 3. Win themes and wow moments

**Win themes:**

1. **Automatic claim from the merchant's own sales data.** Among Track-2 projects we could find in public repos, Chhatri is unique in deciding payouts automatically from live sales inside the payments app. Rivals are journeys, readiness engines, or claim assistants. Chhatri decides the money.
2. **Same-day decisions with grounded explanations in Hindi.** The merchant can ask "Why ₹X?" and get a reproducible answer, not a mystery or a "call customer service" brush-off.
3. **Three live tests show the system catches real cases.** EXPLAINED (merchant disputes the amount), HUMAN (name mismatch), BLOCKED (trying to buy cover during an alert). Not a happy-path demo.

**Three wow moments (in sequence during the demo):**

1. **17:00 on the map.** The monsoon alert (red, A-20250818-01) is live on the hex map for zones Z3, Z7, Z12. At 17:00, the sales index drops below 50% for 3 hours. The trigger fires visually. 312 shops turn green. Live KPIs flip (3 zones, 312 shops paid, 4 min to money).

2. **Voice question in Hindi.** Anil's voice: "मुझे इतने ही पैसे क्यों मिले?" (Why did I get only this much?). Ask Chhatri replies (from DEMO.md): "आपका आम मंगलवार: ₹4,380। आज आपके इलाके की बिक्री 63% गिरी। छतरी खोई हुई बिक्री का आधा देती है।" (Your usual Tuesday: ₹4,380. Today your zone's sales fell 63%. Chhatri pays half of the lost sales.) The answer shows the baseline (₹4,380), the drop (63%), and the principle (half of lost sales).

3. **Hospital-cash claim in one photo.** Merchant uploads a photo of a hospital slip. Gemini vision reads the patient name, admission and discharge dates. Pre-check confirms the fields match the KYC and the silent day. Decision: APPROVED ₹1,500 (½ × expected day for the day in hospital, capped). Credit shows 4 min after decision. No human form-filling, no weeks of back-and-forth. One photo to money, same day.

## 4. Disclosure statement (what to say on stage, word-for-word)

**Read this exactly when a judge asks "How much of this was pre-built?"**

> "The prototype was built in two phases. **Before 2 Oct (29 Sep to 1 Oct),** we built the backend policy engine, the claims-officer console, the backtest, the audit log, the live hex map with the replay orchestrator, and the WhatsApp simulator. That is the core system. **On 2 Oct,** we built the merchant mini-app (N1), the slip-reading pre-check (N3), the grounded assistant (N2), voice in Hindi and English (N4), the complaints ladder (N5), the consent centre (N6), a Marathi draft (N8) and the static build (N7), each behind a feature flag. We have not run the live AI providers with a key, so we say which badges show LIVE. The organisers confirmed that pre-built work is allowed. We used the time before the final to ship a real system with tests, not slides."

(If asked "Why pre-build?": "A claims engine is a data-processing system. It needs tests, an audit trail, and proof that the same seed produces the same output every time. We could not write that in 8 hours on-site. The architecture, the policy rules, and the demo numbers are locked now. Merchants and judges will see the system work, deterministically, every time.")

## 5. On-site day plan (3 Oct)

**Before we arrive (evening 2 Oct):**
- [ ] Code freeze: everything is in `main` behind flags; set the flag list on the demo card.
- [ ] Backend + frontend deployable to a laptop (no cloud infra).
- [ ] Static demo (N7) deployed by the repo owner to GitHub Pages or a free static host (human-only; not done).
- [ ] Backup video recorded (3-min and 7-min cuts, fallback if live fails) (human-only; not done).
- [ ] All three test cases (monsoon, hospital-cash, blocked buy) ready to play from the replay scenarios.

**Omkar's timeline (product, pitch, mini-app, disclosure):**

| Time | Task | Owner | Notes |
|---|---|---|---|
| 08:00–08:30 | Arrive; unpack and boot the demo laptop. Set up workspace (monitor, mouse, WiFi). | Omkar + Ujjwal | Laptop must run the full stack offline. Check power, internet bandwidth, HDMI. |
| 08:30–09:00 | Rehearse the 3-min cut, live, from the replay (monsoon). | Omkar + Ujjwal | Omkar narrates; Ujjwal operates. Focus: clock timing, voice latency, answer grounding. |
| 09:00–10:00 | Final fixes (if any integration is slow, patch or force fallback). Test the three cases (monsoon, hospital-cash, blocked). | Ujjwal leads; Omkar watches. | If Sarvam is slow (>5 s), switch to browser Web Speech. If Gemini is unreliable, pre-cache slips. |
| 10:00–11:00 | Rehearse the 7-min cut, live, with the full test suite. | Omkar + Ujjwal | Omkar narrates the policy story, the numbers, and the judges' evidence. Ujjwal operates. Time the transitions. |
| 11:00–12:00 | Demo operations checklist (T-5 prep below). Update pitch based on morning rehearsal. | Omkar | Refine the voice answers, the "why this amount" grounding. Prepare the disclosure statement. |
| 12:00–13:00 | Lunch and mental reset. | Both | Stay hydrated and focused. |
| 13:00–14:30 | One more full 7-min rehearsal. Record a backup video if live fails on stage. | Both | Lock the narrative. Omkar should be able to say the pitch with no notes, except the exact disclosure statement. |
| 14:30–15:30 | Final code review: is N1 responsive on the projector? Does the minimap zoom work? Are all LIVE/SIMULATED badges correct? | Ujjwal | Catch any rendering bugs on a large screen. |
| 15:30–16:00 | T-30 checklist (see below). Prep workspace: HDMI, mouse, laptop screen-sharing zoom. | Both | Organize gear. Post the backup video link in a note, visible to Omkar if live fails. |
| 16:00–16:30 | Wait and focus. (Demo slot is TBD, likely 16:30–17:00 or later.) | Both | Breathe. The system is ready. |
| 16:30+** | **Demo slot (your turn).** | Omkar presents; Ujjwal operates. | See "Demo run" section below. |
| After demo | T-0 checklist (see below). | Both | Document what went live, what fell back, what we learned. Thank judges. |

**Ujjwal's parallel timeline (tech lead, demo operator):**
- Same rehearsals and checklists as above, with focus on: latency (is Sarvam <5 s?), fallback switches, error handling (404 unknown merchant, 60-s vision timeout, lost WiFi).
- During demo: operate keyboard/mouse; monitor integrations; call "fallback" if a component hangs; cue Omkar if ahead of time or over time.

## 6. Rules of the stage

**Live badges only for what the screen shows as LIVE:**
- **LIVE (on stage only if a key is set and the check call succeeded):** Gemini free tier (Ask Chhatri N2, slip reading N3) and Sarvam (voice N4, speech, chat, vision). Both are built and tested against fakes only: no key has been run. Browser speech recognition (voice fallback) needs the network and is labelled SIMULATED with provider `browser`.
- **SIMULATED (label clearly in the UI):** sales data, alerts feed, KYC check, Soundbox, lender EDI holiday, n8n workflows (use in-process runner for demo), Paytm payment link (no staging keys available for hackathon).

**Say the clock is a replay:**
> "The replay is running at 360× speed: 6 simulated minutes per real second. The decision is instant; the credit rides on that evening's settlement. But the merchant sees the decision in the console and on the Soundbox within seconds of the trigger. The real system would run the same way, without the time acceleration."

**Say the sales are simulated:**
> "The backtest uses real rainfall from Open-Meteo and simulated merchant sales. The monsoon scenario in the demo uses simulated shops and simulated sales. A real deployment would read Paytm's live sales per merchant and trigger the same way."

**Any claim about Paytm's partnership, insurer, or lender:**
> "The pilot partner will be approached after the hackathon. Paytm distributes insurance via its IRDAI-licensed broking arm. The insurer underwrites risk. The lender approves the EDI holiday under its policy."

## 7. Contingency ladder (in order of preference)

1. **Live (primary).** All of N2, N3, N4 online. Sarvam and Gemini responding. Fallback switches off. Demo-check passes.
2. **Force fallback (if latency is bad).** Turn on "force fallback" switches for N2, N3, N4 in the provider panel (X6). Show graceful degradation: templates instead of a model (N2), the simulated reader or a person instead of a live reader (N3), browser speech instead of Sarvam (N4). The demo still works; we explain why.
3. **Static demo (N7, if internet is down or integrations are down for >2 min).** Run `npm run preview` in `frontend/` to serve the mock-mode build on the laptop, or open the public address if the repo owner has deployed one. It is deterministic and needs no backend. We narrate the monsoon and hospital-cash flows while advancing the mock state. Judges see the full UI and journey.
4. **Backup video (last resort, if the laptop fails or we are out of time).** Play a 7-minute recorded walkthrough (built today, 13:00–14:30). Same narrative as live demo, but pre-recorded. Judges see the full flow, polished, with perfect timing.

**Decision rule:** if we are more than 2 minutes behind schedule or an integration hangs for >30 s, Ujjwal calls "fallback" and we move to the next option.

## 8. Stage checklists

### T-60 (one hour before demo)

- [ ] Backup video exists and works (link visible to the team).
- [ ] All three test scenarios (monsoon, hospital-cash, blocked) are loaded and ready to play.
- [ ] N1 mini-app renders on a 1920×1080 projector without scaling. No text cutoff.
- [ ] Gemini and Sarvam keys are set and responding (<2 s latency test).
- [ ] WhatsApp phone, hex map, and officer console are all live on the demo laptop.
- [ ] Every LIVE badge is correct; every SIMULATED label is visible.
- [ ] The disclosure statement is written on a card, word-for-word.
- [ ] Backup: if internet is down, the static demo (N7) is served from the laptop with `npm run preview`.

### T-30

- [ ] Run `make demo-check` one more time. All 70 pass.
- [ ] Full 7-min rehearsal: Omkar narrates, Ujjwal operates. Time it. Adjust pacing if needed.
- [ ] Replay clock: confirm 17:00 trigger timing. Confirm ₹1,380 and ₹58,900 are exact. Confirm Z7 is 37%, not 41%.
- [ ] Test the "why this amount" voice answer. Is the Hindi correct? Is the clause citation (C4) in the reply?
- [ ] Hospital-cash slip: upload a photo, confirm the pre-check shows readable, name-match, and date-match before running the APPROVED decision.
- [ ] Blocked case: click "buy cover" during an alert. Confirm the message is "New cover starts after the waiting period — from 25 August. It won't apply to tomorrow's alert." .
- [ ] Pitch: Omkar can say the win theme (automatic claim from live data) in one sentence without notes.

### T-5 (five minutes before)

- [ ] Close all other apps on the demo laptop. Disk cache cleared. Only the browser and the console are open.
- [ ] WiFi is stable. A phone hotspot is a backup, ready in case the venue WiFi drops.
- [ ] HDMI is plugged in. Projector shows the console UI at full resolution. Mouse and keyboard work.
- [ ] Omkar and Ujjwal are at the demo station. Phones are silent.
- [ ] The replica of the script (the disclosure statement and the win themes) is visible to Omkar, out of sight of the audience.
- [ ] Ujjwal has a laptop with the replay orchestrator ready to restart any scenario if needed.

### T-0 (immediately after demo)

- [ ] Debrief: what went live? What fell back? Did the triggers, amounts and voices work?
- [ ] Screenshot the final state of the console (hex map, case list, audit log).
- [ ] Document any bug or latency we found (for the post-hackathon roadmap).
- [ ] Thank the judges and the Paytm team.
- [ ] Record the energy in the room. Did they ask follow-ups? Did they look at the code?

## 9. What not to say

| Claim | Why not | Say instead |
|---|---|---|
| Mentioning a Paytm area income index | This product is not public. | "Our Area Income Signal roadmap idea." |
| "Reduces disputes 80%" | Unverified. | "The explanation shows the formula and the merchant's own data. Judges will assess whether this reduces disputes." |
| Citing published judging criteria or an expected score | No criteria are published. | "We address these generic criteria: innovation, journey completeness, AI depth, live demo, regulation, business model." |
| Stating a specific amount for Sarvam free credits or a Gemini version | Amounts and versions are not stated publicly. | "Sarvam free starter credits" or "Gemini Flash free tier". |
| "The 8-hour build window is official" | It is reported, not published. | "Reportedly, the on-site build is about 8 hours." |
| "Insurer or lender has agreed to partner" | No partnership agreement is signed yet. | "Pilot partner to be approached after the hackathon." |
| "Same-day claim is unique; all others are weeks" | Not verified for every project. | "Among the Track-2 projects we could find in public repos, none pays a claim automatically from the merchant's own sales." |
| "The backtest validates real performance" | Sales are simulated; calibration is circular. | "The backtest is specification validation on simulated sales and real rainfall. It shows the trigger design." |
| "The replay clock is real-time" | It is accelerated. | "The replay clock is at 360× speed for demo purposes. The real system processes claims in seconds, and credit happens with the evening settlement." |
| Mentioning Zone Z7 at 41% | The prototype shows 37%; 41% was the deck sketch. | "Zone Z7 saw a 37% sales drop (the deck sketch estimated 41%; the prototype is the source of truth)." |

## 10. Links to detailed runbooks

- **[Demo runbook](../06-delivery/demo-runbook.md):** exact 3-min and 7-min runs, word-for-word narrative, fallback choreography, and time cues.
- **[Pitch and judge Q&A](../06-delivery/pitch-and-judge-qa.md):** 45+ judge questions and answers, with evidence and regulatory hedges.
- **[Build plan](../06-delivery/build-plan.md):** the waves, checkpoints, flags and hide order for 2 and 3 Oct.
- **[Risk register](../06-delivery/risk-register.md):** risks with mitigation and contingency.

## Open questions

1. What is the exact demo slot length and the judging format? How do we get the slot number? Owner: Omkar Kadam.
2. Can we pre-connect to the Paytm staging API or a lender test environment? (Fallback: simulate.) Owner: Ujjwal Pardeshi.
3. Should we prepare a version of the pitch for a 2-minute elevator pitch (if asked by judges in the hallway)? Owner: Omkar Kadam.

## Changelog

- 2026-10-03 · v1.6 · audit against the code: the features are BUILT behind flags, Marathi is text only (voice is Hindi and English), the disclosure statement and fallback ladder no longer name planned work or Tesseract
- 2026-10-02 · v1.5 · second fact-check pass: verified Hindi message against DEMO.md; updated BLOCKED case message to match actual system message
- 2026-10-02 · v1.4 · final consistency pass against the code
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.1 · fact-check pass: verified all prohibited claims are correctly listed in section 9; reframed partnership language
- 2026-10-02 · v1 · first draft, with exact disclosure wording, the three wow moments, and the on-site timeline.
