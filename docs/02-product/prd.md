# Product requirements document

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Product, engineering, design, compliance, judges |
| Related | [Personas and JTBD](personas-and-jtbd.md) · [User journeys](user-journeys.md) · [Facts and sources](../01-strategy/facts-and-sources.md) · [Metrics and impact](metrics-and-impact.md) · [SPEC.md](../SPEC.md) · [Risk register](../06-delivery/risk-register.md) |

## TL;DR

- **Problem:** Merchant income-loss claims today take 30–60 days and need multiple documents (A3). Paytm sees the sales fall in real time but has no way to pay automatically.
- **Solution:** Chhatri detects two loss events (area drop during alert, shop silence) via live sales data; the policy engine decides and pays the same day with a single document (or zero for area claims). EDI holiday defers the merchant's loan instalment on shock days.
- **Scope:** 8 keep features (K1–K8), 8 new features (N1–N8), 8 fixes (X1–X8) and 12 ideas from other teams (H1–H12). All deliver on the track's example stages (understand, submit, track, resolve).
- **Success:** 80%+ test coverage, zero unsupported money figures in Ask Chhatri, all decision explanations reproducible, no loan offers during alerts or disputes, live hospital-cash claim with <5 min payout SLA.

---

## 1. Problem and goals

### 1.1 Problem statement

India's informal merchants (₹200k–₹2M annual sales, shop-based, 30–60 min daily operations) face income shocks from weather, power outages, or illness. Paytm's merchant protection plan (A3) covers such losses but requires merchant action: file a claim (typically 30–60 days later) with documents (bank statements, loss photographs, weather proofs). Claims are repudiated at a 1-in-12 rate (A10); processing delays often mean the instalment on the shock day has already been deducted.

**Root cause:** Paytm captures the loss signal (zero or low sales) in real time via POS terminals, but the current claim process relies on the merchant to recognize, document and report the loss. The gap between signal and action is 1–2 days minimum; the gap between claim filing and payout is 30–60 days.

**Impact:** Merchants do not trust the plan; adoption and claims rates are low. Instalment delinquency on shock days rises.

### 1.2 Goals

1. **Reduce time-to-money from 30–60 days to the same day** (North star metric, see Metrics and impact). Paytm initiates claims on its own, using live sales data and automated checks.
2. **Lower claims barriers:** zero documents for area income loss (parametric trigger); one document (hospital slip) for illness. Pre-checks catch bad photos before a decision is made, so doubtful claims always reach a human.
3. **Enable EDI holiday for shock days:** after an approved claim, the merchant's next instalment is deferred to the end of the loan, with no penal charge (if the lender agrees).
4. **Explain every decision in Hindi and English, reproducible from shown numbers.** Merchants can ask "why" and dispute; humans review disputes within 24 h.
5. **Span the full track (insurance, lending, fintech) and the full merchant journey** (understand → buy → track claim → resolve disputes → escalate grievances).
6. **Build on the free AI stack** (Gemini Flash planned, Sarvam free starter available, Tesseract, browser Web Speech API). No paid keys; every integration is labelled LIVE or SIMULATED.

### 1.3 Non-goals

- Multi-branch chains, aggregators or corporate merchants (scope: shop-based, 1–3 staff).
- Family health insurance (scope: income loss during hospitalisation, not family coverage).
- Loan origination (scope: merchant loans pre-exist; Chhatri coordinates with the lender).
- Real-time lending (scope: EDI holiday defers an instalment; the lender decides, using its policy).
- Multi-modal document submission (scope: one hospital slip per claim via photo; no bank statements, proofs, forms).
- Proactive settlement (scope: payouts ride the evening settlement, not instant bank transfers).

---

## 2. Users and personas

| Persona | Role | Motivation | Context |
|---|---|---|---|
| **Anil Jadhav (S-0142)** | Tea-stall owner, Parel, Z7, Mumbai | Needs income protection on rainy days; wants fast, hassle-free claims; mistrusts insurance (30–60 days). | ₹600/day EDI; ₹4,380 expected Tuesday; ≤₹2 premium per day (rules). Speaks Hindi, uses WhatsApp and Soundbox. |
| **Ramesh (S-0907)** | Vada pav shop owner, Worli, Z3, uncovered | Wants to buy cover but needs rules enforced (blocked during alerts). | Z3 premium ₹14.16/day; hears about alerts from news. |
| **Priya** | Kirana owner, Delhi | Future user for heatwave cover (roadmap, not in pilot). | (Roadmap) |
| **Rajesh** | Claims officer, partner insurer | Reviews REFERRED claims; approves after policy engine checks. Does not change amounts (policy engine is the authority). | Uses console (`/claims` panel); checks slip evidence and KYC match; turnaround 24 h. |
| **Amit** | Paytm field sales and relationship executive | Onboards merchants; explains cover over the phone or in person. | Uses the mini-app explainer (N1 coverage card) to show merchants. |

See [Personas and JTBD](personas-and-jtbd.md) for full details.

---

## 3. Scope: features and priorities

### 3.1 Feature scope table

| ID | Feature | Name | Priority | Owner | Target | Status |
|---|---|---|---|---|---|---|
| **Keep (K)** | | | | | | |
| K1 | Area auto-claim | Triggered at area level; no action from merchant; ½ loss × drop%, capped ₹2,500/day. | P0 | Ujjwal | 29 Sep | LIVE |
| K2 | Hospital-cash claim | Silent day → check-in → one slip photo → ½ expected day, capped ₹1,500/day, up to 3 days auto. | P0 | Ujjwal | 29 Sep | LIVE |
| K3 | EDI holiday | Lender's decision (Chhatri requests); defers next instalment, no penal charge. Requires lender policy flag and active-loan guard (X4). | P0 | Ujjwal | 2 Oct | CODE, needs X4 |
| K4 | Policy engine and payout authority | Pure rules in `rules.yaml` (pilot-0.1); only source of APPROVED decisions. | P0 | Ujjwal | 29 Sep | LIVE |
| K5 | Explanations and disputes | "Why this amount" with formula; dispute opens a 24 h case; human review. | P0 | Ujjwal | 29 Sep | LIVE (K5), demo shows dispute (J6) |
| K6 | Cover purchase with waiting period | 7-day wait; 72 h alert lookahead blocks purchase during alerts. | P0 | Ujjwal | 2 Oct | LIVE (rules), demo shows block (J8) |
| K7 | Tamper-evident audit log | Hash chain; `/api/audit/verify` validates. | P0 | Ujjwal | 29 Sep | LIVE |
| K8 | Claims-officer console and live map | Hex map, zone panel, KPIs, feed, case queue, audit, backtest, policy pages. | P0 | Omkar | 2 Oct | LIVE |
| **New (N)** | | | | | | |
| N1 | Merchant mini-app "Chhatri in Paytm for Business" | Phone-sized, Hindi-first, inside console. Screens: home, coverage explainer, consent & buy, claim tracker, help & grievance. | P0 | Omkar | 2 Oct | PLANNED (screens+copy) |
| N2 | Ask Chhatri grounded assistant | Text + voice; Hindi + English. Answers coverage and claim questions, grounded in policy wording (clause citations). | P0 | Ujjwal | 2 Oct | PLANNED (N2 backend + N4 voice) |
| N3 | Live slip reading + pre-check | Gemini vision or Sarvam Vision extracts slip fields; pre-check shows extracted data to merchant; readiness checklist (photo readable, name matches, dates match). | P0 | Ujjwal | 2 Oct | PLANNED (backend + UX) |
| N4 | Real Hindi voice | Sarvam Saaras STT and Bulbul TTS (free credits), fallback browser Web Speech API. | P0 | Ujjwal | 2 Oct | PLANNED (integration) |
| N5 | Grievance ladder and SLA clocks | Insurer GRO → Bima Bharosa → Insurance Ombudsman. Visible clocks. | P1 | Omkar | 3 Oct on-site | PLANNED (post-hackathon) |
| N6 | Consent centre | View, grant, withdraw purpose-specific consents (DPDP A22). "Delete my slip data"; health data minimised. | P1 | Omkar | 3 Oct on-site | PLANNED (post-hackathon) |
| N7 | Public static demo + video | GitHub Pages or Vercel Hobby mock-mode console. 7-minute recorded backup video. | P1 | Omkar | 2 Oct evening | PLANNED (deploy + video) |
| N8 | Marathi (mini-app + Ask Chhatri) | Third language for Mumbai merchants. | P1 | Omkar | 3 Oct on-site | PLANNED (post-hackathon) |
| **Fixes (X)** | | | | | | |
| X1 | Fix 2 failing frontend tests | Cases panel, Overview live map. | P0 | Ujjwal | 2 Oct | PLANNED |
| X2 | Validate expected day at claim creation | Ensure published ₹10-rounded value is used; no unchecked floats. | P0 | Ujjwal | 2 Oct | PLANNED |
| X3 | Fail loudly when zone missing from premium table | Raise an error; do not silently fall back to ₹2/day default. | P0 | Ujjwal | 2 Oct | PLANNED |
| X4 | EDI-holiday guard | Check: loan is active, not in arrears, lender policy flag set. | P0 | Ujjwal | 2 Oct | PLANNED |
| X5 | Off-script merchant → clean 404 | Raise 404 with message ("Merchant not found"), not a KeyError. | P0 | Ujjwal | 2 Oct | PLANNED |
| X6 | Per-component Sarvam toggles + provider panel | Demo-only panel shows LIVE/SIMULATED/FALLBACK badge per component. | P1 | Ujjwal | 2 Oct | PLANNED |
| X7 | Honest-wording test | Test fails if a template promises ("guaranteed", "always"), shows an unsupported money figure, or claims a payout before the payout record exists. | P0 | Ujjwal | 2 Oct | PLANNED |
| X8 | No loan offers during alerts or open disputes; daily message cap | X8 rule: no cross-sell while alert covers zone or claim/dispute open. Cap proactive messages per day (except payment confirmations). | P1 | Ujjwal | 3 Oct on-site | PLANNED |
| **Ideas from other teams (H)** | | | | | | |
| H1 | Step-by-step journey with state badges | N1 claim tracker: Detected → Checked → Decided → Paid → EDI holiday; each step shows state, reason, next step, ETA. | P0 | Omkar | 2 Oct | PLANNED (N1 screens) |
| H2 | Evidence trace, "why this amount", source badges | K5 + N1: card shows rule → numbers → source badges ("Paytm sales index", "alert A-…", "KYC", "slip"). | P0 | Omkar | 2 Oct | PLANNED (N1 screens) |
| H3 | Payout receipt (PDF, audit hash) | N1 receipt: decision id, rules version, formula, data sources, audit hash (first 12 chars), grievance path. Printable. | P1 | Omkar | 3 Oct on-site | PLANNED |
| H4 | Honest-wording test | X7 (same). | P0 | Ujjwal | 2 Oct | PLANNED |
| H5 | Human check of extracted data; readiness checklist | N3: show extracted slip fields; merchant confirms before checks run. Checklist: photo readable, name matches, dates match (not a numeric score). | P0 | Ujjwal | 2 Oct | PLANNED (N3 UX) |
| H6 | Live public demo with no login | N7 (same): static mock-mode console at public URL. | P0 | Omkar | 2 Oct evening | PLANNED |
| H7 | Glass-box provider panel with fallback switch | X6 (same). | P1 | Ujjwal | 2 Oct | PLANNED |
| H8 | Real operational counts (ops strip) | K8: count open cases by state, oldest SLA clock, auto vs human share, today's payouts per zone. No projections. | P1 | Omkar | 2 Oct | PLANNED (K8 screens) |
| H9 | No loan offers during distress; frequency capping | X8 (same). | P1 | Ujjwal | 3 Oct on-site | PLANNED |
| H10 | Deterministic core; LLM has no money authority | K4 (done). "The AI builds the case; code decides the money." | P0 | Ujjwal | 29 Sep | LIVE |
| H11 | Bilingual templates (not LLM translation) | Hindi + English catalogue (done). N8 adds Marathi. | P0/P1 | Omkar | 29 Sep / 3 Oct | LIVE (en+hi) / PLANNED (mr) |
| H12 | Visible, measured test counts | README and pitch show measured counts. Never round up. | P0 | Ujjwal | 2 Oct | PLANNED (after X1–X3) |

### 3.2 Priority explanation

- **P0 (build on 2 Oct):** Must work for the 3 Oct demo; judged on completeness and live AI.
- **P1 (if time on-site, 3 Oct):** Polish, extra languages, regulatory wording; nice-to-have if schedule allows.

---

## 4. Functional requirements

### 4.1 Area auto-claim (K1)

**FR-area-001:** Detect when an area's hourly sales index falls below 50% for 3 consecutive hours AND below the model's conformal lower bound AND an active alert covers the zone.

- *Acceptance criteria:*
  - Given: Z7 alert issued, sales at 37%, 3 h trailing index, no claim exists.
  - When: policy engine evaluates the trigger.
  - Then: trigger outcome is APPROVED, amount = ₹1,380 (= ½ × ₹4,380 × 63%), checks all PASS.

**FR-area-002:** Compute area payout as ½ × expected_day × drop%, capped at ₹2,500/day per shop.

- *Acceptance criteria:*
  - Given: expected ₹4,380, drop 63%.
  - When: area_amount() is called.
  - Then: return (4380 * 63 / 100) // 2 = 1379.7 → 1380 paise (rounded).

**FR-area-003:** Pay all insured shops in the triggered zone simultaneously at the trigger time; credit 4 min later via settlement.

- *Acceptance criteria:*
  - Given: 312 shops triggered in Z3, Z7, Z12 at 17:00 simulated.
  - When: settlement payout is posted.
  - Then: all 312 are credited at 17:04 simulated (payout_rail_delay_minutes: 4).

### 4.2 Hospital-cash claim (K2)

**FR-personal-001:** Detect silent day (zero sales all 24h) and trigger a proactive check-in via voice.

- *Acceptance criteria:*
  - Given: Anil's shop has ₹0 sales from 00:00–23:59 Wed 20 Aug.
  - When: silent-day check runs at 20:00 Wed (or at 11:20 next day for demo).
  - Then: a check-in message is sent: "अनिल जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है?" (exact from DEMO.md).

**FR-personal-002:** Accept one hospital slip photo; extract patient name, admission date, hospital name.

- *Acceptance criteria:*
  - Given: Anil uploads `anil_admission_slip.png` (patient "Anil R. Jadhav", admitted 2025-08-20, KEM Hospital).
  - When: N3 slip vision (Sarvam Vision today; Gemini Vision PLANNED) processes the image.
  - Then: extraction returns {patient_name: "Anil R. Jadhav", admission_date: "2025-08-20", hospital_name: "KEM Hospital", confidence: ≥0.80}.

**FR-personal-003:** Check: name matches KYC at ≥85 score (token-set ratio); slip confidence ≥0.80.

- *Acceptance criteria:*
  - Given: extracted name "Anil R. Jadhav", KYC name "ANIL RAMESH JADHAV".
  - When: name_match_score() is called.
  - Then: rapidfuzz.distance.token_set_ratio("Anil R. Jadhav", "ANIL RAMESH JADHAV") ≥ 85 → PASS.

**FR-personal-004:** Compute hospital-cash payout as ½ × expected_day, capped at ₹1,500/day, up to 3 auto days.

- *Acceptance criteria:*
  - Given: expected Wed ₹4,300, silent 1 day.
  - When: personal_amount() is called.
  - Then: return (4300 // 2) = ₹2,150 a day, capped at ₹1,500 → ₹1,500.

**FR-personal-005:** If any HARD check fails, refer the claim to a human (officer) with a case and 24 h SLA.

- *Acceptance criteria:*
  - Given: slip name "Sunil Pawar" (extracted), KYC "ANIL RAMESH JADHAV" (score 40, < 85).
  - When: policy engine evaluates the claim.
  - Then: outcome is REFERRED, amount = ₹1,500 (computed, not paid), case C-2291 opens, message sent: "धन्यवाद। पर्ची पर नाम आपके KYC से मेल नहीं खा रहा, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।" (exact from DEMO.md).

### 4.3 EDI holiday (K3)

**FR-edi-001:** After an approved payout, request the lender's EDI holiday via the lender integration, quoting the decision ID.

- *Acceptance criteria:*
  - Given: payout decision D-000001 APPROVED at 17:04 for Anil (₹1,380).
  - When: payout is credited.
  - Then: EDI-holiday request is posted to lender, decision_id="D-000001", instalment_date=next day.

**FR-edi-002:** Lender policy decides: loan is active, not in arrears, holiday allowance not used up → grant; otherwise → deny.

- *Acceptance criteria:*
  - Given: Anil's loan is active, 0 arrears, holidays_remaining > 0.
  - When: lender policy evaluates.
  - Then: holiday is granted; next instalment (₹600) is deferred to end of loan, no penal charge.

**FR-edi-003:** Notify merchant of the lender's decision (grant or deny) within 5 min of payout.

- *Acceptance criteria:*
  - Given: holiday granted at 17:04.
  - When: message is posted at 17:05 simulated.
  - Then: message text is "कल की ₹600 की किस्त रोक दी गई है।" (exact from DEMO.md) or "holiday denied, you still owe ₹600 tomorrow".

### 4.4 Policy engine and payout authority (K4)

**FR-policy-001:** The only layer that can produce an APPROVED decision; all decision inputs are checks and `rules.yaml`.

- *Acceptance criteria:*
  - Given: a claim and facts.
  - When: policy engine evaluates.
  - Then: only the APPROVED path is `evaluate_area_claim()` or `evaluate_personal_claim()`; no LLM output sets an amount or approves.

**FR-policy-002:** All money figures shown to a merchant are reproducible from the formula shown next to them.

- *Acceptance criteria:*
  - Given: decision amount ₹1,380, formula "₹4,380 × 63% ÷ 2 = ₹1,380".
  - When: merchant views the card.
  - Then: numbers are from `decision.explanation` (expected_day, drop, share, cap), not free-generated.

### 4.5 Explanations and disputes (K5)

**FR-explain-001:** Generate "why this amount" explanation with formula; offer voice or text questions via Ask Chhatri.

- *Acceptance criteria:*
  - Given: Anil's ₹1,380 payout.
  - When: Anil taps "why" and speaks "मुझे इतने ही पैसे क्यों मिले?"
  - Then: reply is "आपका आम मंगलवार: ₹4,380। आज आपके इलाके की बिक्री 63% गिरी। छतरी खोई हुई बिक्री का आधा देती है।" (exact from DEMO.md).

**FR-explain-002:** Dispute opens a case with a 24 h SLA; human reviews and responds within 24 h.

- *Acceptance criteria:*
  - Given: Anil disputes "मेरा नुकसान ज़्यादा हुआ।"
  - When: case C-2291 is opened.
  - Then: due_by = now + 24h, status OPEN, evidence = original decision + dispute text.

### 4.6 Cover purchase with waiting period (K6)

**FR-cover-001:** Cover starts only when premium is received (cash before cover, s.64VB).

- *Acceptance criteria:*
  - Given: Anil buys cover on 18 Aug, prepayment ₹424.80 for 30 days.
  - When: payment is received.
  - Then: `cover.prepaid_through` is set to 17 Sep; cover starts 25 Aug (7 days after purchase, waiting period).

**FR-cover-002:** Block cover purchase if an alert will be active within 72 h after the waiting period ends.

- *Acceptance criteria:*
  - Given: Ramesh tries to buy cover on 18 Aug 18:00 (alert issued 17:30, valid 14:00–20:00 19 Aug).
  - When: policy engine checks cover_purchase.
  - Then: outcome is BLOCKED, message: "नया कवर वेटिंग पीरियड के बाद शुरू होता है — 25 अगस्त से। कल के अलर्ट पर यह लागू नहीं होगा।" (exact from DEMO.md).

### 4.7 Ask Chhatri grounded assistant (N2)

**FR-ask-001:** Answer coverage and claim questions in Hindi and English, grounded only in policy wording (C1–C12) and the merchant's own records (decision, claim).

- *Acceptance criteria:*
  - Given: question "क्या अस्पताल का खर्च भी मिलेगा?" (Will hospital bills be covered?).
  - When: N2 receives the question.
  - Then: answer cites C3 (hospital cash, not hospital bills) and explains the difference.

**FR-ask-002:** Fallback chain: Gemini Flash (free) → Sarvam sarvam-105b (free credits) → deterministic template. Any provider timeout → next fallback.

- *Acceptance criteria:*
  - Given: Gemini free tier rate limit exceeded.
  - When: N2 tries Gemini.
  - Then: timeout occurs, fallback to Sarvam is attempted; if Sarvam times out, use template: "I don't have enough context to answer. Please contact our team." (with human handoff).

**FR-ask-003:** Guard: no money figure that is not in the decision facts; no promises ("guaranteed", "always").

- *Acceptance criteria:*
  - Given: LLM output "Your claim of ₹2,000 is guaranteed to be approved."
  - When: N2 guard checks the output.
  - Then: output is rejected; fallback to template.

### 4.8 Live slip reading and pre-check (N3)

**FR-slip-001:** Extract slip fields with confidence scores; show merchant a readiness checklist before checks run.

- *Acceptance criteria:*
  - Given: uploaded slip image.
  - When: N3 vision processes the image and pre-check runs.
  - Then: UX shows "Photo readable? OK Name matches KYC? [Confirm] Dates match? OK" with a Retake button if any item fails.

**FR-slip-002:** Confidence ≥0.80 passes the vision gate; below it → REFERRED.

- *Acceptance criteria:*
  - Given: slip confidence 0.92 (clear image).
  - When: N3 gate checks.
  - Then: PASS; no REFERRED.

### 4.9 Real Hindi voice (N4)

**FR-voice-001:** STT: Sarvam Saaras v3 or v4 (free credits); fallback browser Web Speech API.

- *Acceptance criteria:*
  - Given: Anil speaks "मैं अस्पताल में हूँ।"
  - When: N4 STT runs.
  - Then: transcription is "मैं अस्पताल में हूँ।" (exact Hindi).

**FR-voice-002:** TTS: Sarvam Bulbul (free credits); fallback browser speechSynthesis.

- *Acceptance criteria:*
  - Given: message "Paytm par ₹1,380 prapt hue — Chhatri se".
  - When: N4 TTS runs.
  - Then: audio is spoken in Hindi, audible on demo laptop.

### 4.10 Merchant mini-app (N1)

**FR-mini-001:** Home screen: cover status card (zone, start date, caps used, premium paid until), daily-instalment amount.

- *Acceptance criteria:*
  - Given: Anil's active cover in Z7, ₹600/day EDI.
  - When: mini-app opens.
  - Then: card shows "Z7 · Cover starts 25 Aug · Paid until 17 Sep · ₹600/day".

**FR-mini-002:** Coverage explainer: "what am I covered for", examples, exclusions, waiting period, caps.

- *Acceptance criteria:*
  - Given: merchant taps "Coverage".
  - When: explainer loads.
  - Then: sections visible: "Area income loss (triggered by alert + sales drop)", "Hospital cash (1 silent day + slip)", "Caps: ₹2,500/day area, ₹1,500/day hospital, ₹30,000 annual", "Exclusions: seasonal slump, …", "Waiting period: 7 days", "EDI holiday: when you get paid, your instalment is deferred".

**FR-mini-003:** Consent and buy flow: purpose-specific consent check-box, payment link generation, cash-before-cover confirmation.

- *Acceptance criteria:*
  - Given: merchant taps "Buy cover".
  - When: consent screen loads.
  - Then: text states "Sales data for cover and claims", checkbox required, link is generated (SIMULATED on stage).

**FR-mini-004:** Claim tracker: Detected → Checked → Decided → Paid → EDI holiday (J1 H1).

- *Acceptance criteria:*
  - Given: Anil's claim at 17:00 (trigger).
  - When: tracker loads at 17:04 (paid).
  - Then: steps show "Detected · 17:00 · your area sales fell 63% during the alert" → "Checked · 17:02 · cover active, all good" → "Decided · 17:03 · ₹1,380 auto-approved" → "Paid · 17:04 · credited with today's settlement" → "EDI holiday · 17:05 · tomorrow's ₹600 paused".

**FR-mini-005:** Help and grievance: "Ask Chhatri" button, dispute form, escalation ladder (N5, PLANNED).

- *Acceptance criteria:*
  - Given: Anil opens "Help".
  - When: screen loads.
  - Then: options: "Ask a question" (voice/text), "Dispute this decision" (form + 24 h timer), "Escalate to GRO/Bima Bharosa/Ombudsman" (PLANNED).

---

## 5. Non-functional requirements

### 5.1 Latency budgets

- **Ask Chhatri (N2) answer latency:** target ≤ 5 s, to be measured in rehearsal (templates are instant). Demo success: ≥ 95% of rehearsal questions within 5 s.
- **Slip reading (N3) vision latency:** target ≤ 10 s. Demo success: ≥90% within 10 s.
- **Area claim decision latency:** ≤ 500 ms (policy engine is pure Python; confirmed by `make demo-check` at ~100 ms).
- **Payout credit latency:** ≤ 5 min (rules.yaml payout_rail_delay_minutes: 4; settlement system adds ~1 min). Demo shows 17:04 (4 min after 17:00 trigger).

### 5.2 Demo reliability

- **Make demo-check passes 70/70** before the final. Any fix on-site re-runs the suite in <15 s.
- **Rollback to safe state:** `make demo-check --reset` reloads all scenarios from committed artefacts, deterministically.
- **Fallbacks:** every integration (N2, N3, N4, Paytm link) is labeled LIVE/SIMULATED; if an integration times out, the demo continues with the fallback path (template, Tesseract, browser Web Speech, mock link).

### 5.3 Accessibility (WCAG 2.2 AA)

- **Touch targets:** 44×44 px minimum (buttons, chips, form inputs).
- **Contrast:** 4.5:1 on text; 3:1 on graphics.
- **Keyboard navigation:** all interactive elements reachable via Tab / Shift+Tab / Enter.
- **Screen reader:** ARIA labels on dynamic content (chat, live-map hexagon updates).
- **Motion:** all animations respect `prefers-reduced-motion`.

### 5.4 Security

- **Input validation:** all user inputs (claim form, voice transcriptions, question text) are validated and sanitized before storage.
- **Rate limiting:** all endpoints rate-limited to prevent abuse.
- **Auth:** merchant identity verified via Paytm settlement device (in production) or demo bearer token (on stage).
- **Encryption:** all data in transit is HTTPS; payloads over SSL.
- **No secrets in logs:** Paytm MCP token, Sarvam key, Gemini key never logged (secrets.py filters them).

See [SECURITY.md](../SECURITY.md) for full details.

### 5.5 Internationalization (i18n)

- **Live:** Hindi (devanagari) and English (en-US).
- **P1:** Marathi (devanagari) for Mumbai merchants (N8).
- **Message catalogue:** `backend/chhatri/conversation/messages.py` is the single source; no LLM translation.
- **Number format:** Indian rupees (₹), commas (₹1,380), no spaces.
- **Date format:** 25 Aug (word month, no leading zero for dates < 10; from Paytm design).
- **Voice:** STT and TTS support Hindi and English (Sarvam Saaras, Bulbul); Marathi added (Sarvam v4, PLANNED).

### 5.6 Observability and audit

- **Audit log:** every payout, claim, case, dispute, and officer decision is logged as an `AuditEntry` with a hash-chained sequence. `/api/audit/verify` validates the chain.
- **Metrics dashboard:** (PLANNED N10) real-time KPIs: open cases by state, oldest SLA clock, share auto vs human, today's payouts by zone, settlement latency.
- **Errors:** all errors are logged with merchant_id, action, timestamp, and stack trace (server-side only; never to merchant UI).
- **SLA tracking:** dispute and grievance clocks are tracked per case and visible in the UI (N1 tracker, N5 ladder).

---

## 6. Dependencies

### 6.1 Free AI accounts

- **Google AI Studio:** Gemini Flash free tier (rate-limited; we use it only for hero moments: slip vision, Ask Chhatri fallback). Free-tier content may be used to improve products, so we send only synthetic demo data (sample merchants, test slips).
- **Sarvam AI:** free starter credits (amount not published; verify with Sarvam before final). Used for Saaras STT, Bulbul TTS, sarvam-105b chat, Sarvam Vision (premium, but credits given). Falls back to browser Web Speech API and deterministic templates.
- **Tesseract OCR (planned, P1):** open-source (Apache-2.0), with a Hindi "hin" model. Local and offline; a fallback for slip reading when vision APIs are down.

### 6.2 Integrations (not free but simulated/labelled)

- **Paytm payment link:** SIMULATED on stage (PAYTM_MCP_URL not set). In production, MCP server over SSE (requires merchant credentials).
- **Paytm settlement and EDI:** SIMULATED (no live access; Paytm for Business APIs require staging credentials).
- **WhatsApp Cloud API:** SIMULATED in-console phone (no real WhatsApp messages sent; test number would require business verification).
- **n8n workflows:** SIMULATED in-process runner (in-process workflows same as n8n, but n8n UI is not live on stage; `make dev` uses in-process, `make up` with `CHHATRI_STACK_N8N_URL=` also uses in-process).
- **Open-Meteo rainfall:** live API call (free tier, no rate limit per Paytm's use). Data is cached in `backend/data/weather/` for deterministic replay.

---

## 7. Release plan

### 7.1 Oct 2 (today): Build and rehearse

| Time | Owner | Task | Success criteria |
|---|---|---|---|
| Morning | Both | Read docs, set up free keys (Gemini, Sarvam), test browser speech on demo laptop | Gemini key works; Sarvam free credits verified; speech audible |
| 10:00–12:00 | Ujjwal | X1–X6 fixes (2 frontend tests, expected-day validation, zone fallback, EDI guard, 404, Sarvam toggles) | `make test-frontend` 264/264; `make test-backend` passes |
| 12:00–14:00 | Ujjwal | N3 backend (slip vision, pre-check guard) | `/api/merchants/S-0142/slip-precheck` returns extraction + readiness |
| 14:00–16:00 | Ujjwal | N2 backend (Ask Chhatri service, Gemini/Sarvam chain, guard) | `/api/merchants/S-0142/ask` responds within 5 s |
| 16:00–18:00 | Ujjwal | N4 integration (Sarvam STT/TTS, fallbacks) | Soundbox message plays on demo laptop; voice input transcribes |
| 18:00–20:00 | Omkar | N1 screens (mini-app home, coverage explainer, consent & buy, tracker, help) | Console at localhost:5173 shows mini-app on `/merchant/S-0142` |
| 20:00–22:00 | Omkar | Copy and policy wording (C1–C12), commit to docs | `docs/02-product/policy-wording-and-cis.md` is final; cited in N1 |
| 22:00–00:00 | Both | Integration: N1 + N2 + N3 + N4; rehearse 3-minute and 7-minute cuts | Both demo cuts run start-to-finish; no errors in console |
| 00:00–02:00 | Both | N7 static deploy (GitHub Pages or Vercel mock-mode console); backup 7-minute video | Public URL works (no login); video uploaded to repo |

### 7.2 Oct 3 (on-site): Polish and demo

| Stage | Owner | Task | Time |
|---|---|---|---|
| Machine check (8:00–8:30) | Ujjwal | Run `make demo-check` in-process; check preflight; open console at 1280×720, 100% zoom | 30 min |
| Finish N1–N4 (8:30–10:00) | Omkar & Ujjwal | Polish mini-app UI; fix any copy or latency issues; test all voice paths | 90 min |
| Stretch: N5, N6, N8 (10:00–10:30) | Omkar | If time: add grievance ladder screen, consent centre, Marathi toggle (best-effort) | 30 min, optional |
| Freeze code (10:30) | Ujjwal | No more changes after this; final `make test-backend`, `make demo-check` | 5 min |
| Rehearse (10:30–11:00) | Both | Run 3-minute cut twice; run 7-minute cut once | 30 min |
| Demo (timing TBD) | Both | Omkar: pitch and mini-app / merchant voice journey. Ujjwal: console, map, cases, audit, video fallback. | 3 min or 7 min |

### 7.3 Freeze policy

- **Code freeze 90 minutes before demos.** No new commits after 10:30 on 3 Oct. Hotfixes only if a demo crash occurs.
- **Docs freeze 24 h before demos.** No major content changes after freeze deadline.

---

## 8. Success metrics and pass criteria

See [Metrics and impact](metrics-and-impact.md) for the full metrics framework.

**Demo pass criteria:**
- All 3 live tests (EXPLAINED, HUMAN, BLOCKED) complete without errors.
- No unsupported money figures in Ask Chhatri output.
- Every decision explanation is reproducible from the shown numbers.
- Payout decision latency ≤ 5 min (end-to-end, from trigger to credit).
- ≥95% of merchant-facing copy is honest (no promises, no false precision; X7 test validates).

**Pilot success criteria (post-hackathon):**
- 80%+ test coverage maintained.
- Grounded-answer rate ≥95% on Ask Chhatri eval set.
- Dispute resolution SLA met (24 h).
- EDI holiday grant rate ≥80% (lender dependent).
- Renewal rate ≥60% (end of year 1).

---

## 9. Traceability: FR → Feature spec → Test

| FR ID | Feature spec | Test (in code) | Status |
|---|---|---|---|
| FR-area-001 | fs-01-area-auto-claim.md (K1) | `backend/tests/policy/test_engine.py::test_area_trigger_fires` | PLANNED (will be written) |
| FR-area-002 | fs-01-area-auto-claim.md (K1) | `backend/tests/policy/test_amounts.py::test_area_amount` | PLANNED |
| FR-area-003 | fs-01-area-auto-claim.md (K1) | `backend/tests/ledger/test_payouts.py::test_area_payout_batch` | PLANNED |
| FR-personal-001 | fs-02-hospital-cash-claim.md (K2) | `backend/tests/detect/test_silent.py::test_silent_day_detection` | PLANNED |
| FR-personal-002 | fs-02-hospital-cash-claim.md (K2, N3) | `backend/tests/integrations/test_slip_extraction.py::test_vision_extraction` | PLANNED |
| FR-personal-003 | fs-02-hospital-cash-claim.md (K2) | `backend/tests/policy/test_names.py::test_name_match_score` | PLANNED |
| FR-personal-004 | fs-02-hospital-cash-claim.md (K2) | `backend/tests/policy/test_amounts.py::test_personal_amount` | PLANNED |
| FR-personal-005 | fs-02-hospital-cash-claim.md (K2) | `backend/tests/policy/test_engine.py::test_personal_claim_referred` | PLANNED |
| FR-edi-001 | fs-03-edi-holiday.md (K3) | `backend/tests/ledger/test_pauses.py::test_edi_request_posted` | PLANNED |
| FR-edi-002 | fs-03-edi-holiday.md (K3) | `backend/tests/integrations/test_lender.py::test_lender_policy_grant` | PLANNED (mock lender) |
| FR-edi-003 | fs-03-edi-holiday.md (K3) | `backend/tests/conversation/test_messages.py::test_instalment_paused_message` | PLANNED |
| FR-policy-001 | fs-09-policy-engine-and-audit.md (K4) | `backend/tests/policy/test_engine.py::test_only_engine_approves` | LIVE |
| FR-policy-002 | fs-09-policy-engine-and-audit.md (K4, K5) | `backend/tests/conversation/test_messages.py::test_explanation_reproducible` | PLANNED (X7) |
| FR-explain-001 | fs-06-explanations-disputes-and-grievance.md (K5) | `backend/tests/conversation/test_ask_chhatri.py::test_why_explanation` | PLANNED |
| FR-explain-002 | fs-06-explanations-disputes-and-grievance.md (K5) | `backend/tests/cases/test_service.py::test_dispute_case_24h_sla` | PLANNED |
| FR-cover-001 | fs-07-cover-purchase-and-consent.md (K6) | `backend/tests/policy/test_cover.py::test_cash_before_cover` | PLANNED |
| FR-cover-002 | fs-07-cover-purchase-and-consent.md (K6) | `backend/tests/policy/test_cover.py::test_alert_lookahead_blocks` | PLANNED |
| FR-ask-001 | fs-05-ask-chhatri.md (N2) | `backend/tests/conversation/test_ask_chhatri.py::test_grounded_answer` | PLANNED |
| FR-ask-002 | fs-05-ask-chhatri.md (N2) | `backend/tests/conversation/test_ask_chhatri.py::test_fallback_chain` | PLANNED |
| FR-ask-003 | fs-05-ask-chhatri.md (N2) | `backend/tests/conversation/test_guard.py::test_guard_no_unsupported_money` | PLANNED |
| FR-slip-001 | fs-02-hospital-cash-claim.md (N3) | `frontend/tests/unit/ClaimUpload.test.tsx` (N3 UX) | PLANNED |
| FR-slip-002 | fs-02-hospital-cash-claim.md (N3) | `backend/tests/integrations/test_slip_extraction.py::test_confidence_gate` | PLANNED |
| FR-voice-001 | fs-05-ask-chhatri.md (N4) | `backend/tests/integrations/test_sarvam_stt.py::test_hindi_transcription` | PLANNED |
| FR-voice-002 | fs-05-ask-chhatri.md (N4) | `backend/tests/integrations/test_sarvam_tts.py::test_hindi_audio` | PLANNED |
| FR-mini-001 | fs-04-merchant-mini-app.md (N1) | `frontend/tests/unit/CoverCard.test.tsx` | PLANNED |
| FR-mini-002 | fs-04-merchant-mini-app.md (N1) | `frontend/tests/unit/CoverageExplainer.test.tsx` | PLANNED |
| FR-mini-003 | fs-04-merchant-mini-app.md (N1) | `frontend/tests/unit/ConsentAndBuy.test.tsx` | PLANNED |
| FR-mini-004 | fs-04-merchant-mini-app.md (N1) | `frontend/tests/unit/ClaimTracker.test.tsx` | PLANNED |
| FR-mini-005 | fs-04-merchant-mini-app.md (N1) | `frontend/tests/unit/GrievanceForm.test.tsx` | PLANNED |

---

## 10. Out of scope

- Multi-branch chains, aggregators, corporate merchants (scope: 1-shop, 1–3 staff).
- Family health insurance, pure health coverage (scope: income loss during hospitalisation).
- Loan origination, lending marketplace (scope: existing Paytm merchant loans).
- EDI restructuring or permanent changes (scope: lender's decision under its policy).
- Proactive settlement, instant bank transfers (scope: settlement rail only).
- Multi-document claims (scope: one slip per claim).
- Merchant acquisition and signups (scope: assumes Paytm for Business adoption).
- Insurance product design, underwriting (scope: insurer partner's role).

---

## Open questions

1. **Feature spec files:** Who owns fs-01 through fs-09? Are they written in parallel with this PRD or sequentially after? Owner: Omkar Kadam (triage).
2. **EDI holiday lender integration:** Should we mock the lender response (always grant), or wait for a real partner API? Current code simulates it; X4 guard validates loan state locally. Owner: Ujjwal Pardeshi (integration strategy).
3. **N1 mini-app build:** Should N1 be a separate React component in `frontend/`, or inline in the console's `/merchant/{id}` page? Current assumption: inline as a modal or side-panel. Owner: Omkar Kadam.
4. **Grievance ladder (N5) and consent centre (N6):** Should these use the same case and consent service APIs as the console, or have simpler mini-app versions? Owner: Omkar Kadam (architecture decision).

## Changelog

- 2026-10-02 · v1.4 · second fact-check pass: remove invented latency and rate-limit numbers, remove demo slot times and confirmed freeze times
- 2026-10-02 · v1.3 · AI provider and live/simulated framing aligned
- 2026-10-02 · v1.1 · fact-check pass: clarify annual limit IS implemented as HARD check WITHIN_ANNUAL_LIMIT (DECLINED, not REFERRED, not X8); delete answered open question
- 2026-10-02 · v1 · first draft, with 29 FRs across K, N, and X features; scope table; traceability.
